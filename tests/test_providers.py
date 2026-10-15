from datetime import UTC, datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import defusedxml.ElementTree as ET
import pytest

from custom_components.ausnz_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_NZ,
    STATE_QLD,
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


async def test_qld_provider_edge_cases(hass: HomeAssistant) -> None:
    """Test Queensland provider state code, error branches, and bulletin parsing."""
    session = AsyncMock()
    config = {
        "state": STATE_QLD,
        CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
    }
    provider = QueenslandHazardProvider(hass, session, config)
    assert provider.state_code == STATE_QLD

    # QFD and every council endpoint unreachable: the provider reports itself unavailable (#16)
    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("Feed error"))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

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

    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("NSW feed failed"))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

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
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

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
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

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


async def test_bom_provider_exception_and_fallbacks(hass: HomeAssistant) -> None:
    """Test BoM exception catching, advice fallback, and unknown centroid fallback."""
    session = MagicMock()
    session.get.side_effect = aiohttp.ClientError("Fatal network error")
    provider = BoMHazardProvider(hass, session, {"state": "ALL"})

    # Network failure: unavailable, not an all-clear (#16)
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()

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

    # NSW: a non-object payload is a broken feed, not an all-clear (#16)
    nsw_prov = NSWHazardProvider(hass, session, {"state": STATE_NSW})
    nsw_prov.async_fetch_json = AsyncMock(return_value=None)
    with pytest.raises(ProviderUnavailableError):
        await nsw_prov.async_fetch_hazards()
    # ...while a valid feed with no features is a genuine all-clear
    nsw_prov.async_fetch_json = AsyncMock(return_value={"type": "FeatureCollection", "features": []})
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


async def test_nsw_provider_composite_methods(hass: HomeAssistant) -> None:
    """Test NSW provider composite feeds: fire danger, warnings, news, and councils."""
    session = AsyncMock()
    prov_default = NSWHazardProvider(hass, session, {"state": STATE_NSW})
    assert prov_default._get_council_base_url() is None

    assert await prov_default.async_fetch_fire_danger() is None
    assert await prov_default.async_fetch_weather_warnings() == []
    assert await prov_default.async_fetch_emergency_news() == []

    prov_custom = NSWHazardProvider(
        hass,
        session,
        {"state": STATE_NSW, CONF_COUNCIL_DASHBOARD_URL: "https://emergency.bmcc.nsw.gov.au/"},
    )
    assert prov_custom._get_council_base_url() == "https://emergency.bmcc.nsw.gov.au"

    # Fire Danger: Success with TOBAN True
    prov_custom.async_fetch_json = AsyncMock(
        return_value={
            "Data": [
                {
                    "District_Number": "5",
                    "District_Name": "Greater Sydney",
                    "FDR": "Extreme",
                    "TOBAN": "Yes",
                    "Day": "Today",
                }
            ]
        }
    )
    fd = await prov_custom.async_fetch_fire_danger()
    assert fd is not None
    assert fd.rating == "Extreme"
    assert fd.total_fire_ban is True
    assert fd.district_name == "Greater Sydney"

    # Fire Danger: Empty data & Exception
    prov_custom.async_fetch_json = AsyncMock(return_value={"Data": []})
    assert await prov_custom.async_fetch_fire_danger() is None

    prov_custom.async_fetch_json = AsyncMock(side_effect=RuntimeError("FDR API error"))
    assert await prov_custom.async_fetch_fire_danger() is None

    # Weather Warnings: Success & Empty Title & Exception
    prov_custom.async_fetch_json = AsyncMock(
        return_value={
            "item": [
                {
                    "title": "Severe Weather Warning",
                    "link": "https://bom.gov.au/warn1",
                    "locations": "Blue Mountains",
                    "pubDate": "2026-10-15T01:00:00Z",
                },
                {"title": "   "},
            ]
        }
    )
    warnings = await prov_custom.async_fetch_weather_warnings()
    assert len(warnings) == 1
    assert warnings[0].title == "Severe Weather Warning"

    prov_custom.async_fetch_json = AsyncMock(side_effect=RuntimeError("BoM API error"))
    assert await prov_custom.async_fetch_weather_warnings() == []

    # Emergency News: Success & Exception
    prov_custom.async_fetch_json = AsyncMock(
        return_value={
            "features": [
                {
                    "properties": {
                        "id": "NEWS_1",
                        "title": "Council Evacuation Notice",
                        "description": "Evacuate immediately",
                        "url": "https://bmcc.nsw.gov.au/news/1",
                        "created": "2026-10-15T02:00:00Z",
                    }
                }
            ]
        }
    )
    news = await prov_custom.async_fetch_emergency_news()
    assert len(news) == 1
    assert news[0].title == "Council Evacuation Notice"

    prov_custom.async_fetch_json = AsyncMock(side_effect=RuntimeError("News API error"))
    assert await prov_custom.async_fetch_emergency_news() == []

    # Nearby Councils
    councils = await prov_custom.async_fetch_nearby_councils()
    assert len(councils) == 5
    assert any("Hawkesbury" in c["name"] for c in councils)


