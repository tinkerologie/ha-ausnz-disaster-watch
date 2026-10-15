"""Unit tests for Queensland, NSW, Victoria, and BoM hazard providers."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.aus_emergency_hazards.const import CONF_COUNCIL_DASHBOARD_URL, STATE_NSW, STATE_QLD, STATE_VIC
from custom_components.aus_emergency_hazards.models import HazardType, WarningLevel
from custom_components.aus_emergency_hazards.providers.base import BaseHazardProvider
from custom_components.aus_emergency_hazards.providers.bom import BoMHazardProvider
from custom_components.aus_emergency_hazards.providers.nsw import NSWHazardProvider
from custom_components.aus_emergency_hazards.providers.qld import QueenslandHazardProvider
from custom_components.aus_emergency_hazards.providers.vic import VictoriaHazardProvider
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
