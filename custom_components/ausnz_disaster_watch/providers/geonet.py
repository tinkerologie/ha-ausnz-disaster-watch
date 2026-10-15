"""GeoNet (Earth Sciences New Zealand) feeds: quakes and volcanic alert levels via the aio_geojson libraries (#35).

The quake CAP feed (#24) is read separately in ``nz.py``: it lists CAP documents for quakes
GeoNet considers suitable for alerting (intensity moderate or higher, last 48 hours).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aio_geojson_geonetnz_quakes.consts import URL_TEMPLATE as QUAKE_URL_TEMPLATE
from aio_geojson_geonetnz_quakes.feed import GeonetnzQuakesFeed
from aio_geojson_geonetnz_quakes.feed_entry import GeonetnzQuakesFeedEntry
from aio_geojson_geonetnz_volcano.consts import URL as VOLCANO_URL
from aio_geojson_geonetnz_volcano.feed import GeonetnzVolcanoFeed
from aio_geojson_geonetnz_volcano.feed_entry import GeonetnzVolcanoFeedEntry

from .base import MALFORMED_ITEM_ERRORS
from .geojson_feed import CheckedEntryMixin, CheckedFeedMixin

# Quakes that may have caused at least weak shaking (MMI 3) in the New Zealand region
GEONET_QUAKE_MMI = 3
GEONET_QUAKE_URL = QUAKE_URL_TEMPLATE.format(GEONET_QUAKE_MMI)
GEONET_VOLCANO_URL = VOLCANO_URL
GEONET_CAP_FEED_URL = "https://api.geonet.org.nz/cap/1.2/GPA1.0/feed/atom1.0/quake"
GEONET_AGENCY = "GeoNet (Earth Sciences New Zealand)"


class GeoNetQuakeEntry(CheckedEntryMixin, GeonetnzQuakesFeedEntry):
    """GeoNet quake entry; the origin time is None when it is not in GeoNet's usual format."""

    @property
    def origin_time(self) -> datetime | None:
        """Return the quake's origin time, or None if missing or unparsable."""
        try:
            return self.time
        except MALFORMED_ITEM_ERRORS:
            return None

    @property
    def raw_time(self) -> Any:
        """Return the unparsed ``time`` property."""
        return self.properties.get("time")


class GeoNetQuakesFeed(CheckedFeedMixin, GeonetnzQuakesFeed):
    """GeoNet quakes feed (``/quake?MMI=3``)."""

    feed_label = "GeoNet quakes"

    def __init__(self, websession: Any, home: tuple[float, float]) -> None:
        """Create the feed without library-side radius, magnitude or time filters."""
        super().__init__(websession, home, mmi=GEONET_QUAKE_MMI)

    def _new_entry(self, home_coordinates: tuple[float, float], feature: Any, global_data: Any) -> GeoNetQuakeEntry:
        """Wrap a feature in a GeoNet quake entry."""
        return GeoNetQuakeEntry(home_coordinates, feature)


class GeoNetVolcanoEntry(CheckedEntryMixin, GeonetnzVolcanoFeedEntry):
    """GeoNet volcanic alert level entry, plus the aviation colour code the library does not expose."""

    @property
    def aviation_colour_code(self) -> str | None:
        """Return the aviation colour code (``acc``), e.g. Green."""
        return self.properties.get("acc")


class GeoNetVolcanoFeed(CheckedFeedMixin, GeonetnzVolcanoFeed):
    """GeoNet volcanic alert level feed (``/volcano/val``)."""

    feed_label = "GeoNet volcanoes"

    def _new_entry(self, home_coordinates: tuple[float, float], feature: Any, global_data: Any) -> GeoNetVolcanoEntry:
        """Wrap a feature in a GeoNet volcano entry."""
        return GeoNetVolcanoEntry(home_coordinates, feature)
