"""Tasmania Emergency Hazard Provider (TasALERT / TFS).

TasALERT's map is driven by ``data.geojson``: every incident and warning carries its own
coordinates. The older ``incidents-and-alerts.xml`` RSS feed has no coordinates (alerts were
placed at a fixed Hobart point) and is often empty while the map shows live incidents (#14).
"""

from __future__ import annotations

import logging
from typing import Any

from custom_components.ausnz_disaster_watch.const import STATE_TAS
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, stable_id

_LOGGER = logging.getLogger(__name__)

TAS_ALERT_GEOJSON_URL = "https://alert.tas.gov.au/data/data.geojson"
TAS_ALERT_WEB_URL = "https://alert.tas.gov.au/"

# Statuses that mean the incident is over
_CLOSED_STATUSES = {"closed", "safe", "complete", "completed", "out"}
_HAZARD_REDUCTION_TYPES = ("fuel reduction", "planned burn", "hazard reduction")


class TasmaniaHazardProvider(BaseHazardProvider):
    """Provider for Tasmanian emergency incidents and warnings via TasALERT."""

    local_tz = "Australia/Hobart"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_TAS

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active incidents and warnings from the TasALERT GeoJSON feed."""
        payload = await self.async_fetch_feed_json(TAS_ALERT_GEOJSON_URL, "TasALERT")
        return self._parse_tasalert_geojson(self.require_dict(payload, "TasALERT"))

    def _parse_tasalert_geojson(self, data: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse the TasALERT FeatureCollection; features without coordinates are skipped."""
        hazards: list[CanonicalHazard] = []
        for feature in self.require_list(data, "features", "TasALERT"):
            try:
                hazard = self._parse_feature(feature)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed TasALERT feature: %s", err)
                continue
            if hazard is not None:
                hazards.append(hazard)
        return hazards

    def _parse_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        props: dict[str, Any] = feature["properties"]
        status = str(props.get("status") or "Active")
        if status.lower() in _CLOSED_STATUSES:
            return None

        location = props.get("location") or {}
        if isinstance(location, dict) and location.get("lat") is not None and location.get("lng") is not None:
            lat, lon = float(location["lat"]), float(location["lng"])
        elif centroid := self.calculate_centroid(feature.get("geometry") or {}):
            lat, lon = centroid
        else:
            # Never invent a location: an unlocated alert would be counted as nearby (#14)
            _LOGGER.debug("TasALERT feature %s has no coordinates; skipped", props.get("id"))
            return None

        type_info = props.get("type")
        type_name = str(type_info.get("name") or "") if isinstance(type_info, dict) else str(type_info or "")
        title = str(props.get("title") or type_name or "Tasmanian Emergency Alert")
        address = str(props.get("address") or "").strip()
        text = f"{title} {type_name}".lower()

        if "emergency warning" in text:
            level = WarningLevel.EMERGENCY_WARNING
        elif "watch and act" in text:
            level = WarningLevel.WATCH_AND_ACT
        elif "advice" in text:
            level = WarningLevel.ADVICE
        else:
            level = WarningLevel.INFORMATION

        upstream_id = props.get("id")
        return CanonicalHazard(
            id=f"tas_alert_{upstream_id}" if upstream_id else stable_id("tas_alert", title, address),
            source="TasALERT / Tasmania Emergency Services",
            title=f"{title} - {_short_address(address)}" if address else title,
            hazard_type=HazardType.from_str(text),
            warning_level=level,
            latitude=lat,
            longitude=lon,
            updated_at=self.parse_datetime(props.get("changed") or props.get("callTime")),
            location_name=address or "Tasmania",
            is_hazard_reduction=any(kind in text for kind in _HAZARD_REDUCTION_TYPES),
            status=status,
            responsible_agency="TasALERT",
            web_url=TAS_ALERT_WEB_URL,
            raw_properties={
                "feed_type": props.get("feedType"),
                "type": type_name or None,
                "incident_number": props.get("number"),
                "burnt_area_ha": props.get("burntArea"),
                "call_time": props.get("callTime"),
            },
        )


def _short_address(address: str) -> str:
    """Return the locality part of a TasALERT address ("ROAD,LOCALITY,POSTCODE" -> "Locality")."""
    parts = [part.strip() for part in address.split(",") if part.strip() and not part.strip().isdigit()]
    return parts[-1].title() if parts else address
