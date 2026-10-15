"""Unit and integration tests for EmergencyDataCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aus_emergency_hazards.const import DEFAULT_SCAN_INTERVAL, THREAT_SCAN_INTERVAL
from custom_components.aus_emergency_hazards.coordinator import EmergencyDataCoordinator, calculate_haversine_distance
from custom_components.aus_emergency_hazards.models import CanonicalHazard, WarningLevel
from homeassistant.core import HomeAssistant


def test_haversine_distance_accuracy() -> None:
    """Test Haversine distance calculation against known Australian coordinates."""
    # Brisbane (-27.4698, 153.0251) to Gold Coast (-28.0167, 153.4000) ~ 71-72 km
    dist = calculate_haversine_distance(
        -27.4698,
        153.0251,
        -28.0167,
        153.4000,
    )
    assert 70.0 < dist < 73.0

    # Distance to same point must be 0
    assert calculate_haversine_distance(-27.2657, 152.9818, -27.2657, 152.9818) == 0.0


async def test_coordinator_filtering_and_override(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_watch_and_act: CanonicalHazard,
    mock_hazard_advice: CanonicalHazard,
    mock_hazard_hazard_reduction: CanonicalHazard,
    mock_hazard_distant_emergency_warning: CanonicalHazard,
) -> None:
    """Test spatial filtering, hazard reduction exclusion, and emergency warning override."""
    mock_config_entry.add_to_hass(hass)
    coordinator = EmergencyDataCoordinator(hass, mock_config_entry)

    # Mock provider returning 5 hazards:
    # 1. Nearby emergency warning (~21 km) -> Keep
    # 2. Nearby watch and act (~18 km) -> Keep
    # 3. Nearby advice (~10 km) -> Keep
    # 4. Nearby planned burn (~30 km) -> Exclude (exclude_hazard_reduction is True)
    # 5. Distant emergency warning (~230 km) -> Keep because override_emergency is True!
    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
        mock_hazard_watch_and_act,
        mock_hazard_advice,
        mock_hazard_hazard_reduction,
        mock_hazard_distant_emergency_warning,
    ]
    coordinator.providers = [mock_provider]

    await coordinator.async_refresh()
    data = coordinator.data

    # Verify hazard reduction burn was dropped
    assert mock_hazard_hazard_reduction.id not in data

    # Verify nearby hazards are present
    assert mock_hazard_emergency_warning.id in data
    assert mock_hazard_watch_and_act.id in data
    assert mock_hazard_advice.id in data

    # Verify distant emergency warning is kept due to override
    assert mock_hazard_distant_emergency_warning.id in data
    assert len(data) == 4

    # Verify dynamic poll interval shifted to threat mode (60 seconds)
    assert coordinator.update_interval == timedelta(seconds=THREAT_SCAN_INTERVAL)
    assert coordinator.has_emergency_warning_nearby is True
    assert coordinator.highest_warning_level == WarningLevel.EMERGENCY_WARNING
    assert coordinator.nearest_hazard is not None
    assert coordinator.nearest_hazard.id == mock_hazard_advice.id


async def test_coordinator_normal_polling_when_no_threat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test coordinator reverts to standard 5 min polling when only Advice or Information is present."""
    mock_config_entry.add_to_hass(hass)
    coordinator = EmergencyDataCoordinator(hass, mock_config_entry)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_advice]
    coordinator.providers = [mock_provider]

    await coordinator.async_refresh()
    data = coordinator.data
    assert len(data) == 1
    assert coordinator.has_emergency_warning_nearby is False
    assert coordinator.highest_warning_level == WarningLevel.ADVICE
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)


async def test_coordinator_options_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating coordinator options dynamically."""
    mock_config_entry.add_to_hass(hass)
    coordinator = EmergencyDataCoordinator(hass, mock_config_entry)
    assert coordinator.radius_km == 50.0

    # Simulate options update to 100 km radius
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={"radius": 100},
    )
    coordinator.update_options()
    assert coordinator.radius_km == 100.0
