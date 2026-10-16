"""Tests for the river gauge clients, parsers, trend and discovery (#31).

Responses in fixtures/rivers were captured from the live services and trimmed.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
import copy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from yarl import URL

from custom_components.ausnz_disaster_watch import rivers
from custom_components.ausnz_disaster_watch.providers.sources import DATA_SOURCES, REGISTER_PATH
from custom_components.ausnz_disaster_watch.rivers import (
    KISTERS_SERVERS,
    TREND_FALLING,
    TREND_RISING,
    TREND_STEADY,
    GaugeSite,
    RiverSourceError,
    async_discover_gauges,
    async_fetch_readings,
    calculate_trend,
    parse_hilltop_data,
    parse_hilltop_sites,
    parse_kisters_traces,
    sites_from_options,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures" / "rivers"

# Responses were captured on 2026-10-15 at about 22:58 UTC (08:58 AEST, 10:58 NZST).
NOW = datetime(2026, 10, 15, 23, 0, tzinfo=UTC)

QLD_HOST = "water-monitoring.information.qld.gov.au"
NSW_HOST = "realtimedata.waternsw.com.au"
GW_HOST = "hilltop.gw.govt.nz"

Handler = Callable[[URL], AiohttpClientMockResponse | None]


def load_json(name: str) -> Any:
    """Return a captured JSON response."""
    return json.loads((FIXTURES / name).read_text())


def load_text(name: str) -> str:
    """Return a captured XML response."""
    return (FIXTURES / name).read_text()


def kisters_request(url: URL) -> dict[str, Any]:
    """Return the decoded JSON request of a Kisters web service URL."""
    return json.loads(unquote(url.raw_query_string))


def respond(
    url: URL, *, json_body: Any = None, text: str | None = None, status: int = 200
) -> AiohttpClientMockResponse:
    """Return a mock response."""
    return AiohttpClientMockResponse("GET", url, status=status, json=json_body, text=text)


def default_handler(url: URL) -> AiohttpClientMockResponse | None:
    """Answer requests with the captured responses for QLD, NSW and Greater Wellington."""
    if url.host in (QLD_HOST, NSW_HOST):
        prefix = "qld" if url.host == QLD_HOST else "nsw"
        function = kisters_request(url)["function"]
        names = {
            "get_ts_traces": f"{prefix}_ts_traces.json",
            "get_sites_by_datasource": f"{prefix}_sites_by_datasource.json",
            "get_db_info": f"{prefix}_db_info.json",
        }
        return respond(url, json_body=load_json(names[function]))
    if url.host == GW_HOST:
        if url.query["Request"] == "SiteList":
            return respond(url, text=load_text("hilltop_gw_sitelist.xml"))
        if url.query["Site"] == "Waiwhetu Stream at Whites Line East":
            return respond(url, text=load_text("hilltop_gw_getdata.xml"))
        return respond(url, text=load_text("hilltop_gw_error.xml"))
    return None


def route(aioclient_mock: AiohttpClientMocker, *handlers: Handler) -> None:
    """Route every GET through the handlers in order; unknown hosts answer HTTP 503."""

    async def _side_effect(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        for handler in (*handlers, default_handler):
            if (response := handler(url)) is not None:
                return response
        return respond(url, status=503)

    aioclient_mock.get(re.compile(".*"), side_effect=_side_effect)


def fail_host(host: str) -> Handler:
    """Return a handler that makes one host answer HTTP 503."""
    return lambda url: respond(url, status=503) if url.host == host else None


QLD = KISTERS_SERVERS["qld"]
SAVAGES = GaugeSite("qld", "143001C", "Brisbane River at Savages Crossing", -27.439727, 152.668941)
DRAPERS = GaugeSite("qld", "142202A", "South Pine River at Drapers Crossing", -27.35, 152.92)
NORTH_RICHMOND = GaugeSite("nsw", "212200", "HAWKESBURY RIVER AT NORTH RICHMOND", -33.589301, 150.714031)
WAIWHETU = GaugeSite("hilltop_gw", "Waiwhetu Stream at Whites Line East", "Waiwhetu Stream", -41.2248, 174.9206)
ASHBYS = GaugeSite("hilltop_gw", "Ashbys Stream at Ashbys Road Culvert", "Ashbys Stream", -41.1644, 175.3322)


@pytest.fixture(autouse=True)
def clear_site_cache() -> Generator[None]:
    """Start every test without cached site lists."""
    rivers._SITE_CACHE.clear()
    yield
    rivers._SITE_CACHE.clear()


def _points(*values: tuple[int, float]) -> list[tuple[datetime, float]]:
    """Return points at the given minutes after NOW."""
    return [(NOW + timedelta(minutes=minute), value) for minute, value in values]


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (_points((0, 1.0), (30, 1.02), (60, 1.05)), (TREND_RISING, 0.05)),
        (_points((0, 1.0), (60, 0.95)), (TREND_FALLING, -0.05)),
        (_points((0, 1.0), (60, 1.005)), (TREND_STEADY, 0.005)),
        # The newest reading at least an hour older is used, not the oldest one
        (_points((0, 0.5), (50, 1.0), (110, 1.0)), (TREND_STEADY, 0.0)),
        (_points((60, 1.0), (0, 1.2)), (TREND_FALLING, -0.2)),
    ],
)
def test_calculate_trend(points: list[tuple[datetime, float]], expected: tuple[str, float]) -> None:
    """Trend compares the latest level with the level about an hour earlier, with a dead band."""
    assert calculate_trend(points) == expected


@pytest.mark.parametrize("points", [[], _points((0, 1.0)), _points((0, 1.0), (30, 2.0))])
def test_calculate_trend_insufficient_data(points: list[tuple[datetime, float]]) -> None:
    """Without a reading an hour before the latest one the trend is unknown."""
    assert calculate_trend(points) == (None, None)


def test_parse_kisters_traces_converts_local_time() -> None:
    """Hydstra local +10 times become UTC; traces with an error are skipped."""
    series = parse_kisters_traces(QLD, load_json("qld_ts_traces.json")["return"])
    assert set(series) == {"143001C", "142202A"}  # 999999Z has error_num 20
    assert max(series["143001C"]) == (datetime(2026, 10, 15, 22, 0, tzinfo=UTC), 1.333)


def test_parse_kisters_traces_skips_bad_points() -> None:
    """Points with a bad quality code, no value or an unparsable time are skipped."""
    result = copy.deepcopy(load_json("qld_ts_traces.json")["return"])
    trace = result["traces"][0]
    trace["site_details"] = {}  # no time zone: the service default (+10) applies
    trace["trace"] = [
        {"v": "1.0", "t": 20261016080000, "q": 130},
        {"v": "9.9", "t": 20261016081500, "q": 151},
        {"t": 20261016083000, "q": 130},
        {"v": "1.1", "t": "not a time", "q": 130},
        "not a point",
    ]
    result["traces"].append({"error_num": 0})  # no site
    series = parse_kisters_traces(QLD, result)
    assert series[trace["site"]] == [(datetime(2026, 10, 15, 22, 0, tzinfo=UTC), 1.0)]


def test_parse_kisters_traces_rejects_malformed_result() -> None:
    """A result whose traces are not a list is a broken response."""
    with pytest.raises(RiverSourceError):
        parse_kisters_traces(QLD, {"traces": {}})


def test_parse_hilltop_data_units() -> None:
    """Hilltop NZST times become UTC and mm or m readings become metres."""
    points = parse_hilltop_data("hilltop_gw", load_text("hilltop_gw_getdata.xml"))
    latest = max(points)
    assert latest[0] == datetime(2026, 10, 15, 22, 55, tzinfo=UTC)
    assert latest[1] == pytest.approx(0.283)
    trc = max(parse_hilltop_data("hilltop_trc", load_text("hilltop_trc_getdata.xml")))
    assert trc == (datetime(2026, 10, 15, 22, 40, tzinfo=UTC), 1.356)


def test_parse_hilltop_data_errors() -> None:
    """A Hilltop <Error> means no data; broken or unexpected documents raise."""
    assert parse_hilltop_data("hilltop_gw", load_text("hilltop_gw_error.xml")) == []
    with pytest.raises(RiverSourceError):
        parse_hilltop_data("hilltop_gw", "<Hilltop><broken")
    with pytest.raises(RiverSourceError):
        parse_hilltop_data("hilltop_gw", "<html><body>Maintenance</body></html>")
    feet = load_text("hilltop_gw_getdata.xml").replace("<Units>mm</Units>", "<Units>ft</Units>")
    with pytest.raises(RiverSourceError):
        parse_hilltop_data("hilltop_gw", feet)


def test_parse_hilltop_data_skips_bad_points() -> None:
    """An element with an unparsable time or value is skipped."""
    text = load_text("hilltop_gw_getdata.xml").replace(
        "<E><T>2026-10-16T09:00:00</T><I1>281</I1></E>",
        "<E><T>yesterday</T><I1>281</I1></E><E><T>2026-10-16T09:01:00</T><I1>dry</I1></E>",
    )
    assert len(parse_hilltop_data("hilltop_gw", text)) == 23


def test_parse_hilltop_sites() -> None:
    """Sites with coordinates are listed; groundwater bores and sites without coordinates are not."""
    text = load_text("hilltop_gw_sitelist.xml").replace(
        "<CRC>",
        '<Site Name="No Coordinates"></Site><Site Name="Wells Road Bore"><Latitude>-41</Latitude>'
        "<Longitude>175</Longitude></Site><CRC>",
    )
    names = {site.name for site in parse_hilltop_sites("hilltop_gw", text)}
    assert names == {
        "Ashbys Stream at Ashbys Road Culvert",
        "Hutt River at Taita Gorge",
        "Waiwhetu Stream at Whites Line East",
        "Wellington Harbour at Queens Wharf",
    }
    with pytest.raises(RiverSourceError):
        parse_hilltop_sites("hilltop_gw", "<HilltopServer><Site")
    with pytest.raises(RiverSourceError):
        parse_hilltop_sites("hilltop_gw", "<Hilltop/>")


def test_gauge_site_options_round_trip() -> None:
    """Gauges survive storage in options; unusable entries are dropped and duplicates merged."""
    stored = [SAVAGES.as_dict(), SAVAGES.as_dict(), {"source": "qld"}, {**WAIWHETU.as_dict(), "source": "unknown"}]
    assert sites_from_options(stored) == [SAVAGES]
    assert sites_from_options(None) == []
    assert SAVAGES.key == "qld:143001C"
    assert "CC BY 4.0" in SAVAGES.attribution
    assert WAIWHETU.attribution == "Greater Wellington Regional Council"


async def test_fetch_readings(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """QLD and NSW gauges are fetched in one request per service, Hilltop gauges one by one."""
    route(aioclient_mock)
    session = async_get_clientsession(hass)
    readings, failed = await async_fetch_readings(session, [SAVAGES, DRAPERS, NORTH_RICHMOND, WAIWHETU, ASHBYS], NOW)

    assert failed == set()
    assert set(readings) == {SAVAGES.key, DRAPERS.key, NORTH_RICHMOND.key, WAIWHETU.key}  # Ashbys has no data
    savages = readings[SAVAGES.key]
    assert (savages.level_m, savages.observed_at, savages.trend) == (
        1.333,
        datetime(2026, 10, 15, 22, tzinfo=UTC),
        "steady",
    )
    assert readings[NORTH_RICHMOND.key].trend == TREND_FALLING
    assert readings[WAIWHETU.key].level_m == 0.283

    kisters_calls = [call for call in aioclient_mock.mock_calls if call[1].host == QLD_HOST]
    assert len(kisters_calls) == 1
    params = kisters_request(kisters_calls[0][1])["params"]
    assert params["site_list"] == "143001C,142202A"
    assert (params["start_time"], params["end_time"]) == ("20261016030000", "20261016100000")


async def test_fetch_readings_isolates_failures(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A failing service marks only its own gauges as failed; stale readings are dropped."""
    route(aioclient_mock, fail_host(QLD_HOST), fail_host(GW_HOST))
    session = async_get_clientsession(hass)
    readings, failed = await async_fetch_readings(session, [SAVAGES, NORTH_RICHMOND, WAIWHETU], NOW)
    assert failed == {SAVAGES.key, WAIWHETU.key}
    assert set(readings) == {NORTH_RICHMOND.key}

    # 20:45 UTC is more than 6 hours before 03:00
    readings, failed = await async_fetch_readings(session, [NORTH_RICHMOND], NOW + timedelta(hours=4))
    assert (readings, failed) == ({}, set())


