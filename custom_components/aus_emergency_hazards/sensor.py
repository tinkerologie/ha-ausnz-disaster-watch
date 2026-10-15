"""Sensor platform for Australian Emergency Hazards."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EmergencyDataCoordinator
from .entity import EmergencyHazardBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Emergency Hazards sensors."""
    coordinator: EmergencyDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NearestHazardDistanceSensor(coordinator),
            ActiveHazardsCountSensor(coordinator),
            HighestWarningLevelSensor(coordinator),
            NearestHazardTitleSensor(coordinator),
        ]
    )


class NearestHazardDistanceSensor(EmergencyHazardBaseEntity, SensorEntity):
    """Sensor tracking distance to the closest active emergency hazard."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_translation_key = "nearest_hazard_distance"
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize distance sensor."""
        super().__init__(coordinator, "nearest_hazard_distance")
        self._attr_name = "Nearest Hazard Distance"

    @property
    def native_value(self) -> float | None:
        """Return distance in km to closest hazard."""
        nearest = self.coordinator.nearest_hazard
        if nearest and nearest.distance_km is not None:
            return round(nearest.distance_km, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes describing the nearest hazard."""
        nearest = self.coordinator.nearest_hazard
        if not nearest:
            return {}
        return {
            "title": nearest.title,
            "hazard_type": nearest.hazard_type.value,
            "warning_level": nearest.warning_level.value,
            "location_name": nearest.location_name,
            "responsible_agency": nearest.responsible_agency,
            "web_url": nearest.web_url,
        }


class ActiveHazardsCountSensor(EmergencyHazardBaseEntity, SensorEntity):
    """Sensor tracking total count of active hazards within perimeter."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "hazards"
    _attr_translation_key = "active_hazards_count"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize count sensor."""
        super().__init__(coordinator, "active_hazards_count")
        self._attr_name = "Active Hazards Count"

    @property
    def native_value(self) -> int:
        """Return count of active hazards."""
        return len(self.coordinator.active_hazards)


class HighestWarningLevelSensor(EmergencyHazardBaseEntity, SensorEntity):
    """Sensor reporting the highest Australian Warning System level in the perimeter."""

    _attr_translation_key = "highest_warning_level"
    _attr_icon = "mdi:alert-decagram"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize highest warning level sensor."""
        super().__init__(coordinator, "highest_warning_level")
        self._attr_name = "Highest Warning Level"

    @property
    def native_value(self) -> str:
        """Return highest warning level string."""
        if not self.coordinator.active_hazards:
            return "All Clear"
        return self.coordinator.highest_warning_level.value

    @property
    def icon(self) -> str:
        """Return dynamic icon based on highest warning level."""
        lvl = self.coordinator.highest_warning_level
        if lvl.value == "Emergency Warning":
            return "mdi:alert-octagon"
        if lvl.value == "Watch and Act":
            return "mdi:alert"
        if lvl.value == "Advice":
            return "mdi:information"
        return "mdi:shield-check"


class NearestHazardTitleSensor(EmergencyHazardBaseEntity, SensorEntity):
    """Sensor displaying the title/headline of the nearest active hazard."""

    _attr_translation_key = "nearest_hazard_title"
    _attr_icon = "mdi:text-box-search"

    def __init__(self, coordinator: EmergencyDataCoordinator) -> None:
        """Initialize nearest hazard title sensor."""
        super().__init__(coordinator, "nearest_hazard_title")
        self._attr_name = "Nearest Hazard Title"

    @property
    def native_value(self) -> str:
        """Return headline of nearest hazard or 'None'."""
        nearest = self.coordinator.nearest_hazard
        if nearest:
            return nearest.title[:255]
        return "None"
