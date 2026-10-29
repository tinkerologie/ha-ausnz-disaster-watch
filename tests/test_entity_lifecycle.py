"""Tests of the entity and device lifecycle: stale registry entries are removed (#92)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import async_remove_config_entry_device
from custom_components.ausnz_disaster_watch.camera import async_setup_entry as async_setup_cameras
from custom_components.ausnz_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_STATE,
    DOMAIN,
    STATE_NZ,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.entity import camera_unique_id
from custom_components.ausnz_disaster_watch.entity_lifecycle import (
    EntityTracker,
    cameras_complete,
    snapshot_is_complete,
    tracks_entities,
)
from custom_components.ausnz_disaster_watch.models import DisasterCameraItem, DisasterCoordinatorData
from custom_components.ausnz_disaster_watch.providers.base import PartialFeedError, ProviderUnavailableError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

PROVIDERS = "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config"


def _provider(name: str = "Feed", *, fails: bool = False) -> AsyncMock:
    provider = AsyncMock()
    type(provider).__name__ = name
    if fails:
        provider.async_fetch_hazards.side_effect = ProviderUnavailableError("down")
    else:
        provider.async_fetch_hazards.return_value = []
    return provider


def _entry(entry: MockConfigEntry, **data: Any) -> MockConfigEntry:
    """Return a copy of ``entry`` with ``data`` changed."""
    return MockConfigEntry(domain=DOMAIN, title=entry.title, data={**entry.data, **data}, unique_id=entry.unique_id)


def _register(hass: HomeAssistant, entry: MockConfigEntry, domain: str, key: str, **kwargs: Any) -> str:
    """Create a registry entry of ``entry`` for entity key ``key``; return its entity ID."""
    return (
        er.async_get(hass)
        .async_get_or_create(domain, DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry, **kwargs)
        .entity_id
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, providers: list[Any]) -> None:
    with patch(PROVIDERS, return_value=providers):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


# --- configuration-driven entities -----------------------------------------------------------


async def test_setup_removes_entities_the_configuration_no_longer_creates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Entities of features switched off, of another state and of old versions are removed; the rest stay."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    stale = [
        _register(hass, entry, "sensor", "satellite_hotspots_nearby"),  # national feed switched off
        _register(hass, entry, "binary_sensor", "tsunami_warning"),  # tsunami switched off
        _register(hass, entry, "sensor", "fire_season"),  # an NZ-only sensor on a QLD entry
        _register(hass, entry, "sensor", "emergency_broadcaster"),  # broadcaster switched off
        _register(hass, entry, "sensor", "renamed_in_an_old_release"),
        _register(hass, entry, "switch", "platform_no_longer_set_up"),
    ]
    disabled = _register(hass, entry, "sensor", "active_hazards_count", disabled_by=er.RegistryEntryDisabler.USER)
    kept = _register(hass, entry, "binary_sensor", "total_fire_ban")
    camera = _register(hass, entry, "camera", "camera_council_cam")  # cameras follow their own data

    await _setup(hass, entry, [_provider()])

    for entity_id in stale:
        assert registry.async_get(entity_id) is None, entity_id
    for entity_id in (disabled, kept):
        assert registry.async_get(entity_id) is not None, entity_id
    assert registry.async_get(camera) is not None
    assert registry.async_get(disabled).disabled_by is er.RegistryEntryDisabler.USER


async def test_state_change_to_nz_replaces_total_fire_ban_with_fire_season(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After reconfiguring an entry from an Australian state to NZ, the total fire ban sensor goes."""
    entry = _entry(
        mock_config_entry,
        **{CONF_STATE: STATE_NZ, CONF_LATITUDE: -41.29, CONF_LONGITUDE: 174.78, CONF_COUNCIL_DASHBOARD_URL: None},
    )
    entry.add_to_hass(hass)
    total_fire_ban = _register(hass, entry, "binary_sensor", "total_fire_ban")

    await _setup(hass, entry, [_provider()])

    registry = er.async_get(hass)
    assert registry.async_get(total_fire_ban) is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_fire_season") is not None


