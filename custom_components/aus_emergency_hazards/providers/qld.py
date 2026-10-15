"""Queensland emergency hazards provider (QFD & Council Disaster Dashboards)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from custom_components.aus_emergency_hazards.const import CONF_COUNCIL_DASHBOARD_URL, STATE_QLD
from custom_components.aus_emergency_hazards.models import CanonicalHazard, HazardType, WarningLevel

from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

QFD_WARNINGS_URL = (
    "https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com"
    "/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json"
)


class QueenslandHazardProvider(BaseHazardProvider):
    """Provider for Queensland Fire Department and Local Disaster Dashboards."""

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_QLD

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from QFD and optional Council Disaster Dashboard."""
        hazards: list[CanonicalHazard] = []
        seen_ids: set[str] = set()

        # 1. Fetch State-wide QFD Public Warnings feed
        try:
            qfd_data = await self.async_fetch_json(QFD_WARNINGS_URL)
            if qfd_data and isinstance(qfd_data, dict):
                features = qfd_data.get("features", [])
                for feature in features:
                    hazard = self._parse_qfd_feature(feature)
                    if hazard and hazard.id not in seen_ids:
                        seen_ids.add(hazard.id)
                        hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error fetching Queensland Fire Department warnings feed: %s", err)

        # 2. Fetch Council Disaster Dashboard feeds if URL configured
        council_url = self.config.get(CONF_COUNCIL_DASHBOARD_URL)
        if council_url and council_url.strip():
            base_url = council_url.strip().rstrip("/")
            # 2a. Detailed Fire Incidents
            try:
                fire_data = await self.async_fetch_json(f"{base_url}/dashboard/fireDetailed")
                if isinstance(fire_data, list):
                    for item in fire_data:
                        hazard = self._parse_council_fire_item(item)
                        if hazard and hazard.id not in seen_ids:
                            seen_ids.add(hazard.id)
                            hazards.append(hazard)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error fetching council fire incidents from %s: %s", base_url, err)

            # 2b. Road Hazards and Closures
            try:
                road_data = await self.async_fetch_json(f"{base_url}/dashboard/tmrRoadData")
                if isinstance(road_data, list):
                    for item in road_data:
                        hazard = self._parse_council_road_item(item)
                        if hazard and hazard.id not in seen_ids:
                            seen_ids.add(hazard.id)
                            hazards.append(hazard)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error fetching council road conditions from %s: %s", base_url, err)

            # 2c. Weather Warnings (BoM)
            try:
                bom_data = await self.async_fetch_json(f"{base_url}/dashboard/bom")
                if isinstance(bom_data, dict):
                    items = bom_data.get("item", [])
                    if isinstance(items, list):
                        for item in items:
                            hazard = self._parse_council_bom_item(item)
                            if hazard and hazard.id not in seen_ids:
                                seen_ids.add(hazard.id)
                                hazards.append(hazard)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error fetching council weather warnings from %s: %s", base_url, err)

            # 2d. Council Bulletins
            try:
                bulletin_data = await self.async_fetch_json(f"{base_url}/dashboard/imsBulletin")
                if isinstance(bulletin_data, dict):
                    features = bulletin_data.get("features", [])
                    for feat in features:
                        hazard = self._parse_council_bulletin_feature(feat)
                        if hazard and hazard.id not in seen_ids:
                            seen_ids.add(hazard.id)
                            hazards.append(hazard)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error fetching council bulletins from %s: %s", base_url, err)

        return hazards

    def _parse_qfd_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse feature from QFD bushfireAlert.json."""
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        unique_id = (
            str(properties.get("UniqueID")) or str(properties.get("OBJECTID")) or str(properties.get("Incident_Number"))
        )
        if not unique_id:
            return None

        title = str(
            properties.get("WarningTitle") or properties.get("Incident_Name") or "Queensland Fire Incident"
        ).strip()

        raw_level = properties.get("WarningLevel") or properties.get("Alert_Level")
        warning_level = WarningLevel.from_str(str(raw_level))

        raw_type = properties.get("Incident_Type") or properties.get("HazardType") or "Bushfire"
        hazard_type = HazardType.from_str(str(raw_type))

        updated_at = self.parse_datetime(
            properties.get("LastUpdate") or properties.get("Updated") or properties.get("Response_Date")
        )

        location_name = str(
            properties.get("Location")
            or properties.get("Location_Name")
            or properties.get("CallToAction")
            or "Queensland"
        ).strip()

        is_hazard_reduction = bool(
            "hazard reduction" in title.lower()
            or "planned burn" in title.lower()
            or properties.get("Is_Hazard_Reduction")
        )

        return CanonicalHazard(
            id=f"QLD_QFD_{unique_id}",
            source="Queensland Fire Department",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=properties.get("Status") or properties.get("CurrentStatus"),
            responsible_agency=properties.get("Agency") or "QFD",
            web_url=properties.get("Web_URL") or "https://www.fire.qld.gov.au/Current-Incidents",
            raw_properties=properties,
        )

    def _parse_council_fire_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse fire item from Guardian IMS /dashboard/fireDetailed."""
        props = item.get("properties", {})
        lat = props.get("Latitude")
        lon = props.get("Longitude")
        if lat is None or lon is None:
            # Check geometry
            centroid = self.calculate_centroid(item.get("geometry", {}))
            if centroid:
                lat, lon = centroid
            else:
                return None

        try:
            flat = float(lat)
            flon = float(lon)
            if abs(flat) < 0.001 and abs(flon) < 0.001:
                return None
        except (ValueError, TypeError):
            return None

        inc_id = str(props.get("Master_Incident_Number") or props.get("MIN_ID") or item.get("id"))
        if not inc_id or inc_id == "0":
            return None

        title = str(
            props.get("Location_Name")
            or props.get("Location")
            or props.get("name")
            or props.get("Incident_Type")
            or "Incident"
        ).strip()

        hazard_type = HazardType.from_str(props.get("Incident_Type") or props.get("SubType"))
        warning_level = WarningLevel.from_str(props.get("Alert_Level") or props.get("CurrentStatus"))
        if warning_level == WarningLevel.UNKNOWN:
            warning_level = WarningLevel.INFORMATION

        updated_at = self.parse_datetime(props.get("LastUpdate") or props.get("Response_Date"))
        location_name = str(props.get("LGA") or props.get("Location_Name") or "").strip()

        is_hazard_reduction = bool(
            "hazard reduction" in str(props.get("Incident_Type", "")).lower()
            or "permitted burn" in str(props.get("Incident_Type", "")).lower()
        )

        return CanonicalHazard(
            id=f"QLD_COUNCIL_FIRE_{inc_id}",
            source="Council Disaster Dashboard",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=flat,
            longitude=flon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=props.get("CurrentStatus"),
            responsible_agency=props.get("Jurisdiction") or "Emergency Services",
            web_url=props.get("Web_URL"),
            raw_properties=props,
        )

    def _parse_council_road_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse road condition/hazard from Guardian IMS /dashboard/tmrRoadData."""
        props = item.get("properties", {})
        geometry = item.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        road_id = str(props.get("id") or item.get("id"))
        if not road_id:
            return None

        event_type = props.get("event_type", "Hazard")
        impact = props.get("impact", {})
        impact_subtype = impact.get("impact_subtype", "") if isinstance(impact, dict) else ""
        title = f"{event_type}: {impact_subtype}".strip(": ") if impact_subtype else str(event_type)

        duration = props.get("duration", {})
        start_time = duration.get("start") if isinstance(duration, dict) else None
        updated_at = self.parse_datetime(props.get("published") or start_time)

        status = props.get("status", "Active")
        if status == "Reopened":
            return None

        # Road hazards are typically information / advice level
        warning_level = WarningLevel.ADVICE if "closed" in impact_subtype.lower() else WarningLevel.INFORMATION

        source_info = props.get("source", {})
        agency = source_info.get("provided_by") if isinstance(source_info, dict) else "QLDTraffic / Council"

        return CanonicalHazard(
            id=f"QLD_COUNCIL_ROAD_{road_id}",
            source="QLDTraffic / Council",
            title=title,
            hazard_type=HazardType.ROAD_INCIDENT,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=props.get("suburb") or props.get("road_name") or "Queensland",
            status=status,
            responsible_agency=agency,
            web_url=props.get("url") or "https://qldtraffic.qld.gov.au",
            raw_properties=props,
        )

    def _parse_council_bom_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse Bureau of Meteorology warning item from /dashboard/bom."""
        title = str(item.get("title", "")).strip()
        if not title:
            return None

        link = str(item.get("link", ""))
        locations = str(item.get("locations", ""))
        updated_at = self.parse_datetime(item.get("pubDate"))

        # Infer hazard type and warning level from title
        hazard_type = HazardType.from_str(title)
        warning_level = WarningLevel.from_str(title)
        if warning_level == WarningLevel.UNKNOWN:
            # BoM warnings are at least Advice / Watch and Act
            if "severe" in title.lower() or "flood" in title.lower() or "cyclone" in title.lower():
                warning_level = WarningLevel.WATCH_AND_ACT
            else:
                warning_level = WarningLevel.ADVICE

        # Derive stable ID
        id_hash = hashlib.md5(f"{title}_{link}".encode()).hexdigest()[:10]

        # Use configured location latitude/longitude if no geometry in BoM item
        lat = float(self.config.get("latitude", -27.2657))
        lon = float(self.config.get("longitude", 152.9818))

        return CanonicalHazard(
            id=f"QLD_COUNCIL_BOM_{id_hash}",
            source="Bureau of Meteorology",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=locations[:100] if locations else "Queensland",
            responsible_agency="Bureau of Meteorology",
            web_url=link or "http://www.bom.gov.au/qld/warnings/",
            raw_properties=item,
        )

    def _parse_council_bulletin_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse council emergency bulletin from /dashboard/imsBulletin."""
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)

        lat = centroid[0] if centroid else float(self.config.get("latitude", -27.2657))
        lon = centroid[1] if centroid else float(self.config.get("longitude", 152.9818))

        bulletin_id = str(props.get("id") or props.get("bulletin_id"))
        if not bulletin_id:
            return None

        title = str(props.get("title") or props.get("headline") or "Council Disaster Bulletin").strip()
        warning_level = WarningLevel.from_str(props.get("priority") or props.get("level"))
        if warning_level == WarningLevel.UNKNOWN:
            warning_level = WarningLevel.ADVICE

        return CanonicalHazard(
            id=f"QLD_COUNCIL_BULLETIN_{bulletin_id}",
            source="Council Disaster Operations",
            title=title,
            hazard_type=HazardType.OTHER,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=self.parse_datetime(props.get("created") or props.get("updated")),
            location_name=props.get("suburb") or "Moreton Bay",
            status="Active",
            responsible_agency="Local Disaster Management Group",
            web_url=props.get("url"),
            raw_properties=props,
        )
