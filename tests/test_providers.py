from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import geojson
import pytest

from custom_components.ausnz_disaster_watch.const import (
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_NZ,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import (
    ACTHazardProvider,
    BaseHazardProvider,
    BoMHazardProvider,
    NSWHazardProvider,
    NTHazardProvider,
    NZHazardProvider,
    QueenslandHazardProvider,
    SAHazardProvider,
    TasmaniaHazardProvider,
    VictoriaHazardProvider,
    WAHazardProvider,
    get_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError, stable_id
from custom_components.ausnz_disaster_watch.providers.nsw import NSW_RFS_MAJOR_INCIDENTS_URL, NSWRFSIncidentEntry
from homeassistant.core import HomeAssistant


def feature_collection(*features: dict[str, Any]) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": list(features)}


def nsw_entry(feature: dict[str, Any]) -> NSWRFSIncidentEntry:
    """Return an NSW RFS library entry for a GeoJSON feature."""
    return NSWRFSIncidentEntry((0.0, 0.0), geojson.loads(json.dumps(feature)))


def test_base_provider_centroid_calculation() -> None:
    """Test centroid calculation for GeoJSON geometries."""
    # Point geometry
    point_geom = {"type": "Point", "coordinates": [152.9818, -27.2657]}
    lat, lon = BaseHazardProvider.calculate_centroid(point_geom)
    assert abs(lat - (-27.2657)) < 0.0001
    assert abs(lon - 152.9818) < 0.0001

    # Polygon geometry (square around 153.0, -27.0)
    polygon_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [152.9, -26.9],
                [153.1, -26.9],
                [153.1, -27.1],
                [152.9, -27.1],
                [152.9, -26.9],
            ]
        ],
    }
    lat, lon = BaseHazardProvider.calculate_centroid(polygon_geom)
    assert abs(lat - (-27.0)) < 0.01
    assert abs(lon - 153.0) < 0.01


async def test_nsw_provider_parsing(hass: HomeAssistant, feed_routes: Any) -> None:
    """Test NSW RFS provider parsing with HTML description."""
    config = {"state": STATE_NSW, "latitude": -33.8688, "longitude": 151.2093}

    mock_nsw_feed = feature_collection(
        {
            "type": "Feature",
            "geometry": {
                "type": "GeometryCollection",
                "geometries": [{"type": "Point", "coordinates": [152.5598, -29.6950]}],
            },
            "properties": {
                "title": "Baffle Road",
                "category": "Advice",
                "guid": "https://incidents.rfs.nsw.gov.au/api/v1/incidents/681307",
                "description": "ALERT LEVEL: Advice <br />LOCATION: BAFFLE RD, DALMORTON <br />COUNCIL AREA: Clarence Valley <br />STATUS: Under control <br />TYPE: Bush Fire <br />FIRE: Yes <br />RESPONSIBLE AGENCY: Rural Fire Service",
            },
        }
    )

    session = feed_routes({NSW_RFS_MAJOR_INCIDENTS_URL: mock_nsw_feed})
    provider = NSWHazardProvider(hass, session, config)
    hazards = await provider.async_fetch_hazards()

    assert len(hazards) == 1
    h = hazards[0]
    assert h.id == "NSW_RFS_681307"
    assert h.title == "Baffle Road"
    assert h.warning_level == WarningLevel.ADVICE
    assert h.hazard_type == HazardType.BUSHFIRE
    assert h.status == "Under control"
    assert h.location_name == "BAFFLE RD, DALMORTON"
    # The last field has no trailing <br />: still read (the library's own pattern misses it)
    assert h.responsible_agency == "Rural Fire Service"
    assert (h.latitude, h.longitude) == (-29.6950, 152.5598)
    assert h.raw_properties["guid"] == "https://incidents.rfs.nsw.gov.au/api/v1/incidents/681307"
    assert feed_routes.requested == [NSW_RFS_MAJOR_INCIDENTS_URL]


async def test_vic_provider_parsing(hass: HomeAssistant) -> None:
    """Test Victoria provider parsing EMV OSOM feed."""
    session = AsyncMock()
    config = {"state": STATE_VIC, "latitude": -37.8136, "longitude": 144.9631}
    provider = VictoriaHazardProvider(hass, session, config)

    mock_vic_feed = {
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [144.2026, -35.7956],
                },
                "properties": {
                    "id": "43499",
                    "sourceOrg": "EMV",
                    "category1": "Advice",
                    "category2": "Health",
                    "action": "Boil Tap Water",
                    "location": "Cohuna and surrounds",
                    "created": "2026-10-14T14:12:25+11:00",
                    "cap": {"severity": "Minor"},
                },
            }
        ]
    }

    provider.async_fetch_json = AsyncMock(return_value=mock_vic_feed)
    hazards = await provider.async_fetch_hazards()

    assert len(hazards) == 1
    h = hazards[0]
    assert h.id == "VIC_EMV_43499"
    assert "Boil Tap Water" in h.title
    assert h.warning_level == WarningLevel.ADVICE
    assert h.responsible_agency == "EMV"


