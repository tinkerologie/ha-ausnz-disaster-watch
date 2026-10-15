"""Tests for the Guardian IMS council dashboard client (#12, #25).

Payloads are trimmed copies of the shapes the live dashboards returned on 2026-10-16
(Moreton Bay, Townsville, Gold Coast, Noosa, Redland, Fraser Coast, Burdekin).
"""

from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.providers import QueenslandHazardProvider
from custom_components.ausnz_disaster_watch.providers.guardian_ims import (
    GuardianDashboard,
    _bounded,
    _float,
    _lat_lon,
    _text,
    ms_date,
    normalise_dashboard_url,
)
from homeassistant.core import HomeAssistant

BASE = "https://disaster.example.qld.gov.au"


def _http_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _dashboard(hass: HomeAssistant, routes: dict[str, Any]) -> tuple[GuardianDashboard, AsyncMock]:
    """Return a dashboard whose fetches are answered from ``routes`` (endpoint -> payload or exception).

    Endpoints not in ``routes`` answer 404, like a dashboard without that endpoint.
    """
    provider = QueenslandHazardProvider(hass, AsyncMock(), {"state": "QLD"})

    async def fake_fetch(url: str, headers: dict[str, str] | None = None) -> Any:
        endpoint = url.removeprefix(f"{BASE}/dashboard/")
        result = routes.get(endpoint, _http_error(404))
        if isinstance(result, BaseException):
            raise result
        return result

    mock = AsyncMock(side_effect=fake_fetch)
    provider.async_fetch_json = mock  # type: ignore[method-assign]
    return GuardianDashboard(provider, BASE), mock


def _widgets(*details: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"widgets": [{"id": i, "details": json.dumps(d)} for i, d in enumerate(details)]}]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (42, None),
        ("https://", None),
        ("https://disaster.moretonbay.qld.gov.au/", "https://disaster.moretonbay.qld.gov.au"),
        ("disaster.noosa.qld.gov.au", "https://disaster.noosa.qld.gov.au"),
        ("http://disaster.somerset.qld.gov.au", "https://disaster.somerset.qld.gov.au"),
        ("https://disaster.goldcoast.qld.gov.au", "https://dashboard.goldcoast.qld.gov.au"),
        ("https://dashboard.cityofgoldcoast.com.au/", "https://dashboard.goldcoast.qld.gov.au"),
        ("https://DISASTER.REDLAND.QLD.GOV.AU", "https://dashboard.redland.qld.gov.au"),
        ("https://disaster.sunshinecoast.qld.gov.au", None),
        ("https://emergency.tweed.nsw.gov.au", None),
    ],
)
def test_normalise_dashboard_url(url: Any, expected: str | None) -> None:
    """Moved hosts are rewritten, non-Guardian hosts dropped, and URLs use https."""
    assert normalise_dashboard_url(url) == expected


def test_value_helpers() -> None:
    """Scalar helpers tolerate the feeds' strings, blanks and swapped coordinates."""
    assert _text(None) == ""
    assert _text(" Ferry Road &amp; Queen Street ") == "Ferry Road & Queen Street"
    assert _float(None) is None
    assert _float("") is None
    assert _float("n/a") is None
    assert _float("12.5") == 12.5
    assert _bounded("150", 0, 100) is None
    assert _bounded("75", 0, 100) == 75.0
    assert _bounded(None, 0, 100) is None
    # Ergon publishes longitude in "Lat" and latitude in "Long"
    assert _lat_lon("146.728934", "-19.287881") == (-19.287881, 146.728934)
    assert _lat_lon("-19.28", "146.72") == (-19.28, 146.72)
    assert _lat_lon(None, "146.7") == (None, None)
    assert _lat_lon("200", "300") == (None, None)
    assert _lat_lon(0, 0) == (None, None)
    assert ms_date("/Date(1792107000000)/") == datetime.fromtimestamp(1792107000, tz=UTC)
    assert ms_date(1780018020000) == datetime.fromtimestamp(1780018020, tz=UTC)
    assert ms_date("tomorrow") is None
    assert ms_date(True) is None
    assert ms_date(0) is None


