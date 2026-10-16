"""River and creek level gauges (#31).

Gauges are separate from the hazard providers: the user picks individual gauges near the
configured location in the options flow, and ``river_coordinator`` polls only those.

Two kinds of keyless source are supported:

- Kisters Hydstra ``webservice.exe`` JSON services: the Queensland Water Monitoring
  Information Portal (CC BY 4.0, stated in every response) and WaterNSW real-time data.
  Levels are variable ``100.00`` (stream water level, metres). Times are local standard
  time of the site (``site_details.timezone``, +10 for both services, no daylight saving).
- Hilltop ``data.hts`` XML servers run by New Zealand regional councils, measurement
  ``Stage``. Units are given per site (usually mm). Hilltop servers report times in New
  Zealand standard time (UTC+12) all year, without daylight saving.

Not used: Environment Canterbury (its Hilltop server returns no sites and the site is behind
a bot wall), Waikato (times out), Bay of Plenty, Otago and Nelson (no public Hilltop host
found), Environment Southland (404) and Gisborne (TLS failure). No open source publishes
flood classification levels in a machine-readable form, so gauges carry levels only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
import json
import logging
import math
import re
from typing import Any, Final
from urllib.parse import quote, urlencode

import aiohttp
import defusedxml.ElementTree as ET
from yarl import URL

from .const import STATE_ACT, STATE_NSW, STATE_NZ, STATE_QLD

_LOGGER = logging.getLogger(__name__)

# How often the selected gauges are polled. Gauges report every 5 to 60 minutes.
RIVER_SCAN_INTERVAL: Final = timedelta(minutes=15)
# Readings older than this are ignored; a gauge without a newer reading is unavailable.
RIVER_READING_WINDOW: Final = timedelta(hours=6)
# Trend compares the latest reading with the newest reading at least this much older.
TREND_PERIOD: Final = timedelta(hours=1)
# Level changes smaller than this (metres) over the trend period count as steady.
TREND_DEADBAND_M: Final = 0.01
# Site lists change rarely; they are fetched again after this long.
RIVER_SITE_CACHE_TTL: Final = timedelta(hours=24)
# Longest the options flow waits for gauge discovery.
RIVER_DISCOVERY_TIMEOUT: Final = timedelta(seconds=60)
# Gauges offered in the options flow, nearest first.
RIVER_GAUGE_CHOICES: Final = 10
# Nearest sites checked for current data before offering them.
_KISTERS_CANDIDATES: Final = 30
_HILLTOP_CANDIDATES: Final = 40
_HILLTOP_CONCURRENCY: Final = 6

TREND_RISING: Final = "rising"
TREND_FALLING: Final = "falling"
TREND_STEADY: Final = "steady"

_TIMEOUT: Final = aiohttp.ClientTimeout(total=30)
_HEADERS: Final = {"User-Agent": "HomeAssistant-AusNZDisasterWatch/1.0"}
# Hydstra quality codes of 150 and above mark missing or unusable values.
_KISTERS_BAD_QUALITY: Final = 150
# Hydstra error 126: "No data within specified period" (a valid, empty answer).
_KISTERS_NO_DATA: Final = 126
# Hydstra error 125: "No data for specified variable in file" (none of the sites has it,
# e.g. spillway discharge at the Sydney dams); also a valid, empty answer.
_KISTERS_NO_VARIABLE: Final = 125
_NZST: Final = timezone(timedelta(hours=12))
_HILLTOP_UNITS: Final[dict[str, float]] = {"mm": 0.001, "cm": 0.01, "m": 1.0}
# Hilltop "Stage" also covers groundwater: bores named by map sheet (R27/1171, BQ32/0022)
# or described as wells, bores or GND sites. They are not offered as river gauges.
_GROUNDWATER_NAME: Final = re.compile(
    r"^[A-Z]{1,2}\d{2}/\d+$|\b(?:wells?|bores?|groundwater|ground water|GND\d+)\b", re.IGNORECASE
)

# Discovered site lists per source: (fetched at, sites).
_SITE_CACHE: dict[str, tuple[datetime, list[GaugeSite]]] = {}


class RiverSourceError(Exception):
    """A gauge service could not be reached or returned an unusable response."""


@dataclass(frozen=True, slots=True)
class KistersServer:
    """A Kisters Hydstra web service with telemetered stream gauges."""

    host: str
    datasource: str
    station_types: tuple[str, ...]
    attribution: str
    default_utc_offset: float = 10.0


@dataclass(frozen=True, slots=True)
class HilltopServer:
    """A New Zealand regional council Hilltop server."""

    url: str
    attribution: str


KISTERS_SERVERS: Final[dict[str, KistersServer]] = {
    "qld": KistersServer(
        host="water-monitoring.information.qld.gov.au",
        datasource="AT",
        # G/GQ: gauging stations; M/MA: manual and automatic river stations
        station_types=("G", "GQ", "M", "MA"),
        attribution="© State of Queensland, Water Monitoring Information Portal, CC BY 4.0",
    ),
    "nsw": KistersServer(
        host="realtimedata.waternsw.com.au",
        datasource="CP",
        station_types=("STR",),
        attribution="© State Government of NSW and WaterNSW, CC BY",
    ),
}

HILLTOP_SERVERS: Final[dict[str, HilltopServer]] = {
    "hilltop_gw": HilltopServer("https://hilltop.gw.govt.nz/Data.hts", "Greater Wellington Regional Council"),
    "hilltop_horizons": HilltopServer("https://hilltopserver.horizons.govt.nz/data.hts", "Horizons Regional Council"),
    "hilltop_hbrc": HilltopServer(
        "https://data.hbrc.govt.nz/Envirodata/EMAR.hts", "Hawke's Bay Regional Council, CC BY"
    ),
    "hilltop_tasman": HilltopServer("https://envdata.tasman.govt.nz/data.hts", "Tasman District Council"),
    "hilltop_nrc": HilltopServer("https://hilltop.nrc.govt.nz/Data.hts", "Northland Regional Council"),
    "hilltop_wcrc": HilltopServer("https://hilltop.wcrc.govt.nz/Data.hts", "West Coast Regional Council"),
    "hilltop_trc": HilltopServer("https://extranet.trc.govt.nz/getdata/merged.hts", "Taranaki Regional Council"),
    "hilltop_mdc": HilltopServer("https://hydro.marlborough.govt.nz/data.hts", "Marlborough District Council"),
}

# Sources searched for each configured state. Neighbouring Kisters services are included so
# border locations (e.g. the Gold Coast hinterland and the Tweed) see gauges on both sides.
STATE_RIVER_SOURCES: Final[dict[str, tuple[str, ...]]] = {
    STATE_QLD: ("qld", "nsw"),
    STATE_NSW: ("nsw", "qld"),
    STATE_ACT: ("nsw",),
    STATE_NZ: tuple(HILLTOP_SERVERS),
}


def _optional_float(value: Any) -> float | None:
    """Return value as a float, or None when it is missing or not a number."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class GaugeSite:
    """A selected gauge, stored in the config entry options."""

    source: str
    site_id: str
    name: str
    latitude: float
    longitude: float
    # User-entered level (m) at which the gauge's alert binary sensor turns on; None for none
    alert_level_m: float | None = None

    @property
    def key(self) -> str:
        """Return the identifier used in options and unique IDs."""
        return f"{self.source}:{self.site_id}"

    @property
    def attribution(self) -> str:
        """Return the data attribution for this gauge's source."""
        if server := KISTERS_SERVERS.get(self.source):
            return server.attribution
        return HILLTOP_SERVERS[self.source].attribution

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form for the config entry options."""
        data: dict[str, Any] = {
            "source": self.source,
            "site_id": self.site_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }
        if self.alert_level_m is not None:
            data["alert_level_m"] = self.alert_level_m
        return data

    def with_alert_level(self, level: float | None) -> GaugeSite:
        """Return this gauge with a different alert level."""
        return replace(self, alert_level_m=level)

    @classmethod
    def from_dict(cls, data: Any) -> GaugeSite | None:
        """Return a gauge from stored options, or None if the entry is unusable."""
        try:
            source = str(data["source"])
            site = cls(
                source=source,
                site_id=str(data["site_id"]),
                name=str(data["name"]),
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                alert_level_m=_optional_float(data.get("alert_level_m")),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if source not in KISTERS_SERVERS and source not in HILLTOP_SERVERS:
            return None
        return site


@dataclass(frozen=True, slots=True)
class GaugeReading:
    """The latest level of a gauge."""

    site: GaugeSite
    level_m: float
    observed_at: datetime
    trend: str | None
    change_m: float | None


def sites_from_options(value: Any) -> list[GaugeSite]:
    """Return the usable gauges stored under the river gauge option."""
    if not isinstance(value, list):
        return []
    sites: dict[str, GaugeSite] = {}
    for item in value:
        if (site := GaugeSite.from_dict(item)) is not None:
            sites.setdefault(site.key, site)
    return list(sites.values())


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_trend(points: Iterable[tuple[datetime, float]]) -> tuple[str | None, float | None]:
    """Return (trend, change in metres) of a gauge over the last hour.

    The latest reading is compared with the newest reading taken at least TREND_PERIOD
    earlier. Without such a reading the trend is unknown (None). Changes within
    TREND_DEADBAND_M are "steady".
    """
    ordered = sorted(points)
    if len(ordered) < 2:
        return None, None
    latest_time, latest_value = ordered[-1]
    earlier = [value for time, value in ordered[:-1] if time <= latest_time - TREND_PERIOD]
    if not earlier:
        return None, None
    change = round(latest_value - earlier[-1], 3)
    if change > TREND_DEADBAND_M:
        return TREND_RISING, change
    if change < -TREND_DEADBAND_M:
        return TREND_FALLING, change
    return TREND_STEADY, change


def _reading(site: GaugeSite, points: list[tuple[datetime, float]]) -> GaugeReading | None:
    """Return the latest reading of a series, or None if it has no points."""
    if not points:
        return None
    observed_at, level = max(points)
    trend, change = calculate_trend(points)
    return GaugeReading(site=site, level_m=round(level, 3), observed_at=observed_at, trend=trend, change_m=change)


async def _async_get(session: aiohttp.ClientSession, url: URL, *, as_json: bool) -> Any:
    """GET a URL and return decoded JSON or text, raising RiverSourceError on failure."""
    try:
        async with session.get(url, headers=_HEADERS, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            if as_json:
                return await resp.json(content_type=None)
            return await resp.text()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise RiverSourceError(f"{url.host} unavailable: {err}") from err


# --- Kisters Hydstra -------------------------------------------------------------------


def kisters_url(server: KistersServer, function: str, params: dict[str, Any], version: str) -> URL:
    """Return a web service URL; the JSON request is the URL-encoded query string."""
    request = json.dumps({"function": function, "version": version, "params": params}, separators=(",", ":"))
    return URL(f"https://{server.host}/cgi/webservice.exe?{quote(request, safe='')}", encoded=True)


async def _async_kisters_call(
    session: aiohttp.ClientSession, server: KistersServer, function: str, params: dict[str, Any], version: str
) -> dict[str, Any]:
    """Call a Hydstra function and return its ``return`` object ({} when there is no data)."""
    payload = await _async_get(session, kisters_url(server, function, params, version), as_json=True)
    if not isinstance(payload, dict):
        raise RiverSourceError(f"{server.host} returned an unexpected payload")
    error = payload.get("error_num", 0)
    if error in (_KISTERS_NO_DATA, _KISTERS_NO_VARIABLE):
        return {}
    if error:
        raise RiverSourceError(f"{server.host} {function} error {error}: {payload.get('error_msg')}")
    result = payload.get("return")
    if not isinstance(result, dict):
        raise RiverSourceError(f"{server.host} {function} returned no result")
    return result


# Public name for the dam storage operator feeds, which read the same WaterNSW service
async_kisters_call = _async_kisters_call


def _kisters_time(value: Any, offset: timezone) -> datetime:
    """Parse a Hydstra ``YYYYMMDDHHMMSS`` local time."""
    return datetime.strptime(str(value), "%Y%m%d%H%M%S").replace(tzinfo=offset).astimezone(UTC)


def _kisters_offset(details: Any, server: KistersServer) -> timezone:
    """Return the site's fixed UTC offset from ``site_details.timezone`` (hours)."""
    try:
        hours = float(details.get("timezone"))
    except (AttributeError, TypeError, ValueError):
        hours = server.default_utc_offset
    return timezone(timedelta(hours=hours))


