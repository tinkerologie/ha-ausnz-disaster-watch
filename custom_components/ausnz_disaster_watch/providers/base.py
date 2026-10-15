"""Base hazard provider definition and utilities for state emergency feeds."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Iterable
import contextlib
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from email.utils import parsedate_to_datetime
import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any, ClassVar

import aiohttp

from custom_components.ausnz_disaster_watch.const import STATE_TIMEZONES
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
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Resolve agency time zones once at import. Home Assistant imports integration modules in
# an executor, so the tz database file reads never happen inside the event loop.
_ZONES: dict[str, tzinfo] = {
    name: zone for name in {"UTC", *STATE_TIMEZONES.values()} if (zone := dt_util.get_time_zone(name)) is not None
}

# Fixed offsets for zone abbreviations agencies append to local timestamps (e.g. ACT ESA
# "2026-10-15 20:46 AEDT").
_TZ_ABBREVIATIONS: dict[str, timezone] = {
    "AEST": timezone(timedelta(hours=10)),
    "AEDT": timezone(timedelta(hours=11)),
    "ACST": timezone(timedelta(hours=9, minutes=30)),
    "ACDT": timezone(timedelta(hours=10, minutes=30)),
    "AWST": timezone(timedelta(hours=8)),
    "NZST": timezone(timedelta(hours=12)),
    "NZDT": timezone(timedelta(hours=13)),
}
_TZ_ABBREVIATION_RE = re.compile(r"\s+(" + "|".join(_TZ_ABBREVIATIONS) + r")$", re.IGNORECASE)

_LOCAL_FORMATS = (
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %I:%M %p",
    "%d/%m/%Y %H:%M",
    "%d %b %Y %H:%M",
    # ACT ESA publishes timestamps such as "15 Oct 2026 15:14:49.77".
    "%d %b %Y %H:%M:%S.%f",
    "%d %b %Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


class ProviderUnavailableError(Exception):
    """A provider could not fetch or decode its feed (as opposed to a valid, empty feed) (#16)."""


# Errors that mean "this one upstream record is malformed": skip the record, keep the feed.
# pydantic's ValidationError is a ValueError subclass.
MALFORMED_ITEM_ERRORS: tuple[type[Exception], ...] = (ValueError, TypeError, KeyError, AttributeError, IndexError)


def stable_id(prefix: str, *parts: object) -> str:
    """Return a deterministic identifier from stable upstream fields (#7).

    Unlike ``hash()``, the digest is identical across processes and restarts, and it
    does not depend on an item's position in the feed.
    """
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class BaseHazardProvider(ABC):
    """Abstract base provider for state and jurisdiction emergency feeds."""

    # IANA zone the agency publishes naive local timestamps in (see const.STATE_TIMEZONES)
    local_tz: ClassVar[str] = "UTC"

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
        """Fetch upstream endpoints, parse payload, and return canonical hazard objects.

        Return a list on success (an empty list is a valid "no hazards" result). Raise
        ProviderUnavailableError when no hazard data could be fetched or decoded, so the
        coordinator can tell an outage apart from an all-clear (#16).
        """

    async def async_collect_sources(
        self,
        sources: Iterable[tuple[str, Callable[[], Awaitable[Any]], Callable[[Any], list[CanonicalHazard]]]],
    ) -> list[CanonicalHazard]:
        """Fetch and parse several endpoints; partial results are fine, all failing is not.

        Each source is ``(label, fetch, parse)``. A source fails when fetch or parse raises
        ProviderUnavailableError. Raises ProviderUnavailableError only if every source failed.
        """
        hazards: list[CanonicalHazard] = []
        failures: list[str] = []
        succeeded = 0
        for label, fetch, parse in sources:
            try:
                payload = await fetch()
                try:
                    parsed = parse(payload)
                except MALFORMED_ITEM_ERRORS as err:
                    # A structurally broken document fails this source only, not the others
                    raise ProviderUnavailableError(f"{label} returned a malformed payload: {err}") from err
                hazards.extend(parsed)
            except ProviderUnavailableError as err:
                _LOGGER.debug("%s source failed: %s", label, err)
                failures.append(str(err))
            else:
                succeeded += 1
        if not succeeded:
            raise ProviderUnavailableError("; ".join(failures) or "no sources configured")
        return hazards

    @staticmethod
    def require_list(payload: dict[str, Any], field: str, label: str) -> list[Any]:
        """Return ``payload[field]`` if it is a list (an empty list is a valid feed).

        A missing or non-list collection is a broken response, so it raises
        ProviderUnavailableError instead of being read as "no hazards".
        """
        value = payload.get(field)
        if not isinstance(value, list):
            raise ProviderUnavailableError(f"{label} returned an unexpected payload ({field!r} is not a list)")
        return value

    @staticmethod
    def require_xml_root(root: Any, kind: str, label: str) -> None:
        """Raise ProviderUnavailableError unless ``root`` is an RSS document with a channel or an Atom feed.

        A well-formed XML error page parses fine but has no items; without this check it
        would be read as a healthy feed with no hazards.
        """
        if kind == "rss":
            ok = root.tag == "rss" and root.find("channel") is not None
        else:
            ok = root.tag == "{http://www.w3.org/2005/Atom}feed"
        if not ok:
            raise ProviderUnavailableError(f"{label} returned an unexpected document <{root.tag}>")

    @staticmethod
    def require_dict(payload: Any, label: str) -> dict[str, Any]:
        """Return payload if it is a JSON object, else raise ProviderUnavailableError."""
        if not isinstance(payload, dict):
            raise ProviderUnavailableError(f"{label} returned an unexpected payload")
        return payload

    async def async_fetch_feed_text(self, url: str, label: str, headers: dict[str, str] | None = None) -> str:
        """Fetch a text/XML feed, raising ProviderUnavailableError on transport failure."""
        try:
            return await self.async_fetch_text(url, headers=headers)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ProviderUnavailableError(f"{label} unavailable: {err}") from err

    async def async_fetch_feed_json(self, url: str, label: str, headers: dict[str, str] | None = None) -> Any:
        """Fetch a JSON feed, raising ProviderUnavailableError on transport or decode failure."""
        try:
            return await self.async_fetch_json(url, headers=headers)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise ProviderUnavailableError(f"{label} unavailable: {err}") from err

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

    @classmethod
    def parse_datetime(cls, val: Any, local_tz: str | None = None) -> datetime | None:
        """Convert an agency timestamp to a timezone-aware UTC datetime, or None.

        Naive values are interpreted in the agency's local time zone (``local_tz`` or the
        provider's ``local_tz``), not UTC: Australian and NZ feeds publish local times. A
        trailing zone abbreviation (AEST, AEDT, ...) takes precedence. Ambiguous wall times
        during the daylight-saving fall-back hour resolve with ``fold=0``.

        Returns None when the value is missing or unparsable, so stale data is never
        presented as freshly updated.
        """
        zone = _ZONES.get(local_tz or cls.local_tz) or UTC

        if isinstance(val, datetime):
            return dt_util.as_utc(val if val.tzinfo else val.replace(tzinfo=zone))

        if isinstance(val, (int, float)) and not isinstance(val, bool):
            # Epoch seconds or milliseconds
            if val > 1e11:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=UTC)

        if not isinstance(val, str) or not val.strip():
            return None

        str_val = val.strip()
        if match := _TZ_ABBREVIATION_RE.search(str_val):
            zone = _TZ_ABBREVIATIONS[match.group(1).upper()]
            str_val = str_val[: match.start()].strip()

        parsed: datetime | None = None
        with contextlib.suppress(ValueError):
            parsed = datetime.fromisoformat(str_val)

        if parsed is None:
            try:
                parsed = parsedate_to_datetime(str_val)
                if parsed.tzinfo is None and str_val.endswith("-0000"):
                    # RFC 2822 "-0000" means UTC with unknown local zone
                    parsed = parsed.replace(tzinfo=UTC)
            except (TypeError, ValueError):
                parsed = None

        if parsed is None:
            for fmt in _LOCAL_FORMATS:
                try:
                    parsed = datetime.strptime(str_val, fmt)
                    break
                except ValueError:
                    continue

        if parsed is None:
            _LOGGER.debug("Unparsable timestamp from %s: %r", cls.__name__, val)
            return None

        return dt_util.as_utc(parsed if parsed.tzinfo else parsed.replace(tzinfo=zone))
