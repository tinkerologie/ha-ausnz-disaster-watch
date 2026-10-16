"""Options step that picks dam and weir storages near the location; none by default."""

from __future__ import annotations

import asyncio
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
    """Return the options-flow label of a discovered storage: name, distance and fill."""
    site = reading.site
    distance = haversine_km(latitude, longitude, site.latitude, site.longitude)
    if (percent := reading.percent_full) is not None:
        value = f"{percent:.1f}% full"
    else:
        value = f"{reading.level_m:.2f} m"
    return f"{site.name} ({distance:.1f} km, {value})"


class DamOptionsFlow(OptionsFlowWithReload):
    """Options step for the dam and weir storage sensors."""

    def __init__(self) -> None:
        """Initialize the step state."""
        super().__init__()
        # Storages offered on the form, by StorageSite.key
        self._discovered_storages: dict[str, StorageSite] = {}

    async def async_step_dam_storages(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick storages near the location to add as sensors."""
        selected = sites_from_options(self.config_entry.options.get(CONF_DAM_STORAGES))
        if user_input is not None:
            known = {**self._discovered_storages, **{site.key: site for site in selected}}
            # The selector only accepts listed keys, all of which are known
            chosen = [known[key].as_dict() for key in user_input.get(CONF_DAM_STORAGES, [])]
            return self.async_create_entry(data={**self.config_entry.options, CONF_DAM_STORAGES: chosen})

        config = {**self.config_entry.data, **self.config_entry.options}
        # Same point as the coordinator: home-mode entries follow the home location (#19)
        home = (self.hass.config.latitude, self.hass.config.longitude)
        stored = (config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE))
        candidates = (home, stored) if config.get(CONF_LOCATION_MODE) == LOCATION_MODE_HOME else (stored, home)
        latitude, longitude = next((float(la), float(lo)) for la, lo in candidates if la is not None and lo is not None)
        errors: dict[str, str] = {}
        labels = {site.key: f"{site.name} (selected)" for site in selected}
        try:
            async with asyncio.timeout(DAM_DISCOVERY_TIMEOUT.total_seconds()):
                discovered = await async_discover_storages(
                    async_get_clientsession(self.hass),
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=float(config.get(CONF_RADIUS, DEFAULT_RADIUS)),
                    now=dt_util.utcnow(),
                )
        except (DamSourceError, TimeoutError) as err:
            _LOGGER.debug("Dam storage discovery failed: %r", err)
            errors["base"] = "dams_unavailable"
            discovered = []
        self._discovered_storages = {reading.site.key: reading.site for reading in discovered}
        for reading in discovered:
            labels[reading.site.key] = storage_label(reading, latitude, longitude)
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
