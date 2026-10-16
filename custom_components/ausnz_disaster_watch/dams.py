"""Dam and weir storage levels from Bureau of Meteorology Water Data Online.

Storages are separate from the hazard providers, like the river gauges (#31): the user
picks individual storages near the configured location in the options flow, and
``dam_coordinator`` polls only those.

Source: the Water Data Online KiWIS web service (``getTimeseriesList`` and
``getTimeseriesValues``). It carries every storage that water agencies report to the
Bureau under the Water Regulations 2008, with the station's full supply volume and level as
station attributes. The data stays the supplying agency's: Water Data Online's copyright
page lists each owner that licenses its data under CC BY 3.0 AU and the attribution it
asks for. Only those owners' storages are offered (``OWNER_ATTRIBUTIONS``); storages of
owners with other terms (e.g. Snowy Hydro) are skipped.

Agencies send data to the Bureau about once a day, so a reading is usually 12 to 48 hours
old. Where an operator publishes its own open data (WaterNSW, Hydro Tasmania), the storage
is matched to it in the options flow and ``dam_operators.py`` adds the fresher level and
spill data (``OperatorReading``, ``merge_operator``). Storages are a slow signal: they say a dam is above full supply (spilling, or using
its flood storage), not that a release has started. No open source publishes dam release
or gate operation notices in a machine-readable form under an open licence (#80).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import logging
import math
from typing import Any, Final

import aiohttp
from yarl import URL

from .rivers import haversine_km

_LOGGER = logging.getLogger(__name__)

KIWIS_URL: Final = "https://www.bom.gov.au/waterdata/services"
PARAM_VOLUME: Final = "Storage Volume"
PARAM_LEVEL: Final = "Storage Level"
# Series read per parameter, best first. Levels prefer the Bureau's PR02 series in metres
# AHD: some suppliers' own levels are relative to full supply level (Warragamba reads
# -2.0 m). Volumes prefer the supplier's series, which matches the full supply volume
# attribute; the PR02 "accessible volume" does not for every owner (Hydro Tasmania), but is
# the only volume for some storages (the Blue Mountains dams).
SERIES_PREFERENCE: Final[dict[str, tuple[str, ...]]] = {
    PARAM_LEVEL: ("PR02AHDQaQc.Merged.AsStored.1", "DMQaQc.Merged.AsStored.1"),
    PARAM_VOLUME: ("DMQaQc.Merged.AsStored.1", "PR02AVQaQc.Merged.AsStored.1"),
}

# Agencies report about once a day, so polling hourly is plenty.
DAM_SCAN_INTERVAL: Final = timedelta(hours=1)
# Readings older than this are ignored; a storage without a newer reading is unavailable.
DAM_READING_WINDOW: Final = timedelta(days=7)
# The 24 h change compares the latest volume with the newest one at least this much older.
CHANGE_PERIOD: Final = timedelta(hours=24)
# How far from the latest reading the earlier one may be for the change to count as 24 h.
CHANGE_WINDOW: Final = (timedelta(hours=18), timedelta(hours=36))
# Site lists change rarely; they are fetched again after this long.
DAM_SITE_CACHE_TTL: Final = timedelta(hours=24)
# Longest the options flow waits for storage discovery.
DAM_DISCOVERY_TIMEOUT: Final = timedelta(seconds=90)
# Storages offered in the options flow, nearest first.
DAM_CHOICES: Final = 15
# Nearest storages read at most while looking for DAM_CHOICES with a reading.
DAM_MAX_CANDIDATES: Final = 60
# Upstream dams are often outside the hazard radius (Wivenhoe is 65 km from Brisbane), so
# storages are searched at least this far out.
DAM_MIN_SEARCH_KM: Final = 150.0
# Series IDs per getTimeseriesValues request; about 1 kB of URL, well under server limits.
TS_IDS_PER_REQUEST: Final = 100
# Series tried per parameter: some listed series have no values for months.
MAX_CANDIDATES: Final = 3
# A storage counts as above full supply once it holds more than this share of its full
# supply volume (or its level is above full supply level).
FULL_SUPPLY_PERCENT: Final = 100.0

_TIMEOUT: Final = aiohttp.ClientTimeout(total=45)
_HEADERS: Final = {"User-Agent": "HomeAssistant-AusNZDisasterWatch/1.0"}
# Australian mainland and Tasmania; some stations carry swapped or placeholder coordinates.
_LAT_RANGE: Final = (-44.0, -9.0)
_LON_RANGE: Final = (112.0, 154.0)

ATTRIBUTION_SUFFIX: Final = "CC BY 3.0 AU, via Bureau of Meteorology Water Data Online"

# Data owner code -> attribution, from the "Data owners using the Creative Commons licence"
# table at https://www.bom.gov.au/waterdata/wiski-web-public/copyright.htm (2026-10-16).
# Only owners that report storages are listed. Icon Water asks for no attribution.
OWNER_ATTRIBUTIONS: Final[dict[str, str]] = {
    "w00002": "Icon Water",
    "w00013": "© Barwon Region Water Corporation (Barwon Water)",
    "w00028": "© Cairns Regional Council",
    "w00032": "© Central Highlands Region Water Corporation",
    "w00045": "© Coliban Region Water Corporation (Coliban Water)",
    "w00066": "© State of Queensland (Department of Local Government, Water and Volunteers)",
    "w00077": "© State of NSW (Department of Planning and Environment – Water)",
    "w00102": "© Gippsland and Southern Rural Water Corporation (Southern Rural Water)",
    "w00103": "© Gladstone Area Water Board",
    "w00114": "© Goulburn-Murray Rural Water Corporation (Goulburn-Murray Water)",
    "w00115": "© Grampians Wimmera Mallee Water Corporation (GWMWater)",
    "w00124": "© TasWater",
    "w00126": "© Hunter Water Corporation",
    "w00129": "© Hydro Tasmania (Hydro-electric Corporation)",
    "w00151": "© Melbourne Water Corporation (Melbourne Water)",
    "w00160": "© Commonwealth of Australia (Murray–Darling Basin Authority)",
    "w00172": "© North East Region Water Corporation (North East Water)",
    "w00189": "© Power and Water Corporation (Power and Water)",
    "w00191": "© Queensland Bulk Water Supply Authority (trading as Seqwater)",
    "w00198": "© Rockhampton Regional Council",
    "w00209": "© South Australian Water Corporation (SA Water)",
    "w00227": "© SunWater Limited A.C.N. 131034985",
    "w00231": "© WaterNSW",
    "w00238": "© Toowoomba Regional Council",
    "w00241": "© Townsville City Council",
    "w00247": "© Water Corporation",
    "w00257": "© Central Coast Council",
    "w00285": "© Livingstone Shire Council",
}

# Operator feeds that add fresher readings, spill and release data to a BoM storage.
OPERATOR_WATERNSW: Final = "waternsw"
OPERATOR_HYDRO_TASMANIA: Final = "hydro_tasmania"
OPERATOR_ATTRIBUTIONS: Final[dict[str, str]] = {
    OPERATOR_WATERNSW: "© State Government of NSW and WaterNSW, CC BY",
    OPERATOR_HYDRO_TASMANIA: "© Hydro Tasmania, CC BY 3.0 AU",
}

# Discovered storages: (fetched at, storages).
_SITE_CACHE: dict[str, tuple[datetime, list[StorageSite]]] = {}


class DamSourceError(Exception):
    """Water Data Online could not be reached or returned an unusable response."""


def _optional_float(value: Any) -> float | None:
    """Return value as a finite float, or None when it is missing or not a number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ts_tuple(value: Any) -> tuple[str, ...]:
    """Return stored series IDs as a tuple; a list or a single ID is accepted."""
    if isinstance(value, (list, tuple)):
        return tuple(str(ts) for ts in value if ts)
    return (str(value),) if value else ()


