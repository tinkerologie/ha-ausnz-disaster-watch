"""Tests for the Queensland provider and the council dashboard wiring of QLD and NSW (#12, #25)."""

from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import NSWHazardProvider, QueenslandHazardProvider
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.guardian_ims import GuardianDashboard
from custom_components.ausnz_disaster_watch.providers.nsw import NSW_RFS_MAJOR_INCIDENTS_URL
from custom_components.ausnz_disaster_watch.providers.qld import QFD_WARNINGS_URL, QFD_WEB_URL, _valid_point
from homeassistant.core import HomeAssistant

BASE = "https://disaster.moretonbay.qld.gov.au"


def _qfd_feature(**overrides: Any) -> dict[str, Any]:
    """Return a feature shaped like the live bushfireAlert.json (2026-10-16)."""
    properties = {
        "OBJECTID": 28996,
        "UniqueID": "QF7-26-123875",
        "WarningTitle": "Information - COEN",
        "WarningLevel": "Information",
        "WarningArea": "COEN",
        "CurrentStatus": "Going",
        "Location": "Birthday Mountain Rd",
        "Jurisdiction": "7 Far Northern Region",
        "Latitude": -13.55258,
        "Longitude": 143.209201,
        "GroupedType": "FIRE VEGETATION",
        "Locality": "COEN",
        "ItemDateTimeLocal_ISO": "2026-09-16T03:11:21+10:00",
        "PublishDateLocal_ISO": "2026-10-16T07:43:02+10:00",
        "ItemExpiryDateTimeLocal_ISO": "2026-09-17T03:11:21+10:00",
        "EventType": "Fire",
    }
    properties.update(overrides)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [143.2, -13.5]}, "properties": properties}


def _http_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _provider(hass: HomeAssistant, routes: dict[str, Any], council: str | None = BASE) -> QueenslandHazardProvider:
    """Return a QLD provider whose fetches are answered from ``routes`` (URL suffix -> payload)."""
    config: dict[str, Any] = {"state": "QLD"}
    if council:
        config[CONF_COUNCIL_DASHBOARD_URL] = council
    provider = QueenslandHazardProvider(hass, AsyncMock(), config)

    async def fake_fetch(url: str, headers: dict[str, str] | None = None) -> Any:
        key = "qfd" if url == QFD_WARNINGS_URL else url.removeprefix(f"{BASE}/dashboard/")
        result = routes.get(key, _http_error(404))
        if isinstance(result, BaseException):
            raise result
        return result

    provider.async_fetch_json = AsyncMock(side_effect=fake_fetch)  # type: ignore[method-assign]
    return provider


def test_valid_point() -> None:
    """Property coordinates are used only when they are a real location."""
    assert _valid_point(-13.5, 143.2) == (-13.5, 143.2)
    assert _valid_point(0, 0) is None
    assert _valid_point(None, 143.2) is None
    assert _valid_point("x", 1) is None
    assert _valid_point(-100, 143.2) is None


async def test_qfd_feature_uses_live_field_names(hass: HomeAssistant) -> None:
    """Type, time, place, agency and coordinates come from the fields the feed really has (#12)."""
    provider = _provider(hass, {}, council=None)
    hazard = provider._parse_qfd_feature(_qfd_feature())
    assert hazard is not None
    assert hazard.id == "QLD_QFD_QF7-26-123875"
    assert hazard.title == "Information - COEN"
    assert hazard.hazard_type == HazardType.BUSHFIRE
    assert hazard.warning_level == WarningLevel.INFORMATION
    # Property coordinates, not the geometry
    assert (hazard.latitude, hazard.longitude) == (-13.55258, 143.209201)
    # The item's own time (Brisbane, +10:00); PublishDateLocal_ISO is the feed's generation time
    assert hazard.updated_at == datetime(2026, 9, 15, 17, 11, 21, tzinfo=UTC)
    assert hazard.location_name == "Birthday Mountain Rd, COEN"
    assert hazard.status == "Going"
    assert hazard.responsible_agency == "Queensland Fire Department"
    assert hazard.web_url == QFD_WEB_URL
    assert hazard.is_hazard_reduction is False


