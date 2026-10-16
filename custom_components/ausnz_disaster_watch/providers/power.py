"""Shared base for electricity distributor outage feeds (#36).

Each distributor feed is a ``PowerOutageSource``: a ``BaseHazardProvider`` (so it shares
the session, retries and timestamp parsing) that publishes no hazards, only outages. The
factory in ``providers/__init__.py`` adds the sources for the configured state; the
coordinator keeps them apart from the hazard providers, so an outage feed never counts as
a working hazard feed.

A source returns only outages that are in effect now: an unplanned outage until it is
restored, and a planned outage between its start and its end. The coordinator drops
planned outages unless the entry includes them, and drops council dashboard copies of a
distributor's outages while that distributor's own feed works.

Sources ask the server for outages within the radius where the feed supports it (ArcGIS
``distance``, Opendatasoft ``within_distance``). Feeds without a spatial query are skipped
when the monitored circle does not reach the distributor's service area. A feed is fetched
at most every ``min_interval`` seconds, so the one-minute threat polling does not multiply
the load on the distributors.
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta
import logging
import math
import time
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlencode

from custom_components.ausnz_disaster_watch.const import (
    CONF_INCLUDE_PLANNED_OUTAGES,
    DEFAULT_INCLUDE_PLANNED_OUTAGES,
    DEFAULT_RADIUS,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, PowerOutageItem
from homeassistant.util import dt as dt_util

from .base import BaseHazardProvider, ProviderUnavailableError
from .cap import CapArea, area_distance_km, haversine_km, representative_point
from .sources import DATA_SOURCES

if TYPE_CHECKING:
    import aiohttp

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type LatLon = tuple[float, float]
type Ring = tuple[LatLon, ...]
# (south, west, north, east) in degrees
type BoundingBox = tuple[float, float, float, float]

# ArcGIS layers allow 1000-2000 features per page; a radius query rarely needs a second page
ARCGIS_PAGE_SIZE = 1000
ARCGIS_MAX_PAGES = 5
# Opendatasoft Explore v2.1 returns at most 100 records per request
ODS_PAGE_SIZE = 100
ODS_MAX_PAGES = 10
# An unplanned outage whose estimated restoration passed this long ago is a stale record
STALE_UNPLANNED_AFTER = timedelta(days=7)


def geojson_rings(geometry: Any) -> tuple[Ring, ...]:
    """Return the outer rings of a GeoJSON Polygon/MultiPolygon as (lat, lon) points."""
    if not isinstance(geometry, dict):
        return ()
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon" and isinstance(coords, list):
        polygons = coords
    else:
        return ()
    rings: list[Ring] = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon or not isinstance(polygon[0], list):
            continue
        ring = tuple((float(pt[1]), float(pt[0])) for pt in polygon[0] if isinstance(pt, list) and len(pt) >= 2)
        if len(ring) >= 3:
            rings.append(ring)
    return tuple(rings)


def arcgis_query_url(
    layer_url: str,
    lat: float,
    lon: float,
    radius_km: float,
    *,
    where: str = "1=1",
    offset: int = 0,
    **extra: str,
) -> str:
    """Return a GeoJSON query for the features of an ArcGIS layer within ``radius_km`` of a point."""
    params = {
        "where": where,
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": f"{radius_km:g}",
        "units": "esriSRUnit_Kilometer",
        "outFields": "*",
        "outSR": "4326",
        "resultOffset": str(offset),
        "resultRecordCount": str(ARCGIS_PAGE_SIZE),
        "f": "geojson",
        **extra,
    }
    return f"{layer_url}/query?{urlencode(params)}"


class PowerOutageSource(BaseHazardProvider):
    """One distributor's outage feed."""

    # Data source register key (providers/sources.py): licence, attribution and terms
    key: ClassVar[str]
    distributor: ClassVar[str]
    # Area the distributor serves, for feeds without a server-side radius query
    service_area: ClassVar[BoundingBox | None] = None
    min_interval: ClassVar[float] = 300.0
    # Only used when the entry turns on extra outage feeds: the terms allow personal,
    # non-commercial use only, or the download is large
    opt_in: ClassVar[bool] = False

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config: dict[str, Any]) -> None:
        """Initialise the source with the entry config."""
        super().__init__(hass, session, config)
        self._cache: tuple[float, list[PowerOutageItem]] | None = None

    @property
    def state_code(self) -> str:
        """Return the configured state."""
        return str(self.config.get("state", "")).upper()

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Return no hazards: a distributor feed only has outages."""
        return []

    @property
    def latitude(self) -> float:
        """Return the monitored latitude."""
        return float(self.config.get("latitude") or 0.0)

    @property
    def longitude(self) -> float:
        """Return the monitored longitude."""
        return float(self.config.get("longitude") or 0.0)

    @property
    def radius_km(self) -> float:
        """Return the monitoring radius."""
        return float(self.config.get("radius") or DEFAULT_RADIUS)

    @property
    def include_planned(self) -> bool:
        """Return True when the entry includes planned outages (feeds can skip planned datasets)."""
        return bool(self.config.get(CONF_INCLUDE_PLANNED_OUTAGES, DEFAULT_INCLUDE_PLANNED_OUTAGES))

    def set_location(self, latitude: float, longitude: float) -> None:
        """Use the new point; a moved point invalidates the cached outages."""
        if (latitude, longitude) != (self.config.get("latitude"), self.config.get("longitude")):
            self._cache = None
        super().set_location(latitude, longitude)

    def reaches_service_area(self) -> bool:
        """Return True if the monitored circle can touch the distributor's service area."""
        if self.service_area is None:
            return True
        south, west, north, east = self.service_area
        lat = min(max(self.latitude, south), north)
        lon = min(max(self.longitude, west), east)
        return haversine_km(self.latitude, self.longitude, lat, lon) <= self.radius_km

    @classmethod
    def metadata(cls) -> dict[str, str]:
        """Return the distributor with its register entry (licence, attribution, terms, status)."""
        return {"distributor": cls.distributor, **DATA_SOURCES[cls.key].as_dict()}

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        """Return the distributor's current outages near the monitored point.

        Raises ProviderUnavailableError when the feed cannot be fetched or decoded, so the
        coordinator can fall back to the council dashboard copy of the outages.
        """
        if not self.reaches_service_area():
            return []
        now = time.monotonic()
        if self._cache is not None and now - self._cache[0] < self.min_interval:
            return self._cache[1]
        outages = await self._async_fetch_outages()
        self._cache = (now, outages)
        return outages

    @abstractmethod
    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        """Fetch and parse the feed."""

    # --- Helpers for subclasses ------------------------------------------------------

    @staticmethod
    def in_effect(planned: bool, start: datetime | None, end: datetime | None) -> bool:
        """Return True if an outage is under way.

        An outage that starts later is not (feeds list upcoming work). A planned outage ends
        at its scheduled end. An unplanned outage stays in effect past its estimated
        restoration (estimates slip), but not weeks past it: feeds keep a few stale records.
        """
        now = dt_util.utcnow()
        if start is not None and start > now:
            return False
        if end is None:
            return True
        return end > now if planned else end > now - STALE_UNPLANNED_AFTER

    def located(
        self,
        geometry: Any = None,
        lat: float | None = None,
        lon: float | None = None,
        rings: tuple[Ring, ...] = (),
    ) -> tuple[float | None, float | None, float | None]:
        """Return (latitude, longitude, distance_km) for polygons, a GeoJSON geometry or a point.

        A polygon's distance is to its edge (0 when the monitored point is inside), and its
        location is a point inside the polygon nearest the monitored point.
        """
        if rings := rings or geojson_rings(geometry):
            areas = (CapArea(description="", polygons=rings, circles=(), geocodes=()),)
            point = representative_point(areas, self.latitude, self.longitude)
            dist = area_distance_km(self.latitude, self.longitude, areas)
            if point is not None and dist is not None:
                return point[0], point[1], round(dist, 2)
        if isinstance(geometry, dict) and geometry.get("type") == "Point":
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
        if lat is None or lon is None or not (math.isfinite(lat) and math.isfinite(lon)):
            return None, None, None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            return None, None, None
        return lat, lon, round(haversine_km(self.latitude, self.longitude, lat, lon), 2)

    @staticmethod
    def time_text(value: datetime | None) -> str | None:
        """Return an ISO 8601 timestamp in Home Assistant's time zone, or None."""
        return dt_util.as_local(value).isoformat() if value is not None else None

    async def async_fetch_arcgis(self, layer_url: str, label: str, where: str = "1=1", **extra: str) -> list[dict]:
        """Return the GeoJSON features of an ArcGIS layer within the radius, following pages."""
        features: list[dict[str, Any]] = []
        for page in range(ARCGIS_MAX_PAGES):
            url = arcgis_query_url(
                layer_url,
                self.latitude,
                self.longitude,
                self.radius_km,
                where=where,
                offset=page * ARCGIS_PAGE_SIZE,
                **extra,
            )
            payload = self.require_dict(await self.async_fetch_feed_json(url, label), label)
            if "error" in payload:
                raise ProviderUnavailableError(f"{label} returned an error: {payload['error']}")
            batch = self.require_list(payload, "features", label)
            features.extend(feat for feat in batch if isinstance(feat, dict))
            exceeded = payload.get("exceededTransferLimit") or (payload.get("properties") or {}).get(
                "exceededTransferLimit"
            )
            if not exceeded:
                break
        else:
            _LOGGER.debug("%s has more than %s outages in the radius", label, len(features))
        return features

    async def async_fetch_ods(self, records_url: str, label: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Return all records of an Opendatasoft Explore v2.1 query, following pages."""
        records: list[dict[str, Any]] = []
        for page in range(ODS_MAX_PAGES):
            query = urlencode({**params, "limit": str(ODS_PAGE_SIZE), "offset": str(page * ODS_PAGE_SIZE)})
            payload = self.require_dict(await self.async_fetch_feed_json(f"{records_url}?{query}", label), label)
            batch = self.require_list(payload, "results", label)
            records.extend(rec for rec in batch if isinstance(rec, dict))
            if len(batch) < ODS_PAGE_SIZE:
                break
        return records
