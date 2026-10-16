"""Warning-area geometry, inside-area detection and the polygon feeds that supply it (#30)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import json
import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import aiohttp
import defusedxml.ElementTree as ET
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.diagnostics import async_get_config_entry_diagnostics
from custom_components.ausnz_disaster_watch.models import (
    CALL_TO_ACTION_MAX_LENGTH,
    CanonicalHazard,
    HazardType,
    WarningLevel,
)
from custom_components.ausnz_disaster_watch.providers import (
    BoMHazardProvider,
    NSWHazardProvider,
    QueenslandHazardProvider,
    SAHazardProvider,
    TasmaniaHazardProvider,
)
from custom_components.ausnz_disaster_watch.providers.base import ARCGIS_MAX_PAGES, ProviderUnavailableError, as_float
from custom_components.ausnz_disaster_watch.providers.cap import CapArea, parse_cap
from custom_components.ausnz_disaster_watch.providers.geometry import (
    AREA_MAX_VERTICES,
    area_distance,
    area_point,
    circle_ring,
    ring_from_latlon_text,
    rings_from_cap_areas,
    rings_from_geojson,
    simplify_area,
)
from custom_components.ausnz_disaster_watch.providers.nsw import NSW_RFS_MAJOR_INCIDENTS_URL
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

HOME = (-27.2657, 152.9818)  # mock_config_entry location
ENTITY = "australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"


def _square(lat: float, lon: float, half: float) -> list[list[float]]:
    """GeoJSON ring ([lon, lat]) of a square centred on (lat, lon)."""
    return [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]


def _area_around(lat: float, lon: float, half: float = 0.1) -> tuple[tuple[tuple[float, float], ...], ...]:
    area = simplify_area(rings_from_geojson({"type": "Polygon", "coordinates": [_square(lat, lon, half)]}))
    assert area is not None
    return area


def _hazard(hazard_id: str, level: WarningLevel, **kwargs: Any) -> CanonicalHazard:
    defaults: dict[str, Any] = {
        "source": "Test",
        "title": f"{level.value} - test",
        "hazard_type": HazardType.FLOOD,
        "latitude": -25.0,  # centroid far from home
        "longitude": 150.0,
    }
    return CanonicalHazard(id=hazard_id, warning_level=level, **(defaults | kwargs))


# --- geometry -------------------------------------------------------------------------


def test_rings_from_geojson_shapes() -> None:
    """Polygons, multipolygons and nested collections give outer rings; points, lines and junk are ignored."""
    poly = {"type": "Polygon", "coordinates": [_square(-27.0, 153.0, 0.1), _square(-27.0, 153.0, 0.01)]}
    rings = rings_from_geojson(poly)
    assert len(rings) == 1  # the hole is dropped
    assert rings[0][0] == (-27.1, 152.9)  # (lat, lon)

    multi = {"type": "MultiPolygon", "coordinates": [[_square(-27.0, 153.0, 0.1)], [_square(-28.0, 153.0, 0.1)]]}
    assert len(rings_from_geojson(multi)) == 2
    nested = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [153.0, -27.0]},
            {"type": "GeometryCollection", "geometries": [poly]},
        ],
    }
    assert len(rings_from_geojson(nested)) == 1
    assert len(rings_from_geojson({"type": "Feature", "geometry": poly})) == 1
    assert (
        len(rings_from_geojson({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": multi}]}))
        == 2
    )

    for junk in (
        None,
        {"type": "LineString", "coordinates": [[153.0, -27.0], [153.1, -27.1]]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[153.0, -27.0], [153.1, -27.0], "bad", ["x", 1], [999, -27.0]]]},
        {"type": "MultiPolygon", "coordinates": [[], "bad"]},
        {"type": "GeometryCollection", "geometries": None},
        {"type": "FeatureCollection", "features": None},
    ):
        assert rings_from_geojson(junk) == []


def test_ring_from_latlon_text_and_circles() -> None:
    """CAP/Emergency WA "lat,lon" and GeoRSS "lat lon" polygons parse; malformed text does not."""
    expected = ((-27.0, 153.0), (-27.1, 153.0), (-27.1, 153.1))
    assert ring_from_latlon_text("-27.0,153.0 -27.1,153.0 -27.1,153.1 -27.0,153.0") == (*expected, (-27.0, 153.0))
    assert ring_from_latlon_text("-27.0 153.0 -27.1 153.0 -27.1 153.1") == expected
    assert ring_from_latlon_text("") is None
    assert ring_from_latlon_text("-27.0,153.0 -27.1,abc") is None
    assert ring_from_latlon_text("-27.0,153.0 -27.1") is None  # odd number of values
    assert ring_from_latlon_text("-27.0,153.0 -27.0,153.0 -27.0,153.0") is None  # degenerate

    ring = circle_ring(-27.0, 153.0, 5.0)
    assert area_distance(-27.0, 153.0, (ring,)) == 0.0
    assert area_distance(-27.0, 153.1, (ring,)) == pytest.approx(9.9 - 5.0, abs=0.2)
    areas = (CapArea("x", (expected,), ((-27.0, 153.0, 5.0), (-26.0, 153.0, 0.0)), ()),)
    assert len(rings_from_cap_areas(areas)) == 2  # the zero-radius circle is a point, not an area


def test_area_distance_inside_outside_and_boundary() -> None:
    """Distance is 0 inside (and on the edge), else the distance to the nearest edge."""
    area = _area_around(-27.0, 153.0, 0.1)
    assert area_distance(-27.0, 153.0, area) == 0.0
    assert area_distance(-27.0, 153.2, area) == pytest.approx(9.9, abs=0.2)  # 0.1° of longitude from the edge
    assert area_distance(-27.0, 153.1, area) == pytest.approx(0.0, abs=0.01)
    lat, lon = area_point(area)
    assert area_distance(lat, lon, area) == 0.0
    two = (*area, *_area_around(-28.0, 153.0, 0.1))
    near_second = area_point(two, -28.5, 153.0)
    assert near_second[0] < -27.5


def test_simplify_area_caps_vertices() -> None:
    """Large rings are simplified under the vertex cap, rounded, and tiny leftovers dropped."""

    circle = [
        [153.0 + 0.5 * math.cos(i / 2000 * 2 * math.pi), -27.0 + 0.5 * math.sin(i / 2000 * 2 * math.pi)]
        for i in range(2000)
    ]
    rings = rings_from_geojson({"type": "Polygon", "coordinates": [[*circle, circle[0]]]})
    area = simplify_area(rings)
    assert area is not None
    assert 10 < sum(len(r) for r in area) <= AREA_MAX_VERTICES
    assert area_distance(-27.0, 153.0, area) == 0.0
    assert all(len(str(lat).split(".")[1]) <= 5 for lat, _ in area[0])

    # Many separate rings: the largest are kept within the cap
    many = [
        rings_from_geojson({"type": "Polygon", "coordinates": [_square(-27.0 + i * 0.1, 153.0, 0.0001 * (i + 1))]})[0]
        for i in range(150)
    ]
    capped = simplify_area(many)
    assert capped is not None
    assert sum(len(r) for r in capped) <= AREA_MAX_VERTICES
    assert capped[0] == max(capped, key=lambda r: abs(r[1][1] - r[0][1]))

    assert simplify_area([]) is None
    assert simplify_area([((-27.0, 153.0), (-27.0, 153.0), (-27.0, 153.0))]) is None


# --- model ----------------------------------------------------------------------------


def test_area_never_reaches_attributes_or_dumps() -> None:
    """The polygon is excluded from dumps and attributes; scalars about it are exposed."""
    hazard = _hazard(
        "h1",
        WarningLevel.WATCH_AND_ACT,
        area=_area_around(*HOME),
        inside_area=True,
        expires="2026-10-16T10:00:00+10:00",
        call_to_action="Prepare to leave " * 40,
        raw_properties={"created_user": "a@b.c", "contact_email": "x@y.z", "last_edited_user": "u", "ok": 1},
    )
    attrs = hazard.to_safe_attributes()
    assert "area" not in attrs
    assert attrs["inside_area"] is True
    assert attrs["expires"] == "2026-10-16T00:00:00+00:00"
    assert len(attrs["call_to_action"]) == CALL_TO_ACTION_MAX_LENGTH
    assert attrs["prop_ok"] == 1
    assert not any(k.startswith("prop_") and k != "prop_ok" for k in attrs)
    assert "area" not in hazard.model_dump(mode="json")
    assert " area=" not in repr(hazard)
    assert hazard.is_inside_warning
    assert not _hazard("h2", WarningLevel.INFORMATION, inside_area=True).is_inside_warning
    assert not _hazard("h3", WarningLevel.EMERGENCY_WARNING).is_inside_warning


# --- coordinator and entities ---------------------------------------------------------


async def test_coordinator_uses_area_for_distance_and_expiry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Home inside a polygon: distance 0, inside, retained despite a far centroid; expired warnings drop."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    inside = _hazard("inside", WarningLevel.WATCH_AND_ACT, area=_area_around(*HOME), distance_km=99.0)
    # Square centred 0.3° east: its west edge is ~0.2° (~20 km) from home
    outside = _hazard("outside", WarningLevel.ADVICE, area=_area_around(HOME[0], HOME[1] + 0.3))
    far = _hazard("far", WarningLevel.ADVICE, area=_area_around(-20.0, 140.0))
    point = _hazard("point", WarningLevel.ADVICE, latitude=HOME[0], longitude=HOME[1])
    expired = _hazard(
        "expired",
        WarningLevel.EMERGENCY_WARNING,
        area=_area_around(*HOME),
        expires=datetime.now(UTC) - timedelta(minutes=1),
    )
    filtered, has_threat = coordinator._filter_and_process_hazards([inside, outside, far, point, expired])
    assert set(filtered) == {"inside", "outside", "point"}
    assert has_threat
    assert filtered["inside"].distance_km == 0.0
    assert filtered["inside"].inside_area is True
    assert filtered["outside"].inside_area is False
    assert filtered["outside"].distance_km == pytest.approx(19.8, abs=0.5)
    assert filtered["point"].inside_area is None


async def test_inside_warning_area_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
    entity_icon: Callable[[str], str | None],
) -> None:
    """The binary sensor and the highest-level sensor report the containing warnings."""
    mock_config_entry.add_to_hass(hass)
    advice = _hazard("advice", WarningLevel.ADVICE, area=_area_around(*HOME, 0.5))
    watch = _hazard("watch", WarningLevel.WATCH_AND_ACT, area=_area_around(*HOME), call_to_action="Prepare to leave")
    info = _hazard("info", WarningLevel.INFORMATION, area=_area_around(*HOME))
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = [advice, watch, info, mock_hazard_advice]
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{ENTITY}_inside_warning_area")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["warning_count"] == 2
    assert state.attributes["warning_level"] == "Watch and Act"
    assert state.attributes["warning_title"] == "Watch and Act - test"
    assert state.attributes["call_to_action"] == "Prepare to leave"
    assert "icon" not in state.attributes
    assert entity_icon(state.entity_id) == "mdi:map-marker-alert"
    highest = hass.states.get(f"sensor.{ENTITY}_highest_warning_level")
    assert highest is not None
    assert highest.attributes["inside_warning_area"] is True
    assert highest.attributes["inside_warning_level"] == "Watch and Act"
    assert all("area" not in str(s.attributes.get("coordinates", "")) for s in hass.states.async_all())

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics["coordinator"]["inside_warning_area"] is True
    assert diagnostics["coordinator"]["hazards_with_area"] == 3
    assert all("area" not in h for h in diagnostics["hazards"])

    # A warning given only as a point never turns it on
    coordinator = mock_config_entry.runtime_data
    provider.async_fetch_hazards.return_value = [mock_hazard_advice]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(f"binary_sensor.{ENTITY}_inside_warning_area")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["warning_count"] == 0
    assert state.attributes["warning_level"] is None
    assert state.attributes["call_to_action"] is None
    assert "icon" not in state.attributes
    assert entity_icon(state.entity_id) == "mdi:map-marker-check"
    highest = hass.states.get(f"sensor.{ENTITY}_highest_warning_level")
    assert highest is not None
    assert highest.attributes["inside_warning_area"] is False
    assert highest.attributes["inside_warning_level"] is None


# --- ArcGIS helper --------------------------------------------------------------------


async def test_arcgis_query_pages_and_errors(hass: HomeAssistant) -> None:
    """The ArcGIS helper requests WGS84 GeoJSON with explicit fields, follows pages and rejects errors."""
    provider = QueenslandHazardProvider(hass, AsyncMock(), {"state": "QLD"})
    page = {"type": "FeatureCollection", "features": [{"id": 1}], "properties": {"exceededTransferLimit": True}}
    provider.async_fetch_json = AsyncMock(
        side_effect=[page, {"features": [{"id": 2}, "junk"], "exceededTransferLimit": False}]
    )
    features = await provider.async_fetch_arcgis_features("https://x/FeatureServer/0", "1=1", ("A", "B"), "Layer")
    assert features == [{"id": 1}, {"id": 2}]
    first, second = (urlsplit(call.args[0]) for call in provider.async_fetch_json.call_args_list)
    query = parse_qs(first.query)
    assert first.path == "/FeatureServer/0/query"
    assert query["outFields"] == ["A,B"]
    assert query["outSR"] == ["4326"]
    assert query["f"] == ["geojson"]
    assert parse_qs(second.query)["resultOffset"] == ["1"]

    # A server that always says "more" stops at the page cap
    provider.async_fetch_json = AsyncMock(return_value=page)
    assert len(await provider.async_fetch_arcgis_features("https://x/0", "1=1", ("A",), "Layer")) == ARCGIS_MAX_PAGES
    # An empty page ends paging even if the flag is set
    provider.async_fetch_json = AsyncMock(return_value={"features": [], "exceededTransferLimit": True})
    assert await provider.async_fetch_arcgis_features("https://x/0", "1=1", ("A",), "Layer") == []
    # ArcGIS reports errors as HTTP 200 JSON objects
    provider.async_fetch_json = AsyncMock(return_value={"error": {"code": 400}})
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_arcgis_features("https://x/0", "1=1", ("A",), "Layer")


# --- QLD ------------------------------------------------------------------------------


def _qld_routes(ocs: Any, qps: Any, s3: Any) -> AsyncMock:
    async def fetch(url: str, headers: Any = None) -> Any:
        for key, value in (("OCSWarnings", ocs), ("Severe_Weather", qps), ("bushfireAlert", s3)):
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(url)

    return AsyncMock(side_effect=fetch)


def _feature(props: dict[str, Any], geometry: Any) -> dict[str, Any]:
    return {"type": "Feature", "properties": props, "geometry": geometry}


async def test_qld_warning_area_layers(hass: HomeAssistant) -> None:
    """QFD and QPS polygon layers become area hazards; a QFD warning also in S3 keeps its polygon."""
    provider = QueenslandHazardProvider(
        hass, AsyncMock(), {"state": "QLD", "council_dashboard_url": None, "latitude": HOME[0], "longitude": HOME[1]}
    )
    polygon = {"type": "Polygon", "coordinates": [_square(*HOME, 0.1)]}
    ocs = {
        "type": "FeatureCollection",
        "features": [
            _feature(
                {
                    "UniqueID": "BCP-26-7",
                    "WarningTitle": "PREPARE TO LEAVE - Irvinebank - fire as at 9:20am",
                    "WarningLevel": "Watch and Act",
                    "WarningArea": "Irvinebank",
                    "CallToAction": "Prepare to leave",
                    "ModifiedDate": 1792109683000,
                },
                polygon,
            ),
            _feature({"UniqueID": "", "WarningLevel": "Advice"}, polygon),  # no ID
            _feature({"UniqueID": "BCP-26-8", "WarningLevel": "Advice"}, {"type": "Point", "coordinates": [153, -27]}),
            _feature({"UniqueID": "BCP-26-9", "WarningTitle": "Emergency Warning - Gap", "WarningLevel": ""}, polygon),
        ],
    }
    qps = {
        "type": "FeatureCollection",
        "features": [
            _feature(
                {
                    "UniqueID": "HN_15102026",
                    "WarningTitle": "ADVICE - STAY INFORMED - Isisford - DO NOT USE TREATED TAP WATER",
                    "WarningLevel": "Advice",
                    "last_edited_date": 1792109683000,
                },
                polygon,
            ),
            "not a feature",
        ],
    }
    s3_duplicate = {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "UniqueID": "BCP-26-7",
                    "WarningTitle": "Watch and Act",
                    "WarningLevel": "Watch and Act",
                    "Latitude": -17.4,
                    "Longitude": 145.2,
                }
            }
        ],
    }
    provider.async_fetch_json = _qld_routes(ocs, qps, s3_duplicate)
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}
    assert set(hazards) == {"QLD_QFD_BCP-26-7", "QLD_QFD_BCP-26-9", "QLD_QPS_HN_15102026"}
    qfd = hazards["QLD_QFD_BCP-26-7"]
    assert qfd.area is not None  # the polygon version won over the S3 point
    assert qfd.warning_level is WarningLevel.WATCH_AND_ACT
    assert qfd.hazard_type is HazardType.BUSHFIRE
    assert qfd.call_to_action == "Prepare to leave"
    assert qfd.location_name == "Irvinebank"
    assert qfd.updated_at == datetime.fromtimestamp(1792109683, tz=UTC)
    assert area_distance(qfd.latitude, qfd.longitude, qfd.area) == 0.0
    assert hazards["QLD_QFD_BCP-26-9"].warning_level is WarningLevel.EMERGENCY_WARNING
    qps_hazard = hazards["QLD_QPS_HN_15102026"]
    assert qps_hazard.responsible_agency == "Queensland Police Service"
    assert qps_hazard.hazard_type is HazardType.OTHER
    assert qps_hazard.web_url is None
    assert qps_hazard.attribution == "Queensland Police Service"
    assert qfd.attribution == "State of Queensland (Queensland Fire and Emergency Services)"
    # No editor fields were asked for
    for call in provider.async_fetch_json.call_args_list:
        assert "created_user" not in call.args[0]
        assert "last_edited_user" not in call.args[0]

    # One layer down: the other sources still count; all down: unavailable
    provider.async_fetch_json = _qld_routes(aiohttp.ClientError("down"), qps, aiohttp.ClientError("down"))
    assert [h.id for h in await provider.async_fetch_hazards()] == ["QLD_QPS_HN_15102026"]
    down = aiohttp.ClientError("down")
    provider.async_fetch_json = _qld_routes(down, down, down)
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()


# --- SA -------------------------------------------------------------------------------


def _ses_feature(objectid: int, category: str, issued: int, **props: Any) -> dict[str, Any]:
    return _feature(
        {
            "objectid": objectid,
            "documentid": 789,
            "alertname": "Severe_Thunderstorm",
            "risk": "Wind",
            "category": category,
            "datetimeissued": issued,
            "datetimeexpires": issued + 4 * 3600 * 1000,
            "shortlocation": "Adelaide Region",
            "calltoaction": "Prepare your property",
            "link": "789_Severe_Thunderstorm.html",
        }
        | props,
        {"type": "Polygon", "coordinates": [_square(-34.9, 138.6, 0.2)]},
    )


async def test_sa_ses_warning_areas(hass: HomeAssistant) -> None:
    """SES warnings map ADV/WAM/EWM to AWS levels, keep one hazard per reissued warning, and expire."""
    provider = SAHazardProvider(hass, AsyncMock(), {"state": "SA", "latitude": -34.9, "longitude": 138.6})
    issued = 1791709200000
    features = [
        _ses_feature(171648, "ADV", issued),
        _ses_feature(171650, "WAM", issued + 3600 * 1000),  # the reissue, now Watch and Act
        _ses_feature(171651, "ADV", issued, shortlocation=None, locationsimpacted=None, link=None, risk="Dam"),
        _ses_feature(171652, "EWM", issued, alertname="Flood", risk="Flood", link="https://example.org/doc.html"),
        _ses_feature(171653, "XYZ", issued, alertname="Heatwave_Advice", risk="Heatwave", shortlocation="Flinders"),
        _feature({"objectid": 1, "category": "ADV"}, None),  # no polygon
    ]
    hazards = provider._parse_ses_warnings(features)
    with patch.object(provider, "_parse_ses_warning", side_effect=TypeError("bad")):
        assert provider._parse_ses_warnings(features) == []
    by_title = {h.title: h for h in hazards}
    assert set(by_title) == {
        "Watch and Act - Severe Thunderstorm - Adelaide Region",
        "Advice - Severe Thunderstorm",
        "Emergency Warning - Flood - Adelaide Region",
        "Advice - Heatwave Advice - Flinders",
    }
    storm = by_title["Watch and Act - Severe Thunderstorm - Adelaide Region"]
    assert storm.hazard_type is HazardType.SEVERE_STORM
    assert storm.inside_area is None and storm.area is not None
    assert storm.call_to_action == "Prepare your property"
    assert storm.attribution == "SA State Emergency Service"
    assert storm.web_url == "https://data.eso.sa.gov.au/prod/ses/sam/789_Severe_Thunderstorm.html"
    assert storm.expires == datetime.fromtimestamp((issued + 5 * 3600 * 1000) / 1000, tz=UTC)
    dam = by_title["Advice - Severe Thunderstorm"]
    assert dam.hazard_type is HazardType.FLOOD
    assert dam.location_name == "South Australia"
    assert dam.web_url == "https://www.ses.sa.gov.au/warnings"
    assert by_title["Emergency Warning - Flood - Adelaide Region"].web_url == "https://example.org/doc.html"
    assert by_title["Advice - Heatwave Advice - Flinders"].hazard_type is HazardType.OTHER

    # Same document and area -> same ID whichever issue is current (#7)
    assert provider._parse_ses_warning(features[0]).id == storm.id  # type: ignore[union-attr]
    # Older issue after the newer one does not replace it
    assert provider._parse_ses_warnings([features[1], features[0]])[0].warning_level is WarningLevel.WATCH_AND_ACT
    no_time = _ses_feature(1, "ADV", issued, datetimeissued=None)
    assert provider._parse_ses_warnings([no_time, features[1]])[0].warning_level is WarningLevel.WATCH_AND_ACT


async def test_sa_cap_area_becomes_hazard_area(hass: HomeAssistant) -> None:
    """A CFS CAP polygon or circle with a radius is the hazard area; a zero-radius circle is just a point."""
    provider = SAHazardProvider(hass, AsyncMock(), {"state": "SA"})
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>F1</id><title>BUSHFIRE : X</title>
      <content><alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>F1</identifier><info>
        <event>Fire</event><expires>2099-01-01T00:00:00+10:30</expires>
        <parameter><valueName>WarningLevel</valueName><value>Watch and Act</value></parameter>
        <parameter><valueName>CallToAction</valueName><value>Leave now</value></parameter>
        <area><areaDesc>X</areaDesc><polygon>-35.0,138.0 -35.1,138.0 -35.1,138.1 -35.0,138.0</polygon></area>
      </info></alert></content></entry>
      <entry><id>F2</id><title>BURN OFF : Y</title><content><alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
        <info><event>Fire</event><area><circle>-34.9,138.7 0.0</circle></area></info></alert></content></entry>
    </feed>"""
    first, second = provider._parse_cap_feed(xml)
    assert first.area is not None
    assert first.call_to_action == "Leave now"
    assert first.expires == datetime(2098, 12, 31, 13, 30, tzinfo=UTC)
    assert second.area is None
    assert second.call_to_action is None