def parse_kisters_traces(server: KistersServer, result: dict[str, Any]) -> dict[str, list[tuple[datetime, float]]]:
    """Return each site's valid (time, level) points from a ``get_ts_traces`` result."""
    series: dict[str, list[tuple[datetime, float]]] = {}
    traces = result.get("traces", [])
    if not isinstance(traces, list):
        raise RiverSourceError(f"{server.host} returned malformed traces")
    for trace in traces:
        if not isinstance(trace, dict) or trace.get("error_num") or "site" not in trace:
            continue
        offset = _kisters_offset(trace.get("site_details"), server)
        points: list[tuple[datetime, float]] = []
        for point in trace.get("trace") or []:
            try:
                if int(point.get("q", 0)) >= _KISTERS_BAD_QUALITY:
                    continue
                points.append((_kisters_time(point["t"], offset), float(point["v"])))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
        series[str(trace["site"])] = points
    return series


def _kisters_window(server: KistersServer, now: datetime) -> dict[str, str]:
    """Return the start and end of the reading window in the service's local time."""
    local = now.astimezone(timezone(timedelta(hours=server.default_utc_offset)))
    return {
        "start_time": (local - RIVER_READING_WINDOW).strftime("%Y%m%d%H%M%S"),
        "end_time": (local + timedelta(hours=1)).strftime("%Y%m%d%H%M%S"),
    }


