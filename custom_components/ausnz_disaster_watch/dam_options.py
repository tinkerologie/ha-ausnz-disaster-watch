"""Options step that picks dam and weir storages near the location; none by default."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAM_STORAGES,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    DEFAULT_RADIUS,
    LOCATION_MODE_HOME,
    STATE_NZ,
)
from .dam_operators import OPERATOR_MATCH_TIMEOUT, async_attach_operators
from .dams import (
    DAM_DISCOVERY_TIMEOUT,
    DamSourceError,
    StorageReading,
    StorageSite,
    async_discover_storages,
    haversine_km,
    sites_from_options,
)

_LOGGER = logging.getLogger(__name__)


def offers_dam_storages(state: str) -> bool:
    """Return True where Water Data Online has storages: every Australian jurisdiction."""
    return bool(state) and state.upper() != STATE_NZ


def storage_label(reading: StorageReading, latitude: float, longitude: float) -> str:
    """Return the options-flow label of a discovered storage: name, distance and fill (or level, or volume)."""
    site = reading.site
    distance = haversine_km(latitude, longitude, site.latitude, site.longitude)
    # A reading has at least a volume or a level; percent full needs the full supply volume too
    if (percent := reading.percent_full) is not None:
        value = f"{percent:.1f}% full"
    elif reading.level_m is not None:
        value = f"{reading.level_m:.2f} m"
    else:
        value = f"{reading.volume_ml or 0:,.0f} ML"
    return f"{site.name} ({distance:.1f} km, {value})"


@dataclass(frozen=True, slots=True)
class StorageSearch:
    """The result of a storage search, kept on the flow while the form is open."""

    readings: list[StorageReading]
    error: str | None
    latitude: float
    longitude: float


class DamOptionsFlow(OptionsFlowWithReload):
    """Options steps for the dam and weir storage sensors.

    The search (up to DAM_DISCOVERY_TIMEOUT plus OPERATOR_MATCH_TIMEOUT) runs as a progress
    task, so the UI shows a spinner instead of a form that seems to hang. Its result is kept
    on the flow, so showing the form again does not search again.
    """

    def __init__(self) -> None:
        """Initialize the step state."""
        super().__init__()
        # Storages offered on the form, by StorageSite.key
        self._discovered_storages: dict[str, StorageSite] = {}
        self._dam_search: StorageSearch | None = None
        self._dam_search_task: asyncio.Task[StorageSearch] | None = None

    async def async_step_dam_storages(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick storages near the location to add as sensors; searches first."""
        selected = sites_from_options(self.config_entry.options.get(CONF_DAM_STORAGES))
        if user_input is not None:
            # A storage discovered again (and matched to its operator feed) replaces the stored copy
            known = {**{site.key: site for site in selected}, **self._discovered_storages}
            # The selector only accepts listed keys, all of which are known
            chosen = [known[key].as_dict() for key in user_input.get(CONF_DAM_STORAGES, [])]
            return self.async_create_entry(data={**self.config_entry.options, CONF_DAM_STORAGES: chosen})
        if (search := self._dam_search) is None:
            return await self.async_step_dam_storages_search()

        errors = {"base": search.error} if search.error else {}
        labels = {site.key: f"{site.name} (selected)" for site in selected}
        self._discovered_storages = {reading.site.key: reading.site for reading in search.readings}
        for reading in search.readings:
            labels[reading.site.key] = storage_label(reading, search.latitude, search.longitude)
        if not labels and not errors:
            errors["base"] = "no_dam_storages"

        schema = vol.Schema(
            {
                vol.Optional(CONF_DAM_STORAGES, default=[site.key for site in selected]): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=key, label=label) for key, label in labels.items()],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="dam_storages",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
        )

    async def async_step_dam_storages_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search for storages in a progress task, then show the storage form."""
        if self._dam_search_task is None:
            self._dam_search_task = self.hass.async_create_task(self._async_search_storages(), eager_start=False)
        if not self._dam_search_task.done():
            return self.async_show_progress(
                step_id="dam_storages_search",
                progress_action="dam_storages_search",
                progress_task=self._dam_search_task,
            )
        try:
            self._dam_search = self._dam_search_task.result()
        except Exception:
            # A bug in the search must end in an error on the form, not an endless spinner
            _LOGGER.exception("Dam storage search failed")
            self._dam_search = StorageSearch([], "dams_unavailable", 0.0, 0.0)
        self._dam_search_task = None
        return self.async_show_progress_done(next_step_id="dam_storages")

    async def _async_search_storages(self) -> StorageSearch:
        """Search Water Data Online, then match the operator feeds; never raises for an outage."""
        config = {**self.config_entry.data, **self.config_entry.options}
        # Same point as the coordinator: home-mode entries follow the home location (#19)
        home = (self.hass.config.latitude, self.hass.config.longitude)
        stored = (config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE))
        candidates = (home, stored) if config.get(CONF_LOCATION_MODE) == LOCATION_MODE_HOME else (stored, home)
        latitude, longitude = next((float(la), float(lo)) for la, lo in candidates if la is not None and lo is not None)
        session = async_get_clientsession(self.hass)
        now = dt_util.utcnow()
        error: str | None = None
        try:
            async with asyncio.timeout(DAM_DISCOVERY_TIMEOUT.total_seconds()):
                discovered = await async_discover_storages(
                    session,
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=float(config.get(CONF_RADIUS, DEFAULT_RADIUS)),
                    now=now,
                )
        except (DamSourceError, TimeoutError) as err:
            _LOGGER.debug("Dam storage discovery failed: %r", err)
            error = "dams_unavailable"
            discovered = []
        try:
            # WaterNSW and Hydro Tasmania storages get their operator feed (fresher, with spill
            # data). Optional: a slow feed leaves the Bureau's storages to choose from.
            async with asyncio.timeout(OPERATOR_MATCH_TIMEOUT.total_seconds()):
                discovered = await async_attach_operators(session, discovered, now)
        except TimeoutError:
            _LOGGER.debug("Dam storage operator matching timed out")
        return StorageSearch(discovered, error, latitude, longitude)
