"""Provider registry and factory for Australian Emergency Hazards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.australian_disaster_watch.const import STATE_NSW, STATE_QLD, STATE_VIC

from .base import BaseHazardProvider
from .bom import BoMHazardProvider
from .nsw import NSWHazardProvider
from .qld import QueenslandHazardProvider
from .vic import VictoriaHazardProvider

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

    # Always include Bureau of Meteorology weather warnings
    providers.append(BoMHazardProvider(hass, session, config))

    return providers


__all__ = [
    "BaseHazardProvider",
    "BoMHazardProvider",
    "NSWHazardProvider",
    "QueenslandHazardProvider",
    "VictoriaHazardProvider",
    "get_providers_for_config",
]
