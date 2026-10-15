"""Unit tests for diagnostics platform."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.australian_disaster_watch.diagnostics import async_get_config_entry_diagnostics
from custom_components.australian_disaster_watch.models import CanonicalHazard
from homeassistant.core import HomeAssistant


async def test_diagnostics_redaction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test diagnostics export redacts geographic coordinates."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_emergency_warning]

    with patch(
        "custom_components.australian_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "entry" in diag
    assert "coordinator" in diag
    assert "hazards" in diag

    # Check redaction in entry data
    assert diag["entry"]["data"]["latitude"] == "**REDACTED**"
    assert diag["entry"]["data"]["longitude"] == "**REDACTED**"

    # Check coordinator info
    assert diag["coordinator"]["state_code"] == "QLD"
    assert diag["coordinator"]["active_hazards_count"] == 1
    assert diag["coordinator"]["has_emergency_warning_nearby"] is True

    # Check redaction in hazards
    assert len(diag["hazards"]) == 1
    assert diag["hazards"][0]["latitude"] == "**REDACTED**"
    assert diag["hazards"][0]["longitude"] == "**REDACTED**"
    assert diag["hazards"][0]["id"] == mock_hazard_emergency_warning.id
