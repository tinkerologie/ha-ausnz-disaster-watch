"""NZ feeds added in #24 and #35: GeoNet via the aio_geojson libraries, GeoNet quake CAP alerts, NZTA road events."""

from datetime import UTC, datetime, timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import geojson
import pytest

from custom_components.ausnz_disaster_watch.const import LAST_GOOD_MAX_AGE, STATE_NZ
from custom_components.ausnz_disaster_watch.models import WarningLevel
from custom_components.ausnz_disaster_watch.providers.base import BaseHazardProvider, ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.cap import parse_cap
from custom_components.ausnz_disaster_watch.providers.geonet import (
    GEONET_CAP_FEED_URL,
    GEONET_QUAKE_URL,
    GEONET_VOLCANO_URL,
    GeoNetQuakeEntry,
    GeoNetVolcanoEntry,
)
from custom_components.ausnz_disaster_watch.providers.nz import NZHazardProvider
from custom_components.ausnz_disaster_watch.providers.nzta import (
    NZTA_SOURCE,
    events_url,
    is_disruption,
    road_closure_item,
    road_events,
    wkt_points,
)
from homeassistant.core import HomeAssistant


def feature_collection(*features: dict[str, Any]) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": list(features)}


def point_feature(lat: float, lon: float, **properties: Any) -> dict[str, Any]:
    """Return a GeoJSON Point feature."""
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": properties}


NOW = datetime(2026, 10, 15, 20, 0, tzinfo=UTC)
HOME = {"latitude": -43.30, "longitude": 171.75}  # Porters Pass, Canterbury
QUAKE_TIME = "2026-10-15T19:30:00.123Z"

# Live trafficnz.info events (2026-10-16), trimmed to the fields the provider reads
ROAD_CLOSED = {
    "alternativeRoute": "Detour via State Highway 3 (SH3) through Otorohanga. ",
    "eventComments": "Symes Bridge on State Highway 39 (SH39) will be closed for up to two months.",
    "eventDescription": "Bridge Repairs",
    "eventModified": "2026-10-11T21:00:39.293+13:00",
    "eventType": "Road Work",
    "geometry": "POINT (175.17701427436 -38.071866293722124)",
    "id": 561819,
    "impact": "Road Closed",
    "journey": {"id": 37, "name": "SH39"},
    "locationArea": "SH 39 Symes Bridge, between Otorohanga and Pirongia",
    "planned": True,
    "region": {"id": 3, "name": "Waikato"},
    "startDate": "2026-10-11T21:00:00+13:00",
    "status": "Active",
}
UNPLANNED_WARNING = {
    "alternativeRoute": "Not Applicable",
    "eventComments": "Due to winter driving conditions, road users are advised to take extra care.",
    "eventDescription": "Other",
    "eventModified": "2026-10-16T09:21:48.263+13:00",
    "eventType": "Area Warning",
    "geometry": "MULTILINESTRING ((171.71788 -43.20853, 171.71840 -43.21180), (171.75 -43.30, 171.92994 -43.33792))",
    "id": 564577,
    "impact": "Caution",
    "journey": {"id": 88, "name": "SH73"},
    "locationArea": "SH 73 Castle Hill to Springfield (Porters Pass)",
    "planned": False,
    "status": "Active",
}
SLIP = {
    "alternativeRoute": "Not Applicable.",
    "eventDescription": "Slip",
    "eventModified": "2026-10-15T13:14:59.427+13:00",
    "eventType": "Road Hazard",
    "geometry": "POINT (171.33988836680496 -42.103027244924576)",
    "id": 564416,
    "impact": "Caution",
    "locationArea": "SH 6 Punakaiki, north of Porarari River Bridge",
    "planned": False,
    "status": "Active",
}
PLANNED_ROADWORK = {
    "eventType": "Road Work",
    "impact": "Caution",
    "planned": True,
    "status": "Active",
    "geometry": "POINT (171.75 -43.30)",
    "id": 1,
}
RESOLVED_CRASH = {**SLIP, "id": 2, "eventDescription": "Crash", "status": "Resolved"}
SCHEDULED_CLOSURE = {**ROAD_CLOSED, "id": 3, "status": "Scheduled"}


