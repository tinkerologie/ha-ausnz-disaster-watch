"""Coordinator polling the river and creek gauges selected in the options flow (#31)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .rivers import RIVER_READING_WINDOW, RIVER_SCAN_INTERVAL, GaugeReading, GaugeSite, async_fetch_readings

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class RiverGaugeCoordinator(DataUpdateCoordinator[dict[str, GaugeReading]]):
    """Fetch the latest level of each selected gauge every 15 minutes.

    Data is keyed by ``GaugeSite.key``. A gauge without a reading in the last
    RIVER_READING_WINDOW is absent, so its sensor is unavailable. When a gauge's service
    cannot be reached, its previous reading is kept while it is still inside that window;
    the update fails only when every service fails and no kept reading remains.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sites: list[GaugeSite]) -> None:
        """Initialize the coordinator for the given gauges."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_river_gauges",
            update_interval=RIVER_SCAN_INTERVAL,
        )
        self.sites = sites
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, GaugeReading]:
        """Fetch readings, bridging short outages with the previous readings."""
        now = dt_util.utcnow()
        fetched, failed = await async_fetch_readings(self._session, self.sites, now)
        readings = dict(fetched)
        previous = self.data or {}
        cutoff = now - RIVER_READING_WINDOW
        for key in failed:
            if (reading := previous.get(key)) is not None and reading.observed_at >= cutoff:
                readings[key] = reading
        if self.sites and len(failed) == len(self.sites) and not readings:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="river_gauges_unavailable")
        return readings
