"""Operator feeds that add fresher readings and spill data to the BoM dam storages (#80).

The Bureau's Water Data Online is the national source (``dams.py``), but agencies send it
data about once a day. Two operators publish their own data under an open licence:

- **WaterNSW real-time data** (the Kisters Hydstra service the river gauges use, CC BY):
  storage gauges (``stntype`` ``STO``) with reservoir level ``130.00`` (m AHD, every 15 to
  60 minutes), volume (``130.00`` converted to ``136.00``, ML), and 24-hour totals to 9 am of
  spillway discharge ``453.00`` and total releases ``459.00`` (ML).
- **Hydro Tasmania lake levels** (https://www.hydro.com.au/water/water-information,
  CC BY 3.0 AU): metres below full and a "Spilling" comment per lake, updated daily.

A storage picked in the options flow is matched to its operator feed there and the match is
stored with it (``StorageSite.operator``). WaterNSW gauges are matched by readings, since
Water Data Online places some Sydney dams up to 20 km from the dam: a gauge within
WATERNSW_MATCH_KM whose level and volume agree with the Bureau's. Hydro Tasmania lakes are
matched by name. An operator feed that cannot be reached is skipped; the Bureau's reading
is used alone.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta, timezone
import html
import logging
import re
from typing import Any, Final
from zoneinfo import ZoneInfo

import aiohttp

from .dams import (
    OPERATOR_HYDRO_TASMANIA,
    OPERATOR_WATERNSW,
    OperatorReading,
    StorageReading,
    StorageSite,
    merge_operator,
)
from .rivers import KISTERS_SERVERS, RiverSourceError, async_kisters_call, haversine_km, parse_kisters_traces

_LOGGER = logging.getLogger(__name__)

HYDRO_TASMANIA_URL: Final = "https://www.hydro.com.au/water/water-information"
# Water Data Online owner codes whose storages WaterNSW gauges ("Water NSW" and its Sydney
# catchment, and the former NSW water department) and Hydro Tasmania's
WATERNSW_OWNERS: Final = frozenset({"w00231", "w00077"})
HYDRO_TASMANIA_OWNER: Final = "w00129"

# A WaterNSW gauge must be this close to the Bureau's storage position
WATERNSW_MATCH_KM: Final = 30.0
# ... and agree with the Bureau's reading: level within this many metres and volume within
# this share (both when both are known; at least one must be compared)
WATERNSW_LEVEL_TOLERANCE_M: Final = 0.5
WATERNSW_VOLUME_TOLERANCE: Final = 0.1
# Operator readings older than this are ignored
OPERATOR_READING_WINDOW: Final = timedelta(days=3)
# The WaterNSW storage gauge list changes rarely
WATERNSW_SITE_CACHE_TTL: Final = timedelta(hours=24)

_TIMEOUT: Final = aiohttp.ClientTimeout(total=30)
_HEADERS: Final = {"User-Agent": "HomeAssistant-AusNZDisasterWatch/1.0"}
_AEST: Final = timezone(timedelta(hours=10))
_HOBART: Final = ZoneInfo("Australia/Hobart")
_NSW = KISTERS_SERVERS["nsw"]
_MONTHS: Final = {
    name: number
    for number, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}
_NAME_STOP_WORDS: Final = frozenset({"lake", "lagoon", "lagoons", "pond", "at", "dam", "the", "intake", "inlet", "no"})

# WaterNSW storage gauges: (fetched at, gauges)
_GAUGE_CACHE: dict[str, tuple[datetime, list[WaterNSWGauge]]] = {}


@dataclass(frozen=True, slots=True)
class WaterNSWGauge:
    """A WaterNSW storage gauge."""

    station: str
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class HydroLake:
    """One row of Hydro Tasmania's lake level table."""

    name: str
    metres_below_full: float | None
    spilling: bool


# --- WaterNSW --------------------------------------------------------------------------


