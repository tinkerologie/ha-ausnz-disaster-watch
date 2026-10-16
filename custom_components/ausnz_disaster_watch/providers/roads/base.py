"""Shared plumbing for the statewide road event feeds (#29).

A road provider reads one state's official open road feed and returns
``RoadClosureItem``s with an explicit ``RoadEventCategory``. It has no hazards of its own:
the coordinator keeps road providers apart from the hazard providers, so a road feed never
counts towards hazard feed health.
"""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, timedelta
import logging
import math
import re
from typing import Any, ClassVar
from urllib.parse import urlencode

from custom_components.ausnz_disaster_watch.const import CONF_INCLUDE_ROADWORKS, LAST_GOOD_MAX_AGE
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, RoadClosureItem
from custom_components.ausnz_disaster_watch.providers.base import (
    MALFORMED_ITEM_ERRORS,
    BaseHazardProvider,
    ProviderUnavailableError,
)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Road feeds change slowly, and two of them (NSW, QLD) are statewide downloads, so they are
# fetched at most this often even while the coordinator polls every minute for a threat.
ROAD_MIN_REFRESH = timedelta(minutes=4)

# Incidents that are routine traffic noise rather than a hazard to someone travelling nearby
_MINOR_INCIDENT_RE = re.compile(
    r"break\s*down|tow away|traffic (?:light|signal)|signal fault|lights? (?:blacked out|flashing)|ferry"
    r"|stationary vehicle",
    re.IGNORECASE,
)

ARCGIS_PAGE_SIZE = 1000
ARCGIS_MAX_PAGES = 5


def is_minor_incident(*texts: str | None) -> bool:
    """Return True for breakdowns, signal faults, ferries and similar routine incidents."""
    return any(text and _MINOR_INCIDENT_RE.search(text) for text in texts)


def text(value: Any) -> str:
    """Return a stripped string, or "" for None and non-scalar values."""
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def mapping(value: Any) -> dict[str, Any]:
    """Return value if it is a dict, else an empty dict (nested objects may be null)."""
    return value if isinstance(value, dict) else {}


def valid_point(lat: Any, lon: Any) -> tuple[float, float] | None:
    """Return (lat, lon) as floats if both are finite and in range, else None."""
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0) or (lat_f == 0.0 and lon_f == 0.0):
        return None
    return lat_f, lon_f


def first_point(geometry: Any) -> tuple[float, float] | None:
    """Return the first (lat, lon) of a GeoJSON geometry, preferring an explicit Point.

    A road closure is usually a line; its first vertex is where the closure starts, which
    is a better "where is it" than the average of every vertex (#29).
    """
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    if kind == "Feature":
        return first_point(geometry.get("geometry"))
    if kind == "GeometryCollection":
        members = [g for g in geometry.get("geometries") or [] if isinstance(g, dict)]
        members.sort(key=lambda g: g.get("type") != "Point")
        for member in members:
            if (point := first_point(member)) is not None:
                return point
        return None
    coords: Any = geometry.get("coordinates")
    while isinstance(coords, list) and coords and isinstance(coords[0], list):
        coords = coords[0]
    if isinstance(coords, list) and len(coords) >= 2:
        return valid_point(coords[1], coords[0])
    return None


