"""Binary sensor platform for Australian Disaster Watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    # Re-exported by the package without __all__; core imports it the same way.
    BinarySensorDeviceClass,  # pyright: ignore[reportPrivateImportUsage]
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AusNZDisasterWatchConfigEntry
from .const import (
    ATTR_HIGHEST_WARNING_LEVEL,
    ATTR_INCIDENT_COUNT,
    ATTR_NEAREST_INCIDENT_DISTANCE,
    ATTR_NEAREST_INCIDENT_TITLE,
)
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity
from .forecast_entity import forecast_binary_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            EmergencyWarningNearbyBinarySensor(coordinator),
            ActiveHazardsNearbyBinarySensor(coordinator),
            PowerOutageActiveBinarySensor(coordinator),
            RoadClosureNearbyBinarySensor(coordinator),
            *forecast_binary_sensors(coordinator),
        ]
    )


class EmergencyWarningNearbyBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Binary sensor that turns on if an Emergency Warning or Watch and Act is active nearby."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "emergency_warning_nearby"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "emergency_warning_nearby")

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


class ActiveHazardsNearbyBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Binary sensor that turns on if any active hazard is within the configured perimeter."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "active_hazards_nearby"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "active_hazards_nearby")

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


class PowerOutageActiveBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Binary sensor that turns on if any active power outage exists in the region."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "power_outage_active"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize power outage binary sensor."""
        super().__init__(coordinator, "power_outage_active")

    @property
    def is_on(self) -> bool:
        """Return True if any power outages exist."""
        return len(self.coordinator.power_outages) > 0

    @property
    def icon(self) -> str:
        """Return icon depending on state."""
        return "mdi:transmission-tower-off" if self.is_on else "mdi:transmission-tower"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return outage counts."""
        outages = self.coordinator.power_outages
        return {
            "outages_count": len(outages),
            "customers_affected": sum(o.customers_affected for o in outages),
        }


class RoadClosureNearbyBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Binary sensor that turns on if any road closures or hazards exist in perimeter."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "road_closure_nearby"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize road closure binary sensor."""
        super().__init__(coordinator, "road_closure_nearby")

    @property
    def is_on(self) -> bool:
        """Return True if any road closures exist."""
        return len(self.coordinator.road_closures) > 0

    @property
    def icon(self) -> str:
        """Return icon depending on state."""
        return "mdi:traffic-cone" if self.is_on else "mdi:road-variant"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return closure counts."""
        return {
            "closures_count": len(self.coordinator.road_closures),
        }