async def test_fetch_decodes_caches_and_remembers_missing_endpoints(hass: HomeAssistant) -> None:
    """Double-encoded bodies are decoded; 404/403 are remembered, other failures retried."""
    dashboard, mock = _dashboard(
        hass,
        {
            "imsRoad": json.dumps({"type": "FeatureCollection", "features": []}),
            "dashOutages": "not json {",
            "bom": _http_error(500),
            "fireDangerRating": aiohttp.ClientError("reset"),
            "getCameras": _http_error(403),
        },
    )
    assert await dashboard.fetch("imsRoad") == {"type": "FeatureCollection", "features": []}
    assert await dashboard.fetch("imsRoad") == {"type": "FeatureCollection", "features": []}
    assert mock.await_count == 1  # reused within the poll

    assert await dashboard.fetch("energexOutages") is None  # 404
    assert await dashboard.fetch("getCameras") is None  # 403
    assert await dashboard.fetch("dashOutages") is None  # undecodable body
    assert await dashboard.fetch("bom") is None  # 500 after retries
    assert await dashboard.fetch("fireDangerRating") is None  # network error

    dashboard.start_poll()
    mock.reset_mock()
    for endpoint in ("imsRoad", "energexOutages", "getCameras", "dashOutages", "bom", "fireDangerRating"):
        await dashboard.fetch(endpoint)
    fetched = {call.args[0].removeprefix(f"{BASE}/dashboard/") for call in mock.await_args_list}
    # Missing endpoints are not asked again; everything else is retried in the next poll
    assert fetched == {"imsRoad", "dashOutages", "bom", "fireDangerRating"}


async def test_power_outages_ergon_and_energex(hass: HomeAssistant) -> None:
    """Ergon coordinates are un-swapped; Energex restore times are decoded."""
    dashboard, _ = _dashboard(
        hass,
        {
            "ergonOutages": [
                {
                    "Customers": "41",
                    "End": "16/10/2026 10:00",
                    "Suburbs": ["HYDE PARK", "PIMLICO"],
                    "Lat": "146.797705",
                    "Long": "-19.280084",
                    "Reason": "The loss of supply is to allow maintenance of the electricity network",
                },
                {"Customers": "2", "End": "Unknown ", "Suburbs": "MONA PARK", "Lat": None, "Long": None},
                "garbage",
            ],
            "energexOutages": [
                {
                    "Outage": {
                        "cause": "Under Investigation",
                        "suburb": "KURWONGBAH",
                        "customersAffected": "124",
                        "restoreTime": "/Date(1792107000000)/",
                    }
                },
                {"suburb": "PETRIE", "customersAffected": None, "restoreTime": None, "cause": None},
            ],
        },
    )
    outages = await dashboard.power_outages()
    assert len(outages) == 4
    hyde, mona, kurwongbah, petrie = outages
    assert hyde.suburb == "HYDE PARK, PIMLICO"
    assert (hyde.latitude, hyde.longitude) == (-19.280084, 146.797705)
    assert hyde.customers_affected == 41
    assert hyde.restore_time == "16/10/2026 10:00"
    assert mona.suburb == "MONA PARK"
    assert mona.restore_time is None
    assert mona.latitude is None
    assert mona.cause == "Under Investigation"
    assert kurwongbah.customers_affected == 124
    assert kurwongbah.restore_time == datetime.fromtimestamp(1792107000, tz=UTC).isoformat()
    assert petrie.customers_affected == 0
    assert petrie.restore_time is None


async def test_power_outages_missing_endpoints(hass: HomeAssistant) -> None:
    """A dashboard with neither outage endpoint returns no outages."""
    dashboard, _ = _dashboard(hass, {})
    assert await dashboard.power_outages() == []


IMS_ROAD = {
    "type": "Feature",
    "geometry": {
        "type": "GeometryCollection",
        "geometries": [{"type": "Point", "coordinates": ["152.933087", "-26.442298"]}],
    },
    "properties": {
        "id": 44100,
        "source": {"provided_by": "Noosa Shire Council"},
        "event_type": "Hazard",
        "event_subtype": "Road damage",
        "event_due_to": "Boggy conditions",
        "impact": {"impact_subtype": "Lane or lanes reduced"},
        "description": "Single lane of traffic with temporary traffic lights due to landslip",
        "advice": "Changed traffic conditions",
        "last_updated": "2026-07-10T15:36:53.1812291+10:00",
        "suburb": "Cooroy",
        "road": "Nandroya Rd",
    },
}

