"""South Australia Emergency Hazard Provider (SAFECOM / CFS CAP-AU)."""

from __future__ import annotations

import logging

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_SA
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

SA_CAP_AU_URL = "https://data.eso.sa.gov.au/feeds/prod/cap-au.xml"


class SAHazardProvider(BaseHazardProvider):
    """Provider for South Australian emergency services (CFS / MFS / SES via SAFECOM CAP-AU)."""

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_SA

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active emergency incidents and warnings from SA CAP-AU feed."""
        hazards: list[CanonicalHazard] = []

        try:
            xml_text = await self.async_fetch_text(SA_CAP_AU_URL)
            hazards.extend(self._parse_cap_feed(xml_text))
        except Exception:
            _LOGGER.exception("Failed to fetch SA SAFECOM CAP-AU feed")

        return hazards

    def _parse_cap_feed(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse SA Emergency Services CAP-AU Atom XML."""
        hazards: list[CanonicalHazard] = []
        if not xml_text.strip():
            return hazards

        try:
            root = ET.fromstring(xml_text)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "cap": "urn:oasis:names:tc:emergency:cap:1.2",
            }

            for entry in root.findall("atom:entry", ns):
                entry_id = entry.findtext("atom:id", "", ns).strip()
                title = entry.findtext("atom:title", "", ns).strip()
                updated_str = entry.findtext("atom:updated", "", ns)
                updated_at = self.parse_datetime(updated_str)

                # Locate CAP fields
                event = entry.findtext(".//cap:event", "", ns) or title
                severity = entry.findtext(".//cap:severity", "", ns).lower()
                urgency = entry.findtext(".//cap:urgency", "", ns).lower()
                area_desc = entry.findtext(".//cap:areaDesc", "", ns)
                circle = entry.findtext(".//cap:circle", "", ns)
                polygon = entry.findtext(".//cap:polygon", "", ns)
                agency = entry.findtext(".//cap:sender", "", ns)

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
                        id=f"sa_cfs_{entry_id}",
                        source="SA Emergency Services / CFS",
                        title=title,
                        hazard_type=HazardType.from_str(event),
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name=area_desc or "South Australia",
                        status="Active",
                        responsible_agency=agency or "CFS / SAFECOM",
                        web_url="https://www.cfs.sa.gov.au",
                        raw_properties={
                            "severity": severity,
                            "urgency": urgency,
                            "event": event,
                        },
                    )
                )
        except Exception:
            _LOGGER.exception("Error parsing SA CAP-AU XML feed")

        return hazards
