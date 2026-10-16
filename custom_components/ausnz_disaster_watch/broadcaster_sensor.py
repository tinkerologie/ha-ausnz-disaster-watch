"""Emergency broadcaster sensor (#73): the station to tune to for the monitored location."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .broadcaster import (
    Broadcaster,
    BroadcasterChoice,
    async_load_broadcasters,
    broadcaster_enabled,
    broadcaster_option,
    choose_broadcaster,
    country_of,
    media_content_id,
)
from .const import DOMAIN
from .entity import AustralianDisasterWatchEntity
from .providers.sources import attribution_for, sources_for_broadcaster

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import AusNZDisasterWatchConfigEntry
    from .coordinator import AustralianDisasterWatchCoordinator

ENTITY_KEY = "emergency_broadcaster"


async def async_setup_broadcaster_sensor(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the sensor when the broadcaster is on; remove its registry entry when it is off."""
    if not broadcaster_enabled(entry):
        registry = er.async_get(hass)
        unique_id = f"{entry.entry_id}_{ENTITY_KEY}"
        if entity_id := registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id):
            registry.async_remove(entity_id)
        return
    stations = await async_load_broadcasters(hass)
    async_add_entities([EmergencyBroadcasterSensor(entry.runtime_data, stations)])


class EmergencyBroadcasterSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Name of the emergency broadcaster station, with its stream for media players.

    The station follows the monitored point (the Home Assistant home for home-zone entries),
    unless a station was chosen in the options. Disabled by default.
    """

    _attr_translation_key = ENTITY_KEY
    _attr_icon = "mdi:radio"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator, stations: dict[str, Broadcaster]) -> None:
        """Initialise the sensor with the bundled station table."""
        super().__init__(coordinator, ENTITY_KEY)
        self._stations = stations
        self._attr_attribution = attribution_for(sources_for_broadcaster(country_of(coordinator.state_code)))

    @property
    def _choice(self) -> BroadcasterChoice | None:
        coordinator = self.coordinator
        return choose_broadcaster(
            self._stations,
            broadcaster_option(coordinator.entry),
            coordinator.state_code,
            coordinator.latitude,
            coordinator.longitude,
        )

    @property
    def available(self) -> bool:
        """Return True while a station can be named; it does not depend on the hazard feeds."""
        return self._choice is not None

    @property
    def native_value(self) -> str | None:
        """Return the station name."""
        choice = self._choice
        return choice.station.name if choice else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the stream and how the station was chosen."""
        if (choice := self._choice) is None:
            return {}
        station = choice.station
        return {
            "stream_url": station.stream_url,
            "media_content_id": media_content_id(self.coordinator.entry.entry_id),
            "media_content_type": "music",
            "region": station.region,
            "network": station.network,
            "state": station.state,
            "station_page": station.station_page,
            "selection": choice.selection,
            "distance_km": round(choice.distance_km, 1),
        }