async def test_qfd_feature_variants(hass: HomeAssistant) -> None:
    """Permitted burns, missing areas, zero coordinates and other event types."""
    provider = _provider(hass, {}, council=None)

    burn = provider._parse_qfd_feature(_qfd_feature(GroupedType="FIRE PERMITTED BURN"))
    assert burn is not None
    assert burn.is_hazard_reduction is True

    # "Information - " with no area: the title gets the locality instead
    no_area = provider._parse_qfd_feature(
        _qfd_feature(WarningTitle="Information - ", WarningArea=None, Locality="LAURA", Location=None)
    )
    assert no_area is not None
    assert no_area.title == "Information - LAURA"
    assert no_area.location_name == "LAURA"

    # Zero property coordinates fall back to the geometry
    centroid = provider._parse_qfd_feature(_qfd_feature(Latitude=0, Longitude=0))
    assert centroid is not None
    assert (centroid.latitude, centroid.longitude) == (-13.5, 143.2)

    structure = provider._parse_qfd_feature(_qfd_feature(GroupedType=None, EventType="Structure Fire"))
    assert structure is not None
    assert structure.hazard_type == HazardType.METROPOLITAN_FIRE

    bare = provider._parse_qfd_feature(
        {"properties": {"UniqueID": "X1", "Latitude": -27.1, "Longitude": 153.0, "WarningLevel": "Advice"}}
    )
    assert bare is not None
    assert bare.title == "Queensland Fire Incident"
    assert bare.location_name == "Queensland"
    assert bare.hazard_type == HazardType.BUSHFIRE
    assert bare.updated_at is None

    assert provider._parse_qfd_feature(_qfd_feature(UniqueID=" ", OBJECTID=None)) is None
    assert provider._parse_qfd_feature({"properties": {"UniqueID": "X2"}, "geometry": None}) is None


TMR_EVENT = {
    "type": "Feature",
    "geometry": {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": [153.13, -27.07]}]},
    "properties": {
        "id": 834569,
        "status": "Published",
        "source": {"provided_by": "Department of Transport and Main Roads"},
        "event_type": "Hazard",
        "event_subtype": "Signal fault",
        "impact": {"impact_subtype": "All lanes affected"},
        "road_summary": {"road_name": "Bribie Island Road", "locality": "Sandstone Point"},
        "last_updated": "2026-10-16T05:48:20+10:00",
    },
}


async def test_hazards_from_qfd_and_council(hass: HomeAssistant) -> None:
    """The JSON-string tmrRoadData is decoded; the BoM summary is never a located hazard (#12, #25)."""
    closed_road = {
        "geometry": {"type": "Point", "coordinates": [153.0, -27.2]},
        "properties": {"id": 1, "event_type": "Flooding", "impact": {"impact_subtype": "Road closed"}},
    }
    provider = _provider(
        hass,
        {
            "qfd": {"type": "FeatureCollection", "features": [_qfd_feature(), _qfd_feature(), {"properties": None}]},
            "tmrRoadData": json.dumps(
                [
                    TMR_EVENT,
                    closed_road,
                    {**TMR_EVENT, "properties": {**TMR_EVENT["properties"], "id": 2, "status": "Reopened"}},
                    {"geometry": None, "properties": {"id": 3}},
                    {"geometry": {"type": "Point", "coordinates": [153.0, -27.2]}, "properties": {}},
                ]
            ),
            "bom": {"item": [{"title": "Marine Wind Warning Summary for Queensland", "link": "http://bom"}]},
            "imsBulletin": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [152.95, -27.25]},
                        "properties": {"id": "B1", "title": "Evacuate low-lying areas", "priority": "Emergency"},
                    },
                    {"geometry": {"type": "Point", "coordinates": [152.95, -27.25]}, "properties": {"id": "B2"}},
                    {"geometry": None, "properties": {"id": "B3", "title": "No location"}},
                ],
            },
        },
    )
    hazards = await provider.async_fetch_hazards()
    ids = [h.id for h in hazards]
    assert ids == [
        "QLD_QFD_QF7-26-123875",
        "QLD_COUNCIL_ROAD_834569",
        "QLD_COUNCIL_ROAD_1",
        "QLD_COUNCIL_BULLETIN_B1",
        "QLD_COUNCIL_BULLETIN_B2",
    ]
    assert not any("BOM" in hazard_id for hazard_id in ids)

    road = hazards[1]
    assert road.title == "Hazard: Signal fault - Bribie Island Road"
    assert road.location_name == "Sandstone Point"
    assert road.warning_level == WarningLevel.INFORMATION
    assert road.status == "All lanes affected"
    assert road.responsible_agency == "Department of Transport and Main Roads"
    assert road.web_url == "https://qldtraffic.qld.gov.au"
    closed = hazards[2]
    assert closed.title == "Flooding"
    assert closed.warning_level == WarningLevel.ADVICE
    assert closed.location_name == "Queensland"

    bulletin, plain = hazards[3], hazards[4]
    assert bulletin.warning_level == WarningLevel.EMERGENCY_WARNING
    assert bulletin.location_name == ""
    assert plain.title == "Council Disaster Bulletin"
    assert plain.warning_level == WarningLevel.ADVICE

    # The BoM summary is a weather warning without a location
    (warning,) = await provider.async_fetch_weather_warnings()
    assert warning.title == "Marine Wind Warning Summary for Queensland"