# --- TAS, NSW, BoM --------------------------------------------------------------------


async def test_tas_warning_area_and_alert_level(hass: HomeAssistant) -> None:
    """TasALERT polygons (nested collections) are the area; ``alertLevel`` sets the AWS level."""
    provider = TasmaniaHazardProvider(hass, AsyncMock(), {"state": "TAS"})
    feature = {
        "properties": {"id": "w1", "title": "Bushfire", "feedType": "warning", "alertLevel": "watch_and_act"},
        "geometry": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "type": "GeometryCollection",
                    "geometries": [{"type": "Polygon", "coordinates": [_square(-42.9, 147.3, 0.1)]}],
                }
            ],
        },
    }
    hazard = provider._parse_feature(feature)
    assert hazard is not None
    assert hazard.warning_level is WarningLevel.WATCH_AND_ACT
    assert hazard.area is not None
    assert area_distance(hazard.latitude, hazard.longitude, hazard.area) == 0.0


async def test_nsw_rfs_fire_ground_area(hass: HomeAssistant, feed_routes: Any) -> None:
    """NSW RFS polygons published with the incident point become the hazard area."""

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [153.07, -29.32]},
                {
                    "type": "GeometryCollection",
                    "geometries": [{"type": "Polygon", "coordinates": [_square(-29.32, 153.07, 0.02)]}],
                },
            ],
        },
        "properties": {
            "title": "OIL RIG RD",
            "category": "Advice",
            "guid": "https://incidents.rfs.nsw.gov.au/api/v1/incidents/681150",
        },
    }
    session = feed_routes({NSW_RFS_MAJOR_INCIDENTS_URL: {"type": "FeatureCollection", "features": [feature]}})
    (hazard,) = await NSWHazardProvider(hass, session, {"state": "NSW"}).async_fetch_hazards()
    assert hazard.id == "NSW_RFS_681150"
    assert hazard.area is not None
    assert len(hazard.area) == 1


def test_bom_alert_area_is_carried() -> None:
    """BoM hazards carry their CAP polygons as the area (checked through the builder)."""

    alert = parse_cap(
        """<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>X</identifier><info>
        <event>Flood</event><headline>Flood Watch</headline><area><areaDesc>A</areaDesc>
        <polygon>-27.0,153.0 -27.5,153.0 -27.5,153.5 -27.0,153.0</polygon></area></info></alert>"""
    )
    assert alert is not None
    provider = BoMHazardProvider(MagicMock(), MagicMock(), {"state": "QLD", "latitude": -27.3, "longitude": 153.2})

    hazard = provider._build_hazard("IDQ1", ET.fromstring("<item><title>Flood Watch</title></item>"), alert)
    assert hazard is not None
    assert hazard.area is not None
    assert json.dumps(hazard.to_safe_attributes())  # attributes stay JSON scalars


def test_small_helpers() -> None:
    """Coordinates that are not numbers are None; a polygon whose ring is not a list has no rings."""

    assert as_float("-27.5") == -27.5
    assert as_float(None) is None
    assert as_float("north") is None
    assert rings_from_geojson({"type": "Polygon", "coordinates": ["bad"]}) == []
