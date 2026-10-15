"""The Australia and New Zealand Disaster Watch integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator
from .frontend import async_register_frontend

PLATFORMS: list[Platform] = [
    Platform.GEO_LOCATION,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CAMERA,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AusNZDisasterWatchConfigEntry = ConfigEntry[AustralianDisasterWatchCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Australia and New Zealand Disaster Watch component."""
    # Register dashboard frontend cards
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AusNZDisasterWatchConfigEntry) -> bool:
    """Set up Australia and New Zealand Disaster Watch from a config entry.

    Option and reconfigure changes are applied by a full reload, owned by the flows
    themselves (OptionsFlowWithReload and async_update_reload_and_abort), so no update
    listener is registered here.
    """
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AusNZDisasterWatchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
