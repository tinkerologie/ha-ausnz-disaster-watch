"""Geolocation platform for Australian Disaster Watch.

Renders active emergency incidents as interactive pins on Home Assistant map with
dynamic lifecycle management (adding and removing entities cleanly).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator
from .models import CanonicalHazard, HazardType

_LOGGER = logging.getLogger(__name__)

HAZARD_ICONS = {
    HazardType.BUSHFIRE: "mdi:fire",
    HazardType.GRASS_FIRE: "mdi:grass",
    HazardType.METROPOLITAN_FIRE: "mdi:fire-alert",
    HazardType.FLOOD: "mdi:water-alert",
    HazardType.SEVERE_STORM: "mdi:weather-lightning",
    HazardType.CYCLONE: "mdi:weather-hurricane",
    HazardType.EARTHQUAKE: "mdi:pulse",
    HazardType.VOLCANO: "mdi:volcano",
    HazardType.TSUNAMI: "mdi:tsunami",
    HazardType.HAZMAT: "mdi:biohazard",
    HazardType.ROAD_INCIDENT: "mdi:car-emergency",
    HazardType.OTHER: "mdi:alert-decagram",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch geolocation entities from a config entry."""
    coordinator: AustralianDisasterWatchCoordinator = hass.data[DOMAIN][entry.entry_id]
    registered_entities: dict[str, AustralianDisasterWatchGeolocationEvent] = {}

    @callback
    def _sync_entities() -> None:
        """Dynamically add new incidents and remove expired ones on coordinator update."""
        current_data: dict[str, CanonicalHazard] = {}
        if coordinator.data:
            if isinstance(coordinator.data, dict):
                current_data = {str(k): v for k, v in coordinator.data.items() if isinstance(v, CanonicalHazard)}
            elif hasattr(coordinator.data, "hazards") and isinstance(coordinator.data.hazards, dict):
                current_data = coordinator.data.hazards

        new_entities: list[AustralianDisasterWatchGeolocationEvent] = []

        # Instantiate new entities for newly appeared incidents
        for hazard_id in list(current_data.keys()):
            if hazard_id not in registered_entities:
                entity = AustralianDisasterWatchGeolocationEvent(coordinator, hazard_id)
                registered_entities[hazard_id] = entity
                new_entities.append(entity)

        # Remove entities that have cleared from upstream feeds
        expired_ids = set(registered_entities.keys()) - set(current_data.keys())
        for hazard_id in expired_ids:
            entity = registered_entities.pop(hazard_id)
            if entity.hass is not None:
                entity.hass.async_create_task(entity.async_remove())

        if new_entities:
            async_add_entities(new_entities)

    # Initial registration
    _sync_entities()

    # Listen for coordinator updates
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class AustralianDisasterWatchGeolocationEvent(CoordinatorEntity[AustralianDisasterWatchCoordinator], GeolocationEvent):
    """Geolocation event entity representing an active disaster hazard or warning."""

    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(
        self,
        coordinator: AustralianDisasterWatchCoordinator,
        hazard_id: str,
    ) -> None:
        """Initialize geolocation event."""
        super().__init__(coordinator)
        self.hazard_id = hazard_id

    @property
    def hazard(self) -> CanonicalHazard | None:
        """Return the hazard instance from coordinator data."""
        if not self.coordinator.data:
            return None
        if isinstance(self.coordinator.data, dict):
            return self.coordinator.data.get(self.hazard_id)
        if hasattr(self.coordinator.data, "hazards") and self.coordinator.data.hazards:
            return self.coordinator.data.hazards.get(self.hazard_id)
        return None

    @property
    def name(self) -> str:
        """Return the event name / headline."""
        if self.hazard:
            return self.hazard.title
        return "Emergency Incident"

    @property
    def source(self) -> str:
        """Return the source agency / integration identifier."""
        if self.hazard:
            return self.hazard.source
        return DOMAIN

    @property
    def distance(self) -> float | None:
        """Return distance in kilometres from configured home / center point."""
        if self.hazard and self.hazard.distance_km is not None:
            return round(self.hazard.distance_km, 2)
        return None

    @property
    def latitude(self) -> float | None:
        """Return event latitude (centroid)."""
        if self.hazard:
            return self.hazard.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return event longitude (centroid)."""
        if self.hazard:
            return self.hazard.longitude
        return None

    @property
    def icon(self) -> str:
        """Return MDI icon based on hazard type."""
        if self.hazard:
            return HAZARD_ICONS.get(self.hazard.hazard_type, "mdi:alert-decagram")
        return "mdi:alert-decagram"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe scalar state attributes (guaranteed < 16 KB SQLite limit)."""
        if not self.hazard:
            return {"integration": DOMAIN}
        attrs = self.hazard.to_safe_attributes()
        attrs["integration"] = DOMAIN
        return attrs


AusNZDisasterWatchGeolocationEvent = AustralianDisasterWatchGeolocationEvent
AustralianEmergencyHazardGeolocationEvent = AustralianDisasterWatchGeolocationEvent
