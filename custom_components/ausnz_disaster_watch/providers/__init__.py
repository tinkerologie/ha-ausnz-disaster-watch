"""Provider registry and factory for Australia and New Zealand Emergency Hazards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.ausnz_disaster_watch.const import (
    CONF_INCLUDE_EARTHQUAKES,
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
from .ga_earthquakes import GAEarthquakeProvider
from .nsw import NSWHazardProvider
from .nt import NTHazardProvider
from .nz import NZHazardProvider
from .qld import QueenslandHazardProvider
from .sa import SAHazardProvider
from .tas import TasmaniaHazardProvider
from .vic import VictoriaHazardProvider
from .wa import WAHazardProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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

    return providers


__all__ = [
    "ACTHazardProvider",
    "BaseHazardProvider",
    "BoMHazardProvider",
    "GAEarthquakeProvider",
    "NSWHazardProvider",
    "NTHazardProvider",
    "NZHazardProvider",
    "QueenslandHazardProvider",
    "SAHazardProvider",
    "TasmaniaHazardProvider",
    "VictoriaHazardProvider",
    "WAHazardProvider",
    "get_providers_for_config",
]