async def test_qld_provider_composite_methods(hass: HomeAssistant) -> None:
    """Test Queensland provider composite feeds for all dashboard sections."""
    session = AsyncMock()
    prov = QueenslandHazardProvider(
        hass,
        session,
        {"state": STATE_QLD, CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au"},
    )
    assert prov._get_council_base_url() == "https://disaster.moretonbay.qld.gov.au"

    # Default URL
    prov_default = QueenslandHazardProvider(hass, session, {"state": STATE_QLD})
    assert prov_default._get_council_base_url() is None
    assert await prov_default.async_fetch_power_outages() == []
    assert await prov_default.async_fetch_road_closures() == []
    assert await prov_default.async_fetch_weather_warnings() == []
    assert await prov_default.async_fetch_emergency_news() == []
    assert await prov_default.async_fetch_fire_danger() is None
    assert await prov_default.async_fetch_weather_telemetry() == []
    assert await prov_default.async_fetch_air_quality() == []
    assert await prov_default.async_fetch_relief_facilities() == []
    assert await prov_default.async_fetch_cameras() == []
    assert await prov_default.async_fetch_nearby_councils() == []

    # 1. Power Outages: nested Outage, flat dict, invalid item, exception
    prov.async_fetch_json = AsyncMock(
        return_value=[
            {
                "Outage": {
                    "suburb": "Burpengary",
                    "cause": "Under Investigation",
                    "restoreTime": "18:00",
                    "customersAffected": "45",
                }
            },
            {
                "suburb": "Morayfield",
                "cause": "Equipment failure",
                "restoreTime": None,
                "customersAffected": 12,
            },
            "invalid_non_dict_model",
        ]
    )
    outages = await prov.async_fetch_power_outages()
    assert len(outages) == 2
    assert outages[0].suburb == "Burpengary"
    assert outages[0].customers_affected == 45
    assert outages[1].suburb == "Morayfield"

    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("Outage feed error"))
    assert await prov.async_fetch_power_outages() == []

    # 2. Road Closures: Council roads and TMR roads (as JSON list and string)
    async def mock_roads(url: str, **kwargs):
        if "moretonRoadClosures" in url:
            return {
                "features": [
                    {
                        "properties": {
                            "ID": "101",
                            "ROAD": "Oakey Flat Rd",
                            "SUBURB": "Morayfield",
                            "STATUS": "Closed",
                            "REASON": "Water over road",
                            "DESCRIPTION": "Heavy flooding",
                            "UPDATETIME": "2026-10-15T03:00:00Z",
                        },
                        "geometry": {"type": "Point", "coordinates": [152.95, -27.12]},
                    },
                    # Duplicate ID should be deduplicated
                    {
                        "properties": {"ID": "101", "ROAD": "Oakey Flat Rd"},
                        "geometry": {"type": "Point", "coordinates": [152.95, -27.12]},
                    },
                ]
            }
        if "tmrRoadData" in url:
            tmr_items = [
                {
                    "properties": {
                        "id": "TMR_500",
                        "status": "Hazardous",
                        "event_due_to": "Flash flooding",
                        "description": "Highway partially submerged",
                        "advice": "Drive with caution",
                        "last_updated": "2026-10-15T03:30:00Z",
                        "road_summary": {"road_name": "Bruce Highway", "locality": "Caboolture"},
                        "impact": {"impact_subtype": "Flooding"},
                    },
                    "geometry": {"type": "Point", "coordinates": [152.96, -27.08]},
                },
                # Duplicate TMR road item to exercise seen_ids check
                {
                    "properties": {"id": "TMR_500"},
                    "geometry": {"type": "Point", "coordinates": [152.96, -27.08]},
                },
            ]
            return json.dumps(tmr_items)
        return None

    prov.async_fetch_json = AsyncMock(side_effect=mock_roads)
    closures = await prov.async_fetch_road_closures()
    assert len(closures) == 2
    assert closures[0].road == "Oakey Flat Rd"
    assert closures[0].source == "Local Council"
    assert closures[1].road == "Bruce Highway"
    assert closures[1].source == "Department of Transport and Main Roads"

    # TMR roads as invalid string and council roads raising error
    async def mock_bad_string_tmr(url: str, **kwargs):
        if "moretonRoadClosures" in url:
            raise RuntimeError("Council road feed offline")
        if "tmrRoadData" in url:
            return "invalid_not_json{"
        return None

    prov.async_fetch_json = AsyncMock(side_effect=mock_bad_string_tmr)
    assert await prov.async_fetch_road_closures() == []

    # TMR roads raising an exception
    async def mock_bad_tmr_exc(url: str, **kwargs):
        if "moretonRoadClosures" in url:
            return {"features": []}
        if "tmrRoadData" in url:
            raise RuntimeError("TMR API connection failed")
        return None

    prov.async_fetch_json = AsyncMock(side_effect=mock_bad_tmr_exc)
    bad_closures = await prov.async_fetch_road_closures()
    assert bad_closures == []

    # 3. Weather Warnings: Success, empty title, exception
    prov.async_fetch_json = AsyncMock(
        return_value={
            "item": [
                {
                    "title": "Severe Thunderstorm Warning",
                    "link": "https://bom.gov.au/warn_qld",
                    "locations": "City of Moreton Bay",
                    "pubDate": "2026-10-15T04:00:00Z",
                },
                {"title": ""},
            ]
        }
    )
    warnings = await prov.async_fetch_weather_warnings()
    assert len(warnings) == 1
    assert warnings[0].title == "Severe Thunderstorm Warning"

    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("BoM feed error"))
    assert await prov.async_fetch_weather_warnings() == []

    # 4. Emergency News: Success, exception
    prov.async_fetch_json = AsyncMock(
        return_value={
            "features": [
                {
                    "properties": {
                        "id": "NEWS_QLD_1",
                        "title": "Local Disaster Management Group Activated",
                        "description": "Council has moved to Lean Forward status",
                        "url": "https://moretonbay.qld.gov.au/news/1",
                        "created": "2026-10-15T05:00:00Z",
                    }
                }
            ]
        }
    )
    news = await prov.async_fetch_emergency_news()
    assert len(news) == 1
    assert news[0].title == "Local Disaster Management Group Activated"

    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("Bulletin feed error"))
    assert await prov.async_fetch_emergency_news() == []

    # 5. Fire Danger: Success with TOBAN="1", exception
    prov.async_fetch_json = AsyncMock(
        return_value={
            "Data": [
                {
                    "District_Number": "1",
                    "District_Name": "Moreton",
                    "FDR": "High",
                    "TOBAN": "1",
                    "Day": "Today",
                }
            ]
        }
    )
    fd = await prov.async_fetch_fire_danger()
    assert fd is not None
    assert fd.rating == "High"
    assert fd.total_fire_ban is True

    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("FDR feed error"))
    assert await prov.async_fetch_fire_danger() is None

    # 6. Weather Telemetry: Stations data and Currtemp fallback
    prov.async_fetch_json = AsyncMock(
        return_value=[
            {
                "id": "BURP_STATION",
                "name": "Burpengary East Telemetry",
                "weatherData": [
                    {"name": "TenMin - AirTC", "currentValue": "26.4"},
                    {"name": "TenMin - RH", "currentValue": 68.2},
                    {"name": "TenMin - BP hPa", "currentValue": "1015.1"},
                    {"name": "Hourly - WindDir-Avg-Vect", "currentValue": "ESE"},
                    {"name": "Hourly - ws-kph-Avg", "currentValue": "14.2"},
                    {"name": "Hourly - ws-kph-Max", "currentValue": "22.5"},
                    {"name": "TenMin - SlrW", "currentValue": "450.0"},
                    {"name": "TenMin - BadFloat", "currentValue": "not_a_number"},
                ],
            }
        ]
    )
    stations = await prov.async_fetch_weather_telemetry()
    assert len(stations) == 1
    assert stations[0].station_id == "BURP_STATION"
    assert stations[0].temperature == 26.4
    assert stations[0].relative_humidity == 68.2
    assert stations[0].solar_radiation == 450.0

    # Currtemp fallback when stations empty
    async def mock_currtemp(url: str, **kwargs):
        if "getWeatherStationsData" in url:
            return []
        if "Currtemp" in url:
            return {"air_temp": "24.5", "apparent_t": "25.0"}
        return None

    prov.async_fetch_json = AsyncMock(side_effect=mock_currtemp)
    fallback_stations = await prov.async_fetch_weather_telemetry()
    assert len(fallback_stations) == 1
    assert fallback_stations[0].station_id == "currtemp"
    assert fallback_stations[0].temperature == 24.5
    assert fallback_stations[0].apparent_temperature == 25.0

    # Exception in telemetry
    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("Weather telemetry error"))
    assert await prov.async_fetch_weather_telemetry() == []

    # 7. Air Quality: Stations data, exception
    prov.async_fetch_json = AsyncMock(
        return_value={
            "AirQualityStationDataList": [
                {
                    "station_id": "burp",
                    "station_name": "Burpengary",
                    "PM2_5_Measurement": "11.2",
                    "PM2_5_Rating": "Good",
                    "PM2_5_Running_Average": "10.8",
                    "PM10_Measurement": "24.1",
                    "PM10_Rating": "Fair",
                    "PM10_Running_Average": "22.0",
                    "NO2_Measurement": "4.5",
                    "NO2_Rating": "Good",
                    "O3_Measurement": "14.0",
                    "O3_Rating": "Good",
                }
            ]
        }
    )
    aq_stations = await prov.async_fetch_air_quality()
    assert len(aq_stations) == 1
    assert aq_stations[0].station_id == "burp"
    assert aq_stations[0].pm2_5_rating == "Good"
    assert aq_stations[0].overall_rating == "Good"

    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("AQ error"))
    assert await prov.async_fetch_air_quality() == []

    # 8. Relief Facilities: Sandbag stations & Evacuation centres
    async def mock_relief(url: str, **kwargs):
        if "sandbagStations" in url:
            return {
                "features": [
                    {
                        "properties": {
                            "OBJECTID": 1,
                            "NAME": "Caboolture SES Sandbags",
                            "SUBURB": "Caboolture",
                            "ADDRESS": "Old Gympie Rd",
                        },
                        "geometry": {"type": "Point", "coordinates": [152.95, -27.08]},
                    }
                ]
            }
        if "moretonEvacs" in url:
            return {
                "features": [
                    {
                        "properties": {
                            "OBJECTID": 2,
                            "NAME": "Morayfield Evacuation Centre",
                            "SUBURB": "Morayfield",
                            "ADDRESS": "298 Morayfield Rd",
                        },
                        "geometry": {"type": "Point", "coordinates": [152.94, -27.11]},
                    }
                ]
            }
        return None

    prov.async_fetch_json = AsyncMock(side_effect=mock_relief)
    relief = await prov.async_fetch_relief_facilities()
    assert len(relief) == 2
    assert relief[0].facility_type == "sandbag_station"
    assert relief[1].facility_type == "evacuation_centre"

    # Relief exception handling
    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("Relief error"))
    assert await prov.async_fetch_relief_facilities() == []

    # 9. Cameras
    cameras = await prov.async_fetch_cameras()
    assert len(cameras) == 4
    assert any("Goodna" in c.name for c in cameras)

    # 10. Nearby Councils
    councils = await prov.async_fetch_nearby_councils()
    assert len(councils) == 5
    assert any("Sunshine Coast" in c["name"] for c in councils)


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


