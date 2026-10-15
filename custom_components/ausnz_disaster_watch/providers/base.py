"""Base hazard provider definition and utilities for state emergency feeds."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCameraItem,
    EmergencyNewsItem,
    FireDangerRating,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WeatherStationObservation,
    WeatherWarningItem,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class BaseHazardProvider(ABC):
    """Abstract base provider for state and jurisdiction emergency feeds."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        config: dict[str, Any],
    ) -> None:
        """Initialize provider with Home Assistant, aiohttp session, and entry config."""
        self.hass = hass
        self.session = session
        self.config = config
        self._payload_cache: dict[str, Any] = {}

    @property
    @abstractmethod
    def state_code(self) -> str:
        """Return the two/three letter state code (e.g., 'QLD', 'NSW', 'VIC')."""

    @abstractmethod
    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch upstream endpoints, parse payload, and return canonical hazard objects."""

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        """Fetch active power outages for jurisdiction/council."""
        return []

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Fetch active road closures for jurisdiction/council."""
        return []

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Fetch active weather warning products."""
        return []

    async def async_fetch_emergency_news(self) -> list[EmergencyNewsItem]:
        """Fetch latest emergency news / bulletins."""
        return []

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch AFDRS fire danger rating."""
        return None

    async def async_fetch_weather_telemetry(self) -> list[WeatherStationObservation]:
        """Fetch local weather station telemetry."""
        return []

    async def async_fetch_air_quality(self) -> list[AirQualityStationData]:
        """Fetch local air quality station telemetry."""
        return []

    async def async_fetch_relief_facilities(self) -> list[ReliefFacilityItem]:
        """Fetch disaster relief facilities (sandbag stations, evacuation centres)."""
        return []

    async def async_fetch_cameras(self) -> list[DisasterCameraItem]:
        """Fetch flood and traffic camera snapshots."""
        return []

    async def async_fetch_nearby_councils(self) -> list[dict[str, str]]:
        """Fetch nearby council disaster dashboard links."""
        return []

    async def _async_request(
        self,
        url: str,
        accept: str,
        is_json: bool,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Fetch URL with exponential retry for transient HTTP (429, 5xx) and network errors."""
        req_headers = {
            "User-Agent": "HomeAssistant-AusNZDisasterWatch/1.0",
            "Accept": accept,
        }
        if headers:
            req_headers.update(headers)

        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with self.session.get(
                    url,
                    headers=req_headers,
                    timeout=DEFAULT_TIMEOUT,
                ) as resp:
                    if resp.status == 200:
                        if is_json:
                            return await resp.json(content_type=None)
                        return await resp.text()
                    if resp.status in (429, 500, 502, 503, 504):
                        _LOGGER.debug(
                            "Transient HTTP %s from %s (attempt %s/%s). Retrying in %ss...",
                            resp.status,
                            url,
                            attempt,
                            MAX_RETRIES,
                            backoff,
                        )
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                    resp.raise_for_status()
            except aiohttp.ClientResponseError as err:
                if err.status not in (429, 500, 502, 503, 504) or attempt >= MAX_RETRIES:
                    raise
                _LOGGER.debug(
                    "Transient HTTP response error %s from %s (attempt %s/%s): %s",
                    err.status,
                    url,
                    attempt,
                    MAX_RETRIES,
                    err,
                )
                await asyncio.sleep(backoff)
                backoff *= 2

            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug(
                    "Network error fetching %s (attempt %s/%s): %s",
                    url,
                    attempt,
                    MAX_RETRIES,
                    err,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise

        msg = f"Failed to fetch {url} after {MAX_RETRIES} attempts"  # pragma: no cover
        raise aiohttp.ClientError(msg)  # pragma: no cover

    async def async_fetch_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Fetch JSON data from URL with exponential retry for 429/5xx errors."""
        return await self._async_request(
            url,
            accept="application/json, text/plain, */*",
            is_json=True,
            headers=headers,
        )

    async def async_fetch_text(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Fetch text/XML data from URL with exponential retry for 429/5xx errors."""
        return await self._async_request(
            url,
            accept="application/xml, text/xml, application/rss+xml, application/atom+xml, text/plain, */*",
            is_json=False,
            headers=headers,
        )

    @staticmethod
    def calculate_centroid(geometry: dict[str, Any]) -> tuple[float, float] | None:
        """Calculate centroid (latitude, longitude) from GeoJSON geometry.

        Supports Point, Polygon, MultiPolygon, and GeometryCollection.
        GeoJSON stores coordinates in [longitude, latitude] order.
        Returns (latitude, longitude) or None if coordinates cannot be extracted.
        """
        if not geometry:
            return None

        geom_type = geometry.get("type")
        coords = geometry.get("coordinates")

        if geom_type == "FeatureCollection":
            features = geometry.get("features", [])
            for feat in features:
                sub_geom = feat.get("geometry", {})
                if sub_geom.get("type") == "Point":
                    return BaseHazardProvider.calculate_centroid(sub_geom)
            for feat in features:
                sub_geom = feat.get("geometry", {})
                result = BaseHazardProvider.calculate_centroid(sub_geom)
                if result is not None:
                    return result
            return None

        if geom_type == "Feature":
            return BaseHazardProvider.calculate_centroid(geometry.get("geometry", {}))

        if geom_type == "Point" and coords and len(coords) >= 2:
            return float(coords[1]), float(coords[0])

        if geom_type == "GeometryCollection":
            geometries = geometry.get("geometries", [])
            for sub_geom in geometries:
                # Prefer explicit Point inside collection if available
                if sub_geom.get("type") == "Point":
                    return BaseHazardProvider.calculate_centroid(sub_geom)
            for sub_geom in geometries:
                result = BaseHazardProvider.calculate_centroid(sub_geom)
                if result is not None:
                    return result
            return None

        # Recursively collect all [lon, lat] pairs from Polygon or MultiPolygon
        points: list[tuple[float, float]] = []

        def _extract_points(data: Any) -> None:
            if not isinstance(data, list):
                return
            if len(data) >= 2 and isinstance(data[0], (int, float)) and isinstance(data[1], (int, float)):
                points.append((float(data[1]), float(data[0])))
                return
            for item in data:
                _extract_points(item)

        _extract_points(coords)

        if not points:
            return None

        # If polygon is closed, omit duplicate closing vertex
        if len(points) > 3 and points[0] == points[-1]:
            calc_points = points[:-1]
        else:
            calc_points = points

        # Compute centroid average
        avg_lat = sum(p[0] for p in calc_points) / len(calc_points)
        avg_lon = sum(p[1] for p in calc_points) / len(calc_points)
        return avg_lat, avg_lon

    @staticmethod
    def parse_datetime(val: Any) -> datetime:
        """Convert various agency date/timestamp formats to timezone-aware UTC datetime."""
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=UTC)

        if isinstance(val, (int, float)):
            # Check if timestamp is in milliseconds
            if val > 1e11:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=UTC)

        if not isinstance(val, str) or not val.strip():
            return datetime.now(UTC)

        str_val = val.strip()

        # Try ISO 8601
        try:
            # Handle trailing Z
            iso_str = str_val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass

        # Try RFC 2822 (e.g. "Thu, 15 Oct 2026 01:27:00 GMT")
        try:
            dt = parsedate_to_datetime(str_val)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass

        # Try specific Australian agency string formats
        formats = [
            "%d/%m/%Y %I:%M:%S %p",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y %H:%M",
            "%d %b %Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(str_val, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue

        # Fallback to now UTC
        return datetime.now(UTC)
