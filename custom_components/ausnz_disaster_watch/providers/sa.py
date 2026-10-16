"""South Australia Emergency Hazard Provider (SAFECOM / CFS CAP-AU, SA SES warnings).

CFS and MFS incidents and warnings come from the SA ESO CAP-AU feed; their CAP areas become
the hazard area (#30). SA SES flood, storm, wind, heatwave and dam warnings come from the SES
public warnings ArcGIS layer as polygons: ``category`` is the AWS level (ADV, WAM, EWM).
"""

from __future__ import annotations

import logging
from typing import Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_SA
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, as_dict, as_float, stable_id
from .cap import cap_from_element
from .geometry import area_point, rings_from_cap_areas, rings_from_geojson, simplify_area
from .sources import DATA_SOURCES

_LOGGER = logging.getLogger(__name__)

SA_CAP_AU_URL = "https://data.eso.sa.gov.au/feeds/prod/cap-au.xml"
SA_SES_WARNINGS_URL = (
    "https://ses.geohub.sa.gov.au/server/rest/services/SAM_PROD_Services/SAM_Warnings_Public_Live/FeatureServer/0"
)
# Explicit allowlist: the layer also has editor fields (created_user, adfs_user, ...)
SA_SES_FIELDS = (
    "objectid",
    "documentid",
    "alertname",
    "risk",
    "category",
    "datetimeissued",
    "datetimeexpires",
    "shortlocation",
    "locationsimpacted",
    "calltoaction",
    "link",
)
SA_SES_DOCUMENT_BASE = "https://data.eso.sa.gov.au/prod/ses/sam/"
SA_SES_WEB_URL = "https://www.ses.sa.gov.au/warnings"
_SES_LEVELS = {
    "EWM": WarningLevel.EMERGENCY_WARNING,
    "WAM": WarningLevel.WATCH_AND_ACT,
    "ADV": WarningLevel.ADVICE,
}
_SES_TYPES = {"dam": HazardType.FLOOD, "heatwave": HazardType.OTHER}


def _warning_level(param_level: str, *texts: str) -> WarningLevel:
    """Map an SA CFS/MFS entry to an Australian Warning System level (#27).

    The feed always sends ``cap:severity`` "Unknown". The agency's level is the CAP
    ``WarningLevel`` parameter ("Emergency Warning", "Watch and Act", "Advice", or
    "Incident" for an incident with no warning). Only when it is missing, use the
    headline, event and title text. Plain incidents are Information.
    """
    for text in (param_level,) if param_level else texts:
        level = WarningLevel.from_str(text)
        if level not in (WarningLevel.UNKNOWN, WarningLevel.INFORMATION):
            return level
    return WarningLevel.INFORMATION