async def async_kisters_series(
    session: aiohttp.ClientSession, server: KistersServer, site_ids: list[str], now: datetime
) -> dict[str, list[tuple[datetime, float]]]:
    """Fetch recent stream levels for several sites in one request."""
    params = {
        "site_list": ",".join(site_ids),
        "datasource": server.datasource,
        "varfrom": "100.00",
        "varto": "100.00",
        **_kisters_window(server, now),
        "data_type": "point",
        "interval": "hour",
        "multiplier": "1",
    }
    result = await _async_kisters_call(session, server, "get_ts_traces", params, "2")
    return parse_kisters_traces(server, result)


async def async_kisters_sites(session: aiohttp.ClientSession, source: str) -> list[GaugeSite]:
    """Return active stream gauges with live telemetry and coordinates."""
    server = KISTERS_SERVERS[source]
    live_result = await _async_kisters_call(
        session, server, "get_sites_by_datasource", {"datasources": [server.datasource]}, "1"
    )
    live: set[str] = set()
    for entry in live_result.get("datasources") or []:
        # Skip malformed entries like the db_info loop below skips malformed rows
        if isinstance(entry, dict) and isinstance(listed := entry.get("sites"), list):
            live.update(str(site) for site in listed)
    tables = await asyncio.gather(
        *(
            _async_kisters_call(
                session,
                server,
                "get_db_info",
                {
                    "table_name": "site",
                    "return_type": "array",
                    "field_list": ["station", "stname", "latitude", "longitude"],
                    "filter_values": {"active": True, "stntype": station_type},
                },
                "3",
            )
            for station_type in server.station_types
        )
    )
    sites: dict[str, GaugeSite] = {}
    for table in tables:
        rows = table.get("rows")
        for row in rows if isinstance(rows, list) else []:
            try:
                station = str(row["station"])
                lat, lon = float(row["latitude"]), float(row["longitude"])
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if station in live and (lat, lon) != (0.0, 0.0):
                name = str(row.get("stname") or station).strip()
                sites.setdefault(station, GaugeSite(source, station, name, lat, lon))
    return list(sites.values())


