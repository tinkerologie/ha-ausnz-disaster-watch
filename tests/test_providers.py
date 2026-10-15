from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import defusedxml.ElementTree as ET
import pytest

from custom_components.australian_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    STATE_NSW,
    STATE_QLD,
    STATE_VIC,
)
from custom_components.australian_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from custom_components.australian_disaster_watch.providers import (
    BaseHazardProvider,
    BoMHazardProvider,
    NSWHazardProvider,
    QueenslandHazardProvider,
    VictoriaHazardProvider,
    get_providers_for_config,
)
from homeassistant.core import HomeAssistant


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


async def test_qld_provider_parsing(hass: HomeAssistant) -> None:
    """Test Queensland provider parsing QFD and council endpoints."""
    session = AsyncMock()
    config = {
        "state": STATE_QLD,
        "latitude": -27.2657,
        "longitude": 152.9818,
        CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
    }
    provider = QueenslandHazardProvider(hass, session, config)

    # 1. Mock QFD bushfireAlert.json
    mock_qfd = {
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [152.95, -27.08, 0],
                            [152.96, -27.08, 0],
                            [152.96, -27.09, 0],
                            [152.95, -27.08, 0],
                        ]
                    ],
                },
                "properties": {
                    "UniqueID": "WARN-9999",
                    "WarningTitle": "STAY INFORMED - Caboolture Fire",
                    "WarningLevel": "Advice",
                    "Incident_Type": "Vegetation Fire",
                    "CallToAction": "Stay Informed",
                    "Agency": "QFD",
                    "LastUpdate": "2026-10-15T01:00:00Z",
                },
            }
        ]
    }

    # 2. Mock council fireDetailed
    mock_council_fire = [
        {
            "properties": {
                "Master_Incident_Number": "88888",
                "Incident_Type": "Bushfire",
                "Location_Name": "Burpengary",
                "CurrentStatus": "Under Control",
                "Latitude": -27.15,
                "Longitude": 152.97,
                "LastUpdate": 1729000000,
            }
        },
        {
            # Zero coordinates should be ignored
            "properties": {
                "Master_Incident_Number": "00000",
                "Incident_Type": "Bushfire",
                "Latitude": 0.0,
                "Longitude": 0.0,
            }
        },
    ]

    # 3. Mock council tmrRoadData
    mock_council_road = [
        {
            "type": "Feature",
            "geometry": {
                "type": "GeometryCollection",
                "geometries": [{"type": "Point", "coordinates": [152.816, -26.992]}],
            },
            "properties": {
                "id": 834413,
                "status": "Published",
                "event_type": "Hazard",
                "impact": {"impact_subtype": "Road closed to all traffic"},
                "duration": {"start": "2026-10-15T00:00:00Z"},
            },
        }
    ]

    async def mock_fetch_json(url: str, **kwargs):
        if "bushfireAlert.json" in url:
            return mock_qfd
        if "fireDetailed" in url:
            return mock_council_fire
        if "tmrRoadData" in url:
            return mock_council_road
        if "bom" in url:
            return {"item": []}
        return None

    provider.async_fetch_json = AsyncMock(side_effect=mock_fetch_json)

    hazards = await provider.async_fetch_hazards()

    # We expect 3 hazards: 1 from QFD, 1 valid from council fire, 1 from council road
    assert len(hazards) == 3

    # Check QFD hazard
    qfd_hazard = next(h for h in hazards if h.id == "QLD_QFD_WARN-9999")
    assert qfd_hazard.warning_level == WarningLevel.ADVICE
    assert qfd_hazard.hazard_type == HazardType.BUSHFIRE
    assert "Caboolture" in qfd_hazard.title

    # Check council fire hazard
    fire_hazard = next(h for h in hazards if h.id == "QLD_COUNCIL_FIRE_88888")
    assert fire_hazard.location_name == "Burpengary"
    assert fire_hazard.latitude == -27.15

    # Check council road hazard
    road_hazard = next(h for h in hazards if h.id == "QLD_COUNCIL_ROAD_834413")
    assert road_hazard.hazard_type == HazardType.ROAD_INCIDENT
    assert "Road closed" in road_hazard.title


