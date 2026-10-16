"""Diagnostics support for Australian Disaster Watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from . import AusNZDisasterWatchConfigEntry
from .const import CONF_COUNCIL_DASHBOARD_URL, CONF_LATITUDE, CONF_LOCATION_NAME, CONF_LONGITUDE, CONF_VIC_API_KEY
from .models import to_json_dict

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    "latitude",
    "longitude",
    # ArcGIS editor fields hold email addresses (#30)
    "created_user",
    "last_edited_user",
    CONF_VIC_API_KEY,
    # The monitored location's name and its council dashboard tell where the user lives (#21)
    CONF_LOCATION_NAME,
    CONF_COUNCIL_DASHBOARD_URL,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    hazards_data = [to_json_dict(hazard) for hazard in coordinator.active_hazards]

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            # The title holds the location name
            "title": REDACTED,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds() if coordinator.update_interval else None
            ),
            "feed_health": {
                key: {"status": status, "last_success": last.isoformat() if last else None}
                for key, (status, last) in coordinator.feed_health.items()
            },
            "state_code": coordinator.state_code,
            "radius_km": coordinator.radius_km,
            "override_emergency": coordinator.override_emergency,
            "exclude_hazard_reduction": coordinator.exclude_hazard_reduction,
            "providers": [p.__class__.__name__ for p in coordinator.providers],
            "attribution": coordinator.attribution,
            "data_sources": [source.as_dict() for source in coordinator.diagnostic_sources],
            "road_providers": [p.__class__.__name__ for p in coordinator.road_providers],
            "include_roadworks": coordinator.include_roadworks,
            "road_closures_count": len(coordinator.road_closures),
            "road_feeds_failed": coordinator.road_feeds_failed,
            "power_outage_sources": [p.__class__.__name__ for p in coordinator.power_sources],
            "active_hazards_count": len(coordinator.active_hazards),
            "highest_warning_level": coordinator.highest_warning_level.value,
            "has_emergency_warning_nearby": coordinator.has_emergency_warning_nearby,
            "inside_warning_area": coordinator.is_inside_warning_area,
            "hazards_with_area": sum(1 for h in coordinator.active_hazards if h.area),
        },
        "hazards": async_redact_data(hazards_data, TO_REDACT),
    }
