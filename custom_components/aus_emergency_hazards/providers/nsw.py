"""New South Wales emergency hazards provider (NSW RFS & SES)."""

from __future__ import annotations

import logging
import re
from typing import Any

from custom_components.aus_emergency_hazards.const import STATE_NSW
from custom_components.aus_emergency_hazards.models import CanonicalHazard, HazardType, WarningLevel

from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

NSW_RFS_MAJOR_INCIDENTS_URL = "https://www.rfs.nsw.gov.au/feeds/majorIncidents.json"


class NSWHazardProvider(BaseHazardProvider):
    """Provider for New South Wales Rural Fire Service and State Emergency Service."""

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_NSW

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from NSW RFS major incidents feed."""
        hazards: list[CanonicalHazard] = []
        try:
            data = await self.async_fetch_json(NSW_RFS_MAJOR_INCIDENTS_URL)
            if not data or not isinstance(data, dict):
                return hazards

            features = data.get("features", [])
            for feature in features:
                hazard = self._parse_nsw_feature(feature)
                if hazard:
                    hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error fetching NSW RFS major incidents feed: %s", err)

        return hazards

    def _parse_nsw_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse GeoJSON feature from NSW RFS feed."""
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        guid = str(props.get("guid", ""))
        inc_id_match = re.search(r"/(\d+)$", guid)
        inc_id = inc_id_match.group(1) if inc_id_match else re.sub(r"\W+", "_", guid)
        if not inc_id:
            title_slug = re.sub(r"\W+", "_", str(props.get("title", "nsw_incident")))
            inc_id = f"{title_slug}_{lat:.4f}_{lon:.4f}"

        title = str(props.get("title", "NSW Incident")).strip()
        category = props.get("category")
        description = str(props.get("description", ""))

        # Parse key-value pairs from HTML description
        desc_fields = self._parse_description_html(description)

        raw_level = desc_fields.get("ALERT LEVEL") or category
        warning_level = WarningLevel.from_str(raw_level)

        raw_type = desc_fields.get("TYPE") or "Bush Fire"
        hazard_type = HazardType.from_str(raw_type)

        location_name = desc_fields.get("LOCATION") or desc_fields.get("COUNCIL AREA") or title

        status = desc_fields.get("STATUS")
        agency = desc_fields.get("RESPONSIBLE AGENCY") or "NSW Rural Fire Service"

        updated_raw = desc_fields.get("UPDATED") or props.get("pubDate")
        updated_at = self.parse_datetime(updated_raw)

        is_hazard_reduction = bool(
            "hazard reduction" in description.lower()
            or "hazard reduction" in title.lower()
            or "hazard reduction" in raw_type.lower()
        )

        return CanonicalHazard(
            id=f"NSW_RFS_{inc_id}",
            source="NSW Rural Fire Service",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=status,
            responsible_agency=agency,
            web_url=props.get("link") or "https://www.rfs.nsw.gov.au/fire-information/fires-near-me",
            raw_properties=props,
        )

    @staticmethod
    def _parse_description_html(desc: str) -> dict[str, str]:
        """Extract key-value fields from HTML description string."""
        fields: dict[str, str] = {}
        if not desc:
            return fields

        # Splits by <br />, <br/>, or <br>
        lines = re.split(r"<br\s*/?>", desc, flags=re.IGNORECASE)
        for line in lines:
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip().upper()] = v.strip()
        return fields