def geonet_cap(public_id: str, identifier: str, *, expires: str = "2026-10-17T19:30:00+00:00") -> str:
    """GeoNet quake CAP document (Google Public Alerts profile), as documented at api.geonet.org.nz."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?><alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">'
        f"<identifier>{identifier}</identifier><sender>https://geonet.org.nz</sender>"
        "<sent>2026-10-15T19:31:00+00:00</sent><status>Actual</status><msgType>Alert</msgType>"
        "<scope>Public</scope><info><event>Earthquake</event><urgency>Past</urgency>"
        f"<severity>Moderate</severity><expires>{expires}</expires>"
        "<headline>Quake 25 km south-west of Arthur's Pass, intensity severe</headline>"
        "<description>A magnitude 6.0 earthquake occurred.</description>"
        f"<parameter><valueName>PublicID</valueName><value>{public_id}</value></parameter>"
        "<parameter><valueName>Intensity</valueName><value>severe</value></parameter>"
        "<area><areaDesc>25 km south-west of Arthur's Pass</areaDesc><circle>-43.06,171.25 71.3</circle></area>"
        "</info></alert>"
    )


def cap_feed(*links: str) -> str:
    """GeoNet quake CAP Atom feed whose entries link to CAP documents."""
    entries = "".join(
        f'<entry><id>{href}</id><title>Quake</title><link rel="alternate" type="application/cap+xml" href="{href}"/>'
        f'<link rel="related" type="text/html" href="https://www.geonet.org.nz/"/></entry>'
        for href in links
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
        f"<id>{GEONET_CAP_FEED_URL}</id><title>CAP quakes</title>{entries}"
        '<entry><id>no-cap</id><link rel="alternate" type="text/html" href="https://x"/></entry></feed>'
    )


def quake(public_id: str, mmi: int, *, time: str = QUAKE_TIME, lat: float = -43.06) -> dict[str, Any]:
    """GeoNet quake feature."""
    return point_feature(
        lat, 171.25, publicID=public_id, time=time, depth=5.1, magnitude=6.0, mmi=mmi, locality="Arthur's Pass"
    )


def provider_with(
    hass: HomeAssistant, feed_routes: Any, texts: dict[str, str], geojson_routes: dict[str, Any] | None = None
) -> NZHazardProvider:
    """NZ provider: GeoNet GeoJSON via the fake library session, text feeds via ``texts``."""
    routes = {
        GEONET_QUAKE_URL: feature_collection(),
        GEONET_VOLCANO_URL: feature_collection(),
        **(geojson_routes or {}),
    }
    provider = NZHazardProvider(hass, feed_routes(routes), {"state": STATE_NZ, **HOME})

    async def fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
        if url not in texts:
            raise aiohttp.ClientError(f"no route for {url}")
        return texts[url]

    provider.async_fetch_text = AsyncMock(side_effect=fetch_text)
    return provider


@pytest.fixture(autouse=True)
def fixed_now():
    """Freeze the provider's clocks."""
    with (
        patch("custom_components.ausnz_disaster_watch.providers.nz.dt_util.utcnow", return_value=NOW),
        patch("custom_components.ausnz_disaster_watch.providers.nz.datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = NOW
        yield


async def test_geonet_cap_alert_enriches_matching_quake(hass: HomeAssistant, feed_routes: Any) -> None:
    """A quake GeoNet issued a CAP alert for is measured to the felt area and carries the alert."""
    texts = {
        GEONET_CAP_FEED_URL: cap_feed("https://cap/a", "https://cap/expired"),
        "https://cap/a": geonet_cap("2026p100", "2.49.0.0.554.1.2026p100.1"),
        "https://cap/expired": geonet_cap("2026p300", "x", expires="2026-10-15T10:00:00+00:00"),
    }
    quakes = feature_collection(quake("2026p100", 5), quake("2026p200", 6), quake("2026p300", 5))
    provider = provider_with(hass, feed_routes, texts, {GEONET_QUAKE_URL: quakes})
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}

    alerted = hazards["nz_quake_2026p100"]
    assert alerted.distance_km == 0.0  # home is inside the CAP circle, ~30 km from the epicentre
    assert alerted.status == "Alert"
    assert alerted.warning_level is WarningLevel.WATCH_AND_ACT  # level still follows MMI (#11)
    assert alerted.raw_properties["cap_identifier"] == "2.49.0.0.554.1.2026p100.1"
    assert alerted.raw_properties["intensity"] == "severe"
    assert alerted.raw_properties["headline"].startswith("Quake 25 km")
    assert alerted.responsible_agency == "GeoNet (Earth Sciences New Zealand)"
    assert alerted.updated_at == datetime(2026, 10, 15, 19, 30, 0, 123000, tzinfo=UTC)
    # No CAP alert (or an expired one): distance is left to the coordinator
    assert hazards["nz_quake_2026p200"].distance_km is None
    assert hazards["nz_quake_2026p200"].status == "Active"
    assert hazards["nz_quake_2026p300"].distance_km is None

    # CAP documents are cached by link
    await provider.async_fetch_hazards()
    assert [c.args[0] for c in provider.async_fetch_text.await_args_list].count("https://cap/a") == 1


async def test_geonet_cap_outage_keeps_last_good_alerts(hass: HomeAssistant, feed_routes: Any) -> None:
    """A CAP feed failure never fails quakes; the last good alerts bridge a short outage."""
    texts = {GEONET_CAP_FEED_URL: cap_feed("https://cap/a"), "https://cap/a": geonet_cap("2026p100", "id-1")}
    provider = provider_with(hass, feed_routes, texts)
    assert set(await provider._async_geonet_cap_alerts()) == {"2026p100"}

    for body in ("<feed", "<html/>"):  # invalid XML, not an Atom feed
        texts[GEONET_CAP_FEED_URL] = body
        assert set(await provider._async_geonet_cap_alerts()) == {"2026p100"}
    del texts[GEONET_CAP_FEED_URL]
    assert set(await provider._async_geonet_cap_alerts()) == {"2026p100"}

    later = "custom_components.ausnz_disaster_watch.providers.nz.dt_util.utcnow"
    with patch(later, return_value=NOW + LAST_GOOD_MAX_AGE + timedelta(seconds=1)):
        assert await provider._async_geonet_cap_alerts() == {}
    # Expired alerts are not reused either
    with patch(later, return_value=NOW + timedelta(days=3)):
        provider._geonet_cap_at = NOW + timedelta(days=3)
        assert await provider._async_geonet_cap_alerts() == {}

    # Never fetched successfully: nothing to bridge with
    assert await provider_with(hass, feed_routes, {})._async_geonet_cap_alerts() == {}


async def test_geonet_library_entries_edge_cases(hass: HomeAssistant, feed_routes: Any) -> None:
    """Entries without a location are skipped; an unusual time format falls back to the generic parser."""
    provider = provider_with(hass, feed_routes, {})

    def entry(cls: type, feature: dict[str, Any]) -> Any:
        return cls((0.0, 0.0), geojson.loads(json.dumps(feature)))

    no_geometry = {"type": "Feature", "geometry": None, "properties": {"publicID": "x", "volcanoID": "x"}}
    assert provider._parse_geonet_quakes(([entry(GeoNetQuakeEntry, no_geometry)], {})) == []
    assert provider._parse_geonet_volcanoes([entry(GeoNetVolcanoEntry, no_geometry)]) == []

    odd_time = entry(GeoNetQuakeEntry, quake("q", 4, time="2026-10-15T19:30:00+00:00"))
    assert odd_time.origin_time is None
    (hazard,) = provider._parse_geonet_quakes(([odd_time], {}))
    assert hazard.updated_at == datetime(2026, 10, 15, 19, 30, tzinfo=UTC)
    assert entry(GeoNetQuakeEntry, {"type": "Feature", "geometry": None, "properties": None}).properties == {}

    # Without a home location a CAP alert still marks the quake; distance is left to the coordinator
    alert = parse_cap(geonet_cap("q", "id-q"))
    assert alert is not None
    provider.config.pop("latitude")
    (hazard,) = provider._parse_geonet_quakes(([odd_time], {"q": alert}))
    assert (hazard.status, hazard.distance_km) == ("Alert", None)


def test_road_events_envelope() -> None:
    """The response envelope: list, single object, empty; anything else is a broken feed."""
    assert road_events({"response": {"roadevent": [SLIP, "junk"]}}) == [SLIP]
    assert road_events({"response": {"roadevent": SLIP}}) == [SLIP]
    assert road_events({"response": ""}) == []
    assert road_events({"response": {}}) == []
    assert road_events({"response": {"roadevent": None}}) == []
    for payload in ({"error": "x"}, [], {"response": "maintenance"}, {"response": {"roadevent": "x"}}):
        with pytest.raises(ProviderUnavailableError, match="NZTA road events"):
            road_events(payload)


def test_road_event_selection_and_mapping() -> None:
    """Closures, hazards and unplanned warnings are kept and mapped; routine and stale events are not."""
    assert is_disruption(ROAD_CLOSED)
    assert is_disruption(UNPLANNED_WARNING)
    assert is_disruption(SLIP)
    for event in (PLANNED_ROADWORK, RESOLVED_CRASH, SCHEDULED_CLOSURE):
        assert not is_disruption(event)

    item = road_closure_item(ROAD_CLOSED, None, BaseHazardProvider.parse_datetime)
    assert item is not None
    assert item.id == "NZTA_561819"
    assert (item.road, item.status, item.reason) == ("SH39", "Road Closed", "Bridge Repairs")
    assert item.suburb == "SH 39 Symes Bridge, between Otorohanga and Pirongia"
    assert item.advice == "Detour via State Highway 3 (SH3) through Otorohanga."
    assert item.description is not None
    assert item.source == NZTA_SOURCE
    assert item.updated_at == datetime(2026, 10, 11, 8, 0, 39, 293000, tzinfo=UTC)
    assert (item.latitude, item.longitude) == (-38.071866293722124, 175.17701427436)

    # A line is placed at its vertex nearest home, not the first vertex
    warning = road_closure_item(UNPLANNED_WARNING, (-43.30, 171.75), BaseHazardProvider.parse_datetime)
    assert warning is not None
    assert (warning.latitude, warning.longitude) == (-43.30, 171.75)
    assert warning.advice is None  # "Not Applicable"

    # No id: a stable hash; missing names fall back; no geometry: no item
    bare = {"eventType": "Road Hazard", "geometry": "POINT (171 -42)", "way": {"name": "006"}}
    item = road_closure_item(bare, None, BaseHazardProvider.parse_datetime)
    assert item is not None
    assert item.id.startswith("NZTA_")
    assert item.id == road_closure_item(bare, None, BaseHazardProvider.parse_datetime).id  # type: ignore[union-attr]
    assert (item.road, item.status, item.reason, item.updated_at) == ("006", "Active", "Road Hazard", None)
    assert road_closure_item({"geometry": None}, None, BaseHazardProvider.parse_datetime) is None
    assert wkt_points("POINT (200 -95)") == []


def test_events_url_bounding_box() -> None:
    """The box around home covers the radius in both directions."""
    assert events_url(-41.0, 174.0, 111.0) == (
        "https://trafficnz.info/service/traffic/rest/4/events/withinbounds/172.675/-42.0/175.325/-40.0/10"
    )


async def test_nz_road_closures(hass: HomeAssistant, feed_routes: Any) -> None:
    """NZTA events near home become road closures; feed failures and missing home are handled."""
    provider = provider_with(hass, feed_routes, {})
    payload = {"response": {"roadevent": [ROAD_CLOSED, ROAD_CLOSED, UNPLANNED_WARNING, PLANNED_ROADWORK, "x"]}}
    provider.async_fetch_json = AsyncMock(return_value=payload)
    closures = await provider.async_fetch_road_closures()
    assert [c.id for c in closures] == ["NZTA_561819", "NZTA_564577"]  # duplicate dropped
    url = provider.async_fetch_json.await_args.args[0]
    assert url == events_url(HOME["latitude"], HOME["longitude"], 50)
    assert provider.async_fetch_json.await_args.kwargs["headers"] == {"Accept": "application/json"}

    # One malformed event is skipped
    bad = {**SLIP, "id": 9, "eventModified": "2026-10-15T13:14:59+13:00", "geometry": "POINT (171 -42)"}
    provider.async_fetch_json = AsyncMock(return_value={"response": {"roadevent": [bad, SLIP]}})
    with patch(
        "custom_components.ausnz_disaster_watch.providers.nz.road_closure_item",
        side_effect=[ValueError("bad"), road_closure_item(SLIP, None, provider.parse_datetime)],
    ):
        assert [c.id for c in await provider.async_fetch_road_closures()] == ["NZTA_564416"]

    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("down"))
    with pytest.raises(ProviderUnavailableError, match="NZTA road events unavailable"):
        await provider.async_fetch_road_closures()

    provider.config.pop("latitude")
    assert await provider.async_fetch_road_closures() == []
