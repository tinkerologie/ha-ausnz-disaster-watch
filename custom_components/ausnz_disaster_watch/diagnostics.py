"""Diagnostics support for Australian Disaster Watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LATITUDE, CONF_LONGITUDE, DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AustralianDisasterWatchCoordinator = hass.data[DOMAIN][entry.entry_id]

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
            "active_hazards_count": len(coordinator.active_hazards),
            "highest_warning_level": coordinator.highest_warning_level.value,
            "has_emergency_warning_nearby": coordinator.has_emergency_warning_nearby,
        },
        "hazards": async_redact_data(hazards_data, TO_REDACT),
    }
