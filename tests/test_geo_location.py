"""Unit tests for the Geolocation platform and dynamic entity synchronization."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.geo_location import (
    AustralianDisasterWatchGeolocationEvent,
    async_setup_entry,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard
from homeassistant.core import HomeAssistant


async def test_geolocation_dynamic_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_watch_and_act: CanonicalHazard,
) -> None:
    """Test dynamic adding and clean removal of geolocation entities without orphaned state."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
    ]

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: AustralianDisasterWatchCoordinator = mock_config_entry.runtime_data

    # Verify initial geolocation entity is present
    geo_states = [s for s in hass.states.async_all() if s.entity_id.startswith("geo_location.")]
    assert len(geo_states) == 1
    geo_state = geo_states[0]

    assert geo_state.attributes["latitude"] == mock_hazard_emergency_warning.latitude
    assert geo_state.attributes["longitude"] == mock_hazard_emergency_warning.longitude
    assert geo_state.attributes["source"] == mock_hazard_emergency_warning.source
    assert geo_state.attributes["warning_level"] == "Emergency Warning"
    assert geo_state.attributes["hazard_type"] == "Bushfire"
    assert geo_state.attributes["icon"] == "mdi:fire"

    # Verify attribute payload is small and within SQLite safety limit (< 16 KB)
    attr_bytes = len(str(geo_state.attributes).encode())
    assert attr_bytes < 2048

    # Now simulate an upstream update: emergency warning cleared, new watch and act appeared
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_watch_and_act,
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # The old emergency warning entity must be removed, and new watch and act entity present
    geo_states2 = [s for s in hass.states.async_all() if s.entity_id.startswith("geo_location.")]
    assert len(geo_states2) == 1
    assert geo_states2[0].name == mock_hazard_watch_and_act.title


async def test_geolocation_empty_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test geolocation handles empty feed without errors."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    geo_states = [s for s in hass.states.async_all() if s.entity_id.startswith("geo_location.")]
    assert len(geo_states) == 0


async def test_geolocation_event_fallback(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hazard_advice: CanonicalHazard
) -> None:
    """Test geolocation event fallback when coordinator data is empty or diverse types."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {}
    event = AustralianDisasterWatchGeolocationEvent(coordinator, "missing_id")
    assert event.hazard is None
    assert event.name == "Emergency Incident"

    # When coordinator.data is a dict containing the hazard
    coordinator.data = {"h1": mock_hazard_advice}
    event_dict = AustralianDisasterWatchGeolocationEvent(coordinator, "h1")
    assert event_dict.hazard == mock_hazard_advice

    # When coordinator.data is an unexpected truthy object
    class DummyData:
        pass

    coordinator.data = DummyData()  # type: ignore[assignment]
    event_dummy = AustralianDisasterWatchGeolocationEvent(coordinator, "h1")
    assert event_dummy.hazard is None


async def test_geolocation_sync_with_dict_and_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test _sync_entities handles plain dict and unexpected coordinator data objects."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {"adv_1": mock_hazard_advice}
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