async def test_council_keeps_provider_available_when_qfd_is_down(hass: HomeAssistant) -> None:
    """QFD down: a working council endpoint keeps the provider available; none fails it (#16)."""
    working = _provider(hass, {"qfd": aiohttp.ClientError("down"), "imsBulletin": {"features": []}})
    assert await working.async_fetch_hazards() == []

    broken = _provider(hass, {"qfd": aiohttp.ClientError("down"), "tmrRoadData": "{}", "imsBulletin": {"x": 1}})
    with pytest.raises(ProviderUnavailableError):
        await broken.async_fetch_hazards()

    no_council = _provider(hass, {"qfd": aiohttp.ClientError("down")}, council=None)
    with pytest.raises(ProviderUnavailableError):
        await no_council.async_fetch_hazards()


async def test_hazard_poll_payloads_are_reused(hass: HomeAssistant) -> None:
    """Auxiliary feeds after a hazard poll reuse its payloads instead of fetching again."""
    provider = _provider(hass, {"qfd": {"features": []}, "tmrRoadData": [TMR_EVENT], "imsBulletin": {"features": []}})
    await provider.async_fetch_hazards()
    assert [c.id for c in await provider.async_fetch_road_closures()] == ["TMR_834569"]
    await provider.async_fetch_emergency_news()
    urls = [call.args[0] for call in provider.async_fetch_json.await_args_list]  # type: ignore[attr-defined]
    assert urls.count(f"{BASE}/dashboard/tmrRoadData") == 1
    assert urls.count(f"{BASE}/dashboard/imsBulletin") == 1


async def test_council_dashboard_selection(hass: HomeAssistant) -> None:
    """Dead and non-Guardian hosts are rewritten or ignored (#12, #25)."""
    gold_coast = _provider(hass, {}, council="https://disaster.goldcoast.qld.gov.au/")
    assert gold_coast.state_code == "QLD"
    assert gold_coast.dashboard is not None
    assert gold_coast.dashboard.base_url == "https://dashboard.goldcoast.qld.gov.au"
    assert _provider(hass, {}, council="https://disaster.sunshinecoast.qld.gov.au").dashboard is None


