"""Entity and device lifecycle: remove registry entries that the configuration no longer creates (#92).

Entities come and go in two ways:

* With the configuration (options, reconfigure): the sensor and binary sensor platforms create
  a fixed set at setup. ``tracks_entities`` records the unique IDs each platform creates, and
  ``async_setup_registry_cleanup`` removes the entry's other registry entries of those platforms
  (and any of a platform the integration no longer sets up), so entities of a feature switched
  off, or of a state the entry no longer monitors, do not linger as "unavailable".
* With the data: geolocation events and cameras follow the feeds. Their platforms remove the
  registry entry of an event or camera that is gone, but only after a refresh that heard from
  every source (``snapshot_is_complete``, ``cameras_complete``): while a source is down, a
  missing item does not prove it has gone.

Devices: every entity belongs to the entry's one service device. Devices of the entry left
without entities are removed, and the user may delete any device that is not the entry's own.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
import functools
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AustralianDisasterWatchCoordinator

type PlatformSetup = Callable[[HomeAssistant, Any, "AddEntitiesCallback"], Awaitable[None]]


def snapshot_is_complete(coordinator: AustralianDisasterWatchCoordinator) -> bool:
    """Return True if the last refresh heard from every hazard feed.

    While a feed is down its hazards may be missing from the data, so an absent hazard
    does not prove the incident has ended.
    """
    return coordinator.last_update_success and not getattr(coordinator.data, "feeds_failed", None)


def cameras_complete(coordinator: AustralianDisasterWatchCoordinator) -> bool:
    """Return True if the last refresh heard from every camera source.

    While a camera source is down its cameras are missing from the data, so an absent
    camera does not prove it has been delisted.
    """
    return (
        coordinator.last_update_success
        and coordinator.data is not None
        and not getattr(coordinator.data, "cameras_failed", None)
    )


@callback
def async_remove_registry_entries(hass: HomeAssistant, entry_id: str, domains: Iterable[str], keep: set[str]) -> int:
    """Remove the entry's registry entries of ``domains`` whose unique ID is not in ``keep``; return how many."""
    registry = er.async_get(hass)
    wanted_domains = set(domains)
    stale = [
        registry_entry.entity_id
        for registry_entry in er.async_entries_for_config_entry(registry, entry_id)
        if registry_entry.domain in wanted_domains and registry_entry.unique_id not in keep
    ]
    for entity_id in stale:
        registry.async_remove(entity_id)
    return len(stale)


class EntityTracker:
    """The unique IDs each of the entry's platforms created, keyed by platform domain.

    A platform is listed only once its setup has finished, so a platform that failed to set
    up never has its registry entries removed.
    """

    def __init__(self) -> None:
        """Start with no platform set up."""
        self.created: dict[str, set[str]] = {}


def _recording(created: set[str], async_add_entities: AddEntitiesCallback) -> AddEntitiesCallback:
    """Return an add-entities callback that also records each entity's unique ID in ``created``."""

    def _add(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        entities = list(new_entities)
        created.update(entity.unique_id for entity in entities if entity.unique_id is not None)
        async_add_entities(entities, update_before_add)

    return _add


def tracks_entities(domain: str) -> Callable[[PlatformSetup], PlatformSetup]:
    """Record in the entry's ``EntityTracker`` the unique IDs a platform's ``async_setup_entry`` creates."""

    def decorate(setup: PlatformSetup) -> PlatformSetup:
        @functools.wraps(setup)
        async def wrapper(hass: HomeAssistant, entry: Any, async_add_entities: AddEntitiesCallback) -> None:
            tracker = getattr(entry.runtime_data, "entity_tracker", None)
            if not isinstance(tracker, EntityTracker):
                # A stand-in coordinator (tests): nothing to record
                await setup(hass, entry, async_add_entities)
                return
            created: set[str] = set()
            await setup(hass, entry, _recording(created, async_add_entities))
            tracker.created[domain] = created

        return wrapper

    return decorate


@callback
def async_remove_stale_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the entry's devices that are not its service device and have no entities left."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) in device.identifiers:
            continue
        if er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True):
            continue
        device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


@callback
def async_setup_registry_cleanup(hass: HomeAssistant, entry: ConfigEntry, platforms: Iterable[str]) -> None:
    """Remove registry entries the configuration no longer creates, once a refresh is complete.

    ``platforms`` are the platforms the integration sets up: entries of any other platform are
    left from an older release and are removed too.

    Runs once per setup, after the platforms are set up: at once if the first refresh heard
    from every feed, otherwise after the first refresh that does, never during an outage.
    Existing installs heal on upgrade.
    """
    coordinator: AustralianDisasterWatchCoordinator = entry.runtime_data
    tracker = coordinator.entity_tracker
    set_up = set(platforms)

    def _clean() -> bool:
        if not snapshot_is_complete(coordinator):
            return False
        registry = er.async_get(hass)
        for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registry_entry.domain not in set_up or (
                registry_entry.domain in tracker.created
                and registry_entry.unique_id not in tracker.created[registry_entry.domain]
            ):
                registry.async_remove(registry_entry.entity_id)
        async_remove_stale_devices(hass, entry)
        return True

    if _clean():
        return

    remove_listener: Callable[[], None] | None = None

    @callback
    def _stop() -> None:
        nonlocal remove_listener
        if remove_listener is not None:
            remove_listener()
            remove_listener = None

    @callback
    def _on_update() -> None:
        if _clean():
            _stop()

    remove_listener = coordinator.async_add_listener(_on_update)
    entry.async_on_unload(_stop)