TMR_EVENT = {
    "type": "Feature",
    "geometry": {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": [153.13, -27.07]}]},
    "properties": {
        "id": 834569,
        "status": "Published",
        "source": {"provided_by": "Department of Transport and Main Roads"},
        "event_type": "Hazard",
        "event_subtype": "Signal fault",
        "event_due_to": "",
        "impact": {"impact_subtype": "All lanes affected"},
        "description": "Intersection with Spinnaker Drive",
        "advice": "Proceed with caution",
        "road_summary": {"road_name": "Bribie Island Road", "locality": "Sandstone Point"},
        "last_updated": "2026-10-16T05:48:20.541062+10:00",
    },
}


async def test_road_closures(hass: HomeAssistant) -> None:
    """Council roads (imsRoad, Moreton Bay) and QLDTraffic events become road closures."""
    dashboard, _ = _dashboard(
        hass,
        {
            "imsRoad": json.dumps({"type": "FeatureCollection", "features": [IMS_ROAD, IMS_ROAD, {"properties": {}}]}),
            "moretonRoadClosures": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": 124,
                        "geometry": {"type": "Point", "coordinates": [152.948, -27.354]},
                        "properties": {
                            "OBJECTID": 124,
                            "ID": "LPR_001",
                            "STATUS": "Closed",
                            "REASON": "Flooded",
                            "ROAD": "Dugandan Road",
                            "SUBURB": "BUNYA",
                            "UPDATETIME": 1780018020000,
                        },
                    },
                    {"type": "Feature", "geometry": None, "properties": {"STATUS": None}},
                ],
            },
            "tmrRoadData": json.dumps([TMR_EVENT, {**TMR_EVENT, "geometry": None}]),
        },
    )
    closures = await dashboard.road_closures()
    assert [c.id for c in closures] == ["COUNCIL_44100", "COUNCIL_LPR_001", "TMR_834569"]
    council, moreton, tmr = closures
    assert council.road == "Nandroya Rd"
    assert council.suburb == "Cooroy"
    assert council.status == "Lane or lanes reduced"
    assert council.reason == "Boggy conditions"
    assert council.source == "Noosa Shire Council"
    assert (council.latitude, council.longitude) == (-26.442298, 152.933087)
    assert council.updated_at == datetime(2026, 7, 10, 5, 36, 53, 181229, tzinfo=UTC)
    assert moreton.status == "Closed"
    assert moreton.updated_at == datetime.fromtimestamp(1780018020, tz=UTC)
    assert tmr.road == "Bribie Island Road"
    assert tmr.suburb == "Sandstone Point"
    assert tmr.reason == "Signal fault"
    assert tmr.advice == "Proceed with caution"


async def test_road_event_without_location(hass: HomeAssistant) -> None:
    """A road event without geometry is kept without coordinates."""
    dashboard, _ = _dashboard(hass, {"tmrRoadData": [{**TMR_EVENT, "geometry": None}]})
    (closure,) = await dashboard.road_closures()
    assert closure.latitude is None
    assert closure.longitude is None


async def test_relief_facilities(hass: HomeAssistant) -> None:
    """imsEvac building types map to facility kinds and keep the upstream status."""

    def evac(fid: Any, building_type: str, status: str | None) -> dict[str, Any]:
        return {
            "id": fid,
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [153.40, -27.49]},
            "properties": {
                "organisation": "Redland City Council",
                "buildingname": f"{building_type} site",
                "buildingtype": building_type,
                "buildingaddress": "11-37 Mitchell Cres, Dunwich QLD 4183",
                "status": status,
            },
        }

    dashboard, _ = _dashboard(
        hass,
        {
            "imsEvac": {
                "type": "FeatureCollection",
                "features": [
                    evac(990, "Sandbag Station", "Operational"),
                    evac(991, "Place of Refuge", None),
                    evac(None, "Evacuation Centre", "Open"),
                    {"id": 5, "properties": None},
                ],
            },
            "sandbagStations": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [152.9, -27.2]},
                        "properties": {"OBJECTID": 7, "NAME": "Caboolture Depot", "SUBURB": "Caboolture"},
                    }
                ],
            },
            "moretonEvacs": {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": None, "properties": {"NAME": "Hall", "STATUS": "Closed"}}],
            },
        },
    )
    facilities = await dashboard.relief_facilities()
    kinds = [(f.facility_type, f.status) for f in facilities]
    assert kinds == [
        ("sandbag_station", "Operational"),
        ("place_of_refuge", "Unknown"),
        ("evacuation_centre", "Open"),
        ("sandbag_station", "Open"),
        ("evacuation_centre", "Closed"),
    ]
    assert facilities[0].id == "ims_990"
    assert facilities[0].address == "11-37 Mitchell Cres, Dunwich QLD 4183"
    assert facilities[0].latitude == -27.49
    assert facilities[2].id.startswith("ims_")
    assert facilities[3].id == "sandbag_7"
    assert facilities[4].id.startswith("evac_qld_relief_")
    assert facilities[4].latitude is None


