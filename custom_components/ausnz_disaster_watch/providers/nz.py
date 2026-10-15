"""New Zealand Emergency Hazard Provider (GeoNet, NEMA, MetService)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_NZ
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel, WeatherWarningItem

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, stable_id

_LOGGER = logging.getLogger(__name__)

QUAKE_MAX_AGE = timedelta(hours=48)
GEONET_QUAKE_URL = "https://api.geonet.org.nz/quake?MMI=3"
GEONET_VOLCANO_URL = "https://api.geonet.org.nz/volcano/val"
NEMA_ALERTHUB_URL = "https://alerthub.civildefence.govt.nz/atom/pwp"
METSERVICE_ALERTS_URL = "https://alerts.metservice.com/cap/rss"


class NZHazardProvider(BaseHazardProvider):
    """Provider for New Zealand natural hazards and civil defence emergencies."""

    local_tz = "Pacific/Auckland"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_NZ

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch and aggregate New Zealand hazards from GeoNet and NEMA."""
        return await self.async_collect_sources(
            [
                (
                    "GeoNet quakes",
                    lambda: self.async_fetch_feed_json(GEONET_QUAKE_URL, "GeoNet quakes"),
                    lambda payload: self._parse_geonet_quakes(self.require_dict(payload, "GeoNet quakes")),
                ),
                (
                    "GeoNet volcanoes",
                    lambda: self.async_fetch_feed_json(GEONET_VOLCANO_URL, "GeoNet volcanoes"),
                    lambda payload: self._parse_geonet_volcanoes(self.require_dict(payload, "GeoNet volcanoes")),
                ),
                (
                    "NEMA AlertHub",
                    lambda: self.async_fetch_feed_text(NEMA_ALERTHUB_URL, "NEMA AlertHub"),
                    self._parse_nema_atom,
                ),
            ]
        )

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Fetch MetService severe weather watches and warnings."""
        warnings: list[WeatherWarningItem] = []
        try:
            rss_text = await self.async_fetch_text(METSERVICE_ALERTS_URL)
            root = ET.fromstring(rss_text)
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "").strip()
                pub_date_str = item.findtext("pubDate", "")
                pub_date = self.parse_datetime(pub_date_str) if pub_date_str else None

                if title:
                    warnings.append(
                        WeatherWarningItem(
                            title=title,
                            link=link or None,
                            locations=desc or None,
                            pub_date=pub_date,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            # Auxiliary feed: an outage here must not affect hazard availability
            _LOGGER.debug("MetService CAP RSS alerts unavailable: %s", err)

        return warnings

    def _parse_geonet_quakes(self, data: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse GeoNet earthquake GeoJSON FeatureCollection."""
        hazards: list[CanonicalHazard] = []
        features = self.require_list(data, "features", "GeoNet")
        now = datetime.now(UTC)

        for feat in features:
            try:
                props = feat.get("properties", {})
                if props.get("quality") == "deleted":
                    continue

                time_str = props.get("time")
                updated_at = self.parse_datetime(time_str)
                if updated_at and (now - updated_at > QUAKE_MAX_AGE):
                    continue

                geom = feat.get("geometry", {})
                centroid = self.calculate_centroid(geom)
                if not centroid:
                    continue

                lat, lon = centroid
                public_id = str(props.get("publicID", ""))
                mag = float(props.get("magnitude", 0.0))
                mmi = int(props.get("mmi", 0))
                locality = props.get("locality", "New Zealand")

                # AWS Warning Level normalization for seismic events
                if mag >= 6.0 or mmi >= 6:
                    level = WarningLevel.EMERGENCY_WARNING
                elif mag >= 5.0 or mmi >= 5:
                    level = WarningLevel.WATCH_AND_ACT
                elif mag >= 4.0 or mmi >= 4:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazard_id = f"nz_quake_{public_id}"
                title = f"M{mag:.1f} Earthquake - {locality}"

                hazards.append(
                    CanonicalHazard(
                        id=hazard_id,
                        source="GeoNet New Zealand",
                        title=title,
                        hazard_type=HazardType.EARTHQUAKE,
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name=locality,
                        status="Active",
                        responsible_agency="GeoNet (GNS Science)",
                        web_url=f"https://www.geonet.org.nz/earthquake/{public_id}",
                        raw_properties={
                            "magnitude": mag,
                            "mmi": mmi,
                            "depth": props.get("depth"),
                            "quality": props.get("quality"),
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed GeoNet quake item: %s", err)

        return hazards

    def _parse_geonet_volcanoes(self, data: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse GeoNet volcanic activity level GeoJSON."""
        hazards: list[CanonicalHazard] = []
        features = self.require_list(data, "features", "GeoNet")

        for feat in features:
            try:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                centroid = self.calculate_centroid(geom)
                if not centroid:
                    continue

                lat, lon = centroid
                volcano_id = str(props.get("volcanoID", ""))
                title_name = props.get("volcanoTitle", volcano_id.capitalize())
                level_num = int(props.get("level", 0))
                acc = props.get("acc", "Green")
                activity = props.get("activity", "No volcanic unrest.")
                hazards_desc = props.get("hazards", "")

                # Determine AWS Warning Level mapping
                if level_num >= 3:
                    level = WarningLevel.EMERGENCY_WARNING
                elif level_num == 2:
                    level = WarningLevel.WATCH_AND_ACT
                elif level_num == 1:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazard_id = f"nz_volcano_{volcano_id}"
                title = f"Volcano Level {level_num} ({acc}) - {title_name}"

                hazards.append(
                    CanonicalHazard(
                        id=hazard_id,
                        source="GeoNet New Zealand",
                        title=title,
                        hazard_type=HazardType.VOLCANO,
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=self.parse_datetime(None),
                        location_name=title_name,
                        status=activity,
                        responsible_agency="GeoNet (GNS Science)",
                        web_url=f"https://www.geonet.org.nz/volcano/{volcano_id}",
                        raw_properties={
                            "volcanoID": volcano_id,
                            "level": level_num,
                            "acc": acc,
                            "activity": activity,
                            "hazards": hazards_desc,
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed GeoNet volcano item: %s", err)

        return hazards

    def _parse_nema_atom(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse NEMA Emergency Mobile Alert feed."""
        hazards: list[CanonicalHazard] = []
        if not xml_text.strip():
            # Even "no alerts" is a well-formed XML document; a blank body is a broken feed (#16)
            raise ProviderUnavailableError("NEMA AlertHub returned an empty response")

        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"NEMA AlertHub returned invalid XML: {err}") from err
        self.require_xml_root(root, "atom", "NEMA AlertHub")
        ns = {"atom": "http://www.w3.org/2005/Atom", "cap": "urn:oasis:names:tc:emergency:cap:1.2"}

        for entry in root.findall("atom:entry", ns):
            try:
                msg_type = entry.findtext(".//cap:msgType", "", ns).lower()
                if msg_type == "cancel":
                    continue

                status_val = entry.findtext(".//cap:status", "", ns).lower()
                if status_val and status_val != "actual":
                    continue

                entry_id = entry.findtext("atom:id", "", ns).strip()
                title = entry.findtext("atom:title", "", ns).strip()
                updated_str = entry.findtext("atom:updated", "", ns)
                updated_at = self.parse_datetime(updated_str)
                severity = entry.findtext(".//cap:severity", "", ns).lower()
                area_desc = entry.findtext(".//cap:areaDesc", "", ns)

                # Extract coordinates from circle or polygon
                lat: float | None = None
                lon: float | None = None
                circle = entry.findtext(".//cap:circle", "", ns)
                if circle and "," in circle:
                    try:
                        coords_part = circle.strip().split()[0]
                        lat_s, lon_s = coords_part.split(",")
                        lat, lon = float(lat_s), float(lon_s)
                    except (ValueError, IndexError):
                        pass

                if lat is None or lon is None:
                    polygon = entry.findtext(".//cap:polygon", "", ns)
                    if polygon:
                        try:
                            points = polygon.strip().split()
                            poly_lat_lon = [p.split(",") for p in points if "," in p]
                            lat = sum(float(p[0]) for p in poly_lat_lon) / len(poly_lat_lon)
                            lon = sum(float(p[1]) for p in poly_lat_lon) / len(poly_lat_lon)
                        except (ValueError, IndexError, ZeroDivisionError):
                            pass

                if lat is None or lon is None:
                    continue

                # Warning Level mapping
                if "extreme" in severity or "catastrophic" in severity or "emergency" in title.lower():
                    level = WarningLevel.EMERGENCY_WARNING
                elif "severe" in severity or "watch and act" in title.lower():
                    level = WarningLevel.WATCH_AND_ACT
                elif "moderate" in severity or "advice" in title.lower():
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazards.append(
                    CanonicalHazard(
                        id=f"nz_nema_{entry_id}" if entry_id else stable_id("nz_nema", title, area_desc),
                        source="NEMA New Zealand Civil Defence",
                        title=title or "Civil Defence Emergency Mobile Alert",
                        hazard_type=HazardType.from_str(title),
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name=area_desc or "New Zealand",
                        status="Active Alert",
                        responsible_agency="NEMA",
                        web_url="https://www.civildefence.govt.nz",
                        raw_properties={
                            "severity": severity,
                            "status": status_val,
                            "msgType": msg_type,
                            "areaDesc": area_desc,
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed NEMA AlertHub item: %s", err)

        return hazards
