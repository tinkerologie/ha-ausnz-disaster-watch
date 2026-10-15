"""South Australia Emergency Hazard Provider (SAFECOM / CFS CAP-AU)."""

from __future__ import annotations

import logging

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_SA
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError

_LOGGER = logging.getLogger(__name__)

SA_CAP_AU_URL = "https://data.eso.sa.gov.au/feeds/prod/cap-au.xml"


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
        """Fetch active emergency incidents and warnings from SA CAP-AU feed."""
        xml_text = await self.async_fetch_feed_text(SA_CAP_AU_URL, "SA SAFECOM")
        return self._parse_cap_feed(xml_text)

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
