"""Unit tests for Australian Emergency Hazards binary sensors."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import (
    ATTR_HIGHEST_WARNING_LEVEL,
    ATTR_INCIDENT_COUNT,
    ATTR_NEAREST_INCIDENT_DISTANCE,
    ATTR_NEAREST_INCIDENT_TITLE,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardProvenance
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_emergency_warning_nearby_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test emergency_warning_nearby turns on when active threat is present."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
        mock_hazard_advice,
    ]

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify binary_sensor.emergency_warning_nearby is ON
    state = hass.states.get(
        "binary_sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby"
    )
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HIGHEST_WARNING_LEVEL] == "Emergency Warning"
    assert state.attributes[ATTR_INCIDENT_COUNT] == 2
    assert state.attributes[ATTR_NEAREST_INCIDENT_DISTANCE] == 10.9
    assert state.attributes[ATTR_NEAREST_INCIDENT_TITLE] == "Hazard: Road closed to all traffic"

    # Verify active hazards nearby binary sensor is ON
    active_state = hass.states.get(
        "binary_sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_active_hazards_nearby"
    )
    assert active_state is not None
    assert active_state.state == STATE_ON


async def test_binary_sensors_off_when_no_threats(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensors turn off when no hazards exist."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby"
    )
    assert state is not None
    assert state.state == STATE_OFF

    active_state = hass.states.get(
        "binary_sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_active_hazards_nearby"
    )
    assert active_state is not None
    assert active_state.state == STATE_OFF


async def test_issued_warning_uses_provenance_radius_and_coverage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hazard_emergency_warning: CanonicalHazard
) -> None:
    """Observed impact and out-of-range warnings do not activate the new entity."""
    observation = replace(mock_hazard_emergency_warning, provenance=HazardProvenance.OBSERVATION)
    provider = AsyncMock()
    second = type("SecondaryWarningSource", (), {"async_fetch_hazards": AsyncMock(return_value=[])})()
    provider.async_fetch_hazards.return_value = [observation]
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider, second]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    issued = next(
        state.entity_id
        for state in hass.states.async_all("binary_sensor")
        if state.entity_id.endswith("_issued_warning_nearby")
    )
    assert hass.states.get(issued).state == STATE_OFF
    coordinator = mock_config_entry.runtime_data
    warning = replace(observation, provenance=HazardProvenance.ISSUED_WARNING, native_warning_level="Emergency Warning")
    provider.async_fetch_hazards.return_value = [replace(warning, distance_km=1000)]
    await coordinator.async_refresh()
    assert hass.states.get(issued).state == STATE_OFF
    provider.async_fetch_hazards.return_value = [replace(warning, distance_km=coordinator.radius_km)]
    await coordinator.async_refresh()
    assert hass.states.get(issued).state == STATE_ON
    assert hass.states.get(issued).attributes["native_warning_level"] == "Emergency Warning"
    provider.async_fetch_hazards.return_value = []
    second.async_fetch_hazards.side_effect = ProviderUnavailableError("down")
    await coordinator.async_refresh()
    assert hass.states.get(issued).state == STATE_UNKNOWN
