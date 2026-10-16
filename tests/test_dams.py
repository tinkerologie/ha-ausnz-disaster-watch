"""Tests for the Water Data Online storage client, parsers and discovery.

Responses in fixtures/dams were captured from the live service on 2026-10-16 at about
02:20 UTC and trimmed: the storage list keeps Wivenhoe, Somerset, Warragamba (three station
IDs and Hideaway, which has no full supply attributes), Prospect and Middle Cascade (level
and volume on different stations), Toonumbar, Hinze (placeholder coordinates), Lake
Jindabyne (Snowy Hydro, not openly licensed) and one storage whose data ended years ago.
"""

from __future__ import annotations

from collections.abc import Generator
import copy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from yarl import URL

from custom_components.ausnz_disaster_watch import dams
from custom_components.ausnz_disaster_watch.dams import (
    DamSourceError,
    StorageReading,
    StorageSite,
    async_discover_storages,
    async_fetch_readings,
    async_storage_sites,
    build_reading,
    parse_station_attributes,
    parse_storage_list,
    parse_values,
    sites_from_options,
)
from custom_components.ausnz_disaster_watch.providers.sources import DATA_SOURCES, REGISTER_PATH
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures" / "dams"
NOW = datetime(2026, 10, 16, 2, 20, tzinfo=UTC)
BRISBANE = (-27.47, 153.02)
WIVENHOE_KEY = "bom:3922223"


def load(name: str) -> Any:
    """Return a captured response."""
    return json.loads((FIXTURES / name).read_text())


def respond(url: URL, body: Any = None, status: int = 200) -> AiohttpClientMockResponse:
    """Return a mock JSON response."""
    return AiohttpClientMockResponse("GET", url, status=status, json=body)


