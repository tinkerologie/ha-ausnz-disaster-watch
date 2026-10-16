"""Geolocation platform for Australian Disaster Watch.

Renders active emergency incidents as interactive pins on Home Assistant map with
dynamic lifecycle management (adding and removing entities cleanly).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Final

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.components.geo_location.const import DOMAIN as GEO_LOCATION_DOMAIN
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import AusNZDisasterWatchConfigEntry
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


# geo_location triggers and the map card filter on ``source``; like the core feed
# integrations, every event from this integration shares one constant source (#18).
SOURCE: Final = DOMAIN

# Longest hazard-ID slug used in an entity ID before it is shortened with a digest.
MAX_HAZARD_SLUG_LENGTH: Final = 60
_DIGEST_LENGTH: Final = 8


def hazard_object_id(hazard_id: str) -> str:
    """Return a short, stable entity object ID for a hazard ID.

    Entity IDs come from the provider hazard ID, never from the headline, so they stay
    short and survive headline edits and restarts. Long IDs are truncated and given a
    digest of the full ID so two hazards with the same prefix do not collide.
    """
    slug = slugify(hazard_id)
    if len(slug) > MAX_HAZARD_SLUG_LENGTH:
        digest = hashlib.sha256(hazard_id.encode()).hexdigest()[:_DIGEST_LENGTH]
        slug = f"{slug[: MAX_HAZARD_SLUG_LENGTH - _DIGEST_LENGTH - 1].rstrip('_')}_{digest}"
    return f"{DOMAIN}_{slug}"


def current_hazards(coordinator: AustralianDisasterWatchCoordinator) -> dict[str, CanonicalHazard]:
    """Return the coordinator's current hazards keyed by hazard ID."""
    data: Any = coordinator.data
    if not data:
        return {}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, CanonicalHazard)}
    hazards = getattr(data, "hazards", None)
    if isinstance(hazards, dict):
        return hazards
    return {}


def snapshot_is_complete(coordinator: AustralianDisasterWatchCoordinator) -> bool:
    """Return True if the last refresh heard from every feed.

    While a feed is down its hazards may be missing from the data, so an absent hazard
    does not prove the incident has ended.
    """
    return coordinator.last_update_success and not getattr(coordinator.data, "feeds_failed", None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch geolocation entities from a config entry."""
    coordinator = entry.runtime_data
    registered_entities: dict[str, AustralianDisasterWatchGeolocationEvent] = {}

    # Events are transient: registry entries left behind by hazards that ended while Home
    # Assistant was stopped would otherwise come back as "unavailable" entities.
    active_unique_ids = {f"{entry.entry_id}_{hazard_id}" for hazard_id in current_hazards(coordinator)}
    entity_registry = er.async_get(hass)
    if snapshot_is_complete(coordinator):
        for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if registry_entry.domain == GEO_LOCATION_DOMAIN and registry_entry.unique_id not in active_unique_ids:
                entity_registry.async_remove(registry_entry.entity_id)

    @callback
    def _sync_entities() -> None:
        """Dynamically add new incidents and remove expired ones on coordinator update."""
        current_data = current_hazards(coordinator)

        new_entities: list[AustralianDisasterWatchGeolocationEvent] = []

        # Instantiate new entities for newly appeared incidents
        for hazard_id, hazard in current_data.items():
            if hazard_id not in registered_entities:
                entity = AustralianDisasterWatchGeolocationEvent(coordinator, entry.entry_id, hazard_id, hazard)
                registered_entities[hazard_id] = entity
                new_entities.append(entity)

        # Remove entities that have cleared from upstream feeds, but only after a refresh
        # that heard from every feed (#16). Removing the registry entry removes the entity
        # and its state; events are transient.
        expired_ids = set(registered_entities) - set(current_data) if snapshot_is_complete(coordinator) else set()
        for hazard_id in expired_ids:
            entity = registered_entities.pop(hazard_id)
            if entity_registry.async_get(entity.entity_id) is not None:
                entity_registry.async_remove(entity.entity_id)
            elif entity.hass is not None:
                entity.hass.async_create_task(entity.async_remove(force_remove=True))

        if new_entities:
            async_add_entities(new_entities)

    # Initial registration
    _sync_entities()

    # Listen for coordinator updates
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class AustralianDisasterWatchGeolocationEvent(CoordinatorEntity[AustralianDisasterWatchCoordinator], GeolocationEvent):
    """Geolocation event entity representing an active disaster hazard or warning.

    Follows the core feed integrations (e.g. ``geonetnz_quakes``): a constant ``source``,
    the headline as the name and a ``<entry_id>_<hazard_id>`` unique ID. The registry
    entry is removed when the event ends.
    """

    _attr_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_source = SOURCE

    def __init__(
        self,
        coordinator: AustralianDisasterWatchCoordinator,
        entry_id: str,
        hazard_id: str,
        hazard: CanonicalHazard,
    ) -> None:
        """Initialize geolocation event."""
        super().__init__(coordinator)
        self.hazard_id = hazard_id
        self._attr_unique_id = f"{entry_id}_{hazard_id}"
        self.entity_id = f"{GEO_LOCATION_DOMAIN}.{hazard_object_id(hazard_id)}"
        self._hazard = hazard
        self._attr_name = hazard.title

    @property
    def hazard(self) -> CanonicalHazard:
        """Return the last known hazard (kept while the entity is being removed)."""
        return self._hazard

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the cached hazard from coordinator data, then write state."""
        if (hazard := current_hazards(self.coordinator).get(self.hazard_id)) is not None:
            self._hazard = hazard
            self._attr_name = hazard.title
        super()._handle_coordinator_update()

    @property
    def attribution(self) -> str | None:
        """Return the attribution of the feed this hazard came from (#34)."""
        return self.hazard.attribution or self.coordinator.attribution

    @property
    def distance(self) -> float | None:
        """Return distance in kilometres from configured home / center point."""
        if self._hazard.distance_km is not None:
            return round(self._hazard.distance_km, 2)
        return None

    @property
    def latitude(self) -> float | None:
        """Return event latitude (centroid)."""
        return self._hazard.latitude

    @property
    def longitude(self) -> float | None:
        """Return event longitude (centroid)."""
        return self._hazard.longitude

    @property
    def icon(self) -> str:
        """Return MDI icon based on hazard type."""
        return HAZARD_ICONS.get(self._hazard.hazard_type, "mdi:alert-decagram")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe scalar state attributes (guaranteed < 16 KB SQLite limit).

        The agency is exposed as ``agency``; the ``source`` state attribute stays the
        integration-level platform source used by geo_location triggers and map cards.
        """
        attrs = self._hazard.to_safe_attributes()
        attrs["agency"] = attrs.pop("source")
        attrs["integration"] = DOMAIN
        return attrs


AusNZDisasterWatchGeolocationEvent = AustralianDisasterWatchGeolocationEvent
AustralianEmergencyHazardGeolocationEvent = AustralianDisasterWatchGeolocationEvent
