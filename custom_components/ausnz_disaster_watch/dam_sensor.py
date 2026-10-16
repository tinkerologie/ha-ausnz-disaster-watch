"""Dam and weir storage sensors: percent full, volume and level per selected storage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .dam_coordinator import DamStorageCoordinator
from .dams import StorageReading, StorageSite
from .entity import entry_device_info
from .rivers import haversine_km

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import AusNZDisasterWatchConfigEntry

UNIQUE_ID_PREFIX = "dam_storage"
# Megalitres: Home Assistant has no unit constant for them.
UNIT_MEGALITRES = "ML"


@dataclass(frozen=True, kw_only=True)
class DamSensorDescription(SensorEntityDescription):
    """A storage sensor and the reading value it shows."""

    value_fn: Callable[[StorageReading], float | None]


DAM_SENSORS: tuple[DamSensorDescription, ...] = (
    DamSensorDescription(
        key="percent_full",
        translation_key="dam_percent_full",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:water-percent",
        value_fn=lambda reading: reading.percent_full,
    ),
    DamSensorDescription(
        key="volume",
        translation_key="dam_volume",
        native_unit_of_measurement=UNIT_MEGALITRES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:water",
        value_fn=lambda reading: reading.volume_ml,
    ),
    DamSensorDescription(
        key="level",
        translation_key="dam_level",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:waves",
        value_fn=lambda reading: reading.level_m,
    ),
)


def dam_unique_id(entry_id: str, site: StorageSite, key: str) -> str:
    """Return a storage entity's unique ID; it depends only on the storage and the value."""
    return f"{entry_id}_{UNIQUE_ID_PREFIX}_{site.site_id}_{key}"


def _remove_stale(hass: HomeAssistant, entry_id: str, domain: str, wanted: set[str]) -> None:
    """Remove storage entities of this platform that are no longer selected."""
    registry = er.async_get(hass)
    prefix = f"{entry_id}_{UNIQUE_ID_PREFIX}_"
    for registry_entry in er.async_entries_for_config_entry(registry, entry_id):
        if (
            registry_entry.domain == domain
            and registry_entry.unique_id.startswith(prefix)
            and registry_entry.unique_id not in wanted
        ):
            registry.async_remove(registry_entry.entity_id)


def _sensor_keys(site: StorageSite) -> list[DamSensorDescription]:
    """Return the sensors a storage has; level-only storages have no volume sensors."""
    has = {
        "percent_full": bool(site.volume_ts and site.full_volume_ml),
        "volume": bool(site.volume_ts),
        "level": bool(site.level_ts),
    }
    return [description for description in DAM_SENSORS if has[description.key]]


def async_setup_dam_sensors(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors per selected storage and remove sensors of storages no longer selected."""
    coordinator = entry.runtime_data
    dams = coordinator.dam_coordinator
    sites = dams.sites if dams is not None else []
    wanted = {dam_unique_id(entry.entry_id, site, d.key) for site in sites for d in _sensor_keys(site)}
    _remove_stale(hass, entry.entry_id, SENSOR_DOMAIN, wanted)
    if dams is not None:
        home = (coordinator.latitude, coordinator.longitude)
        device_info = entry_device_info(coordinator)
        async_add_entities(
            DamStorageSensor(dams, site, description, device_info, home)
            for site in dams.sites
            for description in _sensor_keys(site)
        )


def async_setup_dam_binary_sensors(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an above-full-supply sensor per selected storage; remove the ones no longer selected."""
    coordinator = entry.runtime_data
    dams = coordinator.dam_coordinator
    sites = dams.sites if dams is not None else []
    wanted = {dam_unique_id(entry.entry_id, site, "above_full_supply") for site in sites}
    _remove_stale(hass, entry.entry_id, BINARY_SENSOR_DOMAIN, wanted)
    if dams is not None:
        home = (coordinator.latitude, coordinator.longitude)
        device_info = entry_device_info(coordinator)
        async_add_entities(DamAboveFullSupplyBinarySensor(dams, site, device_info, home) for site in dams.sites)


class DamEntity(CoordinatorEntity[DamStorageCoordinator]):
    """Common parts of the storage entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DamStorageCoordinator,
        site: StorageSite,
        key: str,
        device_info: Any,
        home: tuple[float, float],
    ) -> None:
        """Initialize the storage entity."""
        super().__init__(coordinator)
        self.site = site
        self._attr_unique_id = dam_unique_id(coordinator.config_entry.entry_id, site, key)
        self._attr_translation_placeholders = {"storage": site.name}
        self._attr_device_info = device_info
        self._attr_attribution = site.attribution
        self._distance_km = round(haversine_km(home[0], home[1], site.latitude, site.longitude), 2)

    @property
    def reading(self) -> StorageReading | None:
        """Return this storage's latest reading, if any."""
        return (self.coordinator.data or {}).get(self.site.key)

    @property
    def available(self) -> bool:
        """Return True while the storage has a recent reading."""
        return super().available and self.reading is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the storage details and its latest reading."""
        attrs: dict[str, Any] = {
            "site_id": self.site.site_id,
            "latitude": self.site.latitude,
            "longitude": self.site.longitude,
            "distance_km": self._distance_km,
            "full_supply_volume_ml": self.site.full_volume_ml,
            "full_supply_level_m": self.site.full_level_m,
        }
        if reading := self.reading:
            attrs.update(
                {
                    "observed_at": reading.observed_at.isoformat(),
                    "percent_full": reading.percent_full,
                    "volume_ml": reading.volume_ml,
                    "level_m": reading.level_m,
                    "change_24h_ml": reading.change_24h_ml,
                    "above_full_supply": reading.above_full_supply,
                }
            )
        return attrs


class DamStorageSensor(DamEntity, SensorEntity):
    """Percent full, volume or level of a dam or weir storage."""

    entity_description: DamSensorDescription

    def __init__(
        self,
        coordinator: DamStorageCoordinator,
        site: StorageSite,
        description: DamSensorDescription,
        device_info: Any,
        home: tuple[float, float],
    ) -> None:
        """Initialize the storage sensor."""
        super().__init__(coordinator, site, description.key, device_info, home)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the value from the latest reading."""
        reading = self.reading
        return self.entity_description.value_fn(reading) if reading else None


class DamAboveFullSupplyBinarySensor(DamEntity, BinarySensorEntity):
    """On while a storage holds more than its full supply volume (or is above full supply level).

    An ungated dam above full supply is spilling; a gated flood-mitigation dam is holding
    flood water above its drinking-water compartment and will be releasing it.
    """

    _attr_translation_key = "dam_above_full_supply"
    _attr_icon = "mdi:waves-arrow-up"

    def __init__(
        self, coordinator: DamStorageCoordinator, site: StorageSite, device_info: Any, home: tuple[float, float]
    ) -> None:
        """Initialize the above-full-supply sensor."""
        super().__init__(coordinator, site, "above_full_supply", device_info, home)

    @property
    def is_on(self) -> bool | None:
        """Return True when the storage is above full supply."""
        reading = self.reading
        return reading.above_full_supply if reading else None