async def test_weather_telemetry_from_widget_stations(hass: HomeAssistant) -> None:
    """Observation stations come from the dashboard's own weather widget."""
    widgets = _widgets(
        {"type": 6, "values": "4", "stationIds": "Beerburrum, Redcliffe"},
        {"type": 6, "values": "4", "stationIds": "Redcliffe,Mount Glorious"},
        {"type": 6, "values": "5", "stationIds": "burp,pcer"},
        {"type": 1, "values": "4", "stationIds": "ignored"},
    )
    widgets[0]["widgets"].append({"details": "{broken"})
    widgets[0]["widgets"].append({"details": "[1, 2]"})
    widgets.append("not a template")  # type: ignore[arg-type]
    widgets.append({"widgets": None})
    obs = {
        "msstnname": "BEERBURRUM FOREST STATION",
        "msbomid": "40284",
        "msairtemp": "15.1",
        "msapptemp": "16.7",
        "msrelhum": "98",
        "msmslpres": "",
        "mswinddirdeg": "0",
        "mswindspdkmh": "0",
        "msgustkmh": "6",
        "msrain": "7.4",
    }
    dashboard, mock = _dashboard(
        hass,
        {
            "getTemplateWidgets": widgets,
            "getSurfaceObservation?ObsId=Beerburrum,Redcliffe,Mount%20Glorious": [obs, {"msstnname": ""}],
            "getWeatherStationsData": [
                {
                    "id": "62e1d51780a94fcaa972255d",
                    "name": "Burpengary",
                    "weatherData": [
                        {"name": "TenMin - AirTC", "currentValue": 15.4},
                        {"name": "TenMin - RH", "currentValue": 94.7},
                        {"name": "Hourly - ws-kph-Max", "currentValue": "x"},
                        "junk",
                    ],
                }
            ],
        },
    )
    stations = await dashboard.weather_telemetry()
    assert [s.station_name for s in stations] == ["Beerburrum Forest Station", "Burpengary"]
    beerburrum, burpengary = stations
    assert beerburrum.station_id == "40284"
    assert beerburrum.temperature == 15.1
    assert beerburrum.apparent_temperature == 16.7
    assert beerburrum.relative_humidity == 98.0
    assert beerburrum.pressure_hpa is None
    assert beerburrum.wind_speed_max == 6.0
    assert beerburrum.rain_since_9am == 7.4
    assert burpengary.temperature == 15.4
    assert burpengary.wind_speed_max is None

    # Widgets are read once per session
    mock.reset_mock()
    dashboard.start_poll()
    await dashboard.weather_telemetry()
    assert not any("getTemplateWidgets" in call.args[0] for call in mock.await_args_list)


async def test_weather_telemetry_currtemp_fallback(hass: HomeAssistant) -> None:
    """Without station data the dashboard's current temperature is used."""
    dashboard, _ = _dashboard(
        hass, {"getTemplateWidgets": "not widgets", "Currtemp": {"apparent_t": 25.6, "air_temp": 25.4}}
    )
    (station,) = await dashboard.weather_telemetry()
    assert station.station_id == "currtemp"
    assert station.temperature == 25.4
    assert station.apparent_temperature == 25.6

    empty, _ = _dashboard(hass, {"Currtemp": {"air_temp": None}})
    assert await empty.weather_telemetry() == []


async def test_air_quality_uses_widget_station_ids(hass: HomeAssistant) -> None:
    """Air quality is requested only for the stations the dashboard lists."""
    dashboard, _ = _dashboard(
        hass,
        {
            "getTemplateWidgets": _widgets({"type": 6, "values": "5", "stationIds": "dcb,kipp"}),
            "airQuality?stationIds=dcb,kipp": {
                "AirQualityStationDataList": [
                    {
                        "station_name": "Deception Bay",
                        "station_id": "dcb",
                        "PM2_5_Measurement": "2.8 µg/m³",
                        "PM2_5_Rating": "Good",
                        "NO2_Measurement": "",
                    },
                    {"station_id": "kipp", "PM10_Rating": "Fair"},
                    None,
                ]
            },
        },
    )
    stations = await dashboard.air_quality()
    assert [(s.station_id, s.overall_rating) for s in stations] == [("dcb", "Good"), ("kipp", "Fair")]
    assert stations[0].no2_measurement is None
    assert stations[1].station_name == "Air Station"

    no_widget, mock = _dashboard(hass, {"getTemplateWidgets": _widgets({"type": 6, "values": "4", "stationIds": ""})})
    assert await no_widget.air_quality() == []
    assert not any("airQuality" in call.args[0] for call in mock.await_args_list)

    bad_payload, _ = _dashboard(
        hass,
        {"getTemplateWidgets": _widgets({"type": 6, "values": "5", "stationIds": "x"}), "airQuality?stationIds=x": []},
    )
    assert await bad_payload.air_quality() == []