def test_get_providers_for_config(hass: HomeAssistant) -> None:
    """Test get_providers_for_config factory across states."""
    session = AsyncMock()
    qld_providers = get_providers_for_config(hass, session, {"state": "QLD"})
    assert any(isinstance(p, QueenslandHazardProvider) for p in qld_providers)

    nsw_providers = get_providers_for_config(hass, session, {"state": "NSW"})
    assert any(isinstance(p, NSWHazardProvider) for p in nsw_providers)

    vic_providers = get_providers_for_config(hass, session, {"state": "VIC"})
    assert any(isinstance(p, VictoriaHazardProvider) for p in vic_providers)

    wa_providers = get_providers_for_config(hass, session, {"state": "WA"})
    assert any(isinstance(p, BoMHazardProvider) for p in wa_providers)


class DummyProvider(BaseHazardProvider):
    """Concrete provider for testing BaseHazardProvider methods."""

    @property
    def state_code(self) -> str:
        return "TEST"

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        return []


async def test_base_provider_async_fetch_json(hass: HomeAssistant) -> None:
    """Test BaseHazardProvider async_fetch_json success, retries, and errors."""
    session = MagicMock()
    provider = DummyProvider(hass, session, {})

    # Success 200
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value={"status": "ok"})

    class MockCM:
        def __init__(self, resp):
            self.resp = resp

        async def __aenter__(self):
            return self.resp

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockCM(mock_resp))
    data = await provider.async_fetch_json("https://example.com/api")
    assert data == {"status": "ok"}

    # Retry on 500 then succeed 200
    mock_resp_500 = AsyncMock()
    mock_resp_500.status = 500
    mock_resp_500.raise_for_status = MagicMock()
    mock_resp_200 = AsyncMock()
    mock_resp_200.status = 200
    mock_resp_200.raise_for_status = MagicMock()
    mock_resp_200.json = AsyncMock(return_value={"retry": "ok"})

    session.get.side_effect = [MockCM(mock_resp_500), MockCM(mock_resp_200)]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        data2 = await provider.async_fetch_json("https://example.com/api2")
        assert data2 == {"retry": "ok"}
        mock_sleep.assert_called_once()

    # Transient ClientResponseError (e.g. 503) retry then succeed 200
    req_info = MagicMock()
    err_503 = aiohttp.ClientResponseError(request_info=req_info, history=(), status=503)
    session.get.side_effect = [err_503, MockCM(mock_resp_200)]
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        data3 = await provider.async_fetch_json("https://example.com/api3")
        assert data3 == {"retry": "ok"}
        mock_sleep.assert_called_once()

    # Transient ClientResponseError exhausting MAX_RETRIES
    session.get.side_effect = err_503
    with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(aiohttp.ClientResponseError):
        await provider.async_fetch_json("https://example.com/api_err_exhaust")

    # Network error retry and final raise

    session.get.side_effect = aiohttp.ClientError("Network down")
    with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(aiohttp.ClientError):
        await provider.async_fetch_json("https://example.com/fail")


def test_base_provider_centroid_edge_cases() -> None:
    """Test calculate_centroid edge cases."""
    assert BaseHazardProvider.calculate_centroid({}) is None
    assert BaseHazardProvider.calculate_centroid(None) is None  # type: ignore[arg-type]

    # GeometryCollection with sub-geometries
    geom_col = {
        "type": "GeometryCollection",
        "geometries": [
            {
                "type": "Polygon",
                "coordinates": [[[150.0, -25.0], [151.0, -25.0], [151.0, -26.0], [150.0, -26.0], [150.0, -25.0]]],
            },
        ],
    }
    centroid = BaseHazardProvider.calculate_centroid(geom_col)
    assert centroid is not None

    # Empty geometry collection
    assert BaseHazardProvider.calculate_centroid({"type": "GeometryCollection", "geometries": []}) is None

    # Polygon unclosed
    unclosed_poly = {
        "type": "Polygon",
        "coordinates": [[[150.0, -25.0], [151.0, -25.0], [151.0, -26.0]]],
    }
    assert BaseHazardProvider.calculate_centroid(unclosed_poly) is not None

    # Empty coordinates
    assert BaseHazardProvider.calculate_centroid({"type": "Polygon", "coordinates": []}) is None