async def test_nz_hazard_provider(hass: HomeAssistant) -> None:
    """Test New Zealand hazard provider parsing GeoNet quakes, volcanoes, NEMA atom, and MetService RSS."""
    session = AsyncMock()
    prov = NZHazardProvider(hass, session, {"state": STATE_NZ})
    assert prov.state_code == STATE_NZ

    # 1. Quakes
    quakes_payload = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [174.77, -41.28]},
                "properties": {
                    "publicID": "q1",
                    "magnitude": 6.8,
                    "mmi": 7,
                    "locality": "Cook Strait",
                    "time": "2026-10-15T01:00:00Z",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [175.5, -39.2]},
                "properties": {
                    "publicID": "q2",
                    "magnitude": 5.4,
                    "mmi": 5,
                    "locality": "Taupo",
                    "time": "2026-10-15T02:00:00Z",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [172.6, -43.5]},
                "properties": {
                    "publicID": "q3",
                    "magnitude": 4.2,
                    "mmi": 4,
                    "locality": "Christchurch",
                    "time": "2026-10-15T03:00:00Z",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [170.5, -45.8]},
                "properties": {
                    "publicID": "q4",
                    "magnitude": 3.1,
                    "mmi": 2,
                    "locality": "Dunedin",
                    "time": "2026-10-15T04:00:00Z",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [174.0, -41.0]},
                "properties": {
                    "publicID": "q_deleted",
                    "quality": "deleted",
                    "magnitude": 6.0,
                    "time": "2026-10-15T01:00:00Z",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [174.0, -41.0]},
                "properties": {
                    "publicID": "q_old",
                    "time": "2020-01-01T00:00:00Z",
                    "magnitude": 7.0,
                },
            },
            {
                "geometry": {},
                "properties": {"publicID": "q5"},
            },
        ]
    }

    # 2. Volcanoes
    volcano_payload = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [177.18, -37.52]},
                "properties": {
                    "volcanoID": "whiteisland",
                    "volcanoTitle": "White Island",
                    "level": 3,
                    "acc": "Orange",
                    "activity": "Minor volcanic eruption.",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [175.56, -39.28]},
                "properties": {
                    "volcanoID": "ruapehu",
                    "volcanoTitle": "Ruapehu",
                    "level": 2,
                    "acc": "Yellow",
                    "activity": "Moderate unrest.",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [175.89, -38.78]},
                "properties": {
                    "volcanoID": "taupo",
                    "volcanoTitle": "Taupo",
                    "level": 1,
                    "acc": "Green",
                    "activity": "Minor unrest.",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [174.77, -36.98]},
                "properties": {
                    "volcanoID": "auckland",
                    "volcanoTitle": "Auckland Field",
                    "level": 0,
                    "acc": "Green",
                    "activity": "No unrest.",
                },
            },
            {
                "geometry": {},
                "properties": {"volcanoID": "invalid"},
            },
        ]
    }

    # 3. NEMA Atom
    nema_atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
      <entry>
        <id>nema_alert_1</id>
        <title>Tsunami Threat - East Coast</title>
        <updated>2026-10-15T05:00:00Z</updated>
        <cap:severity>Extreme</cap:severity>
        <cap:circle>-38.5,178.0 50.0</cap:circle>
      </entry>
      <entry>
        <id>nema_alert_polygon</id>
        <title>Severe Weather Warning - Bay of Plenty</title>
        <updated>2026-10-15T05:10:00Z</updated>
        <cap:severity>Severe</cap:severity>
        <cap:polygon>-37.0,176.0 -38.0,176.0 -38.0,177.0 -37.0,176.0</cap:polygon>
      </entry>
      <entry>
        <id>nema_alert_cancel</id>
        <title>Cancelled Warning</title>
        <cap:msgType>Cancel</cap:msgType>
        <cap:circle>-38.5,178.0 50.0</cap:circle>
      </entry>
      <entry>
        <id>nema_alert_draft</id>
        <title>Draft Warning</title>
        <cap:status>Draft</cap:status>
        <cap:circle>-38.5,178.0 50.0</cap:circle>
      </entry>
      <entry>
        <id>nema_alert_moderate</id>
        <title>Moderate Warning - Advice</title>
        <updated>2026-10-15T05:20:00Z</updated>
        <cap:severity>Moderate</cap:severity>
        <cap:circle>-39.0,175.0 10.0</cap:circle>
      </entry>
      <entry>
        <id>nema_alert_info</id>
        <title>Minor Information</title>
        <updated>2026-10-15T05:25:00Z</updated>
        <cap:severity>Minor</cap:severity>
        <cap:circle>-40.0,175.0 10.0</cap:circle>
      </entry>
      <entry>
        <id>nema_alert_bad_poly</id>
        <title>Bad Polygon Coordinates</title>
        <updated>2026-10-15T05:35:00Z</updated>
        <cap:polygon>invalid,coordinates,not_two_items</cap:polygon>
      </entry>
      <entry>
        <id>nema_alert_bad_polygon</id>
        <title>Bad Polygon Format</title>
        <cap:polygon>invalid_polygon_points</cap:polygon>
      </entry>

      <entry>
        <id>nema_alert_2</id>
        <title>Severe Flood Warning - West Coast</title>
        <updated>2026-10-15T05:30:00Z</updated>
      </entry>
      <entry>
        <id>nema_alert_bad</id>
        <title>Bad Circle Coords</title>
        <updated>2026-10-15T05:45:00Z</updated>
        <cap:circle>bad_lat,bad_lon 50.0</cap:circle>
      </entry>
    </feed>
    """

    prov.async_fetch_json = AsyncMock(side_effect=[quakes_payload, volcano_payload])
    prov.async_fetch_text = AsyncMock(return_value=nema_atom_xml)

    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 12  # 4 quakes + 4 volcanoes + 4 nema alerts

    # Confirm filtered items were skipped
    assert not any(h.id == "nz_quake_q_deleted" for h in hazards)
    assert not any(h.id == "nz_quake_q_old" for h in hazards)
    assert not any("nema_alert_cancel" in h.id for h in hazards)
    assert not any("nema_alert_draft" in h.id for h in hazards)

    quake_1 = next(h for h in hazards if h.id == "nz_quake_q1")
    assert quake_1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert quake_1.hazard_type == HazardType.EARTHQUAKE

    quake_2 = next(h for h in hazards if h.id == "nz_quake_q2")
    assert quake_2.warning_level == WarningLevel.WATCH_AND_ACT

    quake_3 = next(h for h in hazards if h.id == "nz_quake_q3")
    assert quake_3.warning_level == WarningLevel.ADVICE

    quake_4 = next(h for h in hazards if h.id == "nz_quake_q4")
    assert quake_4.warning_level == WarningLevel.INFORMATION

    volc_1 = next(h for h in hazards if h.id == "nz_volcano_whiteisland")
    assert volc_1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert volc_1.hazard_type == HazardType.VOLCANO

    volc_2 = next(h for h in hazards if h.id == "nz_volcano_ruapehu")
    assert volc_2.warning_level == WarningLevel.WATCH_AND_ACT
    assert volc_2.hazard_type == HazardType.VOLCANO

    volc_3 = next(h for h in hazards if h.id == "nz_volcano_taupo")
    assert volc_3.warning_level == WarningLevel.ADVICE
    assert volc_3.hazard_type == HazardType.VOLCANO

    volc_4 = next(h for h in hazards if h.id == "nz_volcano_auckland")
    assert volc_4.warning_level == WarningLevel.INFORMATION
    assert volc_4.hazard_type == HazardType.VOLCANO

    nema_1 = next(h for h in hazards if h.id == "nz_nema_nema_alert_1")
    assert nema_1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert nema_1.latitude == -38.5
    assert nema_1.longitude == 178.0

    nema_poly = next(h for h in hazards if h.id == "nz_nema_nema_alert_polygon")
    assert nema_poly.warning_level == WarningLevel.WATCH_AND_ACT
    assert nema_poly.latitude is not None and nema_poly.longitude is not None

    nema_mod = next(h for h in hazards if h.id == "nz_nema_nema_alert_moderate")
    assert nema_mod.warning_level == WarningLevel.ADVICE

    nema_info = next(h for h in hazards if h.id == "nz_nema_nema_alert_info")
    assert nema_info.warning_level == WarningLevel.INFORMATION

    nema_mod = next(h for h in hazards if h.id == "nz_nema_nema_alert_moderate")
    assert nema_mod.warning_level == WarningLevel.ADVICE

    nema_info = next(h for h in hazards if h.id == "nz_nema_nema_alert_info")
    assert nema_info.warning_level == WarningLevel.INFORMATION

    # Test error handling and empty parsing in NZ
    prov.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("GeoNet API down"))
    prov.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("NEMA down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_nema_atom("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_nema_atom("<invalid")

    # 4. MetService Weather Warnings
    metservice_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Heavy Rain Warning - Canterbury</title>
          <link>https://alerts.metservice.com/alert1</link>
          <description>Expect up to 120mm of rainfall.</description>
          <pubDate>Thu, 15 Oct 2026 10:00:00 +1300</pubDate>
        </item>
      </channel>
    </rss>
    """
    prov.async_fetch_text = AsyncMock(return_value=metservice_rss)
    warnings = await prov.async_fetch_weather_warnings()
    assert len(warnings) == 1
    assert warnings[0].title == "Heavy Rain Warning - Canterbury"

    prov.async_fetch_text = AsyncMock(side_effect=RuntimeError("MetService down"))
    assert await prov.async_fetch_weather_warnings() == []


