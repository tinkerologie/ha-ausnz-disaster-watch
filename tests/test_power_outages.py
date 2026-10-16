"""Electricity distributor outage feeds (#36).

The payloads in ``tests/fixtures/power/`` follow the shapes the live feeds returned on
2026-10-16, with made-up incident numbers, places and counts (no upstream records are
copied, so the Endeavour ODbL database is not redistributed). Time is frozen at
2026-10-16 01:00 UTC (12:00 in Sydney and Hobart, 09:00 in Perth, 14:00 in NZ).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import CONF_EXTRA_OUTAGE_FEEDS, CONF_INCLUDE_PLANNED_OUTAGES, DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import PowerOutageItem
from custom_components.ausnz_disaster_watch.providers import (
    POWER_OUTAGE_SOURCES,
    EndeavourOutageSource,
    EssentialEnergyOutageSource,
    MainPowerOutageSource,
    PowercoOutageSource,
    TasNetworksOutageSource,
    UnisonOutageSource,
    WesternPowerOutageSource,
    get_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.power import PowerOutageSource, arcgis_query_url, geojson_rings
from custom_components.ausnz_disaster_watch.providers.power_endeavour import ENDEAVOUR_LIVE_URL, ENDEAVOUR_PLANNED_URL
from custom_components.ausnz_disaster_watch.providers.power_essential import ESSENTIAL_OUTAGES_URL
from custom_components.ausnz_disaster_watch.providers.power_nz import (
    MAINPOWER_OUTAGES_URL,
    POWERCO_OUTAGES_URL,
    UNISON_OUTAGES_URL,
)
from custom_components.ausnz_disaster_watch.providers.power_tasnetworks import TASNETWORKS_OUTAGES_URL, wkt_rings
from custom_components.ausnz_disaster_watch.providers.power_western_power import WESTERN_POWER_OUTAGES_URL
from custom_components.ausnz_disaster_watch.sensor import PowerOutagesCountSensor
from homeassistant.core import HomeAssistant

FIXTURES = Path(__file__).parent / "fixtures" / "power"
NOW = "2026-10-16T01:00:00+00:00"

PENRITH = {"state": "NSW", "latitude": -33.75, "longitude": 150.69, "radius": 50}
DUBBO = {"state": "NSW", "latitude": -32.25, "longitude": 148.6, "radius": 50}
PERTH = {"state": "WA", "latitude": -31.95, "longitude": 115.86, "radius": 50}
WELLINGTON = {"state": "NZ", "latitude": -41.29, "longitude": 174.78, "radius": 50}
WHANGANUI = {"state": "NZ", "latitude": -39.93, "longitude": 175.05, "radius": 100}
RANGIORA = {"state": "NZ", "latitude": -43.30, "longitude": 172.60, "radius": 50}
NAPIER = {"state": "NZ", "latitude": -39.49, "longitude": 176.91, "radius": 50}
HOBART = {"state": "TAS", "latitude": -42.88, "longitude": 147.33, "radius": 50}


def fixture(name: str) -> Any:
    """Return a fixture file: JSON decoded, other files as text."""
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith((".json", ".geojson")) else text


def query(url: str) -> dict[str, str]:
    """Return the single-valued query parameters of a URL."""
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


@pytest.fixture(autouse=True)
def _frozen(freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(NOW)


def by_id(items: list[PowerOutageItem]) -> dict[str | None, PowerOutageItem]:
    """Index outages by ID."""
    return {item.id: item for item in items}


# --- Western Power -------------------------------------------------------------------


async def test_western_power_polygons(hass: HomeAssistant, feed_routes: Any) -> None:
    """Polygon distance is to the edge; F rows (permit, scheduled hours) are planned; stale rows dropped."""
    session = feed_routes({f"{WESTERN_POWER_OUTAGES_URL}/query": fixture("western_power.geojson")})
    source = WesternPowerOutageSource(hass, session, PERTH)

    outages = by_id(await source.async_fetch_power_outages())

    # 3 starts tomorrow, 4 is months past its restoration, 5 (planned) has ended
    assert set(outages) == {"INCD-990001-U", "INCD-990002-X"}
    fault = outages["INCD-990001-U"]
    assert not fault.planned
    assert fault.distance_km == 0.0  # Perth CBD is inside the square
    assert fault.latitude is not None
    assert -31.96 <= fault.latitude <= -31.94
    assert fault.suburb == "Ballajura, Whiteman"
    assert fault.customers_affected == 172
    assert fault.cause == "Under Investigation"
    work = outages["INCD-990002-X"]
    assert work.planned
    assert work.cause == "Planned work"
    assert work.distance_km is not None
    assert work.distance_km > 0

    params = query(feed_routes.requested[0])
    assert params["where"] == "OUTAGETYPE NOT IN ('P','F') AND PLANNEDOUTAGE<>'Planned'"
    assert params["maxAllowableOffset"] == "0.0005"


# --- Endeavour Energy ----------------------------------------------------------------


async def test_endeavour_groups_incidents(hass: HomeAssistant, feed_routes: Any) -> None:
    """Per-suburb groups merge into one outage; planned data is not requested by default."""
    session = feed_routes({ENDEAVOUR_LIVE_URL: fixture("endeavour_live.json")})
    source = EndeavourOutageSource(hass, session, PENRITH)

    outages = by_id(await source.async_fetch_power_outages())

    assert set(outages) == {"INC 9000000001", "INC 9000000002"}
    merged = outages["INC 9000000002"]
    assert merged.suburb == "Baulkham Hills, Norwest"
    assert merged.customers_affected == 30
    assert merged.cause == "Defective equipment"
    assert merged.status == "Repair control room"
    # Coordinates are the record-weighted mean of the groups
    assert merged.latitude == pytest.approx((-33.7626 + 3 * -33.7330) / 4)
    assert outages["INC 9000000001"].cause == "Under Investigation"
    assert outages["INC 9000000001"].restore_time is not None

    assert len(feed_routes.requested) == 1
    params = query(feed_routes.requested[0])
    assert params["where"] == "within_distance(geom, geom'POINT(150.69 -33.75)', 50km)"
    assert "incident_id" in params["group_by"]
    assert "street_name" not in params["select"]
    assert params["limit"] == "100"


async def test_endeavour_planned(hass: HomeAssistant, feed_routes: Any) -> None:
    """Planned work under way is kept, future work dropped; a failing planned dataset keeps the live one."""
    session = feed_routes(
        {ENDEAVOUR_LIVE_URL: fixture("endeavour_live.json"), ENDEAVOUR_PLANNED_URL: fixture("endeavour_planned.json")}
    )
    source = EndeavourOutageSource(hass, session, {**PENRITH, CONF_INCLUDE_PLANNED_OUTAGES: True})

    outages = by_id(await source.async_fetch_power_outages())
    assert set(outages) == {"INC 9000000001", "INC 9000000002", "SP 9000000101"}
    assert outages["SP 9000000101"].planned

    feed_routes.routes[ENDEAVOUR_PLANNED_URL] = 404
    source = EndeavourOutageSource(hass, session, {**PENRITH, CONF_INCLUDE_PLANNED_OUTAGES: True})
    assert set(by_id(await source.async_fetch_power_outages())) == {"INC 9000000001", "INC 9000000002"}


async def test_endeavour_pages(hass: HomeAssistant) -> None:
    """Opendatasoft results are read page by page until a short page."""
    source = EndeavourOutageSource(hass, AsyncMock(), PENRITH)
    record = fixture("endeavour_live.json")["results"][0]
    pages = [{"results": [record] * 100}, {"results": [record]}]
    source.async_fetch_json = AsyncMock(side_effect=pages)  # type: ignore[method-assign]

    outages = await source.async_fetch_power_outages()

    assert len(outages) == 1
    offsets = [query(call.args[0])["offset"] for call in source.async_fetch_json.call_args_list]
    assert offsets == ["0", "100"]


async def test_endeavour_unavailable(hass: HomeAssistant, feed_routes: Any) -> None:
    """A broken live dataset makes the feed unavailable."""
    session = feed_routes({ENDEAVOUR_LIVE_URL: {"error_code": "ODSQLError"}})
    source = EndeavourOutageSource(hass, session, PENRITH)
    with pytest.raises(ProviderUnavailableError):
        await source.async_fetch_power_outages()


# --- Essential Energy ----------------------------------------------------------------


async def test_essential_energy_kml(hass: HomeAssistant, feed_routes: Any) -> None:
    """Placemarks map to outages with polygon distances; placemarks without an ID are skipped."""
    session = feed_routes({ESSENTIAL_OUTAGES_URL: fixture("essential.kml")})
    source = EssentialEnergyOutageSource(hass, session, DUBBO)

    outages = by_id(await source.async_fetch_power_outages())

    assert set(outages) == {"INCD-900001-q", "INCD-900002-r", "INCD-900003-t"}
    fault = outages["INCD-900001-q"]
    assert not fault.planned
    assert fault.distance_km == 0.0
    assert fault.customers_affected == 5
    assert fault.cause == "We are investigating"
    work = outages["INCD-900002-r"]
    assert work.planned
    assert work.cause == "General network maintenance & upgrades"
    unlocated = outages["INCD-900003-t"]
    assert unlocated.latitude is None
    assert unlocated.distance_km is None
    assert unlocated.restore_time is None


@pytest.mark.parametrize(
    ("body", "message"),
    [("<kml><Document>", "malformed KML"), ("<html><body>blocked</body></html>", "unexpected document")],
)
async def test_essential_energy_bad_document(hass: HomeAssistant, feed_routes: Any, body: str, message: str) -> None:
    """A broken or foreign document makes the feed unavailable."""
    session = feed_routes({ESSENTIAL_OUTAGES_URL: body})
    source = EssentialEnergyOutageSource(hass, session, DUBBO)
    with pytest.raises(ProviderUnavailableError, match=message):
        await source.async_fetch_power_outages()


async def test_feeds_outside_their_network_are_not_fetched(hass: HomeAssistant, feed_routes: Any) -> None:
    """Feeds without a spatial query are skipped when the radius cannot reach their network."""
    session = feed_routes({})
    assert await EssentialEnergyOutageSource(hass, session, {**PERTH, "state": "NSW"}).async_fetch_power_outages() == []
    assert await TasNetworksOutageSource(hass, session, {**PERTH, "state": "TAS"}).async_fetch_power_outages() == []
    assert await UnisonOutageSource(hass, session, RANGIORA).async_fetch_power_outages() == []
    assert await MainPowerOutageSource(hass, session, WELLINGTON).async_fetch_power_outages() == []
    assert feed_routes.requested == []


# --- New Zealand ---------------------------------------------------------------------


async def test_unison(hass: HomeAssistant, feed_routes: Any) -> None:
    """Only current Unison outages are kept; the Overall window gives the area."""
    session = feed_routes({UNISON_OUTAGES_URL: fixture("unison.json")})
    outages = by_id(await UnisonOutageSource(hass, session, NAPIER).async_fetch_power_outages())

    assert set(outages) == {"SP 900000001", "INC 900000002"}
    work = outages["SP 900000001"]
    assert work.planned
    assert work.cause == "Planned work"
    assert work.suburb == "Napier"
    assert work.status == "Active"
    assert work.latitude is not None
    assert work.distance_km is not None
    fault = outages["INC 900000002"]
    assert not fault.planned
    assert fault.cause == "Tree on line"
    assert fault.latitude is None
    assert fault.restore_time is None


async def test_unison_unavailable(hass: HomeAssistant, feed_routes: Any) -> None:
    """A payload that is not a list makes the feed unavailable."""
    session = feed_routes({UNISON_OUTAGES_URL: {"message": "maintenance"}})
    with pytest.raises(ProviderUnavailableError):
        await UnisonOutageSource(hass, session, NAPIER).async_fetch_power_outages()


async def test_powerco(hass: HomeAssistant, feed_routes: Any) -> None:
    """Powerco points map to outages; N/A crew status is dropped and quotes are stripped."""
    session = feed_routes({f"{POWERCO_OUTAGES_URL}/query": fixture("powerco.geojson")})
    source = PowercoOutageSource(hass, session, {**WHANGANUI, CONF_INCLUDE_PLANNED_OUTAGES: True})

    outages = by_id(await source.async_fetch_power_outages())

    assert set(outages) == {"JE90000001", "JE90000002"}  # JE90000003 starts on Monday
    fault = outages["JE90000001"]
    assert fault.suburb == "Wanganui East, Whanganui"
    assert fault.status == "Job assigned, field crew en route (Stage 2 of 5)"
    assert fault.customers_affected == 4
    work = outages["JE90000002"]
    assert work.planned
    assert work.status is None
    assert work.suburb == "Hāwera"
    assert work.cause == "Network Project Work"
    assert query(feed_routes.requested[0])["where"] == "1=1"


async def test_mainpower(hass: HomeAssistant, feed_routes: Any) -> None:
    """MainPower jobs map to outages with polygon or point locations; street addresses are cut."""
    session = feed_routes({MAINPOWER_OUTAGES_URL: fixture("mainpower.json")})
    outages = by_id(await MainPowerOutageSource(hass, session, RANGIORA).async_fetch_power_outages())

    # J.90.10.0004 starts on Monday; "not a job" is skipped
    assert set(outages) == {"J.90.10.0001", "J.90.10.0002", "J.90.10.0005"}
    assert outages["J.90.10.0005"].latitude is None  # "unknown" latitude
    work = outages["J.90.10.0001"]
    assert work.planned
    assert work.suburb == "Kaiapoi"
    assert work.status == "On-Site"
    assert work.distance_km is not None
    fault = outages["J.90.10.0002"]
    assert not fault.planned
    assert (fault.latitude, fault.longitude) == (-43.305, 172.595)
    assert fault.status is None
    assert fault.cause == "Under Investigation"
    assert fault.restore_time is None


@pytest.mark.parametrize("current", [[], None, ""])
async def test_mainpower_no_current_outages(hass: HomeAssistant, feed_routes: Any, current: Any) -> None:
    """An empty current_outages value means no outages."""
    session = feed_routes({MAINPOWER_OUTAGES_URL: {"current_outages": current}})
    assert await MainPowerOutageSource(hass, session, RANGIORA).async_fetch_power_outages() == []


async def test_mainpower_unavailable(hass: HomeAssistant, feed_routes: Any) -> None:
    """A foreign current_outages value makes the feed unavailable."""
    session = feed_routes({MAINPOWER_OUTAGES_URL: {"current_outages": ["x"]}})
    with pytest.raises(ProviderUnavailableError):
        await MainPowerOutageSource(hass, session, RANGIORA).async_fetch_power_outages()


# --- TasNetworks ---------------------------------------------------------------------


async def test_tasnetworks(hass: HomeAssistant, feed_routes: Any) -> None:
    """TasNetworks outages map with WKT polygons or centroids; free-text restoration is kept."""
    session = feed_routes({TASNETWORKS_OUTAGES_URL: fixture("tasnetworks.json")})
    outages = by_id(await TasNetworksOutageSource(hass, session, HOBART).async_fetch_power_outages())

    assert set(outages) == {"J9000000001", "J9000000002"}
    fault = outages["J9000000001"]
    assert not fault.planned
    assert fault.suburb == "Mountain River"
    assert fault.customers_affected == 37
    assert fault.restore_time == "This Afternoon"
    assert fault.status == "Enroute"
    assert fault.distance_km is not None
    work = outages["J9000000002"]
    assert work.planned
    assert (work.latitude, work.longitude) == (-41.4498, 147.1394)
    assert work.suburb == "Launceston, South Launceston"


async def test_tasnetworks_unavailable(hass: HomeAssistant, feed_routes: Any) -> None:
    """A payload that is not a list makes the feed unavailable."""
    session = feed_routes({TASNETWORKS_OUTAGES_URL: {"Message": "error"}})
    with pytest.raises(ProviderUnavailableError):
        await TasNetworksOutageSource(hass, session, HOBART).async_fetch_power_outages()


def test_wkt_rings() -> None:
    """WKT polygons and multipolygons give (lat, lon) rings; degenerate rings are dropped."""
    assert wkt_rings("POLYGON ((1 2, 3 4, 5 6, 1 2))") == (((2.0, 1.0), (4.0, 3.0), (6.0, 5.0), (2.0, 1.0)),)
    assert len(wkt_rings("MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)), ((0 0, 1 1)))")) == 1
    assert wkt_rings(None) == ()


# --- Shared base ---------------------------------------------------------------------


async def test_arcgis_paging_and_errors(hass: HomeAssistant) -> None:
    """ArcGIS pages are followed while the transfer limit is exceeded; an error object fails the feed."""
    source = WesternPowerOutageSource(hass, AsyncMock(), PERTH)
    feature = fixture("western_power.geojson")["features"][0]
    pages = [
        {"features": [feature], "exceededTransferLimit": True},
        {"features": [feature], "properties": {"exceededTransferLimit": False}},
    ]
    source.async_fetch_json = AsyncMock(side_effect=pages)  # type: ignore[method-assign]
    assert len(await source.async_fetch_power_outages()) == 2  # same ID twice: the coordinator de-duplicates
    offsets = [query(call.args[0])["resultOffset"] for call in source.async_fetch_json.call_args_list]
    assert offsets == ["0", "1000"]

    source = WesternPowerOutageSource(hass, AsyncMock(), PERTH)
    source.async_fetch_json = AsyncMock(return_value={"error": {"code": 400}})  # type: ignore[method-assign]
    with pytest.raises(ProviderUnavailableError, match="returned an error"):
        await source.async_fetch_power_outages()


async def test_arcgis_page_limit(hass: HomeAssistant) -> None:
    """Paging stops after the page limit."""
    source = PowercoOutageSource(hass, AsyncMock(), WHANGANUI)
    page = {"features": [], "exceededTransferLimit": True}
    source.async_fetch_json = AsyncMock(return_value=page)  # type: ignore[method-assign]
    assert await source.async_fetch_power_outages() == []
    assert source.async_fetch_json.await_count == 5


async def test_fetch_interval_and_location(
    hass: HomeAssistant, feed_routes: Any, freezer: FrozenDateTimeFactory
) -> None:
    """A feed is fetched at most every five minutes, or again when the monitored point moves."""
    session = feed_routes({f"{POWERCO_OUTAGES_URL}/query": fixture("powerco.geojson")})
    source = PowercoOutageSource(hass, session, WHANGANUI)

    first = await source.async_fetch_power_outages()
    assert await source.async_fetch_power_outages() is first
    assert len(feed_routes.requested) == 1

    source.set_location(WHANGANUI["latitude"], WHANGANUI["longitude"])  # same point: cache kept
    await source.async_fetch_power_outages()
    assert len(feed_routes.requested) == 1

    source.set_location(-39.9, 175.0)
    await source.async_fetch_power_outages()
    assert len(feed_routes.requested) == 2

    freezer.tick(301)
    await source.async_fetch_power_outages()
    assert len(feed_routes.requested) == 3


async def test_source_basics(hass: HomeAssistant) -> None:
    """Sources publish no hazards and describe their licence."""
    source = EndeavourOutageSource(hass, AsyncMock(), {"state": "nsw"})
    assert source.state_code == "NSW"
    assert await source.async_fetch_hazards() == []
    assert source.radius_km == 50
    assert source.reaches_service_area()  # no service area: always fetched
    meta = source.metadata()
    assert meta["distributor"] == "Endeavour Energy"
    assert meta["licence"] == "ODbL 1.0"
    assert meta["status"] == "open"
    assert "ODbL" in meta["attribution"]
    # Invalid, null-island and out-of-range points have no location
    assert source.located(lat=float("nan"), lon=150.0) == (None, None, None)
    assert source.located(lat=0.0, lon=0.0) == (None, None, None)
    assert source.located(lat=-95.0, lon=150.0) == (None, None, None)
    assert source.located({"type": "Point", "coordinates": [1]}) == (None, None, None)
    assert PowerOutageSource.time_text(None) is None


def test_geojson_rings() -> None:
    """Outer rings come from polygons and multipolygons; other shapes give none."""
    square = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    assert geojson_rings({"type": "Polygon", "coordinates": [square]}) == (
        ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.0, 0.0)),
    )
    assert len(geojson_rings({"type": "MultiPolygon", "coordinates": [[square], [], [[[0, 0], [1, 1]]]]})) == 1
    assert geojson_rings({"type": "Point", "coordinates": [0, 0]}) == ()
    assert geojson_rings(None) == ()


def test_arcgis_query_url_extra_parameters() -> None:
    """Extra parameters are added to the query."""
    url = arcgis_query_url("https://example.com/FeatureServer/0", -27.0, 153.0, 12.5, geometryPrecision="4")
    params = query(url)
    assert params["distance"] == "12.5"
    assert params["geometryPrecision"] == "4"
    assert params["where"] == "1=1"


def test_factory_adds_sources_per_state(hass: HomeAssistant) -> None:
    """Each state gets its distributors' feeds; opt-in feeds only with extra outage feeds on."""
    for state, expected in POWER_OUTAGE_SOURCES.items():
        for extra in (False, True):
            providers = get_providers_for_config(hass, AsyncMock(), {"state": state, CONF_EXTRA_OUTAGE_FEEDS: extra})
            wanted = [cls for cls in expected if extra or not cls.opt_in]
            assert [type(p) for p in providers if isinstance(p, PowerOutageSource)] == wanted
    assert [cls.__name__ for cls in POWER_OUTAGE_SOURCES["WA"] if cls.opt_in] == ["WesternPowerOutageSource"]
    for state in ("QLD", "VIC", "SA", "NT"):
        providers = get_providers_for_config(hass, AsyncMock(), {"state": state, CONF_EXTRA_OUTAGE_FEEDS: True})
        assert not [p for p in providers if isinstance(p, PowerOutageSource)]