async def test_kisters_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Hydstra 'no data' is an empty answer; other errors and unexpected payloads are failures."""
    answers = iter(
        [
            {"error_num": 126, "error_msg": "No data within specified period"},
            {"error_num": 122, "error_msg": "Parameter error"},
            [],
            {"error_num": 0},
        ]
    )
    route(aioclient_mock, lambda url: respond(url, json_body=next(answers)))
    session = async_get_clientsession(hass)
    assert await async_fetch_readings(session, [SAVAGES], NOW) == ({}, set())
    for _ in range(3):
        assert await async_fetch_readings(session, [SAVAGES], NOW) == ({}, {SAVAGES.key})


async def test_invalid_json_is_a_failure(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """An HTML error page instead of JSON fails the request."""
    route(aioclient_mock, lambda url: respond(url, text="<html>busy</html>"))
    session = async_get_clientsession(hass)
    assert await async_fetch_readings(session, [SAVAGES], NOW) == ({}, {SAVAGES.key})


async def test_discover_qld(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """QLD discovery lists live stream gauges near Moreton Bay with a current level, nearest first.

    The NSW service is also searched for border locations; its failure does not fail discovery.
    """

    def traces(url: URL):
        if url.host == QLD_HOST and kisters_request(url)["function"] == "get_ts_traces":
            assert kisters_request(url)["params"]["site_list"] == "143032A"
            payload = load_json("qld_ts_traces.json")
            payload["return"]["traces"][0]["site"] = "143032A"
            return respond(url, json_body=payload)
        return None

    route(aioclient_mock, traces, fail_host(NSW_HOST))
    session = async_get_clientsession(hass)
    found = await async_discover_gauges(
        session, state="qld", latitude=-27.2657, longitude=152.9818, radius_km=50, now=NOW
    )
    assert [reading.site.key for reading in found] == ["qld:143032A"]  # the only G gauge in the capture
    # One db_info request per QLD station type, all inside the radius check
    db_info = [c for c in aioclient_mock.mock_calls if c[1].host == QLD_HOST and "get_db_info" in str(c[1])]
    assert len(db_info) == len(QLD.station_types)


async def test_discover_nsw_and_cache(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """NSW discovery near North Richmond finds 212200; site lists are cached for 24 hours."""

    def traces(url: URL):
        if url.host == NSW_HOST and kisters_request(url)["function"] == "get_ts_traces":
            assert kisters_request(url)["params"]["site_list"] == "212200,212201"  # 201001 is too far
            return respond(url, json_body=load_json("nsw_ts_traces.json"))
        return None

    route(aioclient_mock, traces, fail_host(QLD_HOST))
    session = async_get_clientsession(hass)
    found = await async_discover_gauges(
        session, state="NSW", latitude=-33.5893, longitude=150.7140, radius_km=50, now=NOW
    )
    assert [(reading.site.key, reading.level_m) for reading in found] == [("nsw:212200", -0.02)]
    assert found[0].site.name == "HAWKESBURY RIVER AT NORTH RICHMOND"

    calls = len(aioclient_mock.mock_calls)
    await async_discover_gauges(session, state="NSW", latitude=-33.5893, longitude=150.7140, radius_km=50, now=NOW)
    nsw_lists = [c for c in aioclient_mock.mock_calls[calls:] if c[1].host == NSW_HOST and "get_db_info" in str(c[1])]
    assert nsw_lists == []
    later = NOW + rivers.RIVER_SITE_CACHE_TTL
    await async_discover_gauges(session, state="NSW", latitude=-33.5893, longitude=150.7140, radius_km=50, now=later)
    assert any(c[1].host == NSW_HOST and "get_db_info" in str(c[1]) for c in aioclient_mock.mock_calls[calls:])


async def test_discover_nz(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Wellington discovery merges council servers, skips failed ones and gauges without data."""
    route(aioclient_mock)  # every council but Greater Wellington answers 503
    session = async_get_clientsession(hass)
    found = await async_discover_gauges(
        session, state="NZ", latitude=-41.2865, longitude=174.7762, radius_km=50, now=NOW
    )
    assert [reading.site.key for reading in found] == ["hilltop_gw:Waiwhetu Stream at Whites Line East"]
    assert found[0].level_m == 0.283


