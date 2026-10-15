"""Unit tests for the Geolocation platform and dynamic entity synchronization."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.geo_location import (
    MAX_HAZARD_SLUG_LENGTH,
    AustralianDisasterWatchGeolocationEvent,
    async_setup_entry,
    current_hazards,
    hazard_object_id,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

EMERGENCY_ENTITY_ID = "geo_location.ausnz_disaster_watch_qld_qfd_warn_101"
WATCH_ENTITY_ID = "geo_location.ausnz_disaster_watch_qld_qfd_warn_102"


async def _setup_with_hazards(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hazards: list[CanonicalHazard],
) -> AsyncMock:
    """Set up the entry with a single mocked provider returning ``hazards``."""
    entry.add_to_hass(hass)
    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = hazards
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return mock_provider


def _geo_states(hass: HomeAssistant) -> list:
    return [s for s in hass.states.async_all() if s.entity_id.startswith("geo_location.")]


async def test_geolocation_dynamic_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_watch_and_act: CanonicalHazard,
) -> None:
    """Test adding and clean removal of geolocation entities without orphaned state or registry entries."""
    mock_provider = await _setup_with_hazards(hass, mock_config_entry, [mock_hazard_emergency_warning])
    coordinator: AustralianDisasterWatchCoordinator = mock_config_entry.runtime_data
    entity_registry = er.async_get(hass)

    geo_states = _geo_states(hass)
    assert len(geo_states) == 1
    geo_state = geo_states[0]

    # Short entity ID from the hazard ID, headline as the friendly name (#18)
    assert geo_state.entity_id == EMERGENCY_ENTITY_ID
    assert geo_state.name == mock_hazard_emergency_warning.title
    assert geo_state.attributes["latitude"] == mock_hazard_emergency_warning.latitude
    assert geo_state.attributes["longitude"] == mock_hazard_emergency_warning.longitude
    # Constant integration-level source; the agency moves to an attribute (#18)
    assert geo_state.attributes["source"] == DOMAIN
    assert geo_state.attributes["agency"] == mock_hazard_emergency_warning.source
    assert geo_state.attributes["integration"] == DOMAIN
    assert geo_state.attributes["warning_level"] == "Emergency Warning"
    assert geo_state.attributes["hazard_type"] == "Bushfire"
    assert geo_state.attributes["icon"] == "mdi:fire"
    # Cards scope incidents per config entry through these attributes (#26).
    assert geo_state.attributes["integration"] == "ausnz_disaster_watch"
    assert geo_state.attributes["entry_id"] == mock_config_entry.entry_id

    registry_entry = entity_registry.async_get(EMERGENCY_ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.unique_id == f"{mock_config_entry.entry_id}_{mock_hazard_emergency_warning.id}"

    # Verify attribute payload is small and within SQLite safety limit (< 16 KB)
    attr_bytes = len(str(geo_state.attributes).encode())
    assert attr_bytes < 2048

    # A refresh with the same hazard keeps the entity ID and picks up headline changes
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning.model_copy(
            update={"title": "EMERGENCY WARNING - Bushfire at Caboolture (updated)"}
        )
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    geo_states = _geo_states(hass)
    assert [s.entity_id for s in geo_states] == [EMERGENCY_ENTITY_ID]
    assert geo_states[0].name == "EMERGENCY WARNING - Bushfire at Caboolture (updated)"

    # Upstream update: emergency warning cleared, new watch and act appeared
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_watch_and_act]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    geo_states2 = _geo_states(hass)
    assert [s.entity_id for s in geo_states2] == [WATCH_ENTITY_ID]
    assert geo_states2[0].name == mock_hazard_watch_and_act.title
    assert hass.states.get(EMERGENCY_ENTITY_ID) is None
    # The registry entry of the ended event is removed with it
    assert entity_registry.async_get(EMERGENCY_ENTITY_ID) is None
    assert entity_registry.async_get(WATCH_ENTITY_ID) is not None


async def test_geolocation_unload_and_reload_cleans_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test an event that ends while the entry is unloaded is cleaned up on the next setup."""
    mock_provider = await _setup_with_hazards(hass, mock_config_entry, [mock_hazard_emergency_warning])
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(EMERGENCY_ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(EMERGENCY_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"

    mock_provider.async_fetch_hazards.return_value = []
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(EMERGENCY_ENTITY_ID) is None
    assert hass.states.get(EMERGENCY_ENTITY_ID) is None


async def test_geolocation_setup_cleans_stale_registry_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test registry entries of events that ended while HA was stopped are removed; active ones are reused."""
    mock_config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    stale = entity_registry.async_get_or_create(
        "geo_location",
        DOMAIN,
        f"{mock_config_entry.entry_id}_QLD_QFD_GONE",
        suggested_object_id="ausnz_disaster_watch_qld_qfd_gone",
        config_entry=mock_config_entry,
    )
    active = entity_registry.async_get_or_create(
        "geo_location",
        DOMAIN,
        f"{mock_config_entry.entry_id}_{mock_hazard_emergency_warning.id}",
        suggested_object_id="ausnz_disaster_watch_qld_qfd_warn_101",
        config_entry=mock_config_entry,
    )
    other_platform = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_keep_me",
        config_entry=mock_config_entry,
    )

    await _setup_with_hazards(hass, mock_config_entry, [mock_hazard_emergency_warning])

    assert entity_registry.async_get(stale.entity_id) is None
    assert entity_registry.async_get(active.entity_id) is not None
    assert entity_registry.async_get(other_platform.entity_id) is not None
    assert hass.states.get(active.entity_id) is not None
    assert hass.states.get(stale.entity_id) is None


async def test_geolocation_empty_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test geolocation handles empty feed without errors."""
    await _setup_with_hazards(hass, mock_config_entry, [])
    assert len(_geo_states(hass)) == 0


def test_hazard_object_id() -> None:
    """Test entity object IDs are short, namespaced and stable."""
    assert hazard_object_id("QLD_QFD_WARN_101") == "ausnz_disaster_watch_qld_qfd_warn_101"
    assert hazard_object_id("nz_quake/2026p123456") == "ausnz_disaster_watch_nz_quake_2026p123456"
    assert hazard_object_id("!!!") == "ausnz_disaster_watch_unknown"

    prefix = "BOM_IDQ21035_" + "severe_thunderstorm_warning_for_central_highlands_" * 3
    long_a = hazard_object_id(prefix + "A")
    long_b = hazard_object_id(prefix + "B")
    assert long_a != long_b
    assert long_a == hazard_object_id(prefix + "A")
    for object_id in (long_a, long_b):
        slug = object_id.removeprefix("ausnz_disaster_watch_")
        assert len(slug) <= MAX_HAZARD_SLUG_LENGTH
        assert slug.startswith("bom_idq21035_severe_thunderstorm")


async def test_geolocation_long_hazard_ids_get_distinct_entity_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test two long hazard IDs with the same prefix produce two distinct, short entity IDs."""
    prefix = "BOM_" + "x" * 80
    hazards = [
        mock_hazard_emergency_warning.model_copy(update={"id": prefix + "1"}),
        mock_hazard_emergency_warning.model_copy(update={"id": prefix + "2"}),
    ]
    await _setup_with_hazards(hass, mock_config_entry, hazards)

    entity_ids = sorted(s.entity_id for s in _geo_states(hass))
    assert len(entity_ids) == 2
    assert entity_ids[0] != entity_ids[1]
    assert all(len(eid) <= len("geo_location.ausnz_disaster_watch_") + MAX_HAZARD_SLUG_LENGTH for eid in entity_ids)


async def test_geolocation_slug_collisions_get_distinct_entity_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test hazard IDs that slugify alike still get distinct entity IDs (the registry suffixes the second)."""
    hazards = [
        mock_hazard_emergency_warning.model_copy(update={"id": "QLD-1"}),
        mock_hazard_emergency_warning.model_copy(update={"id": "QLD_1"}),
    ]
    await _setup_with_hazards(hass, mock_config_entry, hazards)

    entity_ids = sorted(s.entity_id for s in _geo_states(hass))
    assert entity_ids == [
        "geo_location.ausnz_disaster_watch_qld_1",
        "geo_location.ausnz_disaster_watch_qld_1_2",
    ]


async def test_geolocation_event_keeps_last_known_hazard(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test an event keeps its last known values once the hazard leaves coordinator data."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {"h1": mock_hazard_advice}  # type: ignore[assignment]
    event = AustralianDisasterWatchGeolocationEvent(coordinator, "entry", "h1", mock_hazard_advice)
    event.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    assert event.unique_id == "entry_h1"
    assert event.entity_id == "geo_location.ausnz_disaster_watch_h1"
    assert event.source == DOMAIN
    assert event.hazard is mock_hazard_advice

    coordinator.data = {}  # type: ignore[assignment]
    event._handle_coordinator_update()

    assert event.hazard is mock_hazard_advice
    assert event.name == mock_hazard_advice.title
    assert event.latitude == mock_hazard_advice.latitude
    assert event.longitude == mock_hazard_advice.longitude
    assert event.extra_state_attributes["agency"] == mock_hazard_advice.source
    assert "source" not in event.extra_state_attributes


async def test_geolocation_event_without_distance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test distance is None when the hazard has no distance."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    event = AustralianDisasterWatchGeolocationEvent(
        coordinator, "entry", "h1", mock_hazard_advice.model_copy(update={"distance_km": None})
    )
    assert event.distance is None


async def test_current_hazards_handles_data_shapes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test hazard lookup accepts plain dicts and composite data, and ignores anything else."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    coordinator.data = None  # type: ignore[assignment]
    assert current_hazards(coordinator) == {}

    coordinator.data = {"h1": mock_hazard_advice, "junk": "not a hazard"}  # type: ignore[assignment]
    assert current_hazards(coordinator) == {"h1": mock_hazard_advice}

    class NonHazardData:
        pass

    coordinator.data = NonHazardData()  # type: ignore[assignment]
    assert current_hazards(coordinator) == {}


async def test_geolocation_sync_with_dict_and_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test _sync_entities handles plain dict and unexpected coordinator data objects."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {"adv_1": mock_hazard_advice}  # type: ignore[assignment]
    mock_config_entry.runtime_data = coordinator

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert async_add_entities.called

    # Test with object that has no hazards attribute
    class NonHazardData:
        pass

    coordinator.data = NonHazardData()  # type: ignore[assignment]
    async_add_entities.reset_mock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert not async_add_entities.called

    # Test with coordinator.data = None
    coordinator.data = None  # type: ignore[assignment]
    async_add_entities.reset_mock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert not async_add_entities.called


async def test_geolocation_expiry_without_registry_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test expired events without a registry entry are removed directly, and unadded ones are skipped."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {"adv_1": mock_hazard_advice, "adv_2": mock_hazard_advice}  # type: ignore[assignment]
    mock_config_entry.runtime_data = coordinator

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    added, never_added = async_add_entities.call_args.args[0]
    added.hass = hass
    added.async_remove = AsyncMock()  # type: ignore[method-assign]
    never_added.async_remove = AsyncMock()  # type: ignore[method-assign]

    coordinator.data = {}  # type: ignore[assignment]
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    added.async_remove.assert_awaited_once_with(force_remove=True)
    never_added.async_remove.assert_not_called()


async def test_geolocation_keeps_entities_during_partial_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_watch_and_act: CanonicalHazard,
) -> None:
    """A hazard missing from a refresh where some feed failed is not removed (#16)."""
    mock_provider = await _setup_with_hazards(
        hass, mock_config_entry, [mock_hazard_emergency_warning, mock_hazard_watch_and_act]
    )
    coordinator: AustralianDisasterWatchCoordinator = mock_config_entry.runtime_data
    entity_registry = er.async_get(hass)
    assert {s.entity_id for s in _geo_states(hass)} == {EMERGENCY_ENTITY_ID, WATCH_ENTITY_ID}

    # Snapshot that is missing a hazard while another feed is down: nothing is removed
    partial = coordinator.data.model_copy(
        update={"hazards": {mock_hazard_watch_and_act.id: mock_hazard_watch_and_act}, "feeds_failed": ["Other feed"]}
    )
    coordinator.async_set_updated_data(partial)
    await hass.async_block_till_done()
    assert entity_registry.async_get(EMERGENCY_ENTITY_ID) is not None

    # A complete refresh confirms the hazard ended
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_watch_and_act]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_registry.async_get(EMERGENCY_ENTITY_ID) is None
    assert entity_registry.async_get(WATCH_ENTITY_ID) is not None


async def test_geolocation_setup_keeps_registry_during_partial_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Setup does not clean registry entries when the first refresh was incomplete."""
    mock_config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    stale = entity_registry.async_get_or_create(
        "geo_location", DOMAIN, f"{mock_config_entry.entry_id}_old_hazard", config_entry=mock_config_entry
    )
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = MagicMock(hazards={}, feeds_failed=["QLD"])
    mock_config_entry.runtime_data = coordinator
    await async_setup_entry(hass, mock_config_entry, MagicMock())
    assert entity_registry.async_get(stale.entity_id) is not None