# --- Coordinator and entities ----------------------------------------------------------


def _entry(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"state": "NSW", "location_mode": "custom", "latitude": -33.75, "longitude": 150.69, "radius": 50},
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


def _provider(outages: list[PowerOutageItem]) -> AsyncMock:
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_power_outages.return_value = outages
    for name in ("road_closures", "weather_warnings", "emergency_news", "weather_telemetry", "air_quality"):
        getattr(provider, f"async_fetch_{name}").return_value = []
    provider.async_fetch_relief_facilities.return_value = []
    provider.async_fetch_cameras.return_value = []
    provider.async_fetch_nearby_councils.return_value = []
    provider.async_fetch_fire_danger.return_value = None
    return provider


def _source(distributor: str, outages: list[PowerOutageItem] | Exception) -> AsyncMock:
    source = AsyncMock(spec=EndeavourOutageSource)
    source.distributor = distributor
    source.metadata.return_value = {"distributor": distributor}
    if isinstance(outages, Exception):
        source.async_fetch_power_outages.side_effect = outages
    else:
        source.async_fetch_power_outages.return_value = outages
    return source


COUNCIL = PowerOutageItem(suburb="Windsor", customers_affected=9, latitude=-33.6, longitude=150.8)
COUNCIL_FAR = PowerOutageItem(suburb="Bathurst", customers_affected=9, latitude=-33.42, longitude=149.58)


