"""Northern Territory Emergency Hazard Provider (NT PFES)."""

from __future__ import annotations

import logging
from typing import Any

from custom_components.ausnz_disaster_watch.const import STATE_NT
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

NT_INCIDENTS_URL = "https://pfes.nt.gov.au/incidentmap/json/incidents.json"


class NTHazardProvider(BaseHazardProvider):
    """Provider for Northern Territory Police, Fire and Emergency Services (PFES)."""

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_NT

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active incidents and warnings from NT PFES."""
        hazards: list[CanonicalHazard] = []

        try:
            data = await self.async_fetch_json(NT_INCIDENTS_URL)
            hazards.extend(self._parse_nt_incidents(data))
        except Exception:
            _LOGGER.exception("Failed to fetch NT PFES incident map feed")

        return hazards

    def _parse_nt_incidents(self, data: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse NT PFES incident JSON structure."""
        hazards: list[CanonicalHazard] = []
        incidents_data = data.get("incidents", {})

        # Collect features whether incidents is a dict of lists or a single list
        feature_list: list[dict[str, Any]] = []
        if isinstance(incidents_data, dict):
            for group in incidents_data.values():
                if isinstance(group, list):
                    feature_list.extend(group)
        elif isinstance(incidents_data, list):
            feature_list.extend(incidents_data)

        # Also support top-level "features" if present
        if "features" in data and isinstance(data["features"], list):
            feature_list.extend(data["features"])

        for idx, feat in enumerate(feature_list):
            if not isinstance(feat, dict):
                continue

            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            centroid = self.calculate_centroid(geom)
            if not centroid:
                continue

            lat, lon = centroid
            event_type = str(props.get("_eventtype") or props.get("Fire Type") or "Emergency Incident")
            location = str(props.get("_location") or props.get("Location") or "Northern Territory")
            alert_level_str = str(props.get("Alert Level") or props.get("_category") or "")
            status = str(props.get("Status") or props.get("_status") or "Active")
            agency = str(props.get("Responsible Agency") or "NT PFES")
            last_update = props.get("_lastupdate") or props.get("_datenotified") or props.get("Last Update")

            # Check if hazard reduction
            is_hr = "hazard reduction" in event_type.lower() or "planned" in event_type.lower()

            # Warning Level
            if "emergency" in alert_level_str.lower():
                level = WarningLevel.EMERGENCY_WARNING
            elif "watch" in alert_level_str.lower():
                level = WarningLevel.WATCH_AND_ACT
            elif "advice" in alert_level_str.lower():
                level = WarningLevel.ADVICE
            else:
                level = WarningLevel.INFORMATION

            item_id = f"nt_{props.get('_datenotified', idx)}_{location[:20].strip()}"
            title = f"{event_type} - {location}"

            hazards.append(
                CanonicalHazard(
                    id=item_id,
                    source="NT Police, Fire and Emergency Services",
                    title=title,
                    hazard_type=HazardType.from_str(event_type),
                    warning_level=level,
                    latitude=lat,
                    longitude=lon,
                    updated_at=self.parse_datetime(last_update),
                    location_name=location,
                    is_hazard_reduction=is_hr,
                    status=status,
                    responsible_agency=agency,
                    web_url="https://securent.nt.gov.au/alerts",
                    raw_properties={
                        "risks": props.get("Risks"),
                        "what_to_do": props.get("What to do"),
                        "current_situation": props.get("Current Situation"),
                    },
                )
            )

        return hazards