async def test_discover_stops_at_choice_limit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hilltop candidates are probed in batches until enough gauges with data are found."""
    monkeypatch.setattr(rivers, "RIVER_GAUGE_CHOICES", 1)
    monkeypatch.setattr(rivers, "_HILLTOP_CONCURRENCY", 1)
    route(
        aioclient_mock,
        lambda url: respond(url, text=load_text("hilltop_gw_getdata.xml")) if "GetData" in str(url) else None,
    )
    session = async_get_clientsession(hass)
    found = await async_discover_gauges(
        session, state="NZ", latitude=-41.2865, longitude=174.7762, radius_km=50, now=NOW
    )
    assert [reading.site.name for reading in found] == ["Wellington Harbour at Queens Wharf"]
    assert len([c for c in aioclient_mock.mock_calls if "GetData" in str(c[1])]) == 1


async def test_discover_failures(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Discovery fails only when every source fails; states without a source find nothing."""
    route(aioclient_mock, fail_host(QLD_HOST), fail_host(NSW_HOST))
    session = async_get_clientsession(hass)
    with pytest.raises(RiverSourceError):
        await async_discover_gauges(session, state="QLD", latitude=-27.3, longitude=153.0, radius_km=50, now=NOW)
    assert (
        await async_discover_gauges(session, state="VIC", latitude=-37.8, longitude=145.0, radius_km=50, now=NOW) == []
    )


