"""Diagnostics support for Australian Disaster Watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AusNZDisasterWatchConfigEntry
from .const import CONF_LATITUDE, CONF_LONGITUDE

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    "latitude",
    "longitude",
    # ArcGIS editor fields hold email addresses (#30)
    "created_user",
    "last_edited_user",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    hazards_data = [hazard.model_dump(mode="json") for hazard in coordinator.active_hazards]

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "state_code": coordinator.state_code,
            "radius_km": coordinator.radius_km,
            "override_emergency": coordinator.override_emergency,
            "exclude_hazard_reduction": coordinator.exclude_hazard_reduction,
            "providers": [p.__class__.__name__ for p in coordinator.providers],
            "attribution": coordinator.attribution,
            "data_sources": [source.as_dict() for source in coordinator.data_sources],
            "active_hazards_count": len(coordinator.active_hazards),
            "highest_warning_level": coordinator.highest_warning_level.value,
            "has_emergency_warning_nearby": coordinator.has_emergency_warning_nearby,
            "inside_warning_area": coordinator.is_inside_warning_area,
            "hazards_with_area": sum(1 for h in coordinator.active_hazards if h.area),
        },
        "hazards": async_redact_data(hazards_data, TO_REDACT),
    }