async def test_cleanup_waits_for_a_complete_refresh(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """During a feed outage nothing is removed; the first refresh that hears from every feed cleans once."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    orphan = _register(hass, entry, "sensor", "renamed_in_an_old_release")
    failing = _provider("Down", fails=True)

    await _setup(hass, entry, [_provider("Up"), failing])
    coordinator: AustralianDisasterWatchCoordinator = entry.runtime_data
    assert coordinator.data.feeds_failed == ["Down"]
    assert registry.async_get(orphan) is not None

    failing.async_fetch_hazards.side_effect = None
    failing.async_fetch_hazards.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert registry.async_get(orphan) is None

    # The cleanup runs once: an entry created afterwards (by anyone) is left alone
    late = _register(hass, entry, "sensor", "created_later")
    await coordinator.async_refresh()
    assert registry.async_get(late) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_before_a_complete_refresh(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """An entry unloaded during an outage stops waiting for the cleanup and removes nothing."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    orphan = _register(hass, entry, "sensor", "renamed_in_an_old_release")
    await _setup(hass, entry, [_provider("Up"), _provider("Down", fails=True)])
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(orphan) is not None


async def test_platform_that_fails_setup_keeps_its_entries(hass: HomeAssistant) -> None:
    """Only platforms that finished setting up are cleaned, so a failed one loses nothing."""
    tracker = EntityTracker()
    entry = MagicMock()
    entry.runtime_data.entity_tracker = tracker
    entity = MagicMock(unique_id="id_1")
    unnamed = MagicMock(unique_id=None)

    @tracks_entities("sensor")
    async def good(hass: HomeAssistant, entry: Any, add: Any) -> None:
        add(entity for entity in (entity, unnamed))

    @tracks_entities("binary_sensor")
    async def bad(hass: HomeAssistant, entry: Any, add: Any) -> None:
        add([entity])
        raise RuntimeError("boom")

    add = MagicMock()
    await good(hass, entry, add)
    add.assert_called_once_with([entity, unnamed], False)
    with pytest.raises(RuntimeError):
        await bad(hass, entry, add)
    assert tracker.created == {"sensor": {"id_1"}}


async def test_tracking_skips_a_stand_in_coordinator(hass: HomeAssistant) -> None:
    """Without an EntityTracker (a stand-in coordinator) the platform setup runs unchanged."""
    entry = MagicMock()
    entry.runtime_data = object()
    add = MagicMock()

    @tracks_entities("sensor")
    async def setup(hass: HomeAssistant, entry: Any, add_entities: Any) -> None:
        assert add_entities is add

    await setup(hass, entry, add)


# --- devices ------------------------------------------------------------------------------------


async def test_stale_devices_are_removed(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Devices of the entry other than its service device are removed once they have no entities."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    empty = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "old_device")})
    in_use = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "in_use")})
    # A camera follows its own data, so the entity cleanup leaves it on this device
    er.async_get(hass).async_get_or_create(
        "camera", DOMAIN, f"{entry.entry_id}_camera_x", config_entry=entry, device_id=in_use.id
    )

    await _setup(hass, entry, [_provider()])

    assert devices.async_get(empty.id) is None
    assert devices.async_get(in_use.id) is not None
    (service,) = (
        device
        for device in dr.async_entries_for_config_entry(devices, entry.entry_id)
        if (DOMAIN, entry.entry_id) in device.identifiers
    )
    assert not await async_remove_config_entry_device(hass, entry, service)
    assert await async_remove_config_entry_device(hass, entry, in_use)


# --- completeness ------------------------------------------------------------------------------


def test_snapshot_and_camera_completeness() -> None:
    """A snapshot is complete only after a successful refresh with no failed feed or camera source."""
    coordinator = MagicMock(last_update_success=True, data=DisasterCoordinatorData())
    assert snapshot_is_complete(coordinator)
    assert cameras_complete(coordinator)
    coordinator.data = DisasterCoordinatorData(feeds_failed=["QLD"], cameras_failed=["Cams"])
    assert not snapshot_is_complete(coordinator)
    assert not cameras_complete(coordinator)
    coordinator.data = None
    assert not cameras_complete(coordinator)
    coordinator.data = DisasterCoordinatorData()
    coordinator.last_update_success = False
    assert not snapshot_is_complete(coordinator)
    assert not cameras_complete(coordinator)