def test_base_provider_parse_datetime_all_formats() -> None:
    """parse_datetime returns aware UTC datetimes, interpreting naive values in the agency zone (#13)."""
    now_dt = datetime.now(UTC)
    assert BaseHazardProvider.parse_datetime(now_dt) == now_dt

    # Base provider zone is UTC; naive datetimes take it
    assert BaseHazardProvider.parse_datetime(datetime(2026, 10, 15, 10, 30)) == datetime(
        2026, 10, 15, 10, 30, tzinfo=UTC
    )

    # Epoch seconds and milliseconds
    assert BaseHazardProvider.parse_datetime(1729000000).year == 2024
    assert BaseHazardProvider.parse_datetime(1729000000000).year == 2024

    # Missing, blank, unsupported and unparsable values are None, never "now"
    assert BaseHazardProvider.parse_datetime(None) is None
    assert BaseHazardProvider.parse_datetime("") is None
    assert BaseHazardProvider.parse_datetime(True) is None
    assert BaseHazardProvider.parse_datetime("unparsable date string") is None

    # Explicit offsets are honoured
    assert BaseHazardProvider.parse_datetime("2026-10-15T12:00:00Z") == datetime(2026, 10, 15, 12, tzinfo=UTC)
    assert BaseHazardProvider.parse_datetime("2026-10-15T12:00:00+10:00") == datetime(2026, 10, 15, 2, tzinfo=UTC)
    assert BaseHazardProvider.parse_datetime("Thu, 15 Oct 2026 01:27:00 GMT") == datetime(
        2026, 10, 15, 1, 27, tzinfo=UTC
    )
    assert BaseHazardProvider.parse_datetime("Thu, 15 Oct 2026 01:27:00 -0000") == datetime(
        2026, 10, 15, 1, 27, tzinfo=UTC
    )

    # Agency formats (naive): interpreted in the requested agency zone
    sydney = "Australia/Sydney"  # AEDT (UTC+11) in mid-October
    expected = datetime(2026, 10, 15, 2, 30, tzinfo=UTC)
    for value in (
        "15/10/2026 01:30:00 PM",
        "15/10/2026 13:30:00",
        "15/10/2026 01:30 PM",
        "15/10/2026 13:30",
        "15 Oct 2026 13:30",
        "2026-10-15 13:30:00",
    ):
        assert BaseHazardProvider.parse_datetime(value, sydney) == expected, value

    # Brisbane has no daylight saving (UTC+10)
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 13:30", "Australia/Brisbane") == datetime(
        2026, 10, 15, 3, 30, tzinfo=UTC
    )

    # A trailing zone abbreviation wins over the provider zone (ACT ESA style)
    assert BaseHazardProvider.parse_datetime("2026-10-15 20:46 AEDT", "Australia/Perth") == datetime(
        2026, 10, 15, 9, 46, tzinfo=UTC
    )
    assert BaseHazardProvider.parse_datetime("2026-07-15 20:46 aest") == datetime(2026, 7, 15, 10, 46, tzinfo=UTC)

    # Unknown zone names fall back to UTC
    assert BaseHazardProvider.parse_datetime("2026-10-15 13:30:00", "Mars/Olympus") == datetime(
        2026, 10, 15, 13, 30, tzinfo=UTC
    )


def test_provider_local_timezones() -> None:
    """Each provider interprets naive feed times in its agency's zone (#13)."""
    expected = {
        QueenslandHazardProvider: "Australia/Brisbane",
        NSWHazardProvider: "Australia/Sydney",
        ACTHazardProvider: "Australia/Sydney",
        VictoriaHazardProvider: "Australia/Melbourne",
        SAHazardProvider: "Australia/Adelaide",
        WAHazardProvider: "Australia/Perth",
        TasmaniaHazardProvider: "Australia/Hobart",
        NTHazardProvider: "Australia/Darwin",
        NZHazardProvider: "Pacific/Auckland",
    }
    for provider_cls, zone in expected.items():
        assert provider_cls.local_tz == zone
    # NSW RFS "UPDATED" value is Sydney local time, not UTC (was ~11 h in the future)
    assert NSWHazardProvider.parse_datetime("15 Oct 2026 16:26") == datetime(2026, 10, 15, 5, 26, tzinfo=UTC)


def test_stable_id_is_deterministic() -> None:
    """stable_id does not depend on process hash seeds or list position (#7)."""
    first = stable_id("nt", "2026-10-15T10:00:00+09:30", "Grass Fire", "Litchfield Park")
    assert first == stable_id("nt", "2026-10-15T10:00:00+09:30", "Grass Fire", "Litchfield Park")
    assert first.startswith("nt_")
    assert len(first) == len("nt_") + 16
    assert first != stable_id("nt", "2026-10-15T10:00:00+09:30", "Grass Fire", "Litchfield Park Rd")
    assert stable_id("x", None, "a") == stable_id("x", "", "a")


async def test_nsw_provider_edge_cases(hass: HomeAssistant, feed_routes: Any) -> None:
    """Test NSW provider state code, error branches, and description parsing."""
    provider = NSWHazardProvider(hass, feed_routes(), {"state": STATE_NSW})
    assert provider.state_code == STATE_NSW

    with pytest.raises(ProviderUnavailableError, match="NSW RFS unavailable"):
        await provider.async_fetch_hazards()

    # Feature without centroid
    assert provider._parse_nsw_feature(nsw_entry({"type": "Feature", "geometry": None, "properties": {}})) is None

    # Feature without guid (fallback ID generation)
    feat_no_guid = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [151.0, -33.0]},
        "properties": {
            "title": "Grass Fire Hunter",
            "category": "Advice",
            "description": "",
        },
    }
    h = provider._parse_nsw_feature(nsw_entry(feat_no_guid))
    assert h is not None
    assert "Hunter" in h.id


