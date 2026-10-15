"""Victoria emergency hazards provider (Emergency Management Victoria OSOM feed)."""

from __future__ import annotations

import logging
from typing import Any

from custom_components.ausnz_disaster_watch.const import STATE_VIC
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError

_LOGGER = logging.getLogger(__name__)

VIC_OSOM_URL = "https://emergency.vic.gov.au/public/osom-geojson.json"


class VictoriaHazardProvider(BaseHazardProvider):
    """Provider for Emergency Management Victoria (EMV OSOM)."""

    local_tz = "Australia/Melbourne"

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_VIC

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from VicEmergency OSOM feed."""
        headers = {"Accept-Encoding": "gzip, deflate"}
        data = await self.async_fetch_feed_json(VIC_OSOM_URL, "VicEmergency", headers=headers)
        if not isinstance(data, dict):
            raise ProviderUnavailableError("VicEmergency returned an unexpected payload")

        hazards: list[CanonicalHazard] = []
        for feature in self.require_list(data, "features", "VicEmergency"):
            try:
                hazard = self._parse_vic_feature(feature)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed VicEmergency item: %s", err)
                continue
            if hazard:
                hazards.append(hazard)
        return hazards

    def _parse_vic_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse GeoJSON feature from Vic OSOM feed."""
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        raw_id = props.get("id") or props.get("sourceId")
        if not raw_id:
            return None
        inc_id = str(raw_id)

        cat1 = str(props.get("category1", ""))
        cat2 = str(props.get("category2", ""))
        source_title = str(props.get("sourceTitle", ""))
        action = str(props.get("action", ""))
        location = str(props.get("location", "Victoria")).strip()

        # Build clean title
        if action and cat1:
            title = f"{cat1} - {action} ({location.split(',')[0]})"
        elif source_title:
            title = f"{source_title} - {location.split(',')[0]}"
        else:
            title = f"{cat1} {cat2} - {location.split(',')[0]}".strip()

        # Determine warning level
        raw_level = source_title or cat1 or props.get("status")
        warning_level = WarningLevel.from_str(str(raw_level))
        if warning_level == WarningLevel.UNKNOWN:
            # Check cap severity
            cap = props.get("cap", {})
            if isinstance(cap, dict):
                severity = cap.get("severity", "")
                if severity == "Extreme":
                    warning_level = WarningLevel.EMERGENCY_WARNING
                elif severity == "Severe":
                    warning_level = WarningLevel.WATCH_AND_ACT
                elif severity in ("Moderate", "Minor"):
                    warning_level = WarningLevel.ADVICE
                else:
                    warning_level = WarningLevel.INFORMATION
            else:
                warning_level = WarningLevel.INFORMATION

        # Determine hazard type
        type_str = f"{cat1} {cat2} {source_title}"
        hazard_type = HazardType.from_str(type_str)

        updated_at = self.parse_datetime(props.get("updated") or props.get("created"))
        feed_type = str(props.get("feedType", "")).lower()

        is_hazard_reduction = bool(
            feed_type == "burn-area" or "planned burn" in type_str.lower() or "hazard reduction" in type_str.lower()
        )

        responsible_agency = props.get("sourceOrg") or "Emergency Management Victoria"

        return CanonicalHazard(
            id=f"VIC_EMV_{inc_id}",
            source="VicEmergency",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=location[:120],
            is_hazard_reduction=is_hazard_reduction,
            status=props.get("status"),
            responsible_agency=responsible_agency,
            web_url=f"http://emergency.vic.gov.au/respond/#!/warning/{inc_id}/moreinfo",
            raw_properties=props,
        )
