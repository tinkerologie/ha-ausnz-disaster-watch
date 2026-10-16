"""River and creek level sensors, one per gauge selected in the options flow (#31)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity import entry_device_info
from .river_coordinator import RiverGaugeCoordinator
from .rivers import GaugeReading, GaugeSite, haversine_km

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import AusNZDisasterWatchConfigEntry


def river_unique_id(entry_id: str, site: GaugeSite) -> str:
    """Return a gauge sensor's unique ID; it depends only on the gauge, not on its rank."""
    return f"{entry_id}_river_gauge_{site.source}_{site.site_id}"


def async_setup_river_sensors(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a sensor per selected gauge and remove sensors of gauges no longer selected."""
    coordinator = entry.runtime_data
    river = coordinator.river_coordinator
    sites = river.sites if river is not None else []
    wanted = {river_unique_id(entry.entry_id, site) for site in sites}

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_river_gauge_"
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain == SENSOR_DOMAIN
            and registry_entry.unique_id.startswith(prefix)
            and registry_entry.unique_id not in wanted
        ):
            registry.async_remove(registry_entry.entity_id)

    if river is not None:
        home = (coordinator.latitude, coordinator.longitude)
        async_add_entities(RiverLevelSensor(river, site, entry_device_info(coordinator), home) for site in river.sites)


class RiverLevelSensor(CoordinatorEntity[RiverGaugeCoordinator], SensorEntity):
    """Water level at a river, creek or lake gauge, in metres above the gauge datum."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_suggested_display_precision = 2
    _attr_translation_key = "river_level"

    def __init__(
        self,
        coordinator: RiverGaugeCoordinator,
        site: GaugeSite,
        device_info: Any,
        home: tuple[float, float],
    ) -> None:
        """Initialize the gauge sensor."""
        super().__init__(coordinator)
        self.site = site
        self._attr_unique_id = river_unique_id(coordinator.config_entry.entry_id, site)
        self._attr_translation_placeholders = {"gauge": site.name}
        self._attr_device_info = device_info
        self._attr_attribution = site.attribution
        self._distance_km = round(haversine_km(home[0], home[1], site.latitude, site.longitude), 2)

    @property
    def reading(self) -> GaugeReading | None:
        """Return this gauge's latest reading, if any."""
        return (self.coordinator.data or {}).get(self.site.key)

    @property
    def available(self) -> bool:
        """Return True while the gauge has a recent reading."""
        return super().available and self.reading is not None

    @property
    def native_value(self) -> float | None:
        """Return the water level in metres."""
        reading = self.reading
        return reading.level_m if reading else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the gauge details, observation time and trend."""
        attrs: dict[str, Any] = {
            "site_id": self.site.site_id,
            "source": self.site.source,
            "latitude": self.site.latitude,
            "longitude": self.site.longitude,
            "distance_km": self._distance_km,
        }
        if self.site.alert_level_m is not None:
            attrs["alert_level_m"] = self.site.alert_level_m
        if reading := self.reading:
            attrs["observed_at"] = reading.observed_at.isoformat()
            attrs["trend"] = reading.trend
            attrs["change_1h_m"] = reading.change_m
        return attrs