async def test_wa_hazard_provider(hass: HomeAssistant) -> None:
    """Test Western Australia provider parsing Emergency WA warnings, incidents and FDR."""
    session = AsyncMock()
    prov = WAHazardProvider(hass, session, {"state": STATE_WA})
    assert prov.state_code == STATE_WA

    warnings_payload = {
        "warnings": [
            {
                "id": "w1",
                "title": "Emergency Warning - Kalgoorlie",
                "warning-type": "Emergency Warning",
                "entitySubType": "warnings_bushfire--emergency",
                "location": {"latitude": -30.7, "longitude": 121.5, "value": "Kalgoorlie"},
                "suburbs": ["PARKESTON"],
                "updatedAt": "2026-10-15T02:00:00Z",
                "action-statement": "Leave now",
            },
            {
                "id": "w2",
                "title": "Watch and Act - Albany",
                "warning-type": "Watch and Act",
                "entitySubType": "warnings_bushfire--watch-and-act",
                "location": {"latitude": -35.0, "longitude": 117.8, "value": "Albany"},
                "suburbs": ["ALBANY"],
                "updatedAt": "2026-10-15T02:30:00Z",
            },
            {
                "id": "w3",
                "title": "Bushfire Advice - Esperance",
                "warning-type": "Bushfire Advice",
                "entitySubType": "warnings_bushfire--advice",
                "location": {"latitude": -33.8, "longitude": 121.9, "value": "Esperance"},
                "updatedAt": "2026-10-15T03:00:00Z",
            },
            {
                "id": "w4",
                "title": "Flood Notification",
                "warning-type": "Notification",
                "entitySubType": "warnings_flood--info",
                "location": {},
                "geo-source": {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [115.8, -31.9]}}],
                },
                "updatedAt": "2026-10-15T03:30:00Z",
            },
            {
                "id": "w5",
                "title": "No Coords Warning",
                "location": {},
                "geo-source": {},
            },
        ]
    }

    incidents_payload = {
        "incidents": [
            {
                "id": "inc1",
                "incident-type": "Bushfire",
                "incident-status": "Going",
                "location": {"latitude": -32.0, "longitude": 116.0, "value": "Armadale"},
                "suburbs": ["ARMADALE"],
                "updatedAt": "2026-10-15T04:00:00Z",
            },
            {
                "id": "inc2",
                "incident-type": "Structure Fire",
                "incident-status": "Contained",
                "location": {},
                "geo-source": {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [115.9, -31.8]}}],
                },
                "updatedAt": "2026-10-15T04:30:00Z",
            },
            {
                "id": "inc3",
                "location": {},
                "geo-source": {},
            },
        ]
    }

    prov.async_fetch_json = AsyncMock(side_effect=[warnings_payload, incidents_payload])
    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 6  # 4 warnings + 2 incidents

    w1 = next(h for h in hazards if h.id == "wa_warn_w1")
    assert w1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert w1.latitude == -30.7

    w2 = next(h for h in hazards if h.id == "wa_warn_w2")
    assert w2.warning_level == WarningLevel.WATCH_AND_ACT

    w3 = next(h for h in hazards if h.id == "wa_warn_w3")
    assert w3.warning_level == WarningLevel.ADVICE

    w4 = next(h for h in hazards if h.id == "wa_warn_w4")
    assert w4.warning_level == WarningLevel.INFORMATION

    inc1 = next(h for h in hazards if h.id == "wa_inc_inc1")
    assert inc1.hazard_type == HazardType.BUSHFIRE
    assert inc1.warning_level == WarningLevel.INFORMATION

    # Test error handling
    prov.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("WA API down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()

    # Test Fire Danger Rating
    prov.async_fetch_json = AsyncMock(
        return_value={
            "fireDangerRatings": [
                {
                    "districtCode": "MID",
                    "districtName": "Midwest Inland",
                    "rating": "Extreme",
                    "totalFireBan": True,
                }
            ]
        }
    )
    fdr = await prov.async_fetch_fire_danger()
    assert fdr is not None
    assert fdr.rating == "Extreme"
    assert fdr.total_fire_ban is True

    # Empty FDR
    prov.async_fetch_json = AsyncMock(return_value={"fireDangerRatings": []})
    assert await prov.async_fetch_fire_danger() is None

    # Error FDR
    prov.async_fetch_json = AsyncMock(side_effect=RuntimeError("FDR error"))
    assert await prov.async_fetch_fire_danger() is None


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
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_cap_feed("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_cap_feed("<bad")


async def test_tas_hazard_provider(hass: HomeAssistant) -> None:
    """Test Tasmania provider parsing TasALERT feed."""
    session = AsyncMock()
    prov = TasmaniaHazardProvider(hass, session, {"state": STATE_TAS})
    assert prov.state_code == STATE_TAS

    xml_text = """<?xml version="1.0" encoding="utf-8"?>
    <rss xmlns:georss="http://www.georss.org/georss" version="2.0">
      <channel>
        <item>
          <title>Emergency Warning - Evacuate Bushfire at Huonville</title>
          <guid>tas_1</guid>
          <description>Bushfire out of control. Leave now.</description>
          <georss:point>-43.03 147.05</georss:point>
          <pubDate>Thu, 15 Oct 2026 11:00:00 +1100</pubDate>
        </item>
        <item>
          <title>Watch and Act - Prepare to leave Launceston</title>
          <guid>tas_2</guid>
          <description>Flood warning.</description>
          <point>-41.43 147.13</point>
          <pubDate>Thu, 15 Oct 2026 11:15:00 +1100</pubDate>
        </item>
        <item>
          <title>Advice - Smoke in area Hobart</title>
          <guid>tas_3</guid>
          <description>Controlled burn.</description>
          <pubDate>Thu, 15 Oct 2026 11:30:00 +1100</pubDate>
        </item>
        <item>
          <title>General Alert - St Helens</title>
          <guid>tas_4</guid>
          <description>Marine hazard.</description>
          <georss:point>-41.32 148.24</georss:point>
          <pubDate>Thu, 15 Oct 2026 11:45:00 +1100</pubDate>
        </item>
        <item>
          <title>Bad Coords Alert - Devonport</title>
          <guid>tas_5</guid>
          <description>Bad coords.</description>
          <georss:point>bad_lat bad_lon</georss:point>
          <pubDate>Thu, 15 Oct 2026 12:00:00 +1100</pubDate>
        </item>
      </channel>
    </rss>
    """

    prov.async_fetch_text = AsyncMock(return_value=xml_text)
    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 5

    h1 = next(h for h in hazards if h.id == "tas_alert_tas_1")
    assert h1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert h1.latitude == -43.03

    h2 = next(h for h in hazards if h.id == "tas_alert_tas_2")
    assert h2.warning_level == WarningLevel.WATCH_AND_ACT

    h3 = next(h for h in hazards if h.id == "tas_alert_tas_3")
    assert h3.warning_level == WarningLevel.ADVICE
    assert h3.latitude == -42.8821  # Default Hobart fallback

    h4 = next(h for h in hazards if h.id == "tas_alert_tas_4")
    assert h4.warning_level == WarningLevel.INFORMATION

    # Error handling & empty XML
    prov.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("TasALERT down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_tasalert_feed("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_tasalert_feed("<bad")


async def test_nt_hazard_provider(hass: HomeAssistant) -> None:
    """Test Northern Territory provider parsing NT PFES incident JSON."""
    session = AsyncMock()
    prov = NTHazardProvider(hass, session, {"state": STATE_NT})
    assert prov.state_code == STATE_NT

    payload = {
        "incidents": {
            "bushfire": [
                {
                    "geometry": {"type": "Point", "coordinates": [130.84, -12.46]},
                    "properties": {
                        "_eventtype": "Bushfire",
                        "_location": "Darwin River",
                        "Alert Level": "Emergency Warning",
                        "Status": "Going",
                        "_lastupdate": "2026-10-15T08:00:00+09:30",
                    },
                },
                {
                    "geometry": {"type": "Point", "coordinates": [131.00, -12.60]},
                    "properties": {
                        "_eventtype": "Bushfire",
                        "_location": "Weddell",
                        "Alert Level": "Watch and Act",
                        "Status": "Being Controlled",
                    },
                },
                {
                    "geometry": {"type": "Point", "coordinates": [133.88, -23.70]},
                    "properties": {
                        "_eventtype": "Hazard Reduction Burn",
                        "_location": "Alice Springs",
                        "Alert Level": "Advice",
                        "Status": "Safe",
                    },
                },
                {
                    "geometry": {"type": "Point", "coordinates": [132.26, -14.46]},
                    "properties": {
                        "_eventtype": "Structure Fire",
                        "_location": "Katherine",
                        "Alert Level": "Notification",
                    },
                },
                {
                    "geometry": {},
                    "properties": {"_eventtype": "Invalid"},
                },
            ]
        },
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [136.78, -12.18]},
                "properties": {
                    "_eventtype": "Automatic Fire Alarm",
                    "_location": "Nhulunbuy",
                    "Alert Level": "Advice",
                },
            }
        ],
    }

    prov.async_fetch_json = AsyncMock(return_value=payload)
    hazards = await prov.async_fetch_hazards()
    assert len(hazards) == 5

    h1 = hazards[0]
    assert h1.warning_level == WarningLevel.EMERGENCY_WARNING
    assert h1.latitude == -12.46

    h2 = hazards[1]
    assert h2.warning_level == WarningLevel.WATCH_AND_ACT

    h3 = hazards[2]
    assert h3.warning_level == WarningLevel.ADVICE
    assert h3.is_hazard_reduction is True

    h4 = hazards[3]
    assert h4.warning_level == WarningLevel.INFORMATION

    h5 = hazards[4]
    assert h5.location_name == "Nhulunbuy"

    # Test list format for incidents and non-dict item
    payload_list = {
        "incidents": [
            "not_a_dict",
            {
                "geometry": {"type": "Point", "coordinates": [130.84, -12.46]},
                "properties": {
                    "_eventtype": "Bushfire",
                    "_location": "Darwin",
                },
            },
        ]
    }
    prov.async_fetch_json = AsyncMock(return_value=payload_list)
    hazards_list = await prov.async_fetch_hazards()
    assert len(hazards_list) == 1

    # Test error handling
    prov.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("NT PFES down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()


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
          <title>AMBULANCE RESPONSE - BELCONNEN</title>
          <guid>act_5</guid>
          <description>Routine dispatch.</description>
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

    # Test error handling & empty XML
    prov.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("ACT ESA down"))
    with pytest.raises(ProviderUnavailableError):
        await prov.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        prov._parse_act_feed("")
    with pytest.raises(ProviderUnavailableError):
        prov._parse_act_feed("<bad")


