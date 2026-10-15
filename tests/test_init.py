"""Unit tests for Australian Emergency Hazards integration entry and unload lifecycle."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import async_setup, async_update_listener
from custom_components.ausnz_disaster_watch.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_integration_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and cleanly unloading the integration."""
    # Test top-level async_setup
    assert await async_setup(hass, {}) is True

    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Test update listener triggers coordinator refresh
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    with patch.object(coordinator, "async_refresh", new_callable=AsyncMock) as mock_refresh:
        await async_update_listener(hass, mock_config_entry)
        mock_refresh.assert_called_once()

    # Test unload entry
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data or mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
