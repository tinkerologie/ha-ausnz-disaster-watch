"""Binary sensor platform for Australian Emergency Hazards."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_HIGHEST_WARNING_LEVEL,
    ATTR_INCIDENT_COUNT,
    ATTR_NEAREST_INCIDENT_DISTANCE,
    ATTR_NEAREST_INCIDENT_TITLE,
    DOMAIN,
)
from .coordinator import EmergencyDataCoordinator
from .entity import EmergencyHazardBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Emergency Hazards binary sensors."""
    coordinator: EmergencyDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EmergencyWarningNearbyBinarySensor(coordinator),
            ActiveHazardsNearbyBinarySensor(coordinator),
        ]
    )


class EmergencyWarningNearbyBinarySensor(EmergencyHazardBaseEntity, BinarySensorEntity):
    """Binary sensor that turns on if an Emergency Warning or Watch and Act is active nearby."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "emergency_warning_nearby"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "emergency_warning_nearby")
        self._attr_name = "Emergency Warning Nearby"

    @property
    def is_on(self) -> bool:
        """Return True if an emergency warning or watch and act is active in perimeter."""
        return self.coordinator.has_emergency_warning_nearby

    @property
    def icon(self) -> str:
        """Return icon depending on alert state."""
        return "mdi:alert-octagon" if self.is_on else "mdi:shield-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alert attributes for automation logic."""
        nearest = self.coordinator.nearest_hazard
        return {
            ATTR_HIGHEST_WARNING_LEVEL: self.coordinator.highest_warning_level.value,
            ATTR_INCIDENT_COUNT: len(self.coordinator.active_hazards),
            ATTR_NEAREST_INCIDENT_TITLE: nearest.title if nearest else None,
            ATTR_NEAREST_INCIDENT_DISTANCE: (
                round(nearest.distance_km, 2) if nearest and nearest.distance_km is not None else None
            ),
        }


class ActiveHazardsNearbyBinarySensor(EmergencyHazardBaseEntity, BinarySensorEntity):
    """Binary sensor that turns on if any active hazard is within the configured perimeter."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "active_hazards_nearby"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "active_hazards_nearby")
        self._attr_name = "Active Hazards Nearby"

    @property
    def is_on(self) -> bool:
        """Return True if any hazard exists in perimeter."""
        return len(self.coordinator.active_hazards) > 0

    @property
    def icon(self) -> str:
        """Return icon depending on state."""
        return "mdi:alert" if self.is_on else "mdi:check-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes."""
        return {
            ATTR_INCIDENT_COUNT: len(self.coordinator.active_hazards),
            ATTR_HIGHEST_WARNING_LEVEL: self.coordinator.highest_warning_level.value,
        }
