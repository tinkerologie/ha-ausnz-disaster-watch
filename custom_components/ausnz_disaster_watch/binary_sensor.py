"""Binary sensor platform for Australian Disaster Watch."""

from __future__ import annotations

from datetime import timedelta
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
    STATE_NZ,
)
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity
from .forecast_entity import forecast_binary_sensors
from .models import CALL_TO_ACTION_MAX_LENGTH
from .providers.fire_danger import local_today
from .providers.sources import attribution_for
from .river_binary_sensor import async_setup_river_alert_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch binary sensors."""
    coordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        EmergencyWarningNearbyBinarySensor(coordinator),
        InsideWarningAreaBinarySensor(coordinator),
        ActiveHazardsNearbyBinarySensor(coordinator),
        PowerOutageActiveBinarySensor(coordinator),
        RoadClosureNearbyBinarySensor(coordinator),
        *forecast_binary_sensors(coordinator),
    ]
    if coordinator.state_code != STATE_NZ:
        entities.append(TotalFireBanBinarySensor(coordinator))
    async_add_entities(entities)
    async_setup_river_alert_sensors(hass, entry, async_add_entities)


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


class InsideWarningAreaBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Binary sensor that turns on while the monitored point is inside a warning area (#30).

    Only warnings published with an area count (Advice or higher); a warning given only as a
    point never turns it on. Attributes are scalars; the polygons are never exposed.
    """

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "inside_warning_area"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "inside_warning_area")

    @property
    def is_on(self) -> bool:
        """Return True if the monitored point is inside an Advice or higher warning area."""
        return self.coordinator.is_inside_warning_area

    @property
    def icon(self) -> str:
        """Return icon depending on state."""
        return "mdi:map-marker-alert" if self.is_on else "mdi:map-marker-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the number of containing warnings and the most severe one."""
        inside = self.coordinator.inside_warning_hazards
        top = inside[0] if inside else None
        return {
            "warning_count": len(inside),
            "warning_level": top.warning_level.value if top else None,
            "warning_title": top.title if top else None,
            "call_to_action": top.call_to_action[:CALL_TO_ACTION_MAX_LENGTH] if top and top.call_to_action else None,
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


class TotalFireBanBinarySensor(AustralianDisasterWatchEntity, BinarySensorEntity):
    """Total fire ban declared today for the location's fire weather district (#28).

    Unknown (not off) when the district's agency publishes no ban feed (QLD, NT, TAS) or
    the feed could not be read: an unknown ban is never reported as "no ban".
    """

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "total_fire_ban"

    @property
    def attribution(self) -> str | None:
        """Credit the fire danger and total fire ban sources for this district (#28, #34)."""
        return attribution_for(self.coordinator.fire_service.data_sources) or super().attribution

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize total fire ban binary sensor."""
        super().__init__(coordinator, "total_fire_ban")

    @property
    def is_on(self) -> bool | None:
        """Return True if a total fire ban is declared for today."""
        outlook = self.coordinator.fire_outlook
        if outlook is None:
            return None
        today = outlook.day(local_today(outlook.time_zone))
        return today.total_fire_ban if today else None

    @property
    def icon(self) -> str:
        """Return icon depending on state."""
        return "mdi:fire-alert" if self.is_on else "mdi:fire-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the district, tomorrow's ban and the ban outlook."""
        outlook = self.coordinator.fire_outlook
        if outlook is None:
            return {}
        today = local_today(outlook.time_zone)
        tomorrow = outlook.day(today + timedelta(days=1))
        return {
            "date": today.isoformat(),
            "district_name": outlook.district_name,
            "district_number": outlook.district_number,
            "tomorrow": tomorrow.total_fire_ban if tomorrow else None,
            "forecast": [
                {"date": day.date.isoformat(), "total_fire_ban": day.total_fire_ban}
                for day in outlook.days
                if day.date >= today
            ],
            "source": outlook.total_fire_ban_source,
        }