@dataclass(frozen=True, slots=True)
class StorageSite:
    """A selected storage, stored in the config entry options."""

    site_id: str
    name: str
    latitude: float
    longitude: float
    owner: str
    # Candidate series per parameter, best first; the first with data in the window is read
    volume_ts: tuple[str, ...]
    level_ts: tuple[str, ...]
    full_volume_ml: float | None
    full_level_m: float | None
    # Operator feed matched to this storage (OPERATOR_*) and its ID there, if any
    operator: str | None = None
    operator_id: str | None = None

    @property
    def key(self) -> str:
        """Return the identifier used in options and unique IDs."""
        return f"bom:{self.site_id}"

    @property
    def attribution(self) -> str:
        """Return the data owner's attribution and the licence, after the operator feed's."""
        bom = f"{OWNER_ATTRIBUTIONS[self.owner]}, {ATTRIBUTION_SUFFIX}"
        return f"{OPERATOR_ATTRIBUTIONS[self.operator]}; {bom}" if self.operator else bom

    @property
    def ts_ids(self) -> list[str]:
        """Return the time series this storage reads."""
        return [*self.volume_ts, *self.level_ts]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form for the config entry options."""
        data: dict[str, Any] = {
            "site_id": self.site_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "owner": self.owner,
            "volume_ts": list(self.volume_ts),
            "level_ts": list(self.level_ts),
            "full_volume_ml": self.full_volume_ml,
            "full_level_m": self.full_level_m,
        }
        if self.operator:
            data["operator"] = self.operator
            data["operator_id"] = self.operator_id
        return data

    def with_operator(self, operator: str | None, operator_id: str | None) -> StorageSite:
        """Return this storage with a different operator feed."""
        return replace(self, operator=operator, operator_id=operator_id)

    @classmethod
    def from_dict(cls, data: Any) -> StorageSite | None:
        """Return a storage from stored options, or None if the entry is unusable."""
        try:
            site = cls(
                site_id=str(data["site_id"]),
                name=str(data["name"]),
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                owner=str(data["owner"]),
                volume_ts=_ts_tuple(data.get("volume_ts")),
                level_ts=_ts_tuple(data.get("level_ts")),
                full_volume_ml=_optional_float(data.get("full_volume_ml")),
                full_level_m=_optional_float(data.get("full_level_m")),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        if site.owner not in OWNER_ATTRIBUTIONS or not site.ts_ids:
            return None
        operator, operator_id = data.get("operator"), data.get("operator_id")
        # An unknown or incomplete operator entry is dropped; the BoM storage still works
        if operator in OPERATOR_ATTRIBUTIONS and operator_id:
            return site.with_operator(str(operator), str(operator_id))
        return site


@dataclass(frozen=True, slots=True)
class OperatorReading:
    """The latest data from a storage operator's own feed."""

    operator: str
    observed_at: datetime | None
    level_m: float | None = None
    volume_ml: float | None = None
    # WaterNSW 24 h totals to 9 am: spillway discharge and total releases (ML)
    spill_24h_ml: float | None = None
    release_24h_ml: float | None = None
    totals_date: str | None = None
    # Hydro Tasmania: metres below full supply and its "Spilling" comment
    metres_below_full: float | None = None
    spilling: bool | None = None