class SAHazardProvider(BaseHazardProvider):
    """Provider for South Australian emergency services (CFS / MFS / SES via SAFECOM CAP-AU)."""

    local_tz = "Australia/Adelaide"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_SA

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch CFS/MFS incidents and warnings (CAP-AU) and SES warning areas; one may fail alone."""
        return await self.async_collect_sources(
            [
                (
                    "SA SAFECOM",
                    lambda: self.async_fetch_feed_text(SA_CAP_AU_URL, "SA SAFECOM"),
                    self._parse_cap_feed,
                ),
                (
                    "SA SES warnings",
                    lambda: self.async_fetch_arcgis_features(
                        SA_SES_WARNINGS_URL, "status='Published'", SA_SES_FIELDS, "SA SES warnings"
                    ),
                    self._parse_ses_warnings,
                ),
            ]
        )

    def _parse_ses_warnings(self, features: list[dict[str, Any]]) -> list[CanonicalHazard]:
        """Map SA SES warning polygons; a reissued warning keeps its ID, the newest issue wins."""
        newest: dict[str, CanonicalHazard] = {}
        for feature in features:
            try:
                hazard = self._parse_ses_warning(feature)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed SA SES warning: %s", err)
                continue
            if hazard is None:
                continue
            current = newest.get(hazard.id)
            if current is None or _issued(hazard) >= _issued(current):
                newest[hazard.id] = hazard
        return list(newest.values())

    def _parse_ses_warning(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        props = as_dict(feature.get("properties"))
        area = simplify_area(rings_from_geojson(feature.get("geometry")))
        if area is None:
            return None
        name = str(props.get("alertname") or "SES Warning").replace("_", " ").strip()
        place = str(props.get("shortlocation") or props.get("locationsimpacted") or "").strip()
        risk = str(props.get("risk") or "").strip()
        level = _SES_LEVELS.get(str(props.get("category") or "").strip().upper(), WarningLevel.from_str(name))
        lat, lon = area_point(area, as_float(self.config.get("latitude")), as_float(self.config.get("longitude")))
        link = str(props.get("link") or "").strip()
        if link and not link.startswith("http"):
            link = SA_SES_DOCUMENT_BASE + link.lstrip("/")
        hazard_type = _SES_TYPES.get(risk.lower()) or HazardType.from_str(f"{risk} {name}")
        return CanonicalHazard(
            # A warning keeps its document ID and area through updates; objectid changes (#7)
            id=stable_id("sa_ses", props.get("documentid"), name, place),
            source="SA State Emergency Service",
            title=f"{level.value} - {name} - {place}" if place else f"{level.value} - {name}",
            hazard_type=hazard_type,
            warning_level=level,
            latitude=lat,
            longitude=lon,
            updated_at=self.parse_datetime(props.get("datetimeissued")),
            expires=self.parse_datetime(props.get("datetimeexpires")),
            location_name=place or "South Australia",
            status="Active",
            responsible_agency="SA State Emergency Service",
            web_url=link or SA_SES_WEB_URL,
            area=area,
            call_to_action=str(props.get("calltoaction") or "").strip() or None,
            attribution=DATA_SOURCES["sa_ses_warnings"].attribution,
            raw_properties={
                "risk": risk or None,
                "category": props.get("category"),
                "document_id": props.get("documentid"),
            },
        )

    def _parse_cap_feed(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse SA Emergency Services CAP-AU Atom XML."""
        hazards: list[CanonicalHazard] = []
        if not xml_text.strip():
            # Even "no alerts" is a well-formed XML document; a blank body is a broken feed (#16)
            raise ProviderUnavailableError("SA SAFECOM returned an empty response")

        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"SA SAFECOM returned invalid XML: {err}") from err
        self.require_xml_root(root, "atom", "SA SAFECOM")
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "cap": "urn:oasis:names:tc:emergency:cap:1.2",
        }

        for entry in root.findall("atom:entry", ns):
            try:
                entry_id = entry.findtext("atom:id", "", ns).strip()
                title = entry.findtext("atom:title", "", ns).strip()
                updated_str = entry.findtext("atom:updated", "", ns)
                updated_at = self.parse_datetime(updated_str)

                # Locate CAP fields
                event = entry.findtext(".//cap:event", "", ns) or title
                headline = entry.findtext(".//cap:headline", "", ns)
                severity = entry.findtext(".//cap:severity", "", ns).lower()
                urgency = entry.findtext(".//cap:urgency", "", ns).lower()
                area_desc = entry.findtext(".//cap:areaDesc", "", ns)
                circle = entry.findtext(".//cap:circle", "", ns)
                polygon = entry.findtext(".//cap:polygon", "", ns)
                # cap:sender is an email address; the agency name is cap:senderName (#27)
                agency = entry.findtext(".//cap:senderName", "", ns).strip()
                web = entry.findtext(".//cap:web", "", ns).strip()
                params = {
                    param.findtext("cap:valueName", "", ns).strip(): param.findtext("cap:value", "", ns).strip()
                    for param in entry.findall(".//cap:parameter", ns)
                }

                # Extract coordinates
                lat: float | None = None
                lon: float | None = None

                if circle and "," in circle:
                    try:
                        coords_part = circle.strip().split()[0]
                        lat_s, lon_s = coords_part.split(",")
                        lat, lon = float(lat_s), float(lon_s)
                    except (ValueError, IndexError):
                        pass

                if (lat is None or lon is None) and polygon:
                    try:
                        points = polygon.strip().split()
                        poly_lat_lon = [p.split(",") for p in points if "," in p]
                        lat = sum(float(p[0]) for p in poly_lat_lon) / len(poly_lat_lon)
                        lon = sum(float(p[1]) for p in poly_lat_lon) / len(poly_lat_lon)
                    except (ValueError, IndexError, ZeroDivisionError):
                        pass

                if lat is None or lon is None:
                    continue

                level = _warning_level(params.get("WarningLevel", ""), headline, event, title)
                # The CAP area (a polygon for a warning) is the hazard area (#30)
                alert = cap_from_element(entry)
                area = simplify_area(rings_from_cap_areas(alert.areas)) if alert is not None else None

                hazards.append(
                    CanonicalHazard(
                        id=f"sa_cfs_{entry_id}",
                        source="SA Emergency Services / CFS",
                        title=title,
                        hazard_type=HazardType.from_str(event),
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name=area_desc or "South Australia",
                        status=params.get("Status") or "Active",
                        responsible_agency=agency or "CFS / SAFECOM",
                        web_url=web or "https://www.cfs.sa.gov.au",
                        area=area,
                        expires=alert.expires if alert is not None else None,
                        call_to_action=params.get("CallToAction") or None,
                        raw_properties={
                            "severity": severity,
                            "urgency": urgency,
                            "event": event,
                            "headline": headline or None,
                            "warning_level": params.get("WarningLevel"),
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed SA SAFECOM item: %s", err)

        return hazards


def _issued(hazard: CanonicalHazard) -> float:
    return hazard.updated_at.timestamp() if hazard.updated_at else 0.0
