"""Tests for the WaterNSW and Hydro Tasmania operator feeds of the dam storages (#80).

Fixtures in fixtures/dams were captured from the live services on 2026-10-16 at 04:35 UTC
and trimmed: WaterNSW storage gauges for Toonumbar (spilling), Warragamba (the wall gauge
has a level only; the Hideaway Bay gauge has level and volume), Middle Cascade and Hume,
and Hydro Tasmania's North, North West and Central Plateau lake tables.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import unquote

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from yarl import URL

from custom_components.ausnz_disaster_watch import dam_operators
from custom_components.ausnz_disaster_watch.dam_operators import (
    HYDRO_TASMANIA_URL,
    HydroLake,
    WaterNSWGauge,
    async_attach_operators,
    async_fetch_operator_readings,
    async_hydro_lakes,
    async_waternsw_gauges,
    async_waternsw_readings,
    hydro_readings,
    match_hydro_lake,
    match_waternsw,
    parse_hydro_lakes,
    parse_waternsw_gauges,
)
from custom_components.ausnz_disaster_watch.dams import (
    OPERATOR_HYDRO_TASMANIA,
    OPERATOR_WATERNSW,
    OperatorReading,
    StorageReading,
    StorageSite,
    merge_operator,
)
from custom_components.ausnz_disaster_watch.providers.sources import DATA_SOURCES, REGISTER_PATH
from custom_components.ausnz_disaster_watch.rivers import RiverSourceError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures" / "dams"
NOW = datetime(2026, 10, 16, 4, 35, tzinfo=UTC)
NSW_HOST = "realtimedata.waternsw.com.au"
VARIABLES = {"130.00/130.00": "level", "130.00/136.00": "volume", "453.00/453.00": "spill", "459.00/459.00": "release"}


def load(name: str) -> Any:
    """Return a captured JSON response."""
    return json.loads((FIXTURES / name).read_text())


def _site(name: str, owner: str, lat: float, lon: float, **changes: Any) -> StorageSite:
    base = StorageSite(name.lower(), name, lat, lon, owner, ("v",), ("l",), 1000.0, 100.0)
    return StorageSite(**{**base.as_dict(), "volume_ts": ("v",), "level_ts": ("l",), **changes})


# Water Data Online storages and readings as the options flow sees them
WARRAGAMBA = StorageSite(
    "3082564", "Warragamba", -33.9925245, 150.421642, "w00231", ("v1",), ("l1",), 2027000.0, 116.72
)
TOONUMBAR = StorageSite("585899", "TOONUMBAR DAM", -28.6185, 152.7936, "w00077", ("v2",), ("l2",), 11048.902, 129.626)
CETHANA = StorageSite("ce", "CETHANA LAKE - AT DAM", -41.48, 146.13, "w00129", ("v3",), ("l3",), 100.0, 220.0)
WIVENHOE = StorageSite("3922223", "Wivenhoe", -27.3916, 152.6090, "w00191", ("v4",), ("l4",), 1165238.0, 67.0)
BOM_OBSERVED = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


def _bom(site: StorageSite, volume: float | None, level: float | None) -> StorageReading:
    return StorageReading(site, BOM_OBSERVED, volume, level, 10.0)


def kisters_handler(
    url: URL, *, fail: bool = False, bodies: dict[str, Any] | None = None
) -> AiohttpClientMockResponse | None:
    """Answer WaterNSW web service requests with the captured responses."""
    if url.host != NSW_HOST:
        return None
    if fail:
        return AiohttpClientMockResponse("GET", url, status=503)
    request = json.loads(unquote(url.raw_query_string))
    if request["function"] == "get_db_info":
        return AiohttpClientMockResponse("GET", url, json=load("waternsw_sto_sites.json"))
    params = request["params"]
    name = VARIABLES[f"{params['varfrom']}/{params['varto']}"]
    body = (bodies or {}).get(name) or load(f"waternsw_{name}.json")
    return AiohttpClientMockResponse("GET", url, json=body)


def route(
    aioclient_mock: AiohttpClientMocker,
    *,
    nsw_fail: bool = False,
    hydro: Any = None,
    bodies: dict[str, Any] | None = None,
) -> None:
    """Route WaterNSW and Hydro Tasmania requests; an int ``hydro`` is an HTTP status."""
    page = (FIXTURES / "hydro_tasmania.html").read_text() if hydro is None else hydro

    async def _side_effect(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        if (response := kisters_handler(url, fail=nsw_fail, bodies=bodies)) is not None:
            return response
        if isinstance(page, int):
            return AiohttpClientMockResponse("GET", url, status=page)
        return AiohttpClientMockResponse("GET", url, text=page)

    aioclient_mock.get(re.compile(".*"), side_effect=_side_effect)


@pytest.fixture(autouse=True)
def clear_gauge_cache() -> Generator[None]:
    """Start every test without a cached gauge list."""
    dam_operators._GAUGE_CACHE.clear()
    yield
    dam_operators._GAUGE_CACHE.clear()


# --- WaterNSW --------------------------------------------------------------------------


def test_parse_waternsw_gauges() -> None:
    """Gauges need a station and real coordinates."""
    rows = [
        *load("waternsw_sto_sites.json")["return"]["rows"],
        {"station": "1", "latitude": "0", "longitude": "0"},
        {"station": "2", "latitude": "north", "longitude": "150"},
        {"stname": "no station"},
        "not a row",
    ]
    gauges = parse_waternsw_gauges({"rows": rows})
    assert [gauge.station for gauge in gauges] == ["203042", "212242", "212243", "212281", "401027"]
    assert parse_waternsw_gauges({"rows": "nope"}) == []


async def test_waternsw_gauges_cached(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The gauge list is fetched once a day."""
    route(aioclient_mock)
    session = async_get_clientsession(hass)
    first = await async_waternsw_gauges(session, NOW)
    assert len(first) == 5
    assert await async_waternsw_gauges(session, NOW + timedelta(hours=2)) is first
    await async_waternsw_gauges(session, NOW + timedelta(hours=25))
    assert len(aioclient_mock.mock_calls) == 2