async def test_auxiliary_feeds_without_dashboard(hass: HomeAssistant) -> None:
    """Without a council dashboard every auxiliary feed is empty and nothing is fetched."""
    for provider in (
        _provider(hass, {}, council=None),
        NSWHazardProvider(hass, AsyncMock(), {"state": "NSW"}),
    ):
        provider.async_fetch_json = AsyncMock()  # type: ignore[method-assign]
        assert await provider.async_fetch_power_outages() == []
        assert await provider.async_fetch_road_closures() == []
        assert await provider.async_fetch_weather_warnings() == []
        assert await provider.async_fetch_emergency_news() == []
        assert await provider.async_fetch_fire_danger() is None
        assert await provider.async_fetch_weather_telemetry() == []
        assert await provider.async_fetch_air_quality() == []
        assert await provider.async_fetch_relief_facilities() == []
        assert await provider.async_fetch_cameras() == []
        provider.async_fetch_json.assert_not_awaited()
    # Without a council dashboard the nearby links are still offered.
    assert len(await _provider(hass, {}, council=None).async_fetch_nearby_councils()) == 6


@pytest.mark.parametrize(
    "method",
    [
        "power_outages",
        "road_closures",
        "weather_warnings",
        "emergency_news",
        "fire_danger",
        "weather_telemetry",
        "air_quality",
        "relief_facilities",
        "cameras",
    ],
)
@pytest.mark.parametrize("provider_cls", [QueenslandHazardProvider, NSWHazardProvider])
async def test_auxiliary_feeds_delegate_to_dashboard(
    hass: HomeAssistant, provider_cls: type[QueenslandHazardProvider | NSWHazardProvider], method: str
) -> None:
    """Both states read their council dashboard through the shared Guardian client (#25)."""
    provider = provider_cls(hass, AsyncMock(), {"state": "QLD", CONF_COUNCIL_DASHBOARD_URL: BASE})
    assert isinstance(provider.dashboard, GuardianDashboard)
    sentinel = object()
    setattr(provider.dashboard, method, AsyncMock(return_value=sentinel))
    fetch_name = {"weather_telemetry": "async_fetch_weather_telemetry"}.get(method, f"async_fetch_{method}")
    assert await getattr(provider, fetch_name)() is sentinel


async def test_council_links(hass: HomeAssistant) -> None:
    """Council links are the registry dashboards nearest home, without the entry's own (#12, #25, #32)."""
    provider = _provider(hass, {})
    provider.set_location(-27.10, 152.95)  # Caboolture, in the City of Moreton Bay.
    qld_links = await provider.async_fetch_nearby_councils()
    assert [link["name"] for link in qld_links] == [
        "Somerset Regional",
        "Redland City",
        "Ipswich City",
        "Logan City",
        "Noosa Shire",
        "Lockyer Valley Regional",
    ]
    assert BASE not in {link["url"] for link in qld_links}
    assert not any("disasterhub" in link["url"] or "brisbane" in link["url"] for link in qld_links)

    nsw = NSWHazardProvider(
        hass, AsyncMock(), {"latitude": -28.64, "longitude": 153.61}
    )  # Byron Bay, no dashboard set.
    nsw_links = await nsw.async_fetch_nearby_councils()
    assert nsw_links[:2] == [
        {"name": "Byron Shire", "url": "https://emergency.byron.nsw.gov.au"},
        {"name": "Ballina Shire", "url": "https://emergency.ballina.nsw.gov.au"},
    ]
    assert not any("tweed" in link["url"] or "disasterdashboards" in link["url"] for link in nsw_links)

    # Without a monitored point the links are listed by name.
    unlocated = await NSWHazardProvider(hass, AsyncMock(), {}).async_fetch_nearby_councils()
    assert [link["name"] for link in unlocated] == sorted(link["name"] for link in unlocated)


async def test_nsw_hazard_poll_starts_dashboard_poll(hass: HomeAssistant, feed_routes: Any) -> None:
    """The NSW hazard poll resets the dashboard's per-poll cache."""
    session = feed_routes({NSW_RFS_MAJOR_INCIDENTS_URL: {"type": "FeatureCollection", "features": []}})
    provider = NSWHazardProvider(hass, session, {"state": "NSW", CONF_COUNCIL_DASHBOARD_URL: BASE})
    assert provider.dashboard is not None
    provider.dashboard._poll_cache["bom"] = {"item": []}
    assert await provider.async_fetch_hazards() == []
    assert provider.dashboard._poll_cache == {}
