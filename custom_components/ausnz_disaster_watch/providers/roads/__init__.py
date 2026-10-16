"""Statewide road closure, flooded road and road hazard feeds (#29).

One road provider per state with an official open road feed. The coordinator polls these
next to the hazard providers and merges their items with council road items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.ausnz_disaster_watch.const import (
    STATE_NSW,
    STATE_NT,
    STATE_QLD,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
)

from .base import BaseRoadProvider
from .merge import merge_road_items
from .nsw import NSWRoadProvider
from .nt import NTRoadProvider
from .qld import QueenslandRoadProvider
from .sa import SARoadProvider
from .tas import TasmaniaRoadProvider
from .vic import VictoriaRoadProvider
from .wa import WARoadProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ROAD_PROVIDERS: dict[str, type[BaseRoadProvider]] = {
    STATE_NSW: NSWRoadProvider,
    STATE_QLD: QueenslandRoadProvider,
    STATE_VIC: VictoriaRoadProvider,
    STATE_SA: SARoadProvider,
    STATE_WA: WARoadProvider,
    STATE_NT: NTRoadProvider,
    STATE_TAS: TasmaniaRoadProvider,
}


def get_road_providers_for_config(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    config: dict[str, Any],
) -> list[BaseRoadProvider]:
    """Return the road provider for the configured state (VIC only when a DTP key is set)."""
    provider_cls = ROAD_PROVIDERS.get(str(config.get("state", STATE_QLD)).upper())
    if provider_cls is None:
        return []
    provider = provider_cls(hass, session, config)
    if isinstance(provider, VictoriaRoadProvider) and provider.api_key is None:
        return []
    return [provider]


__all__ = [
    "ROAD_PROVIDERS",
    "BaseRoadProvider",
    "NSWRoadProvider",
    "NTRoadProvider",
    "QueenslandRoadProvider",
    "SARoadProvider",
    "TasmaniaRoadProvider",
    "VictoriaRoadProvider",
    "WARoadProvider",
    "get_road_providers_for_config",
    "merge_road_items",
]
