"""Unit tests for Australian Emergency Hazards sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.australian_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.australian_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from custom_components.australian_disaster_watch.sensor import HighestWarningLevelSensor
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
        "custom_components.australian_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australian_disaster_watch_qld_city_of_moreton_bay"

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
        "custom_components.australian_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australian_disaster_watch_qld_city_of_moreton_bay"

    dist_state = hass.states.get(f"{prefix}_nearest_hazard_distance")
    assert dist_state is not None
    assert dist_state.state in {"unknown", "unavailable"} or dist_state.state is None

    count_state = hass.states.get(f"{prefix}_active_hazards_count")
    assert count_state is not None
    assert int(count_state.state) == 0

    level_state = hass.states.get(f"{prefix}_highest_warning_level")
    assert level_state is not None
    assert level_state.state == "All Clear"


async def test_highest_warning_level_sensor_icons(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test icon selection for different warning levels."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    sensor = HighestWarningLevelSensor(coordinator)

    coordinator.data = {}
    assert sensor.icon == "mdi:shield-check"

    hazard_advice = CanonicalHazard(
        id="1",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"1": hazard_advice}
    assert sensor.icon == "mdi:information"

    hazard_wa = CanonicalHazard(
        id="2",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.WATCH_AND_ACT,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"2": hazard_wa}
    assert sensor.icon == "mdi:alert"

    hazard_ew = CanonicalHazard(
        id="3",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"3": hazard_ew}
    assert sensor.icon == "mdi:alert-octagon"
