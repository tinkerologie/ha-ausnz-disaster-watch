"""Alert binary sensors for river gauges with a user-entered alert level (#31)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    # Re-exported by the package without __all__; core imports it the same way.
    BinarySensorDeviceClass,  # pyright: ignore[reportPrivateImportUsage]
    BinarySensorEntity,
)
from homeassistant.components.binary_sensor.const import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity import entry_device_info
from .river_coordinator import RiverGaugeCoordinator
from .rivers import GaugeReading, GaugeSite

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import AusNZDisasterWatchConfigEntry


def river_alert_unique_id(entry_id: str, site: GaugeSite) -> str:
    """Return a gauge alert sensor's unique ID."""
    return f"{entry_id}_river_gauge_alert_{site.source}_{site.site_id}"


def async_setup_river_alert_sensors(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an alert sensor per gauge with an alert level; remove the ones no longer set."""
    coordinator = entry.runtime_data
    river = coordinator.river_coordinator
    sites = [site for site in (river.sites if river is not None else []) if site.alert_level_m is not None]
    wanted = {river_alert_unique_id(entry.entry_id, site) for site in sites}

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_river_gauge_alert_"
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain == BINARY_SENSOR_DOMAIN
            and registry_entry.unique_id.startswith(prefix)
            and registry_entry.unique_id not in wanted
        ):
            registry.async_remove(registry_entry.entity_id)

    if river is not None and sites:
        device_info = entry_device_info(coordinator)
        async_add_entities(RiverAlertBinarySensor(river, site, device_info) for site in sites)


class RiverAlertBinarySensor(CoordinatorEntity[RiverGaugeCoordinator], BinarySensorEntity):
    """On while a gauge's level is at or above the alert level the user set for it."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "river_alert"
    _attr_icon = "mdi:waves-arrow-up"

    def __init__(self, coordinator: RiverGaugeCoordinator, site: GaugeSite, device_info: Any) -> None:
        """Initialize the alert sensor."""
        super().__init__(coordinator)
        self.site = site
        self.alert_level_m = float(site.alert_level_m or 0.0)
        self._attr_unique_id = river_alert_unique_id(coordinator.config_entry.entry_id, site)
        self._attr_translation_placeholders = {"gauge": site.name}
        self._attr_device_info = device_info
        self._attr_attribution = site.attribution

    @property
    def reading(self) -> GaugeReading | None:
        """Return this gauge's latest reading, if any."""
        return (self.coordinator.data or {}).get(self.site.key)

    @property
    def available(self) -> bool:
        """Return True while the gauge has a recent reading."""
        return super().available and self.reading is not None

    @property
    def is_on(self) -> bool | None:
        """Return True when the level has reached the alert level."""
        reading = self.reading
        return reading.level_m >= self.alert_level_m if reading else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alert level and the latest level."""
        reading = self.reading
        return {
            "alert_level_m": self.alert_level_m,
            "level_m": reading.level_m if reading else None,
            "site_id": self.site.site_id,
        }