@dataclass(frozen=True, slots=True)
class StorageReading:
    """The latest reading of a storage."""

    site: StorageSite
    observed_at: datetime
    volume_ml: float | None
    level_m: float | None
    change_24h_ml: float | None
    operator: OperatorReading | None = None
    # Which feed the level and volume come from: "bom" or the operator
    source: str = "bom"

    @property
    def spilling(self) -> bool | None:
        """Return the operator's spill signal: Hydro Tasmania's comment or WaterNSW spillway flow."""
        if (op := self.operator) is None:
            return None
        if op.spilling is not None:
            return op.spilling
        if op.spill_24h_ml is not None:
            return op.spill_24h_ml > 0
        return None

    @property
    def percent_full(self) -> float | None:
        """Return the volume as a share of full supply volume; above 100 when over full."""
        full = self.site.full_volume_ml
        if self.volume_ml is None or not full:
            return None
        return round(self.volume_ml / full * 100, 1)

    @property
    def above_full_supply(self) -> bool | None:
        """Return True when the storage is above full supply volume or level.

        An ungated dam above full supply is spilling; a gated flood-mitigation dam such as
        Wivenhoe is holding water in its flood storage compartment. Any of the signals
        counts: volume over full supply volume, level over full supply level, or an
        operator's spill signal (see ``spilling``). None when none of them is known.
        """
        signals: list[bool] = []
        if (percent := self.percent_full) is not None:
            signals.append(percent > FULL_SUPPLY_PERCENT)
        if self.level_m is not None and self.site.full_level_m is not None:
            signals.append(self.level_m > self.site.full_level_m)
        if (spilling := self.spilling) is not None:
            signals.append(spilling)
        return any(signals) if signals else None


