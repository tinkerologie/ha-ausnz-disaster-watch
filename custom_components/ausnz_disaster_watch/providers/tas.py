"""Tasmania Emergency Hazard Provider (TasALERT / TFS)."""

from __future__ import annotations

import logging

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_TAS
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError

_LOGGER = logging.getLogger(__name__)

TAS_ALERT_FEED_URL = "https://alert.tas.gov.au/data/incidents-and-alerts.xml"


class TasmaniaHazardProvider(BaseHazardProvider):
    """Provider for Tasmanian emergency incidents and warnings via TasALERT."""

    local_tz = "Australia/Hobart"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_TAS

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active incidents and alerts from TasALERT XML feed."""
        xml_text = await self.async_fetch_feed_text(TAS_ALERT_FEED_URL, "TasALERT")
        return self._parse_tasalert_feed(xml_text)

    def _parse_tasalert_feed(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse TasALERT RSS XML."""
        hazards: list[CanonicalHazard] = []
        if not xml_text.strip():
            # Even "no alerts" is a well-formed XML document; a blank body is a broken feed (#16)
            raise ProviderUnavailableError("TasALERT returned an empty response")

        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"TasALERT returned invalid XML: {err}") from err
        self.require_xml_root(root, "rss", "TasALERT")
        ns = {
            "georss": "http://www.georss.org/georss",
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        for item in root.findall(".//item"):
            try:
                title = item.findtext("title", "").strip()
                guid = item.findtext("guid", "").strip() or title
                desc = item.findtext("description", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_str = item.findtext("pubDate", "")
                updated_at = self.parse_datetime(pub_date_str)

                # Look for georss:point or point
                lat: float | None = None
                lon: float | None = None

                point = item.findtext("georss:point", "", ns) or item.findtext("point", "")
                if point and " " in point.strip():
                    try:
                        parts = point.strip().split()
                        lat = float(parts[0])
                        lon = float(parts[1])
                    except (ValueError, IndexError):
                        pass

                if lat is None or lon is None:
                    # Default Hobart centroid if no coordinates given
                    lat, lon = -42.8821, 147.3272

                # Warning Level parsing
                title_lower = title.lower()
                desc_lower = desc.lower()
                combined = f"{title_lower} {desc_lower}"

                if "emergency warning" in combined or "evacuate" in combined:
                    level = WarningLevel.EMERGENCY_WARNING
                elif "watch and act" in combined or "prepare to leave" in combined:
                    level = WarningLevel.WATCH_AND_ACT
                elif "advice" in combined:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazard_type = HazardType.from_str(combined)

                hazards.append(
                    CanonicalHazard(
                        id=f"tas_alert_{guid}",
                        source="TasALERT / Tasmania Emergency Services",
                        title=title or "Tasmanian Emergency Alert",
                        hazard_type=hazard_type,
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name="Tasmania",
                        status="Active",
                        responsible_agency="TasALERT",
                        web_url=link or "https://alert.tas.gov.au",
                        raw_properties={"description": desc},
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed TasALERT item: %s", err)

        return hazards
