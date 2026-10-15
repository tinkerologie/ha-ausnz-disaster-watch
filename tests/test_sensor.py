"""Unit tests for Australian Emergency Hazards sensor platform."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aus_emergency_hazards.models import CanonicalHazard
from homeassistant.core import HomeAssistant


async def test_sensors_telemetry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test distance, active count, highest severity and title sensors."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
        mock_hazard_advice,
    ]

    with patch(
        "custom_components.aus_emergency_hazards.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australian_emergency_hazards_qld_city_of_moreton_bay"

    # Nearest Distance sensor: closest is mock_hazard_advice (~10.9 km)
    dist_state = hass.states.get(f"{prefix}_nearest_hazard_distance")
    assert dist_state is not None
    assert float(dist_state.state) == 10.9
    assert dist_state.attributes["unit_of_measurement"] == "km"
    assert dist_state.attributes["title"] == "Hazard: Road closed to all traffic"

    # Active count sensor: 2
    count_state = hass.states.get(f"{prefix}_active_hazards_count")
    assert count_state is not None
    assert int(count_state.state) == 2
    assert count_state.attributes["unit_of_measurement"] == "hazards"

    # Highest warning level sensor: "Emergency Warning"
    level_state = hass.states.get(f"{prefix}_highest_warning_level")
    assert level_state is not None
    assert level_state.state == "Emergency Warning"

    # Nearest hazard title sensor
    title_state = hass.states.get(f"{prefix}_nearest_hazard_title")
    assert title_state is not None
    assert title_state.state == "Hazard: Road closed to all traffic"


async def test_sensors_clear_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors report clean default values when no hazards exist."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []

    with patch(
        "custom_components.aus_emergency_hazards.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australian_emergency_hazards_qld_city_of_moreton_bay"

    dist_state = hass.states.get(f"{prefix}_nearest_hazard_distance")
    assert dist_state is not None
    assert dist_state.state in {"unknown", "unavailable"} or dist_state.state is None

    count_state = hass.states.get(f"{prefix}_active_hazards_count")
    assert count_state is not None
    assert int(count_state.state) == 0

    level_state = hass.states.get(f"{prefix}_highest_warning_level")
    assert level_state is not None
    assert level_state.state == "All Clear"
