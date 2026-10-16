"""Coordinator polling the dam and weir storages selected in the options flow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .dams import (
    DAM_READING_WINDOW,
    DAM_SCAN_INTERVAL,
    DamSourceError,
    StorageReading,
    StorageSite,
    async_fetch_readings,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DamStorageCoordinator(DataUpdateCoordinator[dict[str, StorageReading]]):
    """Fetch the latest reading of each selected storage every hour.

    Data is keyed by ``StorageSite.key``. A storage without a reading in the last
    DAM_READING_WINDOW is absent, so its sensors are unavailable. When Water Data Online
    cannot be reached, the previous readings are kept while they are inside that window;
    the update fails only when none remain.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sites: list[StorageSite]) -> None:
        """Initialize the coordinator for the given storages."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_dam_storages",
            update_interval=DAM_SCAN_INTERVAL,
        )
        self.sites = sites
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, StorageReading]:
        """Fetch readings, bridging outages with the previous readings."""
        now = dt_util.utcnow()
        try:
            return await async_fetch_readings(self._session, self.sites, now)
        except DamSourceError as err:
            _LOGGER.debug("Dam storages unavailable: %s", err)
            cutoff = now - DAM_READING_WINDOW
            kept = {key: reading for key, reading in (self.data or {}).items() if reading.observed_at >= cutoff}
            if not kept:
                raise UpdateFailed(translation_domain=DOMAIN, translation_key="dam_storages_unavailable") from err
            return kept