def merge_operator(
    site: StorageSite, reading: StorageReading | None, operator: OperatorReading | None
) -> StorageReading | None:
    """Return the storage reading with the operator's data attached.

    When the operator's reading is newer than the Bureau's, its level is used: both are in
    metres AHD, and matching checked they agree. The volume stays the Bureau's, because it
    is measured against the Bureau's full supply volume (WaterNSW's storage tables differ
    by a few per cent, which would put a full dam over 100%); the operator's volume is used
    only without a BoM volume. The operator's spill and release data is always attached.
    Without a BoM reading the operator's alone is used.
    """
    if operator is None:
        return reading
    observed = operator.observed_at
    has_values = operator.level_m is not None or operator.volume_ml is not None
    if observed is not None and has_values and (reading is None or observed > reading.observed_at):
        bom_volume, bom_level = (reading.volume_ml, reading.level_m) if reading else (None, None)
        return StorageReading(
            site=site,
            observed_at=observed,
            volume_ml=bom_volume if bom_volume is not None else operator.volume_ml,
            level_m=operator.level_m if operator.level_m is not None else bom_level,
            change_24h_ml=reading.change_24h_ml if reading else None,
            operator=operator,
            source=operator.operator,
        )
    if reading is None:
        return None
    return replace(reading, operator=operator)


def sites_from_options(value: Any) -> list[StorageSite]:
    """Return the usable storages stored under the dam option."""
    if not isinstance(value, list):
        return []
    sites: dict[str, StorageSite] = {}
    for item in value:
        if (site := StorageSite.from_dict(item)) is not None:
            sites.setdefault(site.key, site)
    return list(sites.values())


def kiwis_url(request: str, **params: str) -> URL:
    """Return a Water Data Online KiWIS request URL."""
    return URL(KIWIS_URL).with_query(
        {"service": "kisters", "type": "queryServices", "format": "json", "request": request, **params}
    )


