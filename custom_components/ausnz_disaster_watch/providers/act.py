"""Australian Capital Territory Emergency Hazard Provider (ACT ESA)."""

from __future__ import annotations

import html
import logging
import re

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_ACT
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

ACT_ESA_FEED_URL = "https://www.esa.act.gov.au/feeds/currentincidents.xml"


_UPDATED_RE = re.compile(r"updated:\s*(.+?)(?:<br\s*/?>|<|\n|$)", re.IGNORECASE)


def _extract_updated(description: str) -> str | None:
    """Return the value of the "Updated:" label in an ACT ESA item description."""
    match = _UPDATED_RE.search(html.unescape(description))
    return match.group(1).strip() if match else None


class ACTHazardProvider(BaseHazardProvider):
    """Provider for Australian Capital Territory Emergency Services Agency (ACT ESA)."""

    local_tz = "Australia/Sydney"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_ACT

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active incidents from ACT ESA GeoRSS feed."""
        hazards: list[CanonicalHazard] = []

        try:
            xml_text = await self.async_fetch_text(ACT_ESA_FEED_URL)
            hazards.extend(self._parse_act_feed(xml_text))
        except Exception:
            _LOGGER.exception("Failed to fetch ACT ESA GeoRSS feed")

        return hazards

    def _parse_act_feed(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse ACT ESA GeoRSS XML."""
        hazards: list[CanonicalHazard] = []
        if not xml_text.strip():
            return hazards

        try:
            root = ET.fromstring(xml_text)
            ns = {"georss": "http://www.georss.org/georss"}

            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                guid = item.findtext("guid", "").strip() or title
                desc = item.findtext("description", "").strip()
                agency = item.findtext("agency", "").strip() or "ACT ESA"
                # pubDate is the feed build time; the incident time is the "Updated:" line in
                # the description (e.g. "Updated: 2026-10-15 20:46 AEDT") (#13)
                updated_at = self.parse_datetime(_extract_updated(desc)) or self.parse_datetime(
                    item.findtext("pubDate", "")
                )

                # Extract georss:point
                lat: float | None = None
                lon: float | None = None

                point = item.findtext("georss:point", "", ns)
                if point and " " in point.strip():
                    try:
                        parts = point.strip().split()
                        lat = float(parts[0])
                        lon = float(parts[1])
                    except (ValueError, IndexError):
                        pass

                if lat is None or lon is None:
                    # Default Canberra centroid
                    lat, lon = -35.2809, 149.1300

                # Check if hazard reduction
                is_hr = "hazard reduction" in title.lower() or "hazard reduction" in desc.lower()

                # Warning level
                combined = f"{title.lower()} {desc.lower()}"
                if "emergency warning" in combined:
                    level = WarningLevel.EMERGENCY_WARNING
                elif "watch and act" in combined:
                    level = WarningLevel.WATCH_AND_ACT
                elif "advice" in combined:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazards.append(
                    CanonicalHazard(
                        id=f"act_esa_{guid}",
                        source="ACT Emergency Services Agency",
                        title=title,
                        hazard_type=HazardType.from_str(title),
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name="Australian Capital Territory",
                        is_hazard_reduction=is_hr,
                        status="Active",
                        responsible_agency=agency,
                        web_url="https://esa.act.gov.au",
                        raw_properties={"description": desc},
                    )
                )
        except Exception:
            _LOGGER.exception("Error parsing ACT ESA feed")

        return hazards