async def test_waternsw_readings(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Level and volume are the latest good points; spill and release the last daily totals."""
    route(aioclient_mock)
    readings = await async_waternsw_readings(
        async_get_clientsession(hass), ["203042", "212242", "212243", "401027", "999999"], NOW
    )
    assert set(readings) == {"203042", "212242", "212243", "401027"}
    toonumbar = readings["203042"]
    assert toonumbar.operator == OPERATOR_WATERNSW
    assert toonumbar.level_m == 129.71
    assert toonumbar.volume_ml == 11158.0
    assert toonumbar.spill_24h_ml == 32.0
    assert toonumbar.release_24h_ml == 29.0
    assert toonumbar.totals_date == "2026-10-15"
    assert toonumbar.observed_at == datetime(2026, 10, 16, 3, 30, tzinfo=UTC)
    # The Warragamba wall gauge has a level only (its volume is flagged unavailable)
    wall = readings["212242"]
    assert (wall.level_m, wall.volume_ml, wall.spill_24h_ml) == (114.695, None, None)
    assert readings["401027"].release_24h_ml == 12003.0
    # Four requests: level, volume, spill and release
    assert len(aioclient_mock.mock_calls) == 4
    assert await async_waternsw_readings(async_get_clientsession(hass), [], NOW) == {}


async def test_waternsw_readings_window(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Readings older than the operator window are ignored."""
    route(aioclient_mock)
    later = await async_waternsw_readings(async_get_clientsession(hass), ["203042"], NOW + timedelta(days=4))
    assert later == {}
    # A day later the levels are still current but the totals have expired
    route(aioclient_mock)
    next_day = await async_waternsw_readings(
        async_get_clientsession(hass), ["203042"], NOW + timedelta(days=2, hours=12)
    )
    assert next_day["203042"].spill_24h_ml is None
    assert next_day["203042"].level_m == 129.71


async def test_waternsw_totals_of_one_day(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Spill and release are only shown together for the same 9 am day."""
    spill = load("waternsw_spill.json")
    for trace in spill["return"]["traces"]:
        # The spill total is a day older than the release total
        trace["trace"] = [
            {**point, "t": point["t"] - 1000000} for point in trace["trace"] if point["t"] == 20261015090000
        ]
    route(aioclient_mock, bodies={"spill": spill})
    readings = await async_waternsw_readings(async_get_clientsession(hass), ["203042"], NOW)
    toonumbar = readings["203042"]
    assert (toonumbar.spill_24h_ml, toonumbar.release_24h_ml, toonumbar.totals_date) == (None, 29.0, "2026-10-15")


async def test_waternsw_no_variable(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Hydstra error 125 (no site has the variable, e.g. Sydney spillways) is an empty answer."""
    aioclient_mock.get(
        re.compile(".*"),
        json={"error_num": 125, "error_msg": "No data for specified variable in file"},
    )
    assert await async_waternsw_readings(async_get_clientsession(hass), ["212205"], NOW) == {}


def _gauges() -> list[WaterNSWGauge]:
    return parse_waternsw_gauges(load("waternsw_sto_sites.json")["return"])


def _op(level: float | None = None, volume: float | None = None) -> OperatorReading:
    return OperatorReading(OPERATOR_WATERNSW, NOW, level_m=level, volume_ml=volume)


def test_match_waternsw() -> None:
    """The gauge within range whose level and volume agree with the Bureau's wins."""
    gauges = _gauges()
    readings = {
        "212242": _op(level=114.695),
        "212243": _op(level=114.704, volume=1925233.0),
        "203042": _op(level=129.71, volume=11158.0),
    }
    # Water Data Online places Warragamba 19 km from the gauges; the closest level wins
    assert match_waternsw(_bom(WARRAGAMBA, 1878198.0, 114.703), gauges, readings) == "212243"
    assert match_waternsw(_bom(TOONUMBAR, 11135.8, 129.693), gauges, readings) == "203042"
    # A level that disagrees, a volume that disagrees, or nothing to compare: no match
    assert match_waternsw(_bom(TOONUMBAR, 11135.8, 128.0), gauges, readings) is None
    assert match_waternsw(_bom(TOONUMBAR, 5000.0, 129.693), gauges, readings) is None
    assert match_waternsw(_bom(TOONUMBAR, None, None), gauges, readings) is None
    # Out of range
    far = StorageSite(**{**TOONUMBAR.as_dict(), "latitude": -30.5, "volume_ts": ("v",), "level_ts": ("l",)})
    assert match_waternsw(_bom(far, 11135.8, 129.693), gauges, readings) is None
    # A gauge without a reading is not a candidate
    assert match_waternsw(_bom(TOONUMBAR, 11135.8, 129.693), gauges, {}) is None


# --- Hydro Tasmania --------------------------------------------------------------------


def test_parse_hydro_lakes() -> None:
    """Lake rows are parsed; navigation and region title rows are skipped."""
    lakes, updated = parse_hydro_lakes((FIXTURES / "hydro_tasmania.html").read_text())
    assert updated == date(2026, 10, 16)
    names = {lake.name: lake for lake in lakes}
    assert names["Lake Cethana"] == HydroLake("Lake Cethana", 0.0, True)
    assert names["Trevallyn Pond"].spilling is False
    assert names["Trevallyn Pond"].metres_below_full == 2.78
    assert "Water alerts" not in names
    # Repeated rows are kept once; unparsable dates are unknown
    text = "<tr><td>Lake A</td><td>1.0</td><td></td></tr>" * 2 + "<tr><td>Lake B</td><td>n/a</td><td></td></tr>"
    lakes, updated = parse_hydro_lakes(text + "Last updated: 31st Februarius 2026")
    assert [lake.name for lake in lakes] == ["Lake A"]
    assert updated is None
    assert parse_hydro_lakes("Last updated: 30th February 2026")[1] is None


@pytest.mark.parametrize(
    ("storage", "expected"),
    [
        ("CETHANA LAKE - AT DAM", "Lake Cethana"),
        ("TUNGATINAH LAGOONS - AT DAM", "Bradys/Binneys/Tungatinah"),
        ("WHITE SPUR POND - AT DAM", "Whitespur Pond"),
        ("LITTLE PINE LAGOON - AT DAM", "Little Pine Lagoon"),
        ("PINE TIER LAGOON - AT DAM", "Pine Tier Lagoon"),
        ("HENTY LAKE - AT DAM", None),
    ],
)
def test_match_hydro_lake(storage: str, expected: str | None) -> None:
    """Lakes match the Bureau's storage names word for word."""
    lakes = [
        HydroLake(name, 1.0, False)
        for name in (
            "Lake Cethana",
            "Bradys/Binneys/Tungatinah",
            "Whitespur Pond",
            "Little Pine Lagoon",
            "Pine Tier Lagoon",
        )
    ]
    site = _site(storage, "w00129", -42.0, 146.0)
    assert match_hydro_lake(site, lakes) == expected


def test_match_hydro_lake_ambiguous() -> None:
    """A storage that matches two lakes is not matched."""
    lakes = [HydroLake("Lake Repulse", 0.2, False), HydroLake("Repulse Lake", 0.2, False)]
    assert match_hydro_lake(_site("REPULSE LAKE - AT DAM", "w00129", -42.0, 146.0), lakes) is None


def test_hydro_readings() -> None:
    """A stale or undated table gives no readings."""
    lakes = [HydroLake("Lake Cethana", 0.0, True)]
    readings = hydro_readings(lakes, date(2026, 10, 16), NOW)
    assert readings["Lake Cethana"].spilling is True
    assert readings["Lake Cethana"].observed_at == datetime(2026, 10, 15, 13, 0, tzinfo=UTC)
    assert hydro_readings(lakes, date(2026, 10, 1), NOW) == {}
    assert hydro_readings(lakes, None, NOW) == {}


@pytest.mark.parametrize("hydro", [503, "<html>no table</html>"])
async def test_hydro_lakes_unavailable(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, hydro: Any) -> None:
    """An HTTP error or a page without the table is an outage."""
    route(aioclient_mock, hydro=hydro)
    with pytest.raises(RiverSourceError):
        await async_hydro_lakes(async_get_clientsession(hass))


async def test_hydro_lakes_connection_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A connection error is an outage."""
    aioclient_mock.get(HYDRO_TASMANIA_URL, exc=aiohttp.ClientError("down"))
    with pytest.raises(RiverSourceError):
        await async_hydro_lakes(async_get_clientsession(hass))


# --- Fetch, attach and merge -----------------------------------------------------------


def _matched() -> list[StorageSite]:
    return [
        TOONUMBAR.with_operator(OPERATOR_WATERNSW, "203042"),
        CETHANA.with_operator(OPERATOR_HYDRO_TASMANIA, "Lake Cethana"),
        _site("Gone", "w00129", -42.0, 146.0).with_operator(OPERATOR_HYDRO_TASMANIA, "Lake Gone"),
        WIVENHOE,
    ]


async def test_fetch_operator_readings(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Each matched storage gets its operator reading; unmatched and unknown ones get none."""
    route(aioclient_mock)
    readings = await async_fetch_operator_readings(async_get_clientsession(hass), _matched(), NOW)
    assert set(readings) == {TOONUMBAR.key, CETHANA.key}
    assert readings[TOONUMBAR.key].spill_24h_ml == 32.0
    assert readings[CETHANA.key].spilling is True


async def test_fetch_operator_readings_outages(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A feed that is down is skipped."""
    route(aioclient_mock, nsw_fail=True, hydro=503)
    assert await async_fetch_operator_readings(async_get_clientsession(hass), _matched(), NOW) == {}


async def test_attach_operators(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Discovered NSW and Tasmanian storages are matched and get the operator's fresher data."""
    route(aioclient_mock)
    discovered = [
        _bom(WARRAGAMBA, 1878198.0, 114.703),
        _bom(TOONUMBAR, 11135.8, 129.693),
        _bom(CETHANA, 87.0, 219.9),
        _bom(_site("HENTY LAKE - AT DAM", "w00129", -41.9, 145.5), 10.0, 5.0),
        _bom(WIVENHOE, 937003.2, 64.686),
    ]
    attached = await async_attach_operators(async_get_clientsession(hass), discovered, NOW)
    by_name = {reading.site.name: reading for reading in attached}
    warragamba = by_name["Warragamba"]
    assert (warragamba.site.operator, warragamba.site.operator_id) == (OPERATOR_WATERNSW, "212243")
    assert warragamba.source == OPERATOR_WATERNSW
    assert warragamba.level_m == 114.704
    # The volume stays the Bureau's, measured against the Bureau's full supply volume
    assert warragamba.volume_ml == 1878198.0
    toonumbar = by_name["TOONUMBAR DAM"]
    assert toonumbar.spilling is True
    assert toonumbar.above_full_supply is True
    cethana = by_name["CETHANA LAKE - AT DAM"]
    assert cethana.site.operator_id == "Lake Cethana"
    assert cethana.source == "bom"
    assert cethana.spilling is True
    assert by_name["HENTY LAKE - AT DAM"].site.operator is None
    assert by_name["Wivenhoe"] is discovered[4]


async def test_attach_operators_outages(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """With both feeds down, discovered storages are returned unchanged."""
    route(aioclient_mock, nsw_fail=True, hydro=503)
    discovered = [_bom(TOONUMBAR, 11135.8, 129.693), _bom(CETHANA, 87.0, 219.9)]
    assert await async_attach_operators(async_get_clientsession(hass), discovered, NOW) == discovered
    assert await async_attach_operators(async_get_clientsession(hass), [], NOW) == []


async def test_attach_operators_feed_fails_after_match(hass: HomeAssistant) -> None:
    """A storage matched while its reading cannot be fetched keeps the match and the Bureau's reading."""
    reading = _bom(CETHANA, 87.0, 219.9)
    with (
        patch.object(
            dam_operators, "async_hydro_lakes", AsyncMock(return_value=([HydroLake("Lake Cethana", 0.0, True)], None))
        ),
    ):
        attached = await async_attach_operators(async_get_clientsession(hass), [reading], NOW)
    assert attached[0].site.operator_id == "Lake Cethana"
    assert attached[0].operator is None
    assert attached[0].volume_ml == 87.0


def test_merge_operator() -> None:
    """The fresher operator level is used; the Bureau's volume and change are kept."""
    bom = _bom(TOONUMBAR, 11135.8, 129.693)
    fresh = _op(level=129.71, volume=11158.0)
    merged = merge_operator(TOONUMBAR, bom, fresh)
    assert merged is not None
    assert (merged.level_m, merged.volume_ml, merged.change_24h_ml, merged.source) == (
        129.71,
        11135.8,
        10.0,
        "waternsw",
    )
    # Without a BoM reading the operator's alone is used
    alone = merge_operator(TOONUMBAR, None, fresh)
    assert alone is not None
    assert (alone.volume_ml, alone.change_24h_ml) == (11158.0, None)
    # An older operator reading only adds its spill data
    old = OperatorReading(OPERATOR_WATERNSW, BOM_OBSERVED - timedelta(hours=1), level_m=1.0, spill_24h_ml=0.0)
    kept = merge_operator(TOONUMBAR, bom, old)
    assert kept is not None
    assert (kept.level_m, kept.source, kept.spilling) == (129.693, "bom", False)
    # Spill data without a BoM reading gives no reading
    assert merge_operator(TOONUMBAR, None, OperatorReading(OPERATOR_HYDRO_TASMANIA, NOW, spilling=True)) is None
    assert merge_operator(TOONUMBAR, bom, None) is bom


@pytest.mark.parametrize(
    ("volume", "level", "operator", "expected"),
    [
        (500.0, 99.0, None, False),
        # Volume under full but level over: spilling
        (999.0, 100.2, None, True),
        (1100.0, None, None, True),
        (None, None, None, None),
        # The operator's spill signal counts on its own
        (None, None, OperatorReading(OPERATOR_HYDRO_TASMANIA, NOW, spilling=True), True),
        (None, None, OperatorReading(OPERATOR_WATERNSW, NOW, spill_24h_ml=0.0), False),
        (None, None, OperatorReading(OPERATOR_WATERNSW, NOW), None),
    ],
)
def test_above_full_supply_signals(
    volume: float | None, level: float | None, operator: OperatorReading | None, expected: bool | None
) -> None:
    """Above full supply when any of volume, level or the operator's spill signal says so."""
    site = _site("Test", "w00191", -27.0, 152.0)
    reading = StorageReading(site, NOW, volume, level, None, operator)
    assert reading.above_full_supply is expected


def test_storage_site_operator_round_trip() -> None:
    """The operator match is stored with the storage; unknown operators are dropped."""
    site = TOONUMBAR.with_operator(OPERATOR_WATERNSW, "203042")
    assert StorageSite.from_dict(site.as_dict()) == site
    assert site.attribution.startswith("© State Government of NSW and WaterNSW, CC BY; © State of NSW")
    assert "operator" not in TOONUMBAR.as_dict()
    unknown = StorageSite.from_dict({**site.as_dict(), "operator": "seqwater"})
    assert unknown is not None
    assert unknown.operator is None
    no_id = StorageSite.from_dict({**site.as_dict(), "operator_id": None})
    assert no_id is not None
    assert no_id.operator is None


def test_register_lists_the_operator_sources() -> None:
    """Both operator feeds are in the data source register."""
    register = (Path(__file__).resolve().parent.parent / REGISTER_PATH).read_text(encoding="utf-8")
    for key in ("waternsw_storages", "hydro_tasmania_lakes"):
        assert f"`{key}`" in register
        assert DATA_SOURCES[key].terms_url in register
    assert HYDRO_TASMANIA_URL in register