# --- Hilltop ---------------------------------------------------------------------------


def hilltop_url(server: HilltopServer, **params: str) -> URL:
    """Return a Hilltop request URL (spaces encoded as %20, which Hilltop requires)."""
    query = urlencode({"Service": "Hilltop", **params}, quote_via=quote)
    return URL(f"{server.url}?{query}", encoded=True)


def parse_hilltop_sites(source: str, text: str) -> list[GaugeSite]:
    """Return the sites with coordinates from a ``SiteList`` response."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise RiverSourceError(f"{source} returned an invalid site list: {err}") from err
    if root.tag != "HilltopServer":
        raise RiverSourceError(f"{source} returned an unexpected document <{root.tag}>")
    sites: list[GaugeSite] = []
    for element in root.findall("Site"):
        name = element.get("Name")
        try:
            lat = float(element.findtext("Latitude") or "")
            lon = float(element.findtext("Longitude") or "")
        except ValueError:
            continue
        if name and not _GROUNDWATER_NAME.search(name):
            sites.append(GaugeSite(source, name, name, lat, lon))
    return sites


def parse_hilltop_data(source: str, text: str) -> list[tuple[datetime, float]]:
    """Return (time, level in metres) points from a ``GetData`` response.

    A ``<HilltopServer><Error>`` answer (no data in the window) is an empty series.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise RiverSourceError(f"{source} returned invalid data: {err}") from err
    if root.tag == "HilltopServer" and root.find("Error") is not None:
        return []
    if root.tag != "Hilltop":
        raise RiverSourceError(f"{source} returned an unexpected document <{root.tag}>")
    units = (root.findtext(".//ItemInfo/Units") or "").strip().lower()
    if (factor := _HILLTOP_UNITS.get(units)) is None:
        raise RiverSourceError(f"{source} reports Stage in unsupported units {units!r}")
    points: list[tuple[datetime, float]] = []
    for element in root.iter("E"):
        try:
            observed = datetime.fromisoformat(element.findtext("T") or "").replace(tzinfo=_NZST).astimezone(UTC)
            points.append((observed, float(element.findtext("I1") or "") * factor))
        except ValueError:
            continue
    return points