async def test_vic_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test Victoria provider state code, error branches, and CAP severities."""
    session = AsyncMock()
    provider = VictoriaHazardProvider(hass, session, {"state": STATE_VIC})
    assert provider.state_code == STATE_VIC

    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("Vic feed error"))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

    # Feature without centroid or ID
    assert provider._parse_vic_feature({"geometry": {}}) is None
    assert provider._parse_vic_feature({"geometry": {"type": "Point", "coordinates": [145.0, -37.0]}}) is None

    # CAP severities
    def make_feat(severity: str, action: str = "", source_title: str = ""):
        return {
            "geometry": {"type": "Point", "coordinates": [145.0, -37.0]},
            "properties": {
                "id": f"VIC_{severity}",
                "category1": "Fire",
                "category2": "Bushfire",
                "action": action,
                "sourceTitle": source_title,
                "cap": {"severity": severity},
            },
        }

    h_extreme = provider._parse_vic_feature(make_feat("Extreme", action="Evacuate"))
    assert h_extreme is not None
    assert h_extreme.warning_level == WarningLevel.EMERGENCY_WARNING
    assert "Evacuate" in h_extreme.title

    h_severe = provider._parse_vic_feature(make_feat("Severe", source_title="Vic Alert"))
    assert h_severe is not None
    assert h_severe.warning_level == WarningLevel.WATCH_AND_ACT
    assert "Vic Alert" in h_severe.title

    h_minor = provider._parse_vic_feature(make_feat("Minor"))
    assert h_minor is not None
    assert h_minor.warning_level == WarningLevel.ADVICE

    h_info = provider._parse_vic_feature(make_feat("Unknown"))
    assert h_info is not None
    assert h_info.warning_level == WarningLevel.INFORMATION


async def test_base_provider_headers_and_status(hass: HomeAssistant) -> None:
    """Test BaseHazardProvider headers update, 404 raise_for_status, and non-list centroid points."""
    session = MagicMock()
    provider = DummyProvider(hass, session, {})

    # Headers passed
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value={"ok": True})

    class MockCM:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockCM())
    res = await provider.async_fetch_json("https://example.com/headers", headers={"X-Custom": "Val"})
    assert res == {"ok": True}

    # 404 calls raise_for_status
    mock_resp_404 = MagicMock()
    mock_resp_404.status = 404
    mock_resp_404.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(None, (), status=404)  # type: ignore[arg-type]
    )

    class MockCM404:
        async def __aenter__(self):
            return mock_resp_404

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockCM404())
    with pytest.raises(aiohttp.ClientResponseError):
        await provider.async_fetch_json("https://example.com/notfound")

    # Centroid extraction with non-list item in coords
    geom = {
        "type": "Polygon",
        "coordinates": ["invalid_string", [150.0, -25.0], [151.0, -25.0], [150.0, -26.0]],
    }
    centroid = BaseHazardProvider.calculate_centroid(geom)
    assert centroid is not None


async def test_nsw_and_vic_empty_and_cap_none(hass: HomeAssistant, feed_routes: Any) -> None:
    """Test NSW and VIC when feeds return empty or non-dict, and VIC cap is None."""
    session = AsyncMock()

    # NSW: a non-object payload is a broken feed, not an all-clear (#16)
    nsw_session = feed_routes()
    nsw_prov = NSWHazardProvider(hass, nsw_session, {"state": STATE_NSW})
    for body in ("null", "[]", "not json", 503):
        feed_routes.routes[NSW_RFS_MAJOR_INCIDENTS_URL] = body
        with pytest.raises(ProviderUnavailableError):
            await nsw_prov.async_fetch_hazards()
    # ...while a valid feed with no features is a genuine all-clear
    feed_routes.routes[NSW_RFS_MAJOR_INCIDENTS_URL] = {"type": "FeatureCollection", "features": []}
    assert await nsw_prov.async_fetch_hazards() == []

    # VIC: same contract
    vic_prov = VictoriaHazardProvider(hass, session, {"state": STATE_VIC})
    vic_prov.async_fetch_json = AsyncMock(return_value=[])
    with pytest.raises(ProviderUnavailableError):
        await vic_prov.async_fetch_hazards()

    # VIC cap is None
    feat_no_cap = {
        "geometry": {"type": "Point", "coordinates": [145.0, -37.0]},
        "properties": {
            "id": "VIC_NO_CAP",
            "category1": "Weather",
            "category2": "Rain",
            "cap": None,
        },
    }
    h_vic = vic_prov._parse_vic_feature(feat_no_cap)
    assert h_vic is not None
    assert h_vic.warning_level == WarningLevel.INFORMATION


async def test_base_provider_default_composite_methods(hass: HomeAssistant) -> None:
    """Test BaseHazardProvider default composite methods return empty collections or None."""
    session = MagicMock()
    provider = DummyProvider(hass, session, {})

    assert await provider.async_fetch_power_outages() == []
    assert await provider.async_fetch_road_closures() == []
    assert await provider.async_fetch_weather_warnings() == []
    assert await provider.async_fetch_emergency_news() == []
    assert await provider.async_fetch_fire_danger() is None
    assert await provider.async_fetch_weather_telemetry() == []
    assert await provider.async_fetch_air_quality() == []
    assert await provider.async_fetch_relief_facilities() == []
    assert await provider.async_fetch_cameras() == []
    assert await provider.async_fetch_nearby_councils() == []


async def test_base_provider_additional_geometries_and_fetch_text(hass: HomeAssistant) -> None:
    """Test BaseHazardProvider geometry centroid calculations, async_fetch_text, and defaults."""
    # 1. GeometryCollection with Point
    geom_with_pt = {
        "type": "GeometryCollection",
        "geometries": [{"type": "Point", "coordinates": [153.0, -27.0]}],
    }
    lat, lon = BaseHazardProvider.calculate_centroid(geom_with_pt)
    assert (lat, lon) == (-27.0, 153.0)

    # 2. GeometryCollection without explicit Point
    geom_with_poly = {
        "type": "GeometryCollection",
        "geometries": [
            {
                "type": "Polygon",
                "coordinates": [[[152.0, -26.0], [154.0, -26.0], [154.0, -28.0], [152.0, -28.0], [152.0, -26.0]]],
            }
        ],
    }
    lat, lon = BaseHazardProvider.calculate_centroid(geom_with_poly)
    assert abs(lat - (-27.0)) < 0.01

    # 3. GeometryCollection empty
    assert BaseHazardProvider.calculate_centroid({"type": "GeometryCollection", "geometries": []}) is None

    # 4. MultiPolygon
    multipoly = {
        "type": "MultiPolygon",
        "coordinates": [[[[[150.0, -30.0], [152.0, -30.0], [152.0, -32.0], [150.0, -32.0], [150.0, -30.0]]]]],
    }
    lat, lon = BaseHazardProvider.calculate_centroid(multipoly)
    assert abs(lat - (-31.0)) < 0.01

    # 5. Empty / invalid geometry
    assert BaseHazardProvider.calculate_centroid({}) is None
    assert BaseHazardProvider.calculate_centroid({"type": "Polygon", "coordinates": []}) is None

    # Feature and FeatureCollection
    fc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [151.2, -33.8]}}],
    }
    assert BaseHazardProvider.calculate_centroid(fc) == (-33.8, 151.2)

    fc_poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[150.0, -30.0], [152.0, -30.0], [152.0, -32.0], [150.0, -32.0], [150.0, -30.0]]],
                },
            }
        ],
    }
    lat_fc, _ = BaseHazardProvider.calculate_centroid(fc_poly)
    assert abs(lat_fc - (-31.0)) < 0.01
    assert BaseHazardProvider.calculate_centroid({"type": "FeatureCollection", "features": []}) is None

    feat = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [144.9, -37.8]}}
    assert BaseHazardProvider.calculate_centroid(feat) == (-37.8, 144.9)

    # 6. Test async_fetch_text
    class DummyProvider(BaseHazardProvider):
        @property
        def state_code(self) -> str:
            return "TEST"

        async def async_fetch_hazards(self):
            return []

    mock_resp_200 = AsyncMock()
    mock_resp_200.status = 200
    mock_resp_200.raise_for_status = MagicMock()
    mock_resp_200.text = AsyncMock(return_value="<xml>ok</xml>")

    class MockCM:
        def __init__(self, resp):
            self.resp = resp

        async def __aenter__(self):
            return self.resp

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session = MagicMock()
    session.get = MagicMock(return_value=MockCM(mock_resp_200))

    dummy = DummyProvider(hass, session, {})
    text = await dummy.async_fetch_text("https://example.com/test.xml", headers={"X-Test": "1"})
    assert text == "<xml>ok</xml>"

    # 500 retry then 200
    mock_resp_500 = AsyncMock()
    mock_resp_500.status = 500
    mock_resp_500.raise_for_status = MagicMock()
    session.get.side_effect = [MockCM(mock_resp_500), MockCM(mock_resp_200)]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        text_retry = await dummy.async_fetch_text("https://example.com/retry.xml")
        assert text_retry == "<xml>ok</xml>"
        mock_sleep.assert_called_once()

    # Network error retry then raise
    session.get.side_effect = aiohttp.ClientError("Failed to connect")
    with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(aiohttp.ClientError):
        await dummy.async_fetch_text("https://example.com/fail.xml")

    # 404 calls raise_for_status
    mock_resp_404 = MagicMock()
    mock_resp_404.status = 404
    mock_resp_404.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=404)
    )
    session.get.side_effect = None
    session.get.return_value = MockCM(mock_resp_404)
    with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(aiohttp.ClientResponseError):
        await dummy.async_fetch_text("https://example.com/notfound.xml")

    # Test default base methods returning empty lists / None
    assert await dummy.async_fetch_power_outages() == []
    assert await dummy.async_fetch_road_closures() == []
    assert await dummy.async_fetch_weather_warnings() == []
    assert await dummy.async_fetch_emergency_news() == []
    assert await dummy.async_fetch_fire_danger() is None
    assert await dummy.async_fetch_weather_telemetry() == []
    assert await dummy.async_fetch_air_quality() == []
    assert await dummy.async_fetch_relief_facilities() == []
    assert await dummy.async_fetch_cameras() == []
    assert await dummy.async_fetch_nearby_councils() == []


def test_get_providers_for_all_states(hass: HomeAssistant) -> None:
    """Test get_providers_for_config registers correct providers for all states."""
    session = AsyncMock()

    # WA
    provs_wa = get_providers_for_config(hass, session, {"state": STATE_WA})
    assert any(isinstance(p, WAHazardProvider) for p in provs_wa)
    assert any(isinstance(p, BoMHazardProvider) for p in provs_wa)

    # SA
    provs_sa = get_providers_for_config(hass, session, {"state": STATE_SA})
    assert any(isinstance(p, SAHazardProvider) for p in provs_sa)

    # TAS
    provs_tas = get_providers_for_config(hass, session, {"state": STATE_TAS})
    assert any(isinstance(p, TasmaniaHazardProvider) for p in provs_tas)

    # NT
    provs_nt = get_providers_for_config(hass, session, {"state": STATE_NT})
    assert any(isinstance(p, NTHazardProvider) for p in provs_nt)

    # ACT
    provs_act = get_providers_for_config(hass, session, {"state": STATE_ACT})
    assert any(isinstance(p, ACTHazardProvider) for p in provs_act)

    # NZ
    provs_nz = get_providers_for_config(hass, session, {"state": STATE_NZ})
    assert any(isinstance(p, NZHazardProvider) for p in provs_nz)
    # BoM is not included for NZ
    assert not any(isinstance(p, BoMHazardProvider) for p in provs_nz)


def _wa_fdr_item(area: str, name: str, rating: str | None) -> dict:
    """Return one district in the live Emergency WA fire-danger-ratings shape."""
    forecasts = {"0": {"behaviourIndex": "21", "fireDanger": rating}} if rating else {}
    return {"description": name, "area": area, "issueDateTime": "2026-10-15T20:35:00Z", "forecasts": forecasts}


async def test_wa_fire_danger_uses_configured_district(hass: HomeAssistant) -> None:
    """WA fire danger reads description/area/forecasts and picks the user's district (#14)."""
    payload = {
        "fireDangerRatings": [
            "not a dict",
            _wa_fdr_item("WA_FW041", "North Kimberley", "Moderate"),
            _wa_fdr_item("WA_FW091", "Perth Inner", "Extreme"),
            {**_wa_fdr_item("WA_FW092", "Rottnest", None), "forecasts": {"1": {"fireDanger": "High"}}},
        ],
        "web-message-fdr-today": "",
    }
    perth = WAHazardProvider(hass, AsyncMock(), {"state": STATE_WA, "latitude": -31.95, "longitude": 115.86})
    perth.async_fetch_json = AsyncMock(return_value=payload)
    fdr = await perth.async_fetch_fire_danger()
    assert fdr is not None
    assert fdr.district_number == "WA_FW091"
    assert fdr.district_name == "Perth Inner"
    assert fdr.rating == "Extreme"
    assert fdr.total_fire_ban is None  # the feed has no total fire ban field
    assert fdr.day == "Today"
    # The district is resolved once per location (in an executor) and reused on later polls
    assert perth._fdr_area == ((-31.95, 115.86), "WA_FW091")
    with patch.object(hass, "async_add_executor_job") as executor_job:
        assert await perth.async_fetch_fire_danger() == fdr
    executor_job.assert_not_called()

    # The district has no forecast for today: unknown, not another district's rating
    rottnest = WAHazardProvider(hass, AsyncMock(), {"state": STATE_WA, "latitude": -32.0, "longitude": 115.52})
    rottnest.async_fetch_json = AsyncMock(return_value=payload)
    assert await rottnest.async_fetch_fire_danger() is None

    # The district is missing from the feed
    kalgoorlie = WAHazardProvider(hass, AsyncMock(), {"state": STATE_WA, "latitude": -30.75, "longitude": 121.47})
    kalgoorlie.async_fetch_json = AsyncMock(return_value=payload)
    assert await kalgoorlie.async_fetch_fire_danger() is None

    # Empty, malformed and failing feeds
    perth.async_fetch_json = AsyncMock(return_value={"fireDangerRatings": []})
    assert await perth.async_fetch_fire_danger() is None
    perth.async_fetch_json = AsyncMock(return_value=["not", "a", "dict"])
    assert await perth.async_fetch_fire_danger() is None
    perth.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("FDR error"))
    assert await perth.async_fetch_fire_danger() is None