def _direct(id_: str, distance: float | None, *, planned: bool = False, customers: int = 1) -> PowerOutageItem:
    return PowerOutageItem(
        id=id_, distributor="Endeavour Energy", planned=planned, distance_km=distance, customers_affected=customers
    )


async def test_coordinator_combines_outage_feeds(hass: HomeAssistant) -> None:
    """Planned and far outages are dropped, duplicates merged, a failing feed skipped, nearest first."""
    coordinator = AustralianDisasterWatchCoordinator(hass, _entry(hass))
    coordinator.providers = [_provider([COUNCIL, COUNCIL_FAR])]
    coordinator.power_sources = [  # type: ignore[list-item]
        _source(
            "Endeavour Energy",
            [
                _direct("near", 3.0),
                _direct("near", 3.0),
                _direct("unlocated", None),
                _direct("closest", 0.5),
                _direct("far", 80.0),
                _direct("work", 1.0, planned=True),
            ],
        ),
        _source("Essential Energy", ProviderUnavailableError("down")),
    ]

    await coordinator.async_refresh()

    assert [(o.id, o.suburb) for o in coordinator.power_outages] == [
        ("closest", ""),
        ("near", ""),
        (None, "Windsor"),
        ("unlocated", ""),
    ]
    assert coordinator.power_outages[2].distance_km is not None  # measured from its coordinates

    sensor = PowerOutagesCountSensor(coordinator)
    attrs = sensor.extra_state_attributes
    assert sensor.native_value == 4
    assert attrs["est_restore"] is None
    assert attrs["nearest_outage_distance_km"] == 0.5
    assert attrs["nearest_outage_distributor"] == "Endeavour Energy"
    assert attrs["data_sources"] == [{"distributor": "Endeavour Energy"}, {"distributor": "Essential Energy"}]