async def test_coordinator_records_failed_camera_sources(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A failed camera source is listed; a partial failure keeps the cameras that did arrive."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    ok, partial, down = _provider("Ok"), _provider("Partial"), _provider("Down")
    ok.async_fetch_cameras.return_value = [_camera("a")]
    partial.async_fetch_cameras.side_effect = PartialFeedError("one network down", [_camera("b"), "junk"])
    down.async_fetch_cameras.side_effect = ProviderUnavailableError("down")
    coordinator.providers = [ok, partial, down]
    await coordinator.async_refresh()
    assert [camera.id for camera in coordinator.cameras] == ["a", "b"]
    assert sorted(coordinator.data.cameras_failed) == ["Down", "Partial"]
    assert not cameras_complete(coordinator)


# --- cameras -----------------------------------------------------------------------------------


def _camera(camera_id: str, name: str | None = None) -> DisasterCameraItem:
    return DisasterCameraItem(id=camera_id, name=name or camera_id, image_url=f"https://example.com/{camera_id}.jpg")


async def _camera_platform(
    hass: HomeAssistant, entry: MockConfigEntry, data: DisasterCoordinatorData
) -> tuple[AustralianDisasterWatchCoordinator, MagicMock]:
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    coordinator.data = data
    entry.runtime_data = coordinator
    add = MagicMock()
    await async_setup_cameras(hass, entry, add)
    return coordinator, add


async def test_setup_removes_registry_entries_of_cameras_that_went(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Cameras delisted or re-keyed while Home Assistant was stopped lose their registry entries (#92)."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    gone = _register(hass, entry, "camera", "camera_gateway_bridge_north", suggested_object_id="gateway_bridge_north")
    current = _register(hass, entry, "camera", "camera_toowong", suggested_object_id="toowong")
    geo = _register(hass, entry, "geo_location", "QLD_1")

    _, add = await _camera_platform(hass, entry, DisasterCoordinatorData(cameras=[_camera("toowong")]))

    assert registry.async_get(gone) is None
    assert registry.async_get(current) is not None  # reused by the entity being added
    assert registry.async_get(geo) is not None
    (entity,) = add.call_args[0][0]
    assert entity.unique_id == camera_unique_id(entry.entry_id, "toowong")


async def test_cameras_are_kept_while_a_camera_source_is_down(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A camera missing because its source failed stays (unavailable); the next complete refresh removes it."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    stale = _register(hass, entry, "camera", "camera_old")
    coordinator, add = await _camera_platform(
        hass, entry, DisasterCoordinatorData(cameras=[_camera("a"), _camera("b")])
    )
    a, b = sorted(add.call_args[0][0], key=lambda entity: entity.camera_id)
    for entity in (a, b):
        entity.hass = hass
        entity.entity_id = _register(hass, entry, "camera", f"camera_{entity.camera_id}")
        entity.async_remove = AsyncMock()

    # Camera "b" is missing during a camera source outage: kept, unavailable
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a")], cameras_failed=["Cams"]))
    await hass.async_block_till_done()
    b.async_remove.assert_not_awaited()
    assert registry.async_get(b.entity_id) is not None
    assert not b.available
    assert registry.async_get(stale) is None  # the setup refresh was complete

    # The source answers again without "b": the entity and its registry entry go
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a")]))
    await hass.async_block_till_done()
    b.async_remove.assert_awaited_once_with(force_remove=True)
    assert registry.async_get(b.entity_id) is None
    assert registry.async_get(a.entity_id) is not None

    # "b" comes back: it is re-created
    add.reset_mock()
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a"), _camera("b")]))
    (returned,) = add.call_args[0][0]
    assert returned.camera_id == "b"


async def test_camera_cleanup_waits_for_a_complete_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A setup refresh with a camera source down removes no registry entry; the first complete one does."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    stale = _register(hass, entry, "camera", "camera_old")
    coordinator, _ = await _camera_platform(hass, entry, DisasterCoordinatorData(cameras_failed=["Cams"]))
    assert registry.async_get(stale) is not None
    coordinator.async_set_updated_data(DisasterCoordinatorData())
    assert registry.async_get(stale) is None


async def test_several_cameras_leaving_in_one_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Removing several cameras at once does not fail the listener.

    Tasks start eagerly, so a removal that finishes without suspending re-syncs while the
    first sync is still walking the cameras that went (KeyError: 'camera_…').
    """
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    coordinator, add = await _camera_platform(
        hass, entry, DisasterCoordinatorData(cameras=[_camera("a"), _camera("b"), _camera("c"), _camera("d")])
    )
    entities = {entity.camera_id: entity for entity in add.call_args[0][0]}
    for entity in entities.values():
        entity.hass = hass
        entity.entity_id = _register(hass, entry, "camera", f"camera_{entity.camera_id}")
        entity.async_remove = AsyncMock()

    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a")]))
    await hass.async_block_till_done()

    assert "Unexpected error updating listener" not in caplog.text
    for camera_id in ("b", "c", "d"):
        entities[camera_id].async_remove.assert_awaited_once_with(force_remove=True)
        assert registry.async_get(entities[camera_id].entity_id) is None
    entities["a"].async_remove.assert_not_awaited()

    # They can come back
    add.reset_mock()
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a"), _camera("c")]))
    (returned,) = add.call_args[0][0]
    assert returned.camera_id == "c"


async def test_camera_entity_id_suffix_is_dropped_once_free(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A camera left with a "_2" entity ID by an old duplicate gets its plain ID back (#125).

    Only Home Assistant's own collision suffix is dropped: a number that belongs to the
    camera's name, an ID a user chose, and an ID still taken stay as they are.
    """
    entry = mock_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    def _named(key: str, name: str) -> str:
        return _register(hass, entry, "camera", key, object_id_base=name)

    old_copy = _named("camera_council_creek", "Creek")
    suffixed = _named("camera_flood_255", "Creek")
    assert (old_copy, suffixed) == ("camera.creek", "camera.creek_2")
    postcode = _named("camera_flood_251", "Road 4510")
    _named("camera_bridge", "Bridge")
    taken = _named("camera_flood_256", "Bridge")
    chosen = _named("camera_flood_257", "Weir")
    registry.async_update_entity(chosen, new_entity_id="camera.my_weir_2")

    # The council copy of the creek camera went; the network copy stays
    await _camera_platform(
        hass,
        entry,
        DisasterCoordinatorData(
            cameras=[_camera(key) for key in ("flood_255", "flood_251", "bridge", "flood_256", "flood_257")]
        ),
    )

    renamed = registry.async_get("camera.creek")
    assert renamed is not None
    assert renamed.unique_id == camera_unique_id(entry.entry_id, "flood_255")
    assert registry.async_get(suffixed) is None
    assert postcode == "camera.road_4510"
    assert registry.async_get(postcode) is not None
    assert taken == "camera.bridge_2"
    assert registry.async_get(taken) is not None  # camera.bridge is still in use
    assert registry.async_get("camera.my_weir_2") is not None