async def test_qld_provider_no_council_url(hass: HomeAssistant) -> None:
    """Test QLD provider when no council URL is configured."""
    session = AsyncMock()
    provider = QueenslandHazardProvider(hass, session, {"state": STATE_QLD})
    assert provider._get_council_base_url() is None
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


async def test_qld_provider_payload_cache(hass: HomeAssistant) -> None:
    """Test QLD provider payload caching for composite feeds."""
    session = AsyncMock()
    base = "https://disaster.moretonbay.qld.gov.au"
    provider = QueenslandHazardProvider(hass, session, {"state": STATE_QLD, CONF_COUNCIL_DASHBOARD_URL: base})
    provider._payload_cache[f"{base}/dashboard/tmrRoadData"] = []
    provider._payload_cache[f"{base}/dashboard/bom"] = {"item": []}
    provider._payload_cache[f"{base}/dashboard/imsBulletin"] = {"features": []}
    provider.async_fetch_json = AsyncMock(return_value={})

    closures = await provider.async_fetch_road_closures()
    warnings = await provider.async_fetch_weather_warnings()
    news = await provider.async_fetch_emergency_news()
    assert closures == []
    assert warnings == []
    assert news == []


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


async def test_nt_ids_stable_across_feed_reordering(hass: HomeAssistant) -> None:
    """NT hazard IDs do not depend on list position, and distinct incidents never collide (#7)."""
    provider = NTHazardProvider(hass, AsyncMock(), {"state": "NT"})

    def feature(location: str, event: str, notified: str) -> dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [131.0, -12.5]},
            "properties": {
                "_location": location,
                "_eventtype": event,
                "_datenotified": notified,
                "_status": "active",
                "Alert Level": "Advice",
            },
        }

    a = feature("Litchfield Park Road, Darwin River Dam area", "Grass Fire", "2026-10-15T10:00:00+09:30")
    b = feature("Litchfield Park Road, Darwin River Dam north", "Grass Fire", "2026-10-15T10:00:00+09:30")
    first = provider._parse_nt_incidents({"incidents": {"type": "FeatureCollection", "features": [a, b]}})
    second = provider._parse_nt_incidents({"incidents": {"type": "FeatureCollection", "features": [b, a]}})

    assert {h.id for h in first} == {h.id for h in second}
    # Same notified time and first 20 characters of location used to collide
    assert len({h.id for h in first}) == 2

    # Features that only carry the alternate (non-underscore) keys still get distinct IDs
    alt = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [131.0, -12.5]},
            "properties": {
                "Location": loc,
                "Fire Type": "Grass Fire",
                "Notified": "15/10/2026 10:00",
                "Alert Level": "Advice",
            },
        }
        for loc in ("Humpty Doo", "Howard Springs")
    ]
    alt_ids = {
        h.id for h in provider._parse_nt_incidents({"incidents": {"type": "FeatureCollection", "features": alt}})
    }
    assert len(alt_ids) == 2

    # No notified time at all: same type and default location at different points stay distinct
    bare = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, -12.5]},
            "properties": {"_eventtype": "Grass Fire", "Alert Level": "Advice"},
        }
        for lon in (131.0, 131.4)
    ]
    bare_ids = {
        h.id for h in provider._parse_nt_incidents({"incidents": {"type": "FeatureCollection", "features": bare}})
    }
    assert len(bare_ids) == 2


