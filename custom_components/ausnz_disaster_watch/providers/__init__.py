"""Provider registry and factory for Australia and New Zealand Emergency Hazards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.ausnz_disaster_watch.const import (
    CONF_EXTRA_OUTAGE_FEEDS,
    CONF_INCLUDE_EARTHQUAKES,
    DEFAULT_EXTRA_OUTAGE_FEEDS,
    NATIONAL_FEED_OPTIONS,
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_NZ,
    STATE_QLD,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
)

from .act import ACTHazardProvider
from .base import BaseHazardProvider
from .bom import BoMHazardProvider
from .cameras import CameraCatalogueProvider, enabled_networks
from .ga_earthquakes import GAEarthquakeProvider
from .national import NationalHazardProvider
from .nsw import NSWHazardProvider
from .nt import NTHazardProvider
from .nz import NZHazardProvider
from .power import PowerOutageSource
from .power_endeavour import EndeavourOutageSource
from .power_essential import EssentialEnergyOutageSource
from .power_nz import MainPowerOutageSource, PowercoOutageSource, UnisonOutageSource
from .power_tasnetworks import TasNetworksOutageSource
from .power_western_power import WesternPowerOutageSource
from .qld import QueenslandHazardProvider
from .sa import SAHazardProvider
from .tas import TasmaniaHazardProvider
from .vic import VictoriaHazardProvider
from .wa import WAHazardProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Electricity distributor outage feeds per configured state (#36). Opt-in feeds are only
# used when the entry turns on extra outage feeds (see PowerOutageSource.opt_in).
POWER_OUTAGE_SOURCES: dict[str, tuple[type[PowerOutageSource], ...]] = {
    STATE_NSW: (EndeavourOutageSource, EssentialEnergyOutageSource),
    STATE_ACT: (EssentialEnergyOutageSource,),
    STATE_TAS: (TasNetworksOutageSource,),
    STATE_WA: (WesternPowerOutageSource,),
    STATE_NZ: (MainPowerOutageSource, PowercoOutageSource, UnisonOutageSource),
}


def get_providers_for_config(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    config: dict[str, Any],
) -> list[BaseHazardProvider]:
    """Instantiate and return applicable hazard providers for given configuration."""
    state = str(config.get("state", STATE_QLD)).upper()
    providers: list[BaseHazardProvider] = []

    if state == STATE_QLD:
        providers.append(QueenslandHazardProvider(hass, session, config))
    elif state == STATE_NSW:
        providers.append(NSWHazardProvider(hass, session, config))
    elif state == STATE_VIC:
        providers.append(VictoriaHazardProvider(hass, session, config))
    elif state == STATE_WA:
        providers.append(WAHazardProvider(hass, session, config))
    elif state == STATE_SA:
        providers.append(SAHazardProvider(hass, session, config))
    elif state == STATE_TAS:
        providers.append(TasmaniaHazardProvider(hass, session, config))
    elif state == STATE_NT:
        providers.append(NTHazardProvider(hass, session, config))
    elif state == STATE_ACT:
        providers.append(ACTHazardProvider(hass, session, config))
    elif state == STATE_NZ:
        providers.append(NZHazardProvider(hass, session, config))

    # Always include Bureau of Meteorology weather warnings for Australian jurisdictions
    if state != STATE_NZ:
        providers.append(BoMHazardProvider(hass, session, config))
        # Geoscience Australia earthquakes are opt-in (#23); NZ quakes come from GeoNet
        if config.get(CONF_INCLUDE_EARTHQUAKES):
            providers.append(GAEarthquakeProvider(hass, session, config))

    # Distributor outage feeds; the coordinator keeps them apart from the hazard feeds (#36)
    extra = bool(config.get(CONF_EXTRA_OUTAGE_FEEDS, DEFAULT_EXTRA_OUTAGE_FEEDS))
    providers.extend(
        source(hass, session, config) for source in POWER_OUTAGE_SOURCES.get(state, ()) if extra or not source.opt_in
    )

    # Opt-in national and regional feeds (#37)
    if any(config.get(option) for option in NATIONAL_FEED_OPTIONS):
        providers.append(NationalHazardProvider(hass, session, config))
    # Opt-in road and flood camera catalogues (#70)
    if enabled_networks(config):
        providers.append(CameraCatalogueProvider(hass, session, config))

    return providers


__all__ = [
    "POWER_OUTAGE_SOURCES",
    "ACTHazardProvider",
    "BaseHazardProvider",
    "BoMHazardProvider",
    "CameraCatalogueProvider",
    "EndeavourOutageSource",
    "EssentialEnergyOutageSource",
    "GAEarthquakeProvider",
    "MainPowerOutageSource",
    "NSWHazardProvider",
    "NTHazardProvider",
    "NZHazardProvider",
    "NationalHazardProvider",
    "PowercoOutageSource",
    "QueenslandHazardProvider",
    "SAHazardProvider",
    "TasNetworksOutageSource",
    "TasmaniaHazardProvider",
    "UnisonOutageSource",
    "VictoriaHazardProvider",
    "WAHazardProvider",
    "WesternPowerOutageSource",
    "get_providers_for_config",
]