def route(aioclient_mock: AiohttpClientMocker, **bodies: Any) -> None:
    """Answer KiWIS requests by request name; a body that is an int is an HTTP status."""
    answers = {
        "getTimeseriesList": load("storage_list.json"),
        "getStationList": load("station_attributes.json"),
        "getTimeseriesValues": load("storage_values.json"),
        **bodies,
    }

    async def _side_effect(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        body = answers[url.query["request"]]
        if isinstance(body, int):
            return respond(url, status=body)
        return respond(url, body)

    aioclient_mock.get(re.compile(".*"), side_effect=_side_effect)


@pytest.fixture(autouse=True)
def clear_site_cache() -> Generator[None]:
    """Start every test without a cached storage list."""
    dams._SITE_CACHE.clear()
    yield
    dams._SITE_CACHE.clear()


def _sites() -> dict[str, StorageSite]:
    attributes = parse_station_attributes(load("station_attributes.json"))
    return {site.name: site for site in parse_storage_list(load("storage_list.json"), attributes, NOW)}


def test_parse_storage_list() -> None:
    """Openly licensed storages with current data and real coordinates are kept, one per place."""
    sites = _sites()
    assert sorted(sites) == ["Middle Cascade", "Prospect", "Somerset", "TOONUMBAR DAM", "Warragamba", "Wivenhoe"]
    wivenhoe = sites["Wivenhoe"]
    assert wivenhoe.key == WIVENHOE_KEY
    assert (wivenhoe.full_volume_ml, wivenhoe.full_level_m) == (1165238.0, 67.0)
    assert wivenhoe.owner == "w00191"
    assert wivenhoe.attribution == (
        "© Queensland Bulk Water Supply Authority (trading as Seqwater), CC BY 3.0 AU, "
        "via Bureau of Meteorology Water Data Online"
    )
    # Levels prefer the metres-AHD series; volumes the supplier's own series
    assert wivenhoe.level_ts == ("373853010", "368478010")
    assert wivenhoe.volume_ts == ("368497010", "374514010")
    # Warragamba's three station IDs are merged; the station with the newest volume data wins
    warragamba = sites["Warragamba"]
    assert warragamba.site_id == "3082564"
    assert len(warragamba.volume_ts) == 3
    # Prospect has its level and volume on different stations
    assert sites["Prospect"].level_ts and sites["Prospect"].volume_ts


def test_parse_storage_list_skips_unusable_rows() -> None:
    """Malformed rows, unknown series, bad coordinates and storages without full supply data are skipped."""
    header = [
        "station_id",
        "station_name",
        "station_latitude",
        "station_longitude",
        "ts_id",
        "ts_name",
        "parametertype_name",
        "from",
        "to",
    ]
    end = "2026-10-15T10:00:00.000+10:00"
    volume = "DMQaQc.Merged.AsStored.1"
    payload = [
        header,
        ["1", "Ok", "-27.0", "152.0", "11", volume, "Storage Volume", "", end],
        ["1", "Ok", "-27.0", "152.0", "12", "DMQaQc.Merged.DailyMean.24HR", "Storage Volume", "", end],
        ["2", "No coordinates", "", "152.0", "21", volume, "Storage Volume", "", end],
        ["3", "No data", "-27.0", "153.0", "31", volume, "Storage Volume", "", ""],
        ["4", "No full supply", "-28.0", "152.0", "41", volume, "Storage Volume", "", end],
        ["5", "Level only", "-29.0", "152.0", "51", "DMQaQc.Merged.AsStored.1", "Storage Level", "", end],
        ["6", "Level only, no full level", "-30.0", "152.0", "61", volume, "Storage Level", "", end],
        ["short row"],
        "not a row",
    ]
    attributes = {
        "1": {"FullStorageVolume": "100", "FullStorageLevel": "", "DATA_OWNER": "w00191"},
        "2": {"FullStorageVolume": "100", "DATA_OWNER": "w00191"},
        "3": {"FullStorageVolume": "100", "DATA_OWNER": "w00191"},
        "4": {"FullStorageVolume": "", "FullStorageLevel": "", "DATA_OWNER": "w00191"},
        "5": {"FullStorageVolume": "", "FullStorageLevel": "12.5", "DATA_OWNER": "w00191"},
        "6": {"FullStorageVolume": "nan", "FullStorageLevel": "", "DATA_OWNER": "w00191"},
    }
    sites = {site.name: site for site in parse_storage_list(payload, attributes, NOW)}
    assert sorted(sites) == ["Level only", "Ok"]
    assert sites["Ok"].volume_ts == ("11",)
    assert sites["Ok"].full_level_m is None
    assert sites["Level only"].volume_ts == ()
    assert sites["Level only"].full_level_m == 12.5


@pytest.mark.parametrize("payload", [{}, [], ["header"], None])
def test_parse_storage_list_rejects_bad_payloads(payload: Any) -> None:
    """A response that is not a KiWIS table is an outage."""
    with pytest.raises(DamSourceError):
        parse_storage_list(payload, {}, NOW)
    with pytest.raises(DamSourceError):
        parse_station_attributes(payload)


def test_parse_values() -> None:
    """Missing values and malformed points are skipped."""
    payload = [
        {"ts_id": "1", "data": [["2026-10-15T10:00:00.000+10:00", 5.0], ["2026-10-15T11:00:00.000+10:00", None]]},
        {"ts_id": "2", "data": [["bad time", 1.0], ["2026-10-15T10:00:00.000+10:00"], None]},
        {"ts_id": "3"},
        {"no": "ts_id"},
        "not a series",
    ]
    series = parse_values(payload)
    assert series == {"1": [(datetime(2026, 10, 15, 0, 0, tzinfo=UTC), 5.0)], "2": [], "3": []}
    with pytest.raises(DamSourceError):
        parse_values({"type": "error"})


def test_readings_from_fixtures() -> None:
    """Readings combine the first volume and level series with data."""
    sites = _sites()
    series = parse_values(load("storage_values.json"))
    wivenhoe = build_reading(sites["Wivenhoe"], series)
    assert wivenhoe is not None
    assert wivenhoe.percent_full == 80.4
    assert wivenhoe.volume_ml == 937003.2
    assert wivenhoe.level_m == 64.686
    assert wivenhoe.above_full_supply is False
    assert wivenhoe.observed_at == datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    # Warragamba's level is in metres AHD, not relative to full supply level
    warragamba = build_reading(sites["Warragamba"], series)
    assert warragamba is not None
    assert warragamba.level_m == pytest.approx(114.7, abs=0.01)
    toonumbar = build_reading(sites["TOONUMBAR DAM"], series)
    assert toonumbar is not None
    assert toonumbar.percent_full == 100.8
    assert toonumbar.above_full_supply is True
    assert build_reading(sites["Wivenhoe"], {}) is None


def _site(**changes: Any) -> StorageSite:
    base = StorageSite(
        site_id="9",
        name="Test Dam",
        latitude=-27.4,
        longitude=152.6,
        owner="w00191",
        volume_ts=("v",),
        level_ts=("l",),
        full_volume_ml=1000.0,
        full_level_m=50.0,
    )
    data = {**base.as_dict(), **changes}
    site = StorageSite.from_dict(data)
    assert site is not None
    return site


def _at(hours: float) -> datetime:
    return NOW + timedelta(hours=hours)


@pytest.mark.parametrize(
    ("site", "series", "percent", "above", "change"),
    [
        # Over 100% is kept: the flood compartment is in use
        (_site(), {"v": [(_at(-25), 1000.0), (_at(-1), 1100.0)], "l": [(_at(-1), 50.5)]}, 110.0, True, 100.0),
        # No volume series with data: the level decides
        (_site(), {"v": [], "l": [(_at(-1), 50.1)]}, None, True, None),
        (_site(), {"l": [(_at(-1), 49.9)]}, None, False, None),
        # No full supply volume: no percent; no level either: unknown
        (_site(full_volume_ml=None, full_level_m=None), {"v": [(_at(-1), 500.0)]}, None, None, None),
        # The 24 h change needs a reading at least 24 h older
        (_site(), {"v": [(_at(-5), 900.0), (_at(-1), 950.0)]}, 95.0, False, None),
    ],
)
def test_reading_values(
    site: StorageSite, series: dict[str, list[tuple[datetime, float]]], percent: Any, above: Any, change: Any
) -> None:
    """Percent full, above full supply and the 24 h change."""
    reading = build_reading(site, series)
    assert reading is not None
    assert (reading.percent_full, reading.above_full_supply, reading.change_24h_ml) == (percent, above, change)


def test_sites_from_options() -> None:
    """Stored storages round-trip; unusable or duplicate entries are dropped."""
    site = _site()
    legacy = {**site.as_dict(), "volume_ts": "v", "level_ts": None}
    stored = [
        site.as_dict(),
        site.as_dict(),
        {**site.as_dict(), "owner": "w00205"},  # not openly licensed
        {**site.as_dict(), "site_id": "10", "volume_ts": [], "level_ts": []},  # no series
        {**site.as_dict(), "latitude": "north"},
        {"name": "missing keys"},
        "not a dict",
    ]
    assert sites_from_options(stored) == [site]
    assert sites_from_options("nope") == []
    restored = StorageSite.from_dict(legacy)
    assert restored is not None
    assert (restored.volume_ts, restored.level_ts) == (("v",), ())


async def test_fetch_readings(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """One values request covers every selected storage; stale readings are dropped."""
    route(aioclient_mock)
    sites = list(_sites().values())
    session = async_get_clientsession(hass)
    readings = await async_fetch_readings(session, sites, NOW)
    assert set(readings) == {site.key for site in sites}
    assert len(aioclient_mock.mock_calls) == 1
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["request"] == "getTimeseriesValues"
    assert url.query["period"] == "P7D"
    assert sites[0].ts_ids[0] in url.query["ts_id"].split(",")

    later = await async_fetch_readings(session, sites, NOW + timedelta(days=9))
    assert later == {}
    assert await async_fetch_readings(session, [], NOW) == {}


@pytest.mark.parametrize("body", [503, {"type": "error", "message": "bad"}, "not json"])
async def test_fetch_readings_failures(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, body: Any) -> None:
    """HTTP errors, KiWIS errors and bodies that are not a list raise DamSourceError."""
    route(aioclient_mock, getTimeseriesValues=body)
    with pytest.raises(DamSourceError):
        await async_fetch_readings(async_get_clientsession(hass), list(_sites().values()), NOW)


async def test_fetch_connection_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A connection error is an outage."""
    aioclient_mock.get(re.compile(".*"), exc=aiohttp.ClientError("down"))
    with pytest.raises(DamSourceError):
        await async_fetch_readings(async_get_clientsession(hass), list(_sites().values()), NOW)


async def test_storage_list_is_cached(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The storage list is fetched once a day, with the station attributes in a separate request."""
    route(aioclient_mock)
    session = async_get_clientsession(hass)
    first = await async_storage_sites(session, NOW)
    assert len(first) == 6
    requests = [call[1].query["request"] for call in aioclient_mock.mock_calls]
    assert requests == ["getStationList", "getTimeseriesList"]
    list_url = aioclient_mock.mock_calls[1][1]
    assert "ca_sta" not in list_url.query["returnfields"]
    assert await async_storage_sites(session, NOW + timedelta(hours=1)) is first
    assert len(aioclient_mock.mock_calls) == 2
    await async_storage_sites(session, NOW + timedelta(hours=25))
    assert len(aioclient_mock.mock_calls) == 4


async def test_discover_storages(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Discovery searches at least 150 km and returns storages with readings, nearest first."""
    route(aioclient_mock)
    found = await async_discover_storages(
        async_get_clientsession(hass), latitude=BRISBANE[0], longitude=BRISBANE[1], radius_km=10, now=NOW
    )
    assert [reading.site.name for reading in found] == ["Wivenhoe", "Somerset", "TOONUMBAR DAM"]
    assert all(isinstance(reading, StorageReading) for reading in found)


async def test_discover_nothing_nearby(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A location with no storage in range needs no values request."""
    route(aioclient_mock)
    found = await async_discover_storages(
        async_get_clientsession(hass), latitude=-12.46, longitude=130.84, radius_km=50, now=NOW
    )
    assert found == []
    assert [call[1].query["request"] for call in aioclient_mock.mock_calls] == ["getStationList", "getTimeseriesList"]


async def test_discover_skips_storages_without_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A nearby storage whose series return no values is not offered."""
    values = copy.deepcopy(load("storage_values.json"))
    for item in values:
        item["data"] = []
    route(aioclient_mock, getTimeseriesValues=values)
    found = await async_discover_storages(
        async_get_clientsession(hass), latitude=BRISBANE[0], longitude=BRISBANE[1], radius_km=10, now=NOW
    )
    assert found == []


def test_register_lists_the_source() -> None:
    """The storage source and its endpoint are in the data source register."""
    register = (Path(__file__).resolve().parent.parent / REGISTER_PATH).read_text(encoding="utf-8")
    assert "`bom_water_storages`" in register
    assert dams.KIWIS_URL in register
    assert DATA_SOURCES["bom_water_storages"].terms_url in register
    # Every owner the integration credits is one the register's licence covers
    assert "w00205" not in dams.OWNER_ATTRIBUTIONS
