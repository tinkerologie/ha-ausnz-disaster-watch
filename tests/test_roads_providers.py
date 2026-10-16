"""Tests for the statewide road event providers (#29), driven by recorded feed fixtures."""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlsplit

from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.ausnz_disaster_watch.const import CONF_INCLUDE_ROADWORKS, CONF_VIC_API_KEY
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.roads import (
    NSWRoadProvider,
    NTRoadProvider,
    QueenslandRoadProvider,
    SARoadProvider,
    TasmaniaRoadProvider,
    VictoriaRoadProvider,
    WARoadProvider,
    get_road_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.roads.base import (
    ARCGIS_MAX_PAGES,
    BaseRoadProvider,
    envelope,
    first_point,
    is_minor_incident,
    mapping,
    text,
    valid_point,
)
from custom_components.ausnz_disaster_watch.providers.roads.nsw import _upstream_id
from custom_components.ausnz_disaster_watch.providers.roads.nt import nt_point
from homeassistant.core import HomeAssistant

FIXTURES = Path(__file__).parent / "fixtures" / "roads"
EMPTY = {"type": "FeatureCollection", "features": []}


def load(name: str) -> Any:
    """Load a recorded road feed fixture."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def routed(provider: BaseRoadProvider, routes: dict[str, Any], default: Any = EMPTY) -> AsyncMock:
    """Route the provider's JSON fetches by URL substring to payloads (or exceptions)."""

    async def fetch(url: str, headers: dict[str, str] | None = None) -> Any:
        for key, payload in routes.items():
            if key in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        return default

    mock = AsyncMock(side_effect=fetch)
    provider.async_fetch_json = mock  # type: ignore[method-assign]
    return mock


def by_id(items: list[RoadClosureItem]) -> dict[str, RoadClosureItem]:
    """Index items by ID."""
    return {item.id: item for item in items}


def make(cls: type[BaseRoadProvider], hass: HomeAssistant, **config: Any) -> Any:
    """Build a road provider with a dummy session."""
    return cls(hass, MagicMock(), config)


# --- helpers ---------------------------------------------------------------------------


def test_first_point_shapes() -> None:
    """The first vertex is used; an explicit Point in a collection wins; bad geometry is None."""
    assert first_point({"type": "Point", "coordinates": [153.0, -27.0]}) == (-27.0, 153.0)
    assert first_point({"type": "LineString", "coordinates": [[150.0, -30.0], [151.0, -31.0]]}) == (-30.0, 150.0)
    assert first_point({"type": "MultiLineString", "coordinates": [[[145.0, -17.0], [146.0, -18.0]]]}) == (
        -17.0,
        145.0,
    )
    assert first_point({"type": "MultiPoint", "coordinates": [[147.0, -42.0]]}) == (-42.0, 147.0)
    collection = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "LineString", "coordinates": [[140.0, -33.0], [141.0, -34.0]]},
            {"type": "Point", "coordinates": [142.0, -35.0]},
        ],
    }
    assert first_point(collection) == (-35.0, 142.0)
    assert first_point({"type": "Feature", "geometry": {"type": "Point", "coordinates": [130.0, -12.0]}}) == (
        -12.0,
        130.0,
    )
    bad_collection = {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": []}, "x"]}
    assert first_point(bad_collection) is None
    assert first_point(None) is None
    assert first_point({"type": "Point", "coordinates": [500.0, -27.0]}) is None
    assert first_point({"type": "Point", "coordinates": [0, 0]}) is None
    assert first_point({"type": "LineString", "coordinates": []}) is None


def test_scalar_helpers() -> None:
    """text, mapping, valid_point and is_minor_incident."""
    assert text(None) == ""
    assert text({"a": 1}) == ""
    assert text(" Road ") == "Road"
    assert mapping(None) == {}
    assert mapping({"a": 1}) == {"a": 1}
    assert valid_point("x", 1) is None
    assert valid_point(float("nan"), 1) is None
    assert valid_point("-27.5", "153.1") == (-27.5, 153.1)
    assert is_minor_incident("BREAKDOWN")
    assert is_minor_incident(None, "Traffic lights blacked out")
    assert not is_minor_incident("CRASH", None)


def test_envelope() -> None:
    """The radius box is centred on the location; no location means no box."""
    assert envelope({}) is None
    xmin, ymin, xmax, ymax = envelope({"latitude": -27.0, "longitude": 153.0, "radius": 111})  # type: ignore[misc]
    assert ymin == pytest.approx(-28.0, abs=0.01)
    assert ymax == pytest.approx(-26.0, abs=0.01)
    assert xmin < 153.0 < xmax
    assert envelope({"latitude": -27.0, "longitude": 153.0, "radius": "bad"}) is not None


def test_nt_point_order() -> None:
    """NT Road Report points are [latitude, longitude]."""
    assert nt_point([-14.36, 131.55]) == (-14.36, 131.55)
    assert nt_point(None) is None
    assert nt_point([131.55, -14.36]) is None  # GeoJSON order is out of range as a latitude


def test_nsw_upstream_id() -> None:
    """Float IDs lose their .0; missing IDs are malformed."""
    assert _upstream_id(164430.0) == "164430"
    assert _upstream_id(286275) == "286275"
    for bad in (None, True, ""):
        with pytest.raises(ValueError):
            _upstream_id(bad)


# --- base road provider ------------------------------------------------------------------


async def test_road_provider_throttle_and_last_good(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Results are reused for a few minutes; an outage keeps the last good items, then fails."""
    provider = make(NTRoadProvider, hass)
    assert await provider.async_fetch_hazards() == []
    mock = routed(provider, {"GetAll": load("nt_obstructions")})
    first = await provider.async_fetch_road_closures()
    assert first
    assert await provider.async_fetch_road_closures() == first
    assert mock.await_count == 1

    freezer.tick(timedelta(minutes=5))
    routed(provider, {"GetAll": ProviderUnavailableError("down")})
    assert await provider.async_fetch_road_closures() == first  # bridged

    freezer.tick(timedelta(minutes=40))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_road_closures()
    freezer.tick(timedelta(minutes=5))
    with pytest.raises(ProviderUnavailableError):  # nothing cached any more
        await provider.async_fetch_road_closures()


async def test_collect_road_sources_partial_and_total_failure(hass: HomeAssistant) -> None:
    """One failed Live Traffic feed is tolerated; all failing raises; bugs propagate."""
    provider = make(NSWRoadProvider, hass)
    routed(
        provider,
        {
            "flood.json": load("nsw_flood"),
            "incident.json": ProviderUnavailableError("timeout"),
            "lga-incidents": {"features": "broken"},
        },
    )
    items = await provider.async_fetch_road_closures()
    assert {item.id for item in items} == {"NSW_286275"}

    provider = make(NSWRoadProvider, hass)
    routed(provider, {}, default=None)  # every feed returns a non-object
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_road_closures()

    provider = make(NSWRoadProvider, hass)
    routed(provider, {"flood.json": RuntimeError("bug")})
    with pytest.raises(RuntimeError):
        await provider.async_fetch_road_closures()

    provider = make(NSWRoadProvider, hass)
    routed(provider, {"flood.json": {"features": [None, {"properties": {}}]}})
    assert await provider.async_fetch_road_closures() == []  # malformed features are skipped


async def test_arcgis_query_envelope_paging_and_errors(hass: HomeAssistant) -> None:
    """ArcGIS queries send the radius box, page while the limit is exceeded and stop at the cap."""
    provider = make(SARoadProvider, hass, latitude=-34.93, longitude=138.6, radius=50)
    page = {"type": "FeatureCollection", "exceededTransferLimit": True, "features": [{"properties": {}}]}
    mock = routed(provider, {"query": page})
    features = await provider.async_arcgis_query("https://example.com/0", "test", "1=1")
    assert len(features) == ARCGIS_MAX_PAGES
    query = parse_qs(urlsplit(mock.await_args_list[1].args[0]).query)
    assert query["geometryType"] == ["esriGeometryEnvelope"]
    assert query["inSR"] == ["4326"]
    assert query["resultOffset"] == ["1000"]
    assert len(query["geometry"][0].split(",")) == 4

    provider = make(SARoadProvider, hass)  # no location: no box
    mock = routed(provider, {"query": EMPTY})
    await provider.async_arcgis_query("https://example.com/0", "test")
    assert "geometry" not in parse_qs(urlsplit(mock.await_args.args[0]).query)

    routed(provider, {"query": {"error": {"code": 400}}})
    with pytest.raises(ProviderUnavailableError):
        await provider.async_arcgis_query("https://example.com/0", "test")


# --- NSW ---------------------------------------------------------------------------------


async def test_nsw_road_events(hass: HomeAssistant) -> None:
    """Live Traffic flood, incident and council feeds map to categories; minor and ended skip."""
    provider = make(NSWRoadProvider, hass)
    mock = routed(
        provider,
        {
            "flood.json": load("nsw_flood"),
            "incident.json": load("nsw_incident"),
            "lga-incidents": load("nsw_lga_incidents"),
        },
    )
    items = by_id(await provider.async_fetch_road_closures())
    urls = [call.args[0] for call in mock.await_args_list]
    assert not any("roadwork" in url or "majorevent" in url for url in urls)

    flood = items["NSW_286275"]
    assert flood.category == RoadEventCategory.FLOODING
    assert flood.is_flooding
    assert (flood.road, flood.suburb, flood.status) == ("Hewart Downs Road", "Milparinka", "Closed")
    assert flood.latitude == pytest.approx(-29.470923)
    assert flood.advice == "Never drive through floodwater. Plan your journey"
    assert flood.updated_at is not None
    assert flood.updated_at.tzinfo is not None
    assert items["NSW_286274"].category == RoadEventCategory.CLOSURE
    assert items["NSW_286281"].category == RoadEventCategory.HAZARD
    assert items["NSW_164430"].category == RoadEventCategory.ROADWORKS  # planned, float ID
    council_flood = items["NSW_LGA_291152"]
    assert council_flood.category == RoadEventCategory.FLOODING
    assert council_flood.source.endswith("(Live Traffic NSW)")
    assert items["NSW_LGA_286793"].category == RoadEventCategory.SPECIAL_EVENT
    assert not any(item.reason and "Breakdown" in item.reason for item in items.values())
    assert len(items) == 7  # the ended crash and the breakdown are skipped


async def test_nsw_fetches_planned_feeds_when_enabled(hass: HomeAssistant) -> None:
    """roadwork.json and majorevent.json are read only with the roadworks option on."""
    provider = make(NSWRoadProvider, hass, **{CONF_INCLUDE_ROADWORKS: True})
    roadwork = {
        "features": [
            {
                "id": 1,
                "geometry": {"type": "Point", "coordinates": [151.0, -33.0]},
                "properties": {"mainCategory": "SCHEDULED ROADWORK", "incidentKind": "Planned", "roads": []},
            },
            {"id": 2, "geometry": None, "properties": {"mainCategory": "SCHEDULED ROADWORK"}},
        ]
    }
    mock = routed(provider, {"roadwork.json": roadwork})
    items = await provider.async_fetch_road_closures()
    assert any("majorevent" in call.args[0] for call in mock.await_args_list)
    assert [(item.id, item.category, item.road) for item in items] == [
        ("NSW_1", RoadEventCategory.ROADWORKS, "Scheduled Roadwork")
    ]


# --- QLD ---------------------------------------------------------------------------------


async def test_qld_road_events(hass: HomeAssistant) -> None:
    """QLDTraffic events: TMR_ IDs, categories, Brisbane timestamps, congestion skipped."""
    provider = make(QueenslandRoadProvider, hass)
    events = load("qld_events_v2")
    events["features"].extend(
        [
            {"type": "Feature", "geometry": None, "properties": {"id": 1, "status": "Published"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [153, -27]}, "properties": {"id": 2}},
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [153, -27]},
                "properties": {"status": "Draft"},
            },
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [153, -27]}, "properties": {}},
        ]
    )
    routed(provider, {"events_v2": events})
    items = by_id(await provider.async_fetch_road_closures())

    flood = items["TMR_717127"]
    assert flood.category == RoadEventCategory.FLOODING
    assert (flood.road, flood.suburb) == ("Dugandan Road", "Bunya")
    assert flood.source == "QLDTraffic (City of Moreton Bay)"
    assert flood.reason == "Flash flooding, Heavy rain"
    assert flood.updated_at is not None
    assert flood.updated_at.isoformat() == "2026-05-29T01:40:01.352716+00:00"
    assert items["TMR_548467"].category == RoadEventCategory.ROADWORKS
    assert items["TMR_248797"].category == RoadEventCategory.CLOSURE
    assert items["TMR_459421"].category == RoadEventCategory.HAZARD
    special = items["TMR_767632"]
    assert special.category == RoadEventCategory.SPECIAL_EVENT
    assert special.status == "Special event"  # "N/A" impact placeholder ignored
    assert items["TMR_539691"].latitude == pytest.approx(-17.5076709, abs=1e-6)  # Point of a collection
    hazard_without_source = items["TMR_2"]
    assert hazard_without_source.source == "QLDTraffic (TMR)"
    assert hazard_without_source.road == "Road"
    assert len(items) == 7  # congestion, stationary vehicle, unlocated, draft and id-less skipped


# --- VIC ---------------------------------------------------------------------------------


async def test_vic_needs_a_key(hass: HomeAssistant) -> None:
    """Without a key there is no provider and no request; with a key the KeyID header is sent."""
    session = MagicMock()
    assert get_road_providers_for_config(hass, session, {"state": "VIC"}) == []
    assert get_road_providers_for_config(hass, session, {"state": "VIC", CONF_VIC_API_KEY: "  "}) == []
    assert get_road_providers_for_config(hass, session, {"state": "ACT"}) == []
    assert get_road_providers_for_config(hass, session, {"state": "NZ"}) == []
    (vic,) = get_road_providers_for_config(hass, session, {"state": "vic", CONF_VIC_API_KEY: "secret"})
    assert isinstance(vic, VictoriaRoadProvider)
    for state, cls in (
        ("NSW", NSWRoadProvider),
        ("QLD", QueenslandRoadProvider),
        ("SA", SARoadProvider),
        ("WA", WARoadProvider),
        ("NT", NTRoadProvider),
        ("TAS", TasmaniaRoadProvider),
    ):
        assert isinstance(get_road_providers_for_config(hass, session, {"state": state})[0], cls)

    keyless = make(VictoriaRoadProvider, hass)
    mock = routed(keyless, {})
    assert await keyless.async_fetch_road_closures() == []
    mock.assert_not_awaited()


async def test_vic_road_events(hass: HomeAssistant) -> None:
    """DTP v3 pages are followed; flooding, closures and hazards map; reopened and breakdowns skip."""
    provider = make(VictoriaRoadProvider, hass, **{CONF_VIC_API_KEY: " secret "})
    mock = routed(provider, {"page=1": load("vic_unplanned_p1"), "page=2": load("vic_unplanned_p2")})
    items = by_id(await provider.async_fetch_road_closures())
    assert mock.await_args_list[0].kwargs["headers"] == {"KeyID": "secret"}
    assert mock.await_count == 2

    flood = items["VIC_88123"]
    assert flood.category == RoadEventCategory.FLOODING
    assert (flood.road, flood.suburb) == ("Yarra Glen Road", "Yarra Glen")
    assert flood.updated_at is not None
    assert flood.updated_at.isoformat() == "2026-10-15T19:12:00+00:00"
    assert items["VIC_88124"].category == RoadEventCategory.HAZARD  # lanes closed, road open
    assert items["VIC_88127_1"].road == "Belgrave-Gembrook Road"
    assert set(items) == {"VIC_88123", "VIC_88124", "VIC_88127_1"}

    # A bare FeatureCollection (no meta) is accepted; a record without any ID is skipped
    provider = make(VictoriaRoadProvider, hass, **{CONF_VIC_API_KEY: "k"})
    bare = {
        "type": "FeatureCollection",
        "features": [
            {"geometry": {"type": "Point", "coordinates": [145, -37]}, "properties": {"eventType": "Hazard"}},
            {
                "geometry": None,
                "properties": {"id": "9", "eventType": "Hazard", "impact": {"impactType": "Road closed"}},
            },
            {
                "geometry": {"type": "Point", "coordinates": [145, -37]},
                "properties": {"id": "10", "impact": {"impactType": "Road closed"}, "closedRoadName": "X Rd"},
            },
        ],
    }
    routed(provider, {"page=1": bare})
    (item,) = await provider.async_fetch_road_closures()
    assert (item.id, item.category) == ("VIC_10", RoadEventCategory.CLOSURE)


# --- SA ----------------------------------------------------------------------------------


async def test_sa_road_events(hass: HomeAssistant) -> None:
    """Traffic SA: only incidents are requested by default; closures read flooding from the text."""
    provider = make(SARoadProvider, hass, latitude=-34.93, longitude=138.6, radius=300)
    layer0 = load("sa_layer0")
    layer0["features"].append(
        {
            "geometry": {"type": "Point", "coordinates": [138.6, -34.9]},
            "properties": {"ROADWORKS_AND_INCIDENTS_ID": "1", "REC_TYPE": "INCIDENT", "DESCRIPTION": "Crash"},
        }
    )
    layer0["features"].append(
        {
            "geometry": None,
            "properties": {
                "ROADWORKS_AND_INCIDENTS_ID": "2",
                "REC_TYPE": "INCIDENT",
                "DESCRIPTION": "Road closed - flooding",
                "LATITUDE": -34.8,
                "LONGITUDE": 138.5,
                "NO_LANES_CLOSED": "Closure",
            },
        }
    )
    layer0["features"].append(
        {
            "geometry": None,
            "properties": {"REC_TYPE": "INCIDENT", "DESCRIPTION": "Road closed", "LATITUDE": -34.8, "LONGITUDE": 138.5},
        }
    )
    layer0["features"].append(
        {"geometry": None, "properties": {"ROADWORKS_AND_INCIDENTS_ID": "3", "REC_TYPE": "INCIDENT"}}
    )
    layer0["features"].append(
        {
            "geometry": {"type": "Point", "coordinates": [138.6, -34.9]},
            "properties": {"ROADWORKS_AND_INCIDENTS_ID": "4", "REC_TYPE": "INCIDENT", "END_DATE": 1_000_000_000_000},
        }
    )
    layer0["features"].append(
        {
            "geometry": {"type": "Point", "coordinates": [138.6, -34.9]},
            "properties": {
                "ROADWORKS_AND_INCIDENTS_ID": "5",
                "REC_TYPE": "INCIDENT",
                "DESCRIPTION": "Tree on road, closed",
            },
        }
    )
    layer1 = load("sa_layer1")
    layer1["features"].extend(
        [
            {"geometry": None, "properties": {"LOCATION_ID": 1, "PLOT_TYPE": "RD_CLOSURE"}},
            {"geometry": {"type": "Point", "coordinates": [138.6, -34.9]}, "properties": {"PLOT_TYPE": "DETOUR"}},
            {"geometry": {"type": "Point", "coordinates": [138.6, -34.9]}, "properties": {"PLOT_TYPE": "RD_CLOSURE"}},
        ]
    )
    mock = routed(provider, {"MapServer/0/": layer0, "MapServer/1/": layer1})
    items = by_id(await provider.async_fetch_road_closures())
    where = parse_qs(urlsplit(mock.await_args_list[0].args[0]).query)["where"][0]
    assert where == "REC_TYPE='INCIDENT'"

    assert items["SA_CLOSURE_105433"].category == RoadEventCategory.FLOODING
    assert items["SA_CLOSURE_105433"].road == "Morgan Mail Road"
    assert items["SA_CLOSURE_105434"].category == RoadEventCategory.CLOSURE
    assert items["SA_1"].category == RoadEventCategory.HAZARD
    assert items["SA_2"].category == RoadEventCategory.FLOODING
    assert items["SA_2"].status == "Closed"
    assert items["SA_5"].category == RoadEventCategory.CLOSURE
    assert items["SA_3405081526"].category == RoadEventCategory.ROADWORKS  # fixture rows are roadworks
    assert "SA_4" not in items  # ended
    assert not any("Ferry" in (item.reason or "") for item in items.values())

    provider = make(SARoadProvider, hass, **{CONF_INCLUDE_ROADWORKS: True})
    mock = routed(provider, {})
    await provider.async_fetch_road_closures()
    assert parse_qs(urlsplit(mock.await_args_list[0].args[0]).query)["where"] == ["1=1"]


# --- WA ----------------------------------------------------------------------------------


async def test_wa_road_events(hass: HomeAssistant) -> None:
    """Main Roads WA: shared incident/closure IDs collapse; ClosureTyp decides closures."""
    provider = make(WARoadProvider, hass)
    layer1 = load("wa_layer1")
    point = {"type": "Point", "coordinates": [115.86, -31.95]}
    layer1["features"].extend(
        [
            {"geometry": point, "properties": {"Id": 1, "IncidentTy": "Flooding", "ClosureTyp": "Road closed"}},
            {"geometry": point, "properties": {"Id": 2, "IncidentTy": "Crash", "ClosureTyp": "Road closed"}},
            {"geometry": point, "properties": {"Id": 3, "IncidentTy": "Bushfire", "TrafficCon": "Road Closure"}},
            {"geometry": None, "properties": {"Id": 4}},
            {"geometry": point, "properties": {"IncidentTy": "Crash"}},
        ]
    )
    mock = routed(provider, {"FeatureServer/1/": layer1, "FeatureServer/4/": load("wa_layer4")})
    items = by_id(await provider.async_fetch_road_closures())
    assert parse_qs(urlsplit(mock.await_args_list[0].args[0]).query)["where"] == ["publishExt='Yes'"]
    assert not any("/FeatureServer/2/" in call.args[0] for call in mock.await_args_list)

    assert items["WA_236828"].category == RoadEventCategory.HAZARD  # "Road open with caution"
    assert items["WA_236828"].latitude == pytest.approx(-28.3480258541404)  # incident point wins
    assert items["WA_1"].category == RoadEventCategory.FLOODING
    assert items["WA_2"].category == RoadEventCategory.CLOSURE
    assert items["WA_3"].category == RoadEventCategory.CLOSURE
    assert items["WA_236683"].updated_at is not None
    assert items["WA_236683"].updated_at.isoformat() == "2026-10-15T22:05:42+00:00"  # Perth local
    assert not any(item.reason == "Break Down / Tow Away" for item in items.values())


async def test_wa_planned_layers(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Roadworks and events layers are read with the option on; only current ones are kept."""
    freezer.move_to("2026-10-16T00:00:00+00:00")
    provider = make(WARoadProvider, hass, **{CONF_INCLUDE_ROADWORKS: True})
    point = {"type": "Point", "coordinates": [116.0, -32.0]}
    roadworks = {
        "features": [
            {
                "geometry": point,
                "properties": {
                    "Id": 69769,
                    "DateStarte": "01/04/2023 00:00:00",
                    "EstimatedC": "30/04/2038 00:00:00",
                    "WorkType": "Maintenance",
                    "Road": "LOCAL ROAD",
                    "LocalRoadName": "Ashcroft Rd",
                    "Descriptio": "Ashcroft Rd - Long term closure",
                    "TrafficImp": "Long term Road Closure",
                },
            },
            {"geometry": point, "properties": {"Id": 2, "Road": "LOCAL ROAD", "EstimatedC": "01/01/2020 00:00:00"}},
            {"geometry": point, "properties": {"Id": 3, "Road": "LOCAL ROAD"}},
        ]
    }
    events = {
        "features": [
            {
                "geometry": point,
                "properties": {
                    "Id": 7284,
                    "DateTimeSt": "15/10/2026 07:45:00",
                    "DateTimeEn": "25/10/2026 13:00:00",
                    "EventType": "Sports Event",
                    "EventName": "Stage Race",
                    "EventDescr": "South Coast Hwy",
                    "Road": "South Coast Hwy",
                },
            },
            {"geometry": point, "properties": {"Id": 7402, "DateTimeSt": "01/11/2026 09:00:00"}},
        ]
    }
    routed(provider, {"FeatureServer/2/": roadworks, "FeatureServer/0/": events})
    items = by_id(await provider.async_fetch_road_closures())
    assert items["WA_RW_69769"].category == RoadEventCategory.ROADWORKS
    assert items["WA_RW_69769"].road == "Ashcroft Rd"
    assert items["WA_RW_3"].road == "Road"
    assert "WA_RW_2" not in items  # finished
    assert items["WA_EVENT_7284"].category == RoadEventCategory.SPECIAL_EVENT
    assert items["WA_EVENT_7284"].description == "Stage Race: South Coast Hwy"
    assert "WA_EVENT_7402" not in items  # not started


# --- NT ----------------------------------------------------------------------------------


async def test_nt_road_events(hass: HomeAssistant) -> None:
    """NT Road Report rows use [lat, lon] points; weight limits and park closures are skipped."""
    provider = make(NTRoadProvider, hass)
    payload = load("nt_obstructions")
    payload["response"].extend(
        [
            {"recordId": 1, "status": "CURRENT", "startPoint": None, "endPoint": [-12.5, 130.9], "roadName": "A Rd"},
            {"recordId": 2, "status": "EXPIRED", "startPoint": [-12.5, 130.9]},
            {"recordId": 3, "status": "CURRENT", "startPoint": None, "endPoint": None},
            {"status": "CURRENT", "startPoint": [-12.5, 130.9]},
        ]
    )
    routed(provider, {"GetAll": payload})
    items = by_id(await provider.async_fetch_road_closures())

    flood = items["NT_8041"]
    assert flood.category == RoadEventCategory.FLOODING
    assert (flood.latitude, flood.longitude) == (-14.3633918936, 131.5554313562)
    assert flood.status == "Impassable"
    assert flood.description is None  # "-" placeholder
    assert flood.updated_at is not None
    assert flood.updated_at.isoformat() == "2025-08-15T03:33:39+00:00"  # Darwin local
    assert items["NT_7450"].category == RoadEventCategory.ROADWORKS
    assert items["NT_9122"].category == RoadEventCategory.CLOSURE
    assert items["NT_7781"].category == RoadEventCategory.HAZARD
    assert items["NT_1"].latitude == -12.5  # endPoint fallback
    assert len(items) == 5


# --- TAS ---------------------------------------------------------------------------------


async def test_tas_road_events(hass: HomeAssistant) -> None:
    """TasALERT closures get stable IDs; an empty collection is a valid all-clear."""
    provider = make(TasmaniaRoadProvider, hass)
    payload = load("tas_road_closures")
    payload["features"].extend(
        [
            {
                "id": "abc",
                "geometry": {"type": "Point", "coordinates": [147.3, -42.9]},
                "properties": {"RoadName": "Huon Hwy", "Reason": "Flooding", "Status": "No Access"},
            },
            {"geometry": {"type": "Point", "coordinates": [147.3, -42.9]}, "properties": {}},
            {"geometry": None, "properties": {"RoadName": "X"}},
        ]
    )
    routed(provider, {"road-closures": payload})
    items = await provider.async_fetch_road_closures()
    assert len(items) == 5
    event, *closures, flood = items
    assert event.category == RoadEventCategory.SPECIAL_EVENT
    assert event.id.startswith("TAS_")
    assert event.description == "Expected opening: 1.00pm 16/11/2025"
    assert {item.category for item in closures} == {RoadEventCategory.CLOSURE}
    assert (flood.id, flood.category, flood.description) == ("TAS_abc", RoadEventCategory.FLOODING, None)

    provider = make(TasmaniaRoadProvider, hass)
    routed(provider, {"road-closures": {"type": "FeatureCollection", "features": []}})
    assert await provider.async_fetch_road_closures() == []


def test_state_codes(hass: HomeAssistant) -> None:
    """Each road provider reports its state."""
    for cls, state in (
        (NSWRoadProvider, "NSW"),
        (QueenslandRoadProvider, "QLD"),
        (VictoriaRoadProvider, "VIC"),
        (SARoadProvider, "SA"),
        (WARoadProvider, "WA"),
        (NTRoadProvider, "NT"),
        (TasmaniaRoadProvider, "TAS"),
    ):
        assert make(cls, hass).state_code == state


async def test_collect_road_sources_broken_payload(hass: HomeAssistant) -> None:
    """A parser tripping over a broken document fails that source, not the provider loop."""
    provider = make(NTRoadProvider, hass)

    async def fetch() -> Any:
        return {}

    def parse(payload: Any) -> list[RoadClosureItem]:
        return payload["missing"]

    with pytest.raises(ProviderUnavailableError, match="malformed payload"):
        await provider.async_collect_road_sources([("broken", fetch, parse)])


async def test_failed_source_keeps_its_last_good_items(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """When one Live Traffic feed fails, its last good events stay for up to 30 minutes."""
    provider = make(NSWRoadProvider, hass)
    routed(provider, {"flood.json": load("nsw_flood"), "incident.json": load("nsw_incident")})
    assert "NSW_286275" in by_id(await provider.async_fetch_road_closures())

    freezer.tick(timedelta(minutes=5))
    routed(provider, {"flood.json": ProviderUnavailableError("down"), "incident.json": load("nsw_incident")})
    assert "NSW_286275" in by_id(await provider.async_fetch_road_closures())

    freezer.tick(timedelta(minutes=31))
    assert "NSW_286275" not in by_id(await provider.async_fetch_road_closures())


async def test_moving_location_refetches(hass: HomeAssistant) -> None:
    """A new monitored point drops the throttled snapshot, so the radius box is queried again."""
    provider = make(SARoadProvider, hass, latitude=-34.93, longitude=138.6, radius=50)
    mock = routed(provider, {})
    await provider.async_fetch_road_closures()
    provider.set_location(-34.93, 138.6)  # unchanged: still throttled
    await provider.async_fetch_road_closures()
    assert mock.await_count == 2  # two layers, one fetch
    provider.set_location(-35.5, 138.9)
    await provider.async_fetch_road_closures()
    assert mock.await_count == 4
    xmin, ymin, xmax, ymax = (
        float(v) for v in parse_qs(urlsplit(mock.await_args.args[0]).query)["geometry"][0].split(",")
    )
    assert ymin < -35.5 < ymax
    assert xmin < 138.9 < xmax
