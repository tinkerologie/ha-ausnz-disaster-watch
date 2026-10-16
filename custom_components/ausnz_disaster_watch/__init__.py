"""The Australia and New Zealand Disaster Watch integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_DAM_STORAGES,
    CONF_LOCATION_MODE,
    CONF_RIVER_GAUGES,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_HOME,
    PRESET_COUNCIL_DASHBOARDS,
    STATE_QLD,
)
from .coordinator import AustralianDisasterWatchCoordinator, nearest_council_dashboard
from .dam_coordinator import DamStorageCoordinator
from .dams import sites_from_options as storages_from_options
from .forecast_coordinator import async_setup_forecasts
from .frontend import async_register_frontend, async_unregister_frontend
from .river_coordinator import RiverGaugeCoordinator
from .rivers import sites_from_options

_LOGGER = logging.getLogger(__name__)

# Camera IDs of the four hard-coded Brisbane cameras earlier releases created (#19)
LEGACY_CAMERA_IDS = (
    "qld_goodna_ipswich_mwy",
    "qld_dinmore_ipswich_mwy",
    "qld_metro_1218",
    "qld_bruce_hwy_caboolture",
)

PLATFORMS: list[Platform] = [
    Platform.GEO_LOCATION,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CAMERA,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AusNZDisasterWatchConfigEntry = ConfigEntry[AustralianDisasterWatchCoordinator]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an entry to the current config version.

    1.1 -> 1.2 (#19): QLD home-zone entries were always given the Moreton Bay dashboard;
    they get the nearest preset dashboard to the current home location instead (or none).
    Only the automatic value in ``entry.data`` changes; a URL chosen in the options is
    kept. The four hard-coded Brisbane camera entities are removed from the registry.
    """
    if entry.version > 1:
        return False  # downgrade from a future version
    if entry.version == 1 and entry.minor_version < 2:
        data = dict(entry.data)
        moreton_bay = PRESET_COUNCIL_DASHBOARDS["moreton_bay"]["url"]
        if (
            data.get(CONF_STATE) == STATE_QLD
            and data.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME) == LOCATION_MODE_HOME
            and data.get(CONF_COUNCIL_DASHBOARD_URL) == moreton_bay
        ):
            data[CONF_COUNCIL_DASHBOARD_URL] = nearest_council_dashboard(
                STATE_QLD, hass.config.latitude, hass.config.longitude
            )
        registry = er.async_get(hass)
        for camera_id in LEGACY_CAMERA_IDS:
            if entity_id := registry.async_get_entity_id("camera", DOMAIN, f"{entry.entry_id}_camera_{camera_id}"):
                registry.async_remove(entity_id)
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
        _LOGGER.debug("Migrated %s to version 1.2", entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AusNZDisasterWatchConfigEntry) -> bool:
    """Set up Australia and New Zealand Disaster Watch from a config entry.

    Option and reconfigure changes are applied by a full reload, owned by the flows
    themselves (OptionsFlowWithReload and async_update_reload_and_abort), so no update
    listener is registered here.
    """
    # Serve and register the dashboard cards; idempotent across entries (#22).
    await async_register_frontend(hass)

    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    # Opt-in forecast features poll on their own schedule and never block setup (#38, #39, #40)
    coordinator.forecasts = await async_setup_forecasts(hass, entry, (coordinator.latitude, coordinator.longitude))

    # River gauges are optional extras: a gauge outage must not block setup, so the first
    # refresh does not raise and the gauge sensors start unavailable instead (#31).
    if sites := sites_from_options(entry.options.get(CONF_RIVER_GAUGES)):
        coordinator.river_coordinator = RiverGaugeCoordinator(hass, entry, sites)
        await coordinator.river_coordinator.async_refresh()
    # Dam storages likewise never block setup
    if storages := storages_from_options(entry.options.get(CONF_DAM_STORAGES)):
        coordinator.dam_coordinator = DamStorageCoordinator(hass, entry, storages)
        await coordinator.dam_coordinator.async_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AusNZDisasterWatchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AusNZDisasterWatchConfigEntry) -> None:
    """Remove the dashboard card resource when the last config entry is deleted (#22)."""
    remaining = [other for other in hass.config_entries.async_entries(DOMAIN) if other.entry_id != entry.entry_id]
    if not remaining:
        await async_unregister_frontend(hass)
