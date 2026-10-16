"""Coordinator polling the dam and weir storages selected in the options flow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .dam_operators import async_fetch_operator_readings
from .dams import (
    DAM_READING_WINDOW,
    DAM_SCAN_INTERVAL,
    DamSourceError,
    StorageReading,
    StorageSite,
    async_fetch_readings,
    merge_operator,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DamStorageCoordinator(DataUpdateCoordinator[dict[str, StorageReading]]):
    """Fetch the latest reading of each selected storage every hour.

    Data is keyed by ``StorageSite.key``. Each storage's Water Data Online reading is merged
    with its operator feed's (WaterNSW or Hydro Tasmania, when matched), which is fresher and
    carries spill data. A storage without a reading in the last DAM_READING_WINDOW is absent,
    so its sensors are unavailable. When Water Data Online cannot be reached, the previous
    readings are kept while they are inside that window and operator readings still update
    them; the update fails only when no reading remains.
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
        # The last Water Data Online readings on their own, kept through outages and aged
        # separately from the merged readings, so an operator reading never refreshes them
        self._bom: dict[str, StorageReading] = {}

    async def _async_update_data(self) -> dict[str, StorageReading]:
        """Fetch readings, bridging outages with the previous readings."""
        now = dt_util.utcnow()
        cutoff = now - DAM_READING_WINDOW
        error: DamSourceError | None = None
        try:
            self._bom = await async_fetch_readings(self._session, self.sites, now)
        except DamSourceError as err:
            _LOGGER.debug("Dam storages unavailable: %s", err)
            error = err
            self._bom = {key: reading for key, reading in self._bom.items() if reading.observed_at >= cutoff}
        bom = self._bom
        # Only this poll's operator readings are merged: a feed that is down adds nothing
        operators = await async_fetch_operator_readings(self._session, self.sites, now)
        readings: dict[str, StorageReading] = {}
        for site in self.sites:
            if (reading := merge_operator(site, bom.get(site.key), operators.get(site.key))) is not None:
                readings[site.key] = reading
        if error is not None and not readings:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="dam_storages_unavailable") from error
        return readings