def parse_waternsw_gauges(result: dict[str, Any]) -> list[WaterNSWGauge]:
    """Return the storage gauges with coordinates from a ``get_db_info`` site table."""
    gauges: list[WaterNSWGauge] = []
    rows = result.get("rows")
    for row in rows if isinstance(rows, list) else []:
        try:
            gauge = WaterNSWGauge(
                station=str(row["station"]),
                name=str(row.get("stname") or row["station"]).strip(),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if (gauge.latitude, gauge.longitude) != (0.0, 0.0):
            gauges.append(gauge)
    return gauges


async def async_waternsw_gauges(session: aiohttp.ClientSession, now: datetime) -> list[WaterNSWGauge]:
    """Return WaterNSW's active storage gauges, fetched at most once a day."""
    if (cached := _GAUGE_CACHE.get("nsw")) and now - cached[0] < WATERNSW_SITE_CACHE_TTL:
        return cached[1]
    result = await async_kisters_call(
        session,
        _NSW,
        "get_db_info",
        {
            "table_name": "site",
            "return_type": "array",
            "field_list": ["station", "stname", "latitude", "longitude"],
            "filter_values": {"active": True, "stntype": "STO"},
        },
        "3",
    )
    gauges = parse_waternsw_gauges(result)
    _GAUGE_CACHE["nsw"] = (now, gauges)
    return gauges


def _traces_params(
    stations: Iterable[str], variables: tuple[str, str], now: datetime, *, daily: bool
) -> dict[str, Any]:
    """Return ``get_ts_traces`` parameters for the stations over the operator window."""
    local = now.astimezone(_AEST)
    start = local - OPERATOR_READING_WINDOW
    if daily:
        # Daily totals run 9 am to 9 am
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
    return {
        "site_list": ",".join(stations),
        "datasource": _NSW.datasource,
        "varfrom": variables[0],
        "varto": variables[1],
        "start_time": start.strftime("%Y%m%d%H%M%S"),
        "end_time": (local + timedelta(hours=1)).strftime("%Y%m%d%H%M%S"),
        "data_type": "tot" if daily else "point",
        "interval": "day" if daily else "hour",
        "multiplier": "1",
    }


async def async_waternsw_readings(
    session: aiohttp.ClientSession, stations: list[str], now: datetime
) -> dict[str, OperatorReading]:
    """Return each WaterNSW station's latest level, volume and daily spill and release totals.

    Raises RiverSourceError when the service cannot be reached.
    """
    if not stations:
        return {}
    requests = {
        "level": (("130.00", "130.00"), False),
        "volume": (("130.00", "136.00"), False),
        "spill": (("453.00", "453.00"), True),
        "release": (("459.00", "459.00"), True),
    }
    results = await asyncio.gather(
        *(
            async_kisters_call(
                session, _NSW, "get_ts_traces", _traces_params(stations, variables, now, daily=daily), "2"
            )
            for variables, daily in requests.values()
        )
    )
    series = {name: parse_kisters_traces(_NSW, result) for name, result in zip(requests, results, strict=True)}
    cutoff = now - OPERATOR_READING_WINDOW
    readings: dict[str, OperatorReading] = {}
    for station in stations:
        latest = {name: max(points[station], default=None) for name, points in series.items() if station in points}
        level, volume = latest.get("level"), latest.get("volume")
        spill, release = latest.get("spill"), latest.get("release")
        current = [point for point in (level, volume) if point is not None and point[0] >= cutoff]
        totals = [point for point in (spill, release) if point is not None and point[0] >= cutoff]
        if not current and not totals:
            continue
        readings[station] = OperatorReading(
            operator=OPERATOR_WATERNSW,
            observed_at=max(point[0] for point in current) if current else None,
            level_m=round(level[1], 3) if level is not None and level in current else None,
            volume_ml=round(volume[1], 1) if volume is not None and volume in current else None,
            spill_24h_ml=round(spill[1], 1) if spill is not None and spill in totals else None,
            release_24h_ml=round(release[1], 1) if release is not None and release in totals else None,
            totals_date=max(point[0] for point in totals).astimezone(_AEST).date().isoformat() if totals else None,
        )
    return readings


def match_waternsw(
    reading: StorageReading, gauges: list[WaterNSWGauge], gauge_readings: dict[str, OperatorReading]
) -> str | None:
    """Return the WaterNSW station that measures the same storage as the Bureau's reading.

    The gauge must be within WATERNSW_MATCH_KM and agree with the Bureau's level and volume
    (each compared when both sides have it, at least one compared). The closest level wins.
    """
    site = reading.site
    best: tuple[float, str] | None = None
    for gauge in gauges:
        if haversine_km(site.latitude, site.longitude, gauge.latitude, gauge.longitude) > WATERNSW_MATCH_KM:
            continue
        if (op := gauge_readings.get(gauge.station)) is None:
            continue
        scores: list[float] = []
        if reading.level_m is not None and op.level_m is not None:
            if abs(reading.level_m - op.level_m) > WATERNSW_LEVEL_TOLERANCE_M:
                continue
            scores.append(abs(reading.level_m - op.level_m) / WATERNSW_LEVEL_TOLERANCE_M)
        if reading.volume_ml and op.volume_ml is not None:
            share = abs(reading.volume_ml - op.volume_ml) / reading.volume_ml
            if share > WATERNSW_VOLUME_TOLERANCE:
                continue
            scores.append(share / WATERNSW_VOLUME_TOLERANCE)
        if scores and (best is None or min(scores) < best[0]):
            best = (min(scores), gauge.station)
    return best[1] if best else None


# --- Hydro Tasmania --------------------------------------------------------------------


def parse_hydro_lakes(text: str) -> tuple[list[HydroLake], date | None]:
    """Return the lakes and the "Last updated" date from Hydro Tasmania's water information page.

    Rows are ``Lake | Metres from full | Comment``; region title rows and the page's
    navigation table are skipped. A lake listed twice is kept once.
    """
    lakes: dict[str, HydroLake] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL):
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        ]
        if len(cells) != 3 or not cells[0]:
            continue
        try:
            metres = float(cells[1])
        except ValueError:
            continue
        lakes.setdefault(cells[0], HydroLake(cells[0], metres, cells[2].casefold().startswith("spill")))
    updated = None
    if match := re.search(r"Last updated:\s*(\d{1,2})(?:[a-z]{2})?\s+([A-Za-z]+)\s+(\d{4})", text):
        day, month, year = match.groups()
        if (number := _MONTHS.get(month.casefold())) is not None:
            try:
                updated = date(int(year), number, int(day))
            except ValueError:
                updated = None
    return list(lakes.values()), updated