async def _async_get_json(session: aiohttp.ClientSession, url: URL) -> Any:
    """GET a KiWIS URL and return decoded JSON, raising DamSourceError on failure."""
    try:
        async with session.get(url, headers=_HEADERS, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise DamSourceError(f"Water Data Online unavailable: {err}") from err
    if isinstance(payload, dict) and payload.get("type") == "error":
        raise DamSourceError(f"Water Data Online error: {payload.get('message')}")
    return payload


def _in_australia(latitude: float, longitude: float) -> bool:
    """Return True for coordinates on the Australian mainland or Tasmania."""
    return _LAT_RANGE[0] <= latitude <= _LAT_RANGE[1] and _LON_RANGE[0] <= longitude <= _LON_RANGE[1]


def _parse_time(value: Any) -> datetime | None:
    """Return a KiWIS timestamp in UTC, or None when it is missing, invalid or has no offset.

    KiWIS sends ISO times with the station's offset; a time without one is not guessed (#13).
    """
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _first_value(rows: list[dict[str, Any]], field: str) -> float | None:
    """Return the first number found in ``field`` of the rows."""
    return next((value for row in rows if (value := _optional_float(row.get(field))) is not None), None)


def _candidates(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    """Return up to MAX_CANDIDATES distinct series IDs of the ranked rows."""
    return tuple(dict.fromkeys(str(row["ts_id"]) for row in rows))[:MAX_CANDIDATES]


def _table(payload: Any, what: str) -> list[dict[str, Any]]:
    """Return a KiWIS table (a header row, then value rows) as dicts; malformed rows are skipped."""
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise DamSourceError(f"Water Data Online returned an unexpected {what}")
    header = [str(field) for field in payload[0]]
    return [
        dict(zip(header, raw, strict=True)) for raw in payload[1:] if isinstance(raw, list) and len(raw) == len(header)
    ]


def parse_station_attributes(payload: Any) -> dict[str, dict[str, Any]]:
    """Return each station's full supply volume, level and data owner from ``getStationList``."""
    return {str(row.get("station_id")): row for row in _table(payload, "station list")}


def parse_storage_list(payload: Any, attributes: dict[str, dict[str, Any]], now: datetime) -> list[StorageSite]:
    """Return the storages with current data from a ``getTimeseriesList`` response.

    ``attributes`` are the station attributes from ``parse_station_attributes``. The
    response is a header row followed by one row per series. Each storage has a volume
    and usually a level series. Storages of owners without an open licence, with
    coordinates outside Australia (several stations carry swapped placeholders), without
    data in the reading window, or without a full supply volume and level are skipped.
    Water Data Online lists many storages under several station IDs at the same position,
    sometimes splitting level and volume between them (Warragamba, Prospect, the Perth
    dams). Stations of one owner at one position are merged into one storage, reading the
    series of each parameter in ``SERIES_PREFERENCE`` order, newest first. Some listed
    series have no values, so up to MAX_CANDIDATES are kept and the first with data is read.
    """
    cutoff = now - DAM_READING_WINDOW
    # place -> parameter -> [(rank, row)]; a lower rank is better
    places: dict[tuple[str, float, float], dict[str, list[tuple[tuple[int, float], dict[str, Any]]]]] = {}
    for series_row in _table(payload, "storage list"):
        row = {**attributes.get(str(series_row.get("station_id")), {}), **series_row}
        preference = SERIES_PREFERENCE.get(str(row.get("parametertype_name")), ())
        end = _parse_time(row.get("to"))
        owner = str(row.get("DATA_OWNER"))
        if row.get("ts_name") not in preference or end is None or end < cutoff or owner not in OWNER_ATTRIBUTIONS:
            continue
        lat, lon = _optional_float(row.get("station_latitude")), _optional_float(row.get("station_longitude"))
        if lat is None or lon is None or not _in_australia(lat, lon):
            continue
        row["_lat"], row["_lon"] = lat, lon
        rank = (preference.index(str(row["ts_name"])), -end.timestamp())
        places.setdefault((owner, round(lat, 3), round(lon, 3)), {}).setdefault(
            str(row["parametertype_name"]), []
        ).append((rank, row))

    sites: list[StorageSite] = []
    for series in places.values():
        volume_rows = [row for _rank, row in sorted(series.get(PARAM_VOLUME, []), key=lambda item: item[0])]
        level_rows = [row for _rank, row in sorted(series.get(PARAM_LEVEL, []), key=lambda item: item[0])]
        # Every place has at least one series
        main = (volume_rows or level_rows)[0]
        full_volume = _first_value(volume_rows + level_rows, "FullStorageVolume")
        full_level = _first_value(level_rows + volume_rows, "FullStorageLevel")
        # Percent full needs the full supply volume; a level-only storage needs the full level
        if not ((volume_rows and full_volume) or (level_rows and full_level is not None)):
            continue
        sites.append(
            StorageSite(
                site_id=str(main.get("station_id")),
                name=str(main.get("station_name") or main.get("station_id")).strip(),
                latitude=main["_lat"],
                longitude=main["_lon"],
                owner=str(main["DATA_OWNER"]),
                volume_ts=_candidates(volume_rows),
                level_ts=_candidates(level_rows),
                full_volume_ml=full_volume or None,
                full_level_m=full_level,
            )
        )
    return sites


def parse_values(payload: Any) -> dict[str, list[tuple[datetime, float]]]:
    """Return each series' (time, value) points from a ``getTimeseriesValues`` response."""
    if not isinstance(payload, list):
        raise DamSourceError("Water Data Online returned unexpected values")
    series: dict[str, list[tuple[datetime, float]]] = {}
    for item in payload:
        if not isinstance(item, dict) or "ts_id" not in item:
            continue
        points: list[tuple[datetime, float]] = []
        for point in item.get("data") or []:
            try:
                value = _optional_float(point[1])
                observed = _parse_time(point[0])
            except (IndexError, KeyError, TypeError):
                continue
            if value is not None and observed is not None:
                points.append((observed, value))
        series[str(item["ts_id"])] = points
    return series


def _change(points: list[tuple[datetime, float]]) -> float | None:
    """Return the change of the latest value over the last CHANGE_PERIOD, if known.

    The earlier reading is the one closest to CHANGE_PERIOD before the latest, and must lie
    within CHANGE_WINDOW (18 to 36 h) of it: a daily-reporting storage with a gap in its
    data would otherwise report a change over several days as a 24 h change.
    """
    if len(points) < 2:
        return None
    latest_time, latest = points[-1]
    low, high = CHANGE_WINDOW
    candidates = [(time, value) for time, value in points[:-1] if low <= latest_time - time <= high]
    if not candidates:
        return None
    _time, earlier = min(candidates, key=lambda point: abs(latest_time - point[0] - CHANGE_PERIOD))
    return round(latest - earlier, 1)


def _first_series(
    candidates: tuple[str, ...], series: dict[str, list[tuple[datetime, float]]]
) -> list[tuple[datetime, float]]:
    """Return the points of the first candidate series that has any, oldest first."""
    for ts in candidates:
        if points := series.get(ts):
            return sorted(points)
    return []


def build_reading(site: StorageSite, series: dict[str, list[tuple[datetime, float]]]) -> StorageReading | None:
    """Return a storage's latest reading from its series, or None without data."""
    volume = _first_series(site.volume_ts, series)
    level = _first_series(site.level_ts, series)
    if not volume and not level:
        return None
    observed = max(points[-1][0] for points in (volume, level) if points)
    return StorageReading(
        site=site,
        observed_at=observed,
        volume_ml=round(volume[-1][1], 1) if volume else None,
        level_m=round(level[-1][1], 3) if level else None,
        change_24h_ml=_change(volume),
    )


async def async_fetch_readings(
    session: aiohttp.ClientSession, sites: list[StorageSite], now: datetime
) -> dict[str, StorageReading]:
    """Fetch the latest reading of each storage, keyed by ``StorageSite.key``.

    Series are requested TS_IDS_PER_REQUEST at a time (one request for a typical selection),
    so a long selection cannot make the URL too long for the server. Raises DamSourceError
    when Water Data Online cannot be reached. A storage without a reading in the last
    DAM_READING_WINDOW is absent.
    """
    ts_ids = list(dict.fromkeys(ts for site in sites for ts in site.ts_ids))
    series: dict[str, list[tuple[datetime, float]]] = {}
    for start in range(0, len(ts_ids), TS_IDS_PER_REQUEST):
        url = kiwis_url(
            "getTimeseriesValues",
            ts_id=",".join(ts_ids[start : start + TS_IDS_PER_REQUEST]),
            period=f"P{DAM_READING_WINDOW.days}D",
            returnfields="Timestamp,Value,Quality Code",
        )
        series.update(parse_values(await _async_get_json(session, url)))
    cutoff = now - DAM_READING_WINDOW
    readings: dict[str, StorageReading] = {}
    for site in sites:
        if (reading := build_reading(site, series)) is not None and reading.observed_at >= cutoff:
            readings[site.key] = reading
    return readings


async def async_storage_sites(session: aiohttp.ClientSession, now: datetime) -> list[StorageSite]:
    """Return every storage with current data, fetching the list at most once a day."""
    if (cached := _SITE_CACHE.get("bom")) and now - cached[0] < DAM_SITE_CACHE_TTL:
        return cached[1]
    parameters = f"{PARAM_VOLUME},{PARAM_LEVEL}"
    # Two requests: asking getTimeseriesList for station attributes (ca_sta) as well takes
    # two minutes at busy times, while each request on its own takes seconds.
    series_url = kiwis_url(
        "getTimeseriesList",
        parametertype_name=parameters,
        ts_name=",".join(dict.fromkeys(name for names in SERIES_PREFERENCE.values() for name in names)),
        returnfields="station_id,station_name,station_latitude,station_longitude,ts_id,ts_name,parametertype_name,coverage",
    )
    stations_url = kiwis_url(
        "getStationList",
        parametertype_name=parameters,
        returnfields="station_id,ca_sta",
        ca_sta_returnfields="FullStorageVolume,FullStorageLevel,DATA_OWNER",
    )
    attributes = parse_station_attributes(await _async_get_json(session, stations_url))
    sites = parse_storage_list(await _async_get_json(session, series_url), attributes, now)
    _SITE_CACHE["bom"] = (now, sites)
    return sites


def nearest_sites(
    sites: Iterable[StorageSite], latitude: float, longitude: float, radius_km: float
) -> list[StorageSite]:
    """Return storages within the radius, nearest first."""
    distances = [(haversine_km(latitude, longitude, s.latitude, s.longitude), s.key, s) for s in sites]
    return [site for distance, _key, site in sorted(distances) if distance <= radius_km]


async def async_discover_storages(
    session: aiohttp.ClientSession, *, latitude: float, longitude: float, radius_km: float, now: datetime
) -> list[StorageReading]:
    """Return the nearest storages with a current reading, nearest first.

    The search reaches at least DAM_MIN_SEARCH_KM, since the dams that flood a town are
    often well upstream of it. Candidates are read in distance order, DAM_CHOICES at a
    time, until DAM_CHOICES storages with a reading are found, so storages whose series are
    empty do not crowd out readable ones further away. At most DAM_MAX_CANDIDATES are read.
    """
    sites = await async_storage_sites(session, now)
    nearby = nearest_sites(sites, latitude, longitude, max(radius_km, DAM_MIN_SEARCH_KM))[:DAM_MAX_CANDIDATES]
    found: list[StorageReading] = []
    for start in range(0, len(nearby), DAM_CHOICES):
        batch = nearby[start : start + DAM_CHOICES]
        readings = await async_fetch_readings(session, batch, now)
        found.extend(readings[site.key] for site in batch if site.key in readings)
        if len(found) >= DAM_CHOICES:
            break
    return found[:DAM_CHOICES]