async def test_coordinator_includes_planned_outages_when_asked(hass: HomeAssistant) -> None:
    """With the option on, planned outages under way count."""
    coordinator = AustralianDisasterWatchCoordinator(hass, _entry(hass, **{CONF_INCLUDE_PLANNED_OUTAGES: True}))
    coordinator.providers = [_provider([])]
    coordinator.power_sources = [_source("Endeavour Energy", [_direct("work", 1.0, planned=True)])]  # type: ignore[list-item]

    await coordinator.async_refresh()

    assert [o.id for o in coordinator.power_outages] == ["work"]


async def test_coordinator_power_sources_and_cancellation(hass: HomeAssistant) -> None:
    """The real factory splits sources from hazard providers; a cancelled feed is not swallowed."""
    coordinator = AustralianDisasterWatchCoordinator(hass, _entry(hass))
    assert {type(s) for s in coordinator.power_sources} == {EndeavourOutageSource, EssentialEnergyOutageSource}
    assert not any(isinstance(p, PowerOutageSource) for p in coordinator.providers)
    assert [s["distributor"] for s in coordinator.power_outage_sources] == ["Endeavour Energy", "Essential Energy"]
    # Sources follow the monitored point
    assert all(s.latitude == -33.75 for s in coordinator.power_sources)

    coordinator.power_sources = [_source("Endeavour Energy", KeyboardInterrupt())]  # type: ignore[list-item]
    with pytest.raises(KeyboardInterrupt):
        await coordinator._collect_distributor_outages([])