async def test_nsw_provider_parsing(hass: HomeAssistant) -> None:
    """Test NSW RFS provider parsing with HTML description."""
    session = AsyncMock()
    config = {"state": STATE_NSW, "latitude": -33.8688, "longitude": 151.2093}
    provider = NSWHazardProvider(hass, session, config)

    mock_nsw_feed = {
        "features": [
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
        ]
    }

    provider.async_fetch_json = AsyncMock(return_value=mock_nsw_feed)
    hazards = await provider.async_fetch_hazards()

    assert len(hazards) == 1
    h = hazards[0]
    assert h.id == "NSW_RFS_681307"
    assert h.title == "Baffle Road"
    assert h.warning_level == WarningLevel.ADVICE
    assert h.hazard_type == HazardType.BUSHFIRE
    assert h.status == "Under control"
    assert h.location_name == "BAFFLE RD, DALMORTON"


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


async def test_bom_provider_parsing(hass: HomeAssistant) -> None:
    """Test BoM weather warnings provider parsing WMO CAP RSS XML."""
    session = AsyncMock()
    config = {"state": STATE_QLD, "latitude": -27.2657, "longitude": 152.9818}
    provider = BoMHazardProvider(hass, session, config)

    xml_content = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Severe Thunderstorm Warning for Moreton Bay</title>
          <description>Severe thunderstorms likely to produce damaging winds and heavy rainfall</description>
          <link>https://www.bom.gov.au/warning/IDQ21033</link>
          <pubDate>Thu, 15 Oct 2026 00:43:07 +0000</pubDate>
          <guid isPermaLink="false">AusBoM-IDQ21033-2026-10-15T00:43:07+00:00</guid>
        </item>
        <item>
          <title>Severe Thunderstorm Warning for Sydney</title>
          <description>NSW Storms</description>
          <link>https://www.bom.gov.au/warning/IDN12345</link>
          <pubDate>Thu, 15 Oct 2026 00:43:07 +0000</pubDate>
          <guid isPermaLink="false">AusBoM-IDN12345-2026-10-15T00:43:07+00:00</guid>
        </item>
      </channel>
    </rss>
    """

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=xml_content)

    class MockContextManager:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockContextManager())

    hazards = await provider.async_fetch_hazards()

    # Config is STATE_QLD, so only IDQ hazard should be returned (IDN is filtered out)
    assert len(hazards) == 1
    h = hazards[0]
    assert "IDQ21033" in h.id
    assert "Moreton Bay" in h.title
    assert h.hazard_type == HazardType.SEVERE_STORM
    assert h.warning_level == WarningLevel.WATCH_AND_ACT


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
    mock_resp_200 = AsyncMock()
    mock_resp_200.status = 200
    mock_resp_200.json = AsyncMock(return_value={"retry": "ok"})
    session.get.side_effect = [MockCM(mock_resp_500), MockCM(mock_resp_200)]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        data2 = await provider.async_fetch_json("https://example.com/api2")
        assert data2 == {"retry": "ok"}
        mock_sleep.assert_called_once()

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
    """Test parse_datetime across all supported date and timestamp formats."""
    now_dt = datetime.now(UTC)
    assert BaseHazardProvider.parse_datetime(now_dt) == now_dt

    naive_dt = datetime(2026, 10, 15, 10, 30)
    assert BaseHazardProvider.parse_datetime(naive_dt).tzinfo == UTC

    # Timestamp seconds and ms
    assert BaseHazardProvider.parse_datetime(1729000000).year == 2024
    assert BaseHazardProvider.parse_datetime(1729000000000).year == 2024

    # Empty and non-string
    assert BaseHazardProvider.parse_datetime(None).tzinfo == UTC
    assert BaseHazardProvider.parse_datetime("").tzinfo == UTC

    # ISO formats
    assert BaseHazardProvider.parse_datetime("2026-10-15T12:00:00Z").year == 2026
    assert BaseHazardProvider.parse_datetime("2026-10-15T12:00:00+10:00").year == 2026

    # RFC 2822
    assert BaseHazardProvider.parse_datetime("Thu, 15 Oct 2026 01:27:00 GMT").year == 2026

    # Australian agency formats
    assert BaseHazardProvider.parse_datetime("15/10/2026 01:30:00 PM").year == 2026
    assert BaseHazardProvider.parse_datetime("15/10/2026 13:30:00").year == 2026
    assert BaseHazardProvider.parse_datetime("15/10/2026 01:30 PM").year == 2026
    assert BaseHazardProvider.parse_datetime("15/10/2026 13:30").year == 2026
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 13:30").year == 2026
    assert BaseHazardProvider.parse_datetime("2026-10-15 13:30:00").year == 2026

    # Fallback for unrecognized string
    assert BaseHazardProvider.parse_datetime("unparsable date string").tzinfo == UTC


async def test_qld_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test Queensland provider state code, error branches, and bulletin parsing."""
    session = AsyncMock()
    config = {
        "state": STATE_QLD,
        CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
    }
    provider = QueenslandHazardProvider(hass, session, config)
    assert provider.state_code == STATE_QLD

    # Exception in fetch returns empty list
    provider.async_fetch_json = AsyncMock(side_effect=RuntimeError("Feed error"))
    hazards = await provider.async_fetch_hazards()
    assert hazards == []

    # Test bulletin and BoM parsing
    bulletin_feat = {
        "properties": {
            "id": "BUL_1",
            "title": "Evacuation Center Open",
            "priority": "High",
            "created": "2026-10-15T00:00:00Z",
        },
        "geometry": {"type": "Point", "coordinates": [152.9, -27.1]},
    }
    h_bul = provider._parse_council_bulletin_feature(bulletin_feat)
    assert h_bul is not None
    assert h_bul.id == "QLD_COUNCIL_BULLETIN_BUL_1"
    assert h_bul.title == "Evacuation Center Open"

    # Bulletin without ID returns None
    assert provider._parse_council_bulletin_feature({"properties": {}}) is None

    # Council BoM item
    bom_item = {
        "title": "Severe Weather Warning",
        "link": "http://example.com/bom",
        "pubDate": "2026-10-15T00:00:00Z",
    }
    h_bom = provider._parse_council_bom_item(bom_item)
    assert h_bom is not None
    assert h_bom.warning_level == WarningLevel.WATCH_AND_ACT

    # BoM item without title returns None
    assert provider._parse_council_bom_item({}) is None