async def test_discover_unexpected_error_propagates(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """A programming error in a source is not hidden as an outage."""

    async def boom(session: object, source: str, now: datetime) -> list[GaugeSite]:
        raise RuntimeError("bug")

    monkeypatch.setattr(rivers, "_async_cached_sites", boom)
    with pytest.raises(RuntimeError):
        await async_discover_gauges(
            async_get_clientsession(hass), state="ACT", latitude=-35.3, longitude=149.1, radius_km=50, now=NOW
        )


async def test_kisters_site_rows_without_coordinates(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Rows with missing or zero coordinates, or not on telemetry, are not candidates."""

    def db_info(url: URL):
        if url.host == QLD_HOST and kisters_request(url)["function"] == "get_db_info":
            rows = [
                {"station": "143001C", "stname": "", "latitude": "-27.44", "longitude": "152.67"},
                {"station": "142001A", "stname": "Zero", "latitude": "0", "longitude": "0"},
                {"station": "142202A", "stname": "Broken", "latitude": "n/a", "longitude": "152.9"},
                {"station": "999999Z", "stname": "Not live", "latitude": "-27.3", "longitude": "152.9"},
            ]
            return respond(url, json_body={"error_num": 0, "return": {"rows": rows}})
        return None

    route(aioclient_mock, db_info)
    sites = await rivers.async_kisters_sites(async_get_clientsession(hass), "qld")
    # Each station type returned the same rows; a station is listed once
    assert sites == [GaugeSite("qld", "143001C", "143001C", -27.44, 152.67)]


def test_river_sources_in_register() -> None:
    """Every gauge service is in the data source register; open ones show the register attribution (#34)."""
    register = (Path(__file__).resolve().parent.parent / REGISTER_PATH).read_text(encoding="utf-8")
    for server in KISTERS_SERVERS.values():
        assert f"https://{server.host}/cgi/webservice.exe" in register
    for server in rivers.HILLTOP_SERVERS.values():
        assert server.url in register
    open_attributions = {
        DATA_SOURCES[key].attribution for key in ("river_qld_wmip", "river_waternsw", "river_hbrc_hilltop")
    }
    assert {KISTERS_SERVERS["qld"].attribution, KISTERS_SERVERS["nsw"].attribution} <= open_attributions
    assert rivers.HILLTOP_SERVERS["hilltop_hbrc"].attribution in open_attributions
    # Unverified councils are credited by name only, without claiming a licence
    unverified = [s.attribution for key, s in rivers.HILLTOP_SERVERS.items() if key != "hilltop_hbrc"]
    assert not any("CC BY" in text for text in unverified)


async def test_kisters_malformed_live_site_list(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Malformed get_sites_by_datasource entries are skipped instead of aborting discovery."""

    def live(url: URL):
        if url.host == QLD_HOST and kisters_request(url)["function"] == "get_sites_by_datasource":
            body = {"error_num": 0, "return": {"datasources": [None, {"sites": "143032A"}, {"sites": ["143032A"]}]}}
            return respond(url, json_body=body)
        return None

    route(aioclient_mock, live)
    sites = await rivers.async_kisters_sites(async_get_clientsession(hass), "qld")
    assert [site.site_id for site in sites] == ["143032A"]