def _name_tokens(name: str) -> frozenset[str]:
    """Return the distinctive words of a lake name ("Lake Cethana" and "CETHANA LAKE - AT DAM" share "cethana")."""
    words = [word for word in re.findall(r"[a-z0-9]+", name.casefold()) if word not in _NAME_STOP_WORDS]
    # "Whitespur Pond" is "WHITE SPUR POND" at the Bureau
    return frozenset([*words, "".join(words)])


def match_hydro_lake(site: StorageSite, lakes: list[HydroLake]) -> str | None:
    """Return the Hydro Tasmania lake whose name matches the storage, if exactly one does.

    Every distinctive word of the lake's name, or of one of its "/"-separated parts
    ("Bradys/Binneys/Tungatinah"), must be in the Bureau's storage name.
    """
    storage = _name_tokens(site.name)
    hits = [
        lake.name
        for lake in lakes
        if any(
            (tokens := _name_tokens(part) - {""}) and (tokens <= storage or "".join(sorted(tokens)) in storage)
            for part in lake.name.split("/")
        )
    ]
    return hits[0] if len(hits) == 1 else None


async def async_hydro_lakes(session: aiohttp.ClientSession) -> tuple[list[HydroLake], date | None]:
    """Fetch Hydro Tasmania's lake table; raises RiverSourceError when it is unavailable."""
    try:
        async with session.get(HYDRO_TASMANIA_URL, headers=_HEADERS, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            text = await resp.text()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise RiverSourceError(f"Hydro Tasmania unavailable: {err}") from err
    lakes, updated = parse_hydro_lakes(text)
    if not lakes:
        raise RiverSourceError("Hydro Tasmania returned no lake table")
    return lakes, updated


def hydro_readings(lakes: list[HydroLake], updated: date | None, now: datetime) -> dict[str, OperatorReading]:
    """Return a reading per lake; none when the table is older than OPERATOR_READING_WINDOW."""
    observed = datetime.combine(updated, time(), _HOBART).astimezone(UTC) if updated else None
    if observed is None or observed < now - OPERATOR_READING_WINDOW:
        return {}
    return {
        lake.name: OperatorReading(
            operator=OPERATOR_HYDRO_TASMANIA,
            observed_at=observed,
            metres_below_full=lake.metres_below_full,
            spilling=lake.spilling,
        )
        for lake in lakes
    }


# --- Public API ------------------------------------------------------------------------


async def async_fetch_operator_readings(
    session: aiohttp.ClientSession, sites: list[StorageSite], now: datetime
) -> dict[str, OperatorReading]:
    """Return the operator reading of each storage with a matched feed, keyed by ``StorageSite.key``.

    A feed that cannot be reached is skipped (logged), so the Bureau's readings are used alone.
    """
    readings: dict[str, OperatorReading] = {}
    nsw = [site for site in sites if site.operator == OPERATOR_WATERNSW and site.operator_id]
    tas = [site for site in sites if site.operator == OPERATOR_HYDRO_TASMANIA and site.operator_id]
    if nsw:
        try:
            by_station = await async_waternsw_readings(
                session, list(dict.fromkeys(str(site.operator_id) for site in nsw)), now
            )
        except RiverSourceError as err:
            _LOGGER.debug("WaterNSW storages unavailable: %s", err)
        else:
            readings.update(
                {site.key: by_station[str(site.operator_id)] for site in nsw if site.operator_id in by_station}
            )
    if tas:
        try:
            lakes, updated = await async_hydro_lakes(session)
        except RiverSourceError as err:
            _LOGGER.debug("Hydro Tasmania lakes unavailable: %s", err)
        else:
            by_lake = hydro_readings(lakes, updated, now)
            readings.update({site.key: by_lake[str(site.operator_id)] for site in tas if site.operator_id in by_lake})
    return readings


async def async_attach_operators(
    session: aiohttp.ClientSession, readings: list[StorageReading], now: datetime
) -> list[StorageReading]:
    """Match discovered storages to their operator feed and merge the operator's reading.

    Used by the options flow; a storage without a match, or whose feed is unavailable, is
    returned unchanged.
    """
    matched: dict[str, StorageSite] = {}
    nsw = [reading for reading in readings if reading.site.owner in WATERNSW_OWNERS]
    if nsw:
        try:
            gauges = await async_waternsw_gauges(session, now)
            nearby = [
                gauge
                for gauge in gauges
                if any(
                    haversine_km(r.site.latitude, r.site.longitude, gauge.latitude, gauge.longitude)
                    <= WATERNSW_MATCH_KM
                    for r in nsw
                )
            ]
            gauge_readings = await async_waternsw_readings(session, [gauge.station for gauge in nearby], now)
        except RiverSourceError as err:
            _LOGGER.debug("WaterNSW storages unavailable for matching: %s", err)
        else:
            for reading in nsw:
                if station := match_waternsw(reading, nearby, gauge_readings):
                    matched[reading.site.key] = reading.site.with_operator(OPERATOR_WATERNSW, station)
    if any(reading.site.owner == HYDRO_TASMANIA_OWNER for reading in readings):
        try:
            lakes, _updated = await async_hydro_lakes(session)
        except RiverSourceError as err:
            _LOGGER.debug("Hydro Tasmania lakes unavailable for matching: %s", err)
        else:
            for reading in readings:
                if reading.site.owner == HYDRO_TASMANIA_OWNER and (lake := match_hydro_lake(reading.site, lakes)):
                    matched[reading.site.key] = reading.site.with_operator(OPERATOR_HYDRO_TASMANIA, lake)
    if not matched:
        return readings
    sites = list(matched.values())
    operator_readings = await async_fetch_operator_readings(session, sites, now)
    attached: list[StorageReading] = []
    for reading in readings:
        if (site := matched.get(reading.site.key)) is None:
            attached.append(reading)
            continue
        merged = merge_operator(site, replace(reading, site=site), operator_readings.get(site.key))
        attached.append(merged or replace(reading, site=site))
    return attached