async def async_hilltop_sites(session: aiohttp.ClientSession, source: str) -> list[GaugeSite]:
    """Return a council's sites that have a Stage measurement."""
    server = HILLTOP_SERVERS[source]
    text = await _async_get(
        session, hilltop_url(server, Request="SiteList", Location="LatLong", Measurement="Stage"), as_json=False
    )
    return parse_hilltop_sites(source, text)


async def async_hilltop_series(session: aiohttp.ClientSession, site: GaugeSite) -> list[tuple[datetime, float]]:
    """Fetch a Hilltop site's Stage readings within the reading window."""
    server = HILLTOP_SERVERS[site.source]
    hours = int(RIVER_READING_WINDOW.total_seconds() // 3600)
    url = hilltop_url(server, Request="GetData", Site=site.site_id, Measurement="Stage", TimeInterval=f"PT{hours}H/now")
    return parse_hilltop_data(site.source, await _async_get(session, url, as_json=False))


# --- Public API ------------------------------------------------------------------------


async def async_fetch_readings(
    session: aiohttp.ClientSession, sites: list[GaugeSite], now: datetime
) -> tuple[dict[str, GaugeReading], set[str]]:
    """Fetch the latest reading of each site.

    Returns the readings keyed by ``GaugeSite.key`` and the keys whose service could not be
    reached. A site that answered but has no reading in the window is in neither.
    """
    readings: dict[str, GaugeReading] = {}
    failed: set[str] = set()

    async def _kisters(source: str, group: list[GaugeSite]) -> None:
        try:
            series = await async_kisters_series(session, KISTERS_SERVERS[source], [s.site_id for s in group], now)
        except RiverSourceError as err:
            _LOGGER.debug("River gauges from %s unavailable: %s", source, err)
            failed.update(site.key for site in group)
            return
        for site in group:
            if reading := _reading(site, series.get(site.site_id, [])):
                readings[site.key] = reading

    async def _hilltop(site: GaugeSite) -> None:
        try:
            points = await async_hilltop_series(session, site)
        except RiverSourceError as err:
            _LOGGER.debug("River gauge %s unavailable: %s", site.key, err)
            failed.add(site.key)
            return
        if reading := _reading(site, points):
            readings[site.key] = reading

    groups: dict[str, list[GaugeSite]] = {}
    for site in sites:
        groups.setdefault(site.source, []).append(site)
    tasks = []
    for source, group in groups.items():
        if source in KISTERS_SERVERS:
            tasks.append(_kisters(source, group))
        else:
            tasks.extend(_hilltop(site) for site in group)
    await asyncio.gather(*tasks)
    cutoff = now - RIVER_READING_WINDOW
    return {key: reading for key, reading in readings.items() if reading.observed_at >= cutoff}, failed


async def _async_cached_sites(session: aiohttp.ClientSession, source: str, now: datetime) -> list[GaugeSite]:
    """Return a source's site list, fetching it at most once per RIVER_SITE_CACHE_TTL."""
    if (cached := _SITE_CACHE.get(source)) and now - cached[0] < RIVER_SITE_CACHE_TTL:
        return cached[1]
    if source in KISTERS_SERVERS:
        sites = await async_kisters_sites(session, source)
    else:
        sites = await async_hilltop_sites(session, source)
    _SITE_CACHE[source] = (now, sites)
    return sites


def nearest_sites(sites: Iterable[GaugeSite], latitude: float, longitude: float, radius_km: float) -> list[GaugeSite]:
    """Return sites within the radius, nearest first."""
    distances = [(haversine_km(latitude, longitude, s.latitude, s.longitude), s.key, s) for s in sites]
    return [site for distance, _key, site in sorted(distances) if distance <= radius_km]


async def async_discover_gauges(
    session: aiohttp.ClientSession,
    *,
    state: str,
    latitude: float,
    longitude: float,
    radius_km: float,
    now: datetime,
) -> list[GaugeReading]:
    """Return the nearest gauges within the radius that report a current level, nearest first.

    Each source is searched independently; RiverSourceError is raised only if every source
    for the state failed.
    """
    sources = STATE_RIVER_SOURCES.get(state.upper(), ())
    if not sources:
        return []
    results = await asyncio.gather(
        *(_async_cached_sites(session, source, now) for source in sources), return_exceptions=True
    )
    candidates: list[GaugeSite] = []
    failures: list[str] = []
    for source, result in zip(sources, results, strict=True):
        if isinstance(result, RiverSourceError):
            _LOGGER.debug("River gauge list from %s unavailable: %s", source, result)
            failures.append(str(result))
        elif isinstance(result, BaseException):
            raise result
        else:
            candidates.extend(result)
    if len(failures) == len(sources):
        raise RiverSourceError("; ".join(failures))

    nearby = nearest_sites(candidates, latitude, longitude, radius_km)
    kisters = [site for site in nearby if site.source in KISTERS_SERVERS][:_KISTERS_CANDIDATES]
    hilltop = [site for site in nearby if site.source in HILLTOP_SERVERS][:_HILLTOP_CANDIDATES]
    found: dict[str, GaugeReading] = {}
    if kisters:
        readings, _failed = await async_fetch_readings(session, kisters, now)
        found.update(readings)
    for start in range(0, len(hilltop), _HILLTOP_CONCURRENCY):
        if len(found) >= RIVER_GAUGE_CHOICES:
            break
        readings, _failed = await async_fetch_readings(session, hilltop[start : start + _HILLTOP_CONCURRENCY], now)
        found.update(readings)
    return [found[site.key] for site in nearby if site.key in found][:RIVER_GAUGE_CHOICES]
