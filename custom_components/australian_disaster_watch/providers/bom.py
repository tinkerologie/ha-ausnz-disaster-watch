"""Bureau of Meteorology (BoM) weather warnings provider via official CAP-AU syndication."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

from custom_components.australian_disaster_watch.const import (
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_QLD,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
)
from custom_components.australian_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import DEFAULT_TIMEOUT, BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

BOM_WMO_FEED_URL = "https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/rss.xml"

# Mapping product prefix to state
STATE_PREFIX_MAP = {
    "IDQ": STATE_QLD,
    "IDN": STATE_NSW,
    "IDV": STATE_VIC,
    "IDW": STATE_WA,
    "IDS": STATE_SA,
    "IDT": STATE_TAS,
    "IDD": STATE_NT,
}

# State reference center coordinates for statewide weather alerts
STATE_CENTROIDS = {
    STATE_QLD: (-23.0, 144.0),
    STATE_NSW: (-32.0, 147.0),
    STATE_ACT: (-35.3, 149.1),
    STATE_VIC: (-37.0, 144.5),
    STATE_WA: (-25.0, 122.0),
    STATE_SA: (-30.0, 135.0),
    STATE_TAS: (-42.0, 146.5),
    STATE_NT: (-19.0, 133.5),
}


class BoMHazardProvider(BaseHazardProvider):
    """Provider for Bureau of Meteorology (BoM) weather warnings."""

    @property
    def state_code(self) -> str:
        """Return state code from config or national."""
        return str(self.config.get("state", "ALL")).upper()

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch weather warnings from BoM CAP syndication."""
        hazards: list[CanonicalHazard] = []
        try:
            req_headers = {"User-Agent": "HomeAssistant-AustralianDisasterWatch/1.0"}
            async with self.session.get(
                BOM_WMO_FEED_URL,
                headers=req_headers,
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("BoM CAP feed returned status %s", resp.status)
                    return hazards
                xml_text = await resp.text()

            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is None:
                return hazards

            for item in channel.findall("item"):
                hazard = self._parse_item(item)
                if hazard:
                    hazards.append(hazard)

        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching Bureau of Meteorology CAP feed: %s", err)

        return hazards

    def _parse_item(self, item: Element) -> CanonicalHazard | None:
        """Parse RSS item into CanonicalHazard."""
        title_el = item.find("title")
        guid_el = item.find("guid")
        desc_el = item.find("description")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        guid = guid_el.text.strip() if guid_el is not None and guid_el.text else ""
        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
        link = (
            link_el.text.strip()
            if link_el is not None and link_el.text
            else "http://www.bom.gov.au/weather-services/about-warnings.shtml"
        )
        pubdate = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""

        if not title:
            return None

        # Exclude cancellations to avoid stale alarms
        if title.lower().startswith("cancellation"):
            return None

        # Determine target state from guid (e.g. AusBoM-IDQ21033-...)
        target_state: str | None = None
        for prefix, st in STATE_PREFIX_MAP.items():
            if prefix in guid or prefix in title:
                target_state = st
                break

        # Filter by configured state if configured and not matching
        configured_state = self.config.get("state")
        if configured_state and target_state and configured_state not in (target_state, "ALL"):
            return None

        # Warning level from title
        warning_level = WarningLevel.from_str(title)
        if warning_level == WarningLevel.UNKNOWN:
            if "severe" in title.lower() or "flood" in title.lower() or "cyclone" in title.lower():
                warning_level = WarningLevel.WATCH_AND_ACT
            else:
                warning_level = WarningLevel.ADVICE

        hazard_type = HazardType.from_str(title)
        updated_at = self.parse_datetime(pubdate)

        # Centroid location: default to user's configured location so relevant state warnings are within radius
        user_lat = self.config.get("latitude")
        user_lon = self.config.get("longitude")
        if user_lat is not None and user_lon is not None:
            lat = float(user_lat)
            lon = float(user_lon)
        elif target_state and target_state in STATE_CENTROIDS:
            lat, lon = STATE_CENTROIDS[target_state]
        else:
            lat, lon = -27.2657, 152.9818

        clean_id = guid.replace(":", "_").replace("-", "_") if guid else f"BOM_{hash(title)}"

        return CanonicalHazard(
            id=f"BOM_{clean_id}",
            source="Bureau of Meteorology",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=desc[:120] if desc else (target_state or "Australia"),
            responsible_agency="Bureau of Meteorology",
            web_url=link,
            raw_properties={"guid": guid, "description": desc},
        )
