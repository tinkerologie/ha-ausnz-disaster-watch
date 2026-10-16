"""Adapter for exxamalte's ``aio_geojson_*`` feed libraries (#35).

The libraries (also used by Home Assistant core) fetch a GeoJSON feed through the injected
aiohttp session and wrap each feature in a typed entry. Two gaps are closed here so the
feed failure contract (#16) holds:

* The library reports a failed fetch as an ``ERROR`` status, not an exception.
* A JSON document that is not a FeatureCollection (an error object, say) would come back
  as ``OK`` with no entries, which is indistinguishable from an all-clear.

Both raise ProviderUnavailableError instead. Radius filtering stays with the coordinator, so
feeds are created without ``filter_radius``.
"""

from __future__ import annotations

from typing import Any

from aio_geojson_client.consts import UPDATE_OK
from aio_geojson_client.feed import GeoJsonFeed
from aio_geojson_client.feed_entry import FeedEntry
from geojson import FeatureCollection

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError

# Seconds; the library default (10) is shorter than the other providers' requests
FEED_TIMEOUT = 30


class CheckedFeedMixin:
    """Mixin for a library feed class: longer timeout, and a non-FeatureCollection is an error.

    List it before the library class (``class Feed(CheckedFeedMixin, LibraryFeed)``).
    """

    feed_label: str = "GeoJSON feed"

    def _client_session_timeout(self) -> int:
        """Return the request timeout in seconds."""
        return FEED_TIMEOUT

    def _extract_from_feed(self, feed: Any) -> dict[str, Any] | None:
        """Reject a payload that is not a FeatureCollection with a list of features."""
        if not isinstance(feed, FeatureCollection) or not isinstance(feed.get("features"), list):
            raise ProviderUnavailableError(f"{self.feed_label} returned an unexpected payload")
        return None

    def _extract_last_timestamp(self, feed_entries: list[Any]) -> None:
        """Skip the library's newest-entry timestamp (unused here).

        The libraries parse every entry's time strictly for it, so one record with an unusual
        timestamp would fail the whole feed.
        """
        return


class CheckedEntryMixin:
    """Mixin for a library entry class: a feature with broken geometry has no geometry.

    The library filters entries by geometry while building the list, so an exception from one
    malformed feature (``"coordinates": []``) would otherwise fail the whole feed.
    """

    @property
    def geometries(self) -> list[Any] | None:
        """Return the entry's geometries, or None if the feature's geometry is malformed."""
        try:
            return super().geometries  # type: ignore[misc]
        except MALFORMED_ITEM_ERRORS:
            return None

    @property
    def raw_geometry(self) -> dict[str, Any]:
        """Return the feature's original GeoJSON geometry (polygons included), or an empty dict."""
        feature: Any = getattr(self, "_feature", None)
        geometry = feature.get("geometry") if feature is not None else None
        return geometry if isinstance(geometry, dict) else {}

    @property
    def properties(self) -> dict[str, Any]:
        """Return the feature's original properties."""
        feature: Any = getattr(self, "_feature", None)
        props = feature.get("properties") if feature is not None else None
        return props if isinstance(props, dict) else {}


async def async_feed_entries[EntryT: FeedEntry](feed: GeoJsonFeed[EntryT], label: str) -> list[EntryT]:
    """Update a library feed and return its entries, or raise ProviderUnavailableError.

    An ``OK`` update with an empty list is a valid "no features" result. Any other status
    (``ERROR`` for transport, HTTP or JSON failures; ``OK_NO_DATA`` for an empty body) and a
    structurally broken document mean the feed is unavailable.
    """
    try:
        status, entries = await feed.update()
    except MALFORMED_ITEM_ERRORS as err:
        raise ProviderUnavailableError(f"{label} returned a malformed payload: {err}") from err
    if status != UPDATE_OK or entries is None:
        raise ProviderUnavailableError(f"{label} unavailable (feed status {status})")
    return entries