async def test_wa_and_bom_id_fallbacks_are_stable(hass: HomeAssistant) -> None:
    """Items without an upstream ID get a deterministic, distinct fallback (#7)."""
    wa = WAHazardProvider(hass, AsyncMock(), {"state": "WA"})
    payload = {
        "warnings": [
            {
                "title": "Bushfire Advice - Gidgegannup",
                "updatedAt": "2026-10-15T09:00:00+08:00",
                "location": {"latitude": -31.79, "longitude": 116.2},
            },
            {
                "title": "Bushfire Advice - Chidlow",
                "updatedAt": "2026-10-15T09:00:00+08:00",
                "location": {"latitude": -31.86, "longitude": 116.27},
            },
        ]
    }
    ids_first = [h.id for h in wa._parse_warnings(payload)]
    ids_second = [h.id for h in wa._parse_warnings(payload)]
    assert ids_first == ids_second
    # An update to the warning (new updatedAt) keeps the same fallback ID
    for warning in payload["warnings"]:
        warning["updatedAt"] = "2026-10-15T11:30:00+08:00"
    assert [h.id for h in wa._parse_warnings(payload)] == ids_first
    assert len(set(ids_first)) == 2
    assert all(i != "wa_warn_" for i in ids_first)

    bom = BoMHazardProvider(hass, AsyncMock(), {"state": "QLD"})
    item = ET.fromstring("<item><title>Severe Thunderstorm Warning for Wide Bay</title></item>")
    first = bom._parse_item(item)
    second = bom._parse_item(item)
    assert first is not None and second is not None
    assert first.id == second.id == f"BOM_{stable_id('BOM', 'Severe Thunderstorm Warning for Wide Bay')}"


async def test_nt_ids_disambiguate_identical_features(hass: HomeAssistant) -> None:
    """Features sharing every identifying field still get distinct, reorder-stable IDs."""
    provider = NTHazardProvider(hass, AsyncMock(), {"state": "NT"})

    def feature(lon: float, lat: float, notified: str | None) -> dict:
        props = {"_location": "Arnhem Hwy", "_eventtype": "Grass Fire", "Alert Level": "Advice"}
        if notified:
            props["_datenotified"] = notified
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}

    def ids(features: list[dict]) -> list[str]:
        return [h.id for h in provider._parse_nt_incidents({"incidents": {"features": features}})]

    # Same notified time, type and location, different positions
    a = feature(131.0, -12.5, "2026-10-15T10:00:00+09:30")
    b = feature(131.2, -12.6, "2026-10-15T10:00:00+09:30")
    assert len(set(ids([a, b]))) == 2
    assert set(ids([a, b])) == set(ids([b, a]))

    # No notified time and coordinates equal after rounding to 3 dp
    c = feature(131.00001, -12.5, None)
    d = feature(131.00002, -12.5, None)
    assert len(set(ids([c, d]))) == 2

    # Exact duplicates fall back to an order suffix
    assert len(set(ids([a, a, a]))) == 3