@pytest.mark.parametrize(
    ("state", "fields"),
    [
        ("NSW", [CONF_INCLUDE_PLANNED_OUTAGES]),
        ("WA", [CONF_INCLUDE_PLANNED_OUTAGES, CONF_EXTRA_OUTAGE_FEEDS]),
        ("NZ", [CONF_INCLUDE_PLANNED_OUTAGES, CONF_EXTRA_OUTAGE_FEEDS]),
        ("QLD", None),
    ],
)
async def test_options_power_outage_page(hass: HomeAssistant, state: str, fields: list[str] | None) -> None:
    """States with a distributor feed get a power outage options page; saving keeps other options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"state": state, "location_mode": "custom", "latitude": -33.75, "longitude": 150.69, "radius": 50},
        options={"radius": 30},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    menu = result["menu_options"]
    if fields is None:
        assert "power_outages" not in menu
        return
    expected_index = menu.index("roads") + 1 if "roads" in menu else 1
    assert menu.index("power_outages") == expected_index
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "power_outages"})
    assert result["step_id"] == "power_outages"
    assert [str(key) for key in result["data_schema"].schema] == fields
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        await hass.config_entries.options.async_configure(result["flow_id"], dict.fromkeys(fields, True))
    assert entry.options == {"radius": 30, **dict.fromkeys(fields, True)}