async def test_nsw_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test NSW provider state code, error branches, and description parsing."""
    session = AsyncMock()
    provider = NSWHazardProvider(hass, session, {"state": STATE_NSW})
    assert provider.state_code == STATE_NSW

    provider.async_fetch_json = AsyncMock(side_effect=RuntimeError("NSW feed failed"))
    assert await provider.async_fetch_hazards() == []

    # Feature without centroid
    assert provider._parse_nsw_feature({"geometry": {}, "properties": {}}) is None

    # Feature without guid (fallback ID generation)
    feat_no_guid = {
        "geometry": {"type": "Point", "coordinates": [151.0, -33.0]},
        "properties": {
            "title": "Grass Fire Hunter",
            "category": "Advice",
            "description": "",
        },
    }
    h = provider._parse_nsw_feature(feat_no_guid)
    assert h is not None
    assert "Hunter" in h.id


async def test_vic_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test Victoria provider state code, error branches, and CAP severities."""
    session = AsyncMock()
    provider = VictoriaHazardProvider(hass, session, {"state": STATE_VIC})
    assert provider.state_code == STATE_VIC

    provider.async_fetch_json = AsyncMock(side_effect=RuntimeError("Vic feed error"))
    assert await provider.async_fetch_hazards() == []

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


async def test_bom_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test BoM provider edge cases."""
    session = MagicMock()
    provider = BoMHazardProvider(hass, session, {"state": "ALL"})
    assert provider.state_code == "ALL"

    # Non-200 status
    mock_resp_404 = AsyncMock()
    mock_resp_404.status = 404

    class MockCM:
        async def __aenter__(self):
            return mock_resp_404

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockCM())
    assert await provider.async_fetch_hazards() == []

    # XML without channel
    mock_resp_bad_xml = AsyncMock()
    mock_resp_bad_xml.status = 200
    mock_resp_bad_xml.text = AsyncMock(return_value="<rss></rss>")

    class MockCM2:
        async def __aenter__(self):
            return mock_resp_bad_xml

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session.get = MagicMock(return_value=MockCM2())
    assert await provider.async_fetch_hazards() == []

    # Parse item cancellation and missing title
    item_cancel = ET.fromstring("<item><title>Cancellation Severe Weather Warning</title></item>")
    assert provider._parse_item(item_cancel) is None

    item_empty = ET.fromstring("<item><title></title></item>")
    assert provider._parse_item(item_empty) is None

    # State prefixes and fallback centroid
    prov_tas = BoMHazardProvider(hass, session, {"state": "TAS"})
    item_tas = ET.fromstring(
        "<item><title>Flood Warning for South Esk River</title><guid>AusBoM-IDT12345</guid></item>"
    )
    h_tas = prov_tas._parse_item(item_tas)
    assert h_tas is not None
    assert h_tas.latitude == -42.0
    assert h_tas.longitude == 146.5


async def test_base_provider_headers_and_status(hass: HomeAssistant) -> None:
    """Test BaseHazardProvider headers update, 404 raise_for_status, and non-list centroid points."""
    session = MagicMock()
    provider = DummyProvider(hass, session, {})

    # Headers passed
    mock_resp = AsyncMock()
    mock_resp.status = 200
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
    mock_resp_404 = AsyncMock()
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


async def test_bom_provider_exception_and_fallbacks(hass: HomeAssistant) -> None:
    """Test BoM exception catching, advice fallback, and unknown centroid fallback."""
    session = MagicMock()
    session.get.side_effect = RuntimeError("Fatal network error")
    provider = BoMHazardProvider(hass, session, {"state": "ALL"})

    # Exception in fetch
    hazards = await provider.async_fetch_hazards()
    assert hazards == []

    # Advice fallback for non-severe/flood/cyclone warning & unknown target_state centroid fallback
    item = ET.fromstring("<item><title>Marine Wind Warning</title><guid>AusBoM-UNK-999</guid></item>")
    h = provider._parse_item(item)
    assert h is not None
    assert h.warning_level == WarningLevel.ADVICE
    assert h.latitude == -27.2657
    assert h.longitude == 152.9818


async def test_nsw_and_vic_empty_and_cap_none(hass: HomeAssistant) -> None:
    """Test NSW and VIC when feeds return empty or non-dict, and VIC cap is None."""
    session = AsyncMock()

    # NSW empty
    nsw_prov = NSWHazardProvider(hass, session, {"state": STATE_NSW})
    nsw_prov.async_fetch_json = AsyncMock(return_value=None)
    assert await nsw_prov.async_fetch_hazards() == []

    # VIC empty
    vic_prov = VictoriaHazardProvider(hass, session, {"state": STATE_VIC})
    vic_prov.async_fetch_json = AsyncMock(return_value=[])
    assert await vic_prov.async_fetch_hazards() == []

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


async def test_qld_provider_detailed_branches(hass: HomeAssistant) -> None:
    """Test all remaining QLD provider branches for 100% coverage."""
    session = AsyncMock()
    provider = QueenslandHazardProvider(
        hass,
        session,
        {"state": STATE_QLD, CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au"},
    )

    # QFD feature without centroid
    assert provider._parse_qfd_feature({"geometry": {}, "properties": {"UniqueID": "1"}}) is None

    # QFD feature without unique_id
    assert (
        provider._parse_qfd_feature(
            {"geometry": {"type": "Point", "coordinates": [152.9, -27.1]}, "properties": {"UniqueID": ""}}
        )
        is None
    )
    assert (
        provider._parse_qfd_feature(
            {"geometry": {"type": "Point", "coordinates": [152.9, -27.1]}, "properties": {"UniqueID": "   "}}
        )
        is None
    )

    # Council fire item with lat/lon None and geometry centroid
    fire_geom = {
        "geometry": {"type": "Point", "coordinates": [152.95, -27.15]},
        "properties": {"Master_Incident_Number": "123", "Location_Name": "Caboolture"},
    }
    h_fire_geom = provider._parse_council_fire_item(fire_geom)
    assert h_fire_geom is not None
    assert h_fire_geom.latitude == -27.15

    # Council fire item with lat/lon None and no geometry centroid
    fire_no_geom = {"geometry": {}, "properties": {"Master_Incident_Number": "123"}}
    assert provider._parse_council_fire_item(fire_no_geom) is None

    # Council fire item with invalid float coordinates
    fire_bad_coords = {"properties": {"Latitude": "invalid", "Longitude": 152.0, "Master_Incident_Number": "123"}}
    assert provider._parse_council_fire_item(fire_bad_coords) is None

    # Council fire item with inc_id == "0"
    fire_zero_id = {"properties": {"Latitude": -27.0, "Longitude": 152.0, "Master_Incident_Number": "0"}}
    assert provider._parse_council_fire_item(fire_zero_id) is None

    # Council road item without centroid
    assert provider._parse_council_road_item({"geometry": {}, "properties": {"id": "1"}}) is None

    # Council road item without road_id
    road_no_id = {
        "geometry": {"type": "Point", "coordinates": [152.9, -27.1]},
        "properties": {"id": ""},
    }
    assert provider._parse_council_road_item(road_no_id) is None

    # Council road item with status == "Reopened"
    road_reopened = {
        "geometry": {"type": "Point", "coordinates": [152.9, -27.1]},
        "properties": {"id": "ROAD_OPEN", "status": "Reopened"},
    }
    assert provider._parse_council_road_item(road_reopened) is None

    # Council BoM item with title without severe/flood/cyclone
    bom_marine = {
        "title": "Marine Wind Warning",
        "link": "http://example.com/marine",
        "pubDate": "2026-10-15T00:00:00Z",
    }
    h_marine = provider._parse_council_bom_item(bom_marine)
    assert h_marine is not None
    assert h_marine.warning_level == WarningLevel.ADVICE

    # Full council fetch loop covering BoM items and bulletins added to hazards
    async def mock_fetch_all(url: str, **kwargs):
        if "bushfireAlert" in url:
            return {"features": []}
        if "fireDetailed" in url:
            return []
        if "tmrRoadData" in url:
            return []
        if "bom" in url:
            return {"item": [bom_marine]}
        if "imsBulletin" in url:
            return {
                "features": [
                    {
                        "properties": {"id": "BUL_LOOP", "title": "Bulletin Alert"},
                        "geometry": {"type": "Point", "coordinates": [152.9, -27.1]},
                    }
                ]
            }
        return None

    provider.async_fetch_json = AsyncMock(side_effect=mock_fetch_all)
    all_hazards = await provider.async_fetch_hazards()
    assert len(all_hazards) == 2
    assert any(h.id == "QLD_COUNCIL_BULLETIN_BUL_LOOP" for h in all_hazards)
