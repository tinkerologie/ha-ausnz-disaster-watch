"""Unit tests for the integration's config entry lifecycle."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import async_setup
from custom_components.ausnz_disaster_watch.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def mock_providers() -> Generator[AsyncMock]:
    """Patch provider construction with a single provider that returns no hazards."""
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[provider],
    ):
        yield provider


async def test_integration_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
) -> None:
    """Set up stores the coordinator in runtime_data, registers no update listener, and unloads cleanly."""
    assert await async_setup(hass, {}) is True

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, AustralianDisasterWatchCoordinator)
    assert mock_config_entry.runtime_data.config_entry is mock_config_entry
    # Option/reconfigure changes are applied by a reload owned by the flows (#15).
    assert mock_config_entry.update_listeners == []

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_flow_reloads_and_applies_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
) -> None:
    """Submitting the options flow reloads the entry so the new radius takes effect."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    first_coordinator = mock_config_entry.runtime_data
    assert first_coordinator.radius_km == 50.0

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RADIUS: 120,
            "override_emergency": True,
            "exclude_hazard_reduction": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not first_coordinator
    assert mock_config_entry.runtime_data.radius_km == 120.0


async def test_reconfigure_reloads_without_listener_deprecation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reconfigure reloads once and no 'update listener ... reload' deprecation is reported (breaks in 2026.12)."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "state": "QLD",
            "location_name": "City of Moreton Bay",
            CONF_LATITUDE: -27.30,
            CONF_LONGITUDE: 153.00,
            CONF_RADIUS: 75,
            "override_emergency": True,
            "exclude_hazard_reduction": True,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.latitude == -27.30
    assert "has an update listener and should use it for scheduling a reload" not in caplog.text