async def test_wa_fire_danger_without_a_wa_location(hass: HomeAssistant) -> None:
    """No configured location, or one outside every WA district, reports no rating (#14)."""
    fetch = AsyncMock(return_value={"fireDangerRatings": [_wa_fdr_item("WA_FW041", "North Kimberley", "High")]})

    no_location = WAHazardProvider(hass, AsyncMock(), {"state": STATE_WA})
    no_location.async_fetch_json = fetch
    assert await no_location.async_fetch_fire_danger() is None

    sydney = WAHazardProvider(hass, AsyncMock(), {"state": STATE_WA, "latitude": -33.87, "longitude": 151.2})
    sydney.async_fetch_json = fetch
    assert await sydney.async_fetch_fire_danger() is None
    fetch.assert_not_awaited()


async def test_sa_hazard_provider(hass: HomeAssistant) -> None:
    """Test South Australia provider parsing SAFECOM / CFS CAP-AU feed."""
    session = AsyncMock()
    prov = SAHazardProvider(hass, session, {"state": STATE_SA})
    assert prov.state_code == STATE_SA

    xml_text = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
      <entry>
        <id>sa_1</id>
        <title>Emergency Warning - Adelaide Hills Bushfire</title>
        <updated>2026-10-15T12:00:00+10:30</updated>
        <cap:event>Bushfire</cap:event>
        <cap:severity>Extreme</cap:severity>
        <cap:urgency>Immediate</cap:urgency>
        <cap:areaDesc>Mount Barker</cap:areaDesc>
        <cap:circle>-35.06,138.85 5.0</cap:circle>
        <cap:sender>CFS</cap:sender>
      </entry>
      <entry>
        <id>sa_2</id>
        <title>Watch and Act - Kangaroo Island</title>
        <updated>2026-10-15T12:15:00+10:30</updated>
        <cap:event>Grass Fire</cap:event>
        <cap:severity>Severe</cap:severity>
        <cap:polygon>-35.8,137.2 -35.9,137.4 -36.0,137.2 -35.8,137.2</cap:polygon>
      </entry>
      <entry>
        <id>sa_3</id>
        <title>Advice - Barossa Valley</title>
        <updated>2026-10-15T12:30:00+10:30</updated>
        <cap:event>Fire</cap:event>
        <cap:severity>Moderate</cap:severity>
        <cap:circle>-34.5,138.9 0.0</cap:circle>
      </entry>
      <entry>
        <id>sa_4</id>
        <title>Information - Port Lincoln</title>
        <updated>2026-10-15T12:45:00+10:30</updated>
        <cap:event>Structure Fire</cap:event>
        <cap:severity>Unknown</cap:severity>
        <cap:circle>-34.7,135.8 0.0</cap:circle>
      </entry>
      <entry>
        <id>sa_5</id>
        <title>Missing Coords</title>
        <updated>2026-10-15T13:00:00+10:30</updated>
      </entry>
      <entry>
        <id>sa_bad_circle</id>
        <title>Emergency Warning - Bad Circle</title>
        <updated>2026-10-15T13:10:00+10:30</updated>
        <cap:event>Bushfire</cap:event>
        <cap:severity>Extreme</cap:severity>
        <cap:circle>bad_lat,bad_lon 5.0</cap:circle>
        <cap:polygon>-35.8,137.2 -35.9,137.4 -36.0,137.2 -35.8,137.2</cap:polygon>
      </entry>
      <entry>
        <id>sa_bad_polygon</id>
        <title>Bad Polygon</title>
        <updated>2026-10-15T13:20:00+10:30</updated>
        <cap:event>Bushfire</cap:event>
        <cap:polygon>bad_poly,coords</cap:polygon>
      </entry>
    </feed>
    """

    prov.async_fetch_text = AsyncMock(return_value=xml_text)
    # No SES warnings published
    prov.async_fetch_json = AsyncMock(return_value={"type": "FeatureCollection", "features": []})
    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 5

    h1 = next(h for h in hazards if h.id == "sa_cfs_sa_1")
    assert h1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert h1.latitude == -35.06

    h2 = next(h for h in hazards if h.id == "sa_cfs_sa_2")
    assert h2.warning_level == WarningLevel.WATCH_AND_ACT

    h3 = next(h for h in hazards if h.id == "sa_cfs_sa_3")
    assert h3.warning_level == WarningLevel.ADVICE

    h4 = next(h for h in hazards if h.id == "sa_cfs_sa_4")
    assert h4.warning_level == WarningLevel.INFORMATION

    # Test error handling & empty XML
    prov.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("SA CAP down"))
    # CAP-AU down alone still returns SES warnings (none here), so no error
    assert await prov.async_fetch_hazards() == []
    prov.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("SA SES down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_cap_feed("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_cap_feed("<bad")


async def test_act_hazard_provider(hass: HomeAssistant) -> None:
    """Test Australian Capital Territory provider parsing ACT ESA GeoRSS."""
    session = AsyncMock()
    prov = ACTHazardProvider(hass, session, {"state": STATE_ACT})
    assert prov.state_code == STATE_ACT

    xml_text = """<?xml version="1.0"?>
    <rss xmlns:georss="http://www.georss.org/georss" version="2.0">
      <channel>
        <item>
          <title>EMERGENCY WARNING - STROMLO BUSHFIRE</title>
          <guid>act_1</guid>
          <description>Emergency Warning active.</description>
          <georss:point>-35.31 149.02</georss:point>
          <agency>Fire</agency>
          <pubDate>2026-10-15 14:00 AEDT</pubDate>
        </item>
        <item>
          <title>WATCH AND ACT - TUGGERANONG</title>
          <guid>act_2</guid>
          <description>Grass fire approaching.</description>
          <pubDate>2026-10-15 14:15 AEDT</pubDate>
        </item>
        <item>
          <title>ADVICE - GUNGAHLIN</title>
          <guid>act_3</guid>
          <description>Smoke advisory.</description>
          <georss:point>-35.18 149.13</georss:point>
          <pubDate>2026-10-15 14:30 AEDT</pubDate>
        </item>
        <item>
          <title>HAZARD REDUCTION BURN - DUFFY</title>
          <guid>act_4</guid>
          <description>Planned burn underway.</description>
          <georss:point>-35.32 149.03</georss:point>
          <pubDate>2026-10-15 14:45 AEDT</pubDate>
        </item>
        <item>
          <title>GRASS FIRE - BELCONNEN</title>
          <guid>act_5</guid>
          <description>Crews on scene.</description>
          <georss:point>-35.24 149.06</georss:point>
          <pubDate>2026-10-15 15:00 AEDT</pubDate>
        </item>
        <item>
          <title>BAD COORDS - ACT</title>
          <guid>act_6</guid>
          <description>Bad coords.</description>
          <georss:point>bad_lat bad_lon</georss:point>
          <agency>Fire</agency>
          <pubDate>2026-10-15 15:15 AEDT</pubDate>
        </item>
      </channel>
    </rss>
    """

    prov.async_fetch_text = AsyncMock(return_value=xml_text)
    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 6

    h1 = next(h for h in hazards if h.id == "act_esa_act_1")
    assert h1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert h1.latitude == -35.31

    h2 = next(h for h in hazards if h.id == "act_esa_act_2")
    assert h2.warning_level == WarningLevel.WATCH_AND_ACT
    assert h2.latitude == -35.2809  # Default Canberra fallback

    h3 = next(h for h in hazards if h.id == "act_esa_act_3")
    assert h3.warning_level == WarningLevel.ADVICE

    h4 = next(h for h in hazards if h.id == "act_esa_act_4")
    assert h4.is_hazard_reduction is True

    h5 = next(h for h in hazards if h.id == "act_esa_act_5")
    assert h5.warning_level == WarningLevel.INFORMATION
    assert h5.hazard_type == HazardType.GRASS_FIRE

    # Test error handling & empty XML
    prov.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("ACT ESA down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_act_feed("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_act_feed("<bad")


async def test_act_incident_time_from_description(hass: HomeAssistant) -> None:
    """ACT uses the "Updated:" line (incident time) rather than pubDate (feed build time) (#13)."""
    provider = ACTHazardProvider(hass, AsyncMock(), {"state": "ACT"})
    xml_text = """<?xml version="1.0"?>
    <rss xmlns:georss="http://www.georss.org/georss"><channel>
      <item>
        <title>GRASS FIRE - Hume</title>
        <guid>ACT-1001</guid>
        <description>Status: Going&lt;br&gt;Updated: 2026-10-15 19:05 AEDT&lt;br&gt;Size: 1 ha</description>
        <pubDate>2026-10-15 20:46 AEDT</pubDate>
        <georss:point>-35.39 149.16</georss:point>
      </item>
      <item>
        <title>GRASS FIRE - Tharwa</title>
        <guid>ACT-1002</guid>
        <description>Status: Going</description>
        <pubDate>2026-10-15 20:46 AEDT</pubDate>
        <georss:point>-35.51 149.07</georss:point>
      </item>
    </channel></rss>"""
    hazards = {h.id: h for h in provider._parse_act_feed(xml_text)}
    assert hazards["act_esa_ACT-1001"].updated_at == datetime(2026, 10, 15, 8, 5, tzinfo=UTC)
    # No "Updated:" label: falls back to pubDate
    assert hazards["act_esa_ACT-1002"].updated_at == datetime(2026, 10, 15, 9, 46, tzinfo=UTC)


def test_nsw_incidents_without_a_warning_are_information(hass: HomeAssistant) -> None:
    """RFS incidents whose ALERT LEVEL is "Not Applicable" are information, not "Unknown"."""
    provider = NSWHazardProvider(hass, AsyncMock(), {"state": STATE_NSW})
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [150.8, -33.6]},
        "properties": {
            "title": "WINDSOR RD, GRANTHAM FARM",
            "guid": "https://www.rfs.nsw.gov.au/fire-information/fires-near-me/681483",
            "category": "Not Applicable",
            "description": "ALERT LEVEL: Not Applicable <br />TYPE: Bush Fire <br />",
        },
    }
    hazard = provider._parse_nsw_feature(nsw_entry(feature))
    assert hazard is not None
    assert hazard.warning_level is WarningLevel.INFORMATION