async def test_fire_danger_day_and_unknown_fire_ban(hass: HomeAssistant) -> None:
    """The forecast day is kept and a missing TOBAN field means "unknown", not "no ban"."""
    payload = {
        "Published": "2026-10-15T21:25:44.607634479Z",
        "Data": [
            {
                "District_Number": "QLD_5",
                "District_Name": "Herbert and Lower Burdekin",
                "Day": "Friday",
                "FDR": "Moderate",
            }
        ],
    }
    dashboard, _ = _dashboard(hass, {"fireDangerRating": payload})
    rating = await dashboard.fire_danger()
    assert rating is not None
    assert rating.day == "Friday"
    assert rating.district_name == "Herbert and Lower Burdekin"
    assert rating.total_fire_ban is None

    payload["Data"][0]["TOBAN"] = "Yes"
    with_ban, _ = _dashboard(hass, {"fireDangerRating": payload})
    rating = await with_ban.fire_danger()
    assert rating is not None
    assert rating.total_fire_ban is True

    for bad in ({"Data": []}, {"Data": ["x"]}, []):
        broken, _ = _dashboard(hass, {"fireDangerRating": bad})
        assert await broken.fire_danger() is None


async def test_weather_warnings_and_news(hass: HomeAssistant) -> None:
    """The BoM summary becomes warnings; bulletins become news with stable IDs."""
    dashboard, _ = _dashboard(
        hass,
        {
            "bom": {
                "pubDate": "Thu, 15 Oct 2026 21:41:00 GMT",
                "item": [
                    {
                        "title": "Marine Wind Warning Summary for Queensland",
                        "link": "http://www.bom.gov.au/qld/warnings/marinewind.shtml",
                        "locations": None,
                        "pubDate": "Thu, 15 Oct 2026 19:24:14 GMT",
                    },
                    {"title": " "},
                    "junk",
                ],
            },
            "imsBulletin": {
                "type": "FeatureCollection",
                "features": [
                    {"properties": {"id": 7, "title": "Sandbags available", "created": "2026-10-15T10:00:00+10:00"}},
                    {"properties": {"headline": "Road update", "content": "Detour", "updated": "2026-10-15"}},
                    {"properties": None},
                ],
            },
        },
    )
    (warning,) = await dashboard.weather_warnings()
    assert warning.title == "Marine Wind Warning Summary for Queensland"
    assert warning.locations is None
    assert warning.pub_date == datetime(2026, 10, 15, 19, 24, 14, tzinfo=UTC)

    news = await dashboard.emergency_news()
    assert [n.title for n in news] == ["Sandbags available", "Road update"]
    assert news[0].id == "7"
    assert news[1].id.startswith("bulletin_")
    assert news[1].description == "Detour"

    missing, _ = _dashboard(hass, {})
    assert await missing.weather_warnings() == []
    assert await missing.emergency_news() == []


async def test_cameras(hass: HomeAssistant) -> None:
    """Cameras come from getCameras with stable IDs and the first snapshot URL."""

    def camera(cid: Any, image_url: Any, **extra: Any) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [153.001488, -27.097121]},
            "properties": {"id": cid, "image_url": image_url, "typeName": "Flood Cameras", **extra},
        }

    dashboard, _ = _dashboard(
        hass,
        {
            "getCameras": {
                "type": "FeatureCollection",
                "features": [
                    camera(309, "https://camera.example/a.jpg", description="Beachmere &amp; Goong Creek"),
                    camera(745, "https://cameras.qldtraffic.qld.gov.au/x.jpg,https://other/y.jpg", locality="Garbutt"),
                    camera(1, None),
                    camera(None, "https://camera.example/b.jpg"),
                    {"properties": None},
                ],
            }
        },
    )
    cameras = await dashboard.cameras()
    assert [c.name for c in cameras] == ["Beachmere & Goong Creek", "Flood Cameras"]
    first, second = cameras
    assert first.image_url == "https://camera.example/a.jpg"
    assert (first.latitude, first.longitude) == (-27.097121, 153.001488)
    assert second.image_url == "https://cameras.qldtraffic.qld.gov.au/x.jpg"
    assert second.suburb == "Garbutt"
    # IDs are deterministic and do not depend on list position (#7)
    again, _ = _dashboard(hass, {"getCameras": {"features": [camera(745, "https://cameras.example/x.jpg")]}})
    assert (await again.cameras())[0].id == second.id