def envelope(config: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return the WGS84 box (xmin, ymin, xmax, ymax) around the configured location and radius."""
    point = valid_point(config.get("latitude"), config.get("longitude"))
    if point is None:
        return None
    lat, lon = point
    try:
        radius_km = float(config.get("radius") or 50)
    except (TypeError, ValueError):
        radius_km = 50.0
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return (
        round(max(lon - dlon, -180.0), 5),
        round(max(lat - dlat, -90.0), 5),
        round(min(lon + dlon, 180.0), 5),
        round(min(lat + dlat, 90.0), 5),
    )


class BaseRoadProvider(BaseHazardProvider):
    """A statewide road event feed. Subclasses implement ``_async_fetch_road_events``.

    ``async_fetch_road_closures`` refreshes at most every ``ROAD_MIN_REFRESH``. When the feed
    is down it returns the last good items for up to ``LAST_GOOD_MAX_AGE`` (so a short outage
    does not read as "all roads open"), then raises ProviderUnavailableError.
    """

    # Name of the feed shown in logs and diagnostics
    feed_name: ClassVar[str] = "road feed"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider and its result cache."""
        super().__init__(*args, **kwargs)
        self._items: list[RoadClosureItem] | None = None
        self._fetched_at: datetime | None = None
        self._good_at: datetime | None = None
        # Last good items of each source of a multi-source feed, so one source's outage does not drop its events
        self._source_items: dict[str, tuple[datetime, list[RoadClosureItem]]] = {}
        # Sources down for longer than LAST_GOOD_MAX_AGE in the latest fetch: the feed is incomplete
        self.failed_sources: list[str] = []

    def set_location(self, latitude: float, longitude: float) -> None:
        """Follow the monitored point; a move refetches, as radius-box queries depend on it."""
        moved = (self.config.get("latitude"), self.config.get("longitude")) != (latitude, longitude)
        super().set_location(latitude, longitude)
        if moved:
            self._items = self._fetched_at = self._good_at = None
            self._source_items.clear()

    @property
    def include_roadworks(self) -> bool:
        """Return True if planned roadworks and events should be fetched as well."""
        return bool(self.config.get(CONF_INCLUDE_ROADWORKS, False))

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Road providers contribute road events only, never hazards."""
        return []

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Return the feed's current road events (throttled, with a short last-good bridge)."""
        now = dt_util.utcnow()
        if self._fetched_at is not None and now - self._fetched_at < ROAD_MIN_REFRESH and self._items is not None:
            return list(self._items)
        self._fetched_at = now
        try:
            items = await self._async_fetch_road_events()
        except ProviderUnavailableError as err:
            if self._items is not None and self._good_at is not None and now - self._good_at <= LAST_GOOD_MAX_AGE:
                _LOGGER.debug("%s unavailable, keeping last good road events: %s", self.feed_name, err)
                return list(self._items)
            self._items = None
            raise
        self._items = items
        self._good_at = now
        return list(items)

    @abstractmethod
    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch and parse the feed; raise ProviderUnavailableError if nothing could be read."""

    def collect(self, records: Iterable[Any], parse: Any) -> list[RoadClosureItem]:
        """Parse records one by one: a malformed record is skipped, not the feed; IDs are unique."""
        items: list[RoadClosureItem] = []
        seen: set[str] = set()
        for record in records:
            try:
                item = parse(record)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed %s record: %s", self.feed_name, err)
                continue
            if item is not None and item.id not in seen:
                seen.add(item.id)
                items.append(item)
        return items

    async def async_collect_road_sources(
        self,
        sources: Iterable[tuple[str, Callable[[], Awaitable[Any]], Callable[[Any], list[RoadClosureItem]]]],
    ) -> list[RoadClosureItem]:
        """Fetch several endpoints concurrently; partial results are fine, all failing is not (#16).

        Each source is ``(label, fetch, parse)``. A source fails when its fetch raises
        ProviderUnavailableError or its payload is structurally broken; a failed source
        contributes its last good items for up to ``LAST_GOOD_MAX_AGE``.
        """
        now = dt_util.utcnow()
        source_list = list(sources)

        async def _run(fetch: Callable[[], Awaitable[Any]], parse: Callable[[Any], list[RoadClosureItem]]) -> Any:
            payload = await fetch()
            try:
                return parse(payload)
            except MALFORMED_ITEM_ERRORS as err:
                raise ProviderUnavailableError(f"malformed payload: {err}") from err

        results = await asyncio.gather(*(_run(fetch, parse) for _, fetch, parse in source_list), return_exceptions=True)
        items: list[RoadClosureItem] = []
        failures: list[str] = []
        stale: list[str] = []
        seen: set[str] = set()
        for (label, _, _), result in zip(source_list, results, strict=True):
            if isinstance(result, BaseException):
                if not isinstance(result, ProviderUnavailableError):
                    raise result
                _LOGGER.debug("%s source failed: %s", label, result)
                failures.append(f"{label}: {result}")
                cached = self._source_items.get(label)
                if cached is None or now - cached[0] > LAST_GOOD_MAX_AGE:
                    stale.append(label)
                    continue
                result = cached[1]
            else:
                self._source_items[label] = (now, result)
            for item in result:
                if item.id not in seen:
                    seen.add(item.id)
                    items.append(item)
        self.failed_sources = stale
        if len(failures) == len(source_list):
            raise ProviderUnavailableError("; ".join(failures) or "no sources configured")
        return items

    async def async_arcgis_query(
        self, layer_url: str, label: str, where: str = "1=1", *, use_envelope: bool = True
    ) -> list[dict[str, Any]]:
        """Return the GeoJSON features of an ArcGIS layer query, filtered to the radius box and paged."""
        params: dict[str, Any] = {"where": where, "outFields": "*", "outSR": 4326, "f": "geojson"}
        if use_envelope and (box := envelope(self.config)) is not None:
            params.update(
                geometry=",".join(str(v) for v in box),
                geometryType="esriGeometryEnvelope",
                inSR=4326,
                spatialRel="esriSpatialRelIntersects",
            )
        features: list[dict[str, Any]] = []
        for page in range(ARCGIS_MAX_PAGES):
            query = {**params, "resultOffset": page * ARCGIS_PAGE_SIZE, "resultRecordCount": ARCGIS_PAGE_SIZE}
            payload = self.require_dict(
                await self.async_fetch_feed_json(f"{layer_url}/query?{urlencode(query)}", label), label
            )
            if "error" in payload:
                raise ProviderUnavailableError(f"{label} returned an error: {payload['error']}")
            features.extend(f for f in self.require_list(payload, "features", label) if isinstance(f, dict))
            if not payload.get("exceededTransferLimit"):
                break
        return features
