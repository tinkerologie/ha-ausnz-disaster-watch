"""Road and flood camera catalogues, options and nearest camera per hazard (#70)."""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ausnz_disaster_watch.const import (
    CAMERA_NETWORK_NZTA,
    CAMERA_NETWORK_QLDTRAFFIC_FLOOD,
    CAMERA_NETWORK_QLDTRAFFIC_WEB,
    CONF_CAMERA_MAX,
    CONF_CAMERA_NETWORKS,
    CONF_CAMERA_RADIUS,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.geo_location import AustralianDisasterWatchGeolocationEvent
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    DisasterCameraItem,
    DisasterCoordinatorData,
    HazardType,
    WarningLevel,
)
from custom_components.ausnz_disaster_watch.providers import (
    CameraCatalogueProvider,
    QueenslandHazardProvider,
    get_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.cameras import (
    NZTA_CAMERAS_URL,
    QLDTRAFFIC_FLOOD_CAMERAS_URL,
    QLDTRAFFIC_WEB_CAMERAS_URL,
    camera_networks_for_state,
    enabled_networks,
    parse_nzta,
    parse_qldtraffic,
)
from custom_components.ausnz_disaster_watch.providers.sources import DATA_SOURCES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

FIXTURES = Path(__file__).parent / "fixtures" / "cameras"
BRISBANE = (-27.4698, 153.0251)
WELLINGTON = (-41.2865, 174.7762)


def load(name: str) -> Any:
    """Load a camera catalogue recorded on 2026-10-16 (trimmed)."""
    return json.loads((FIXTURES / name).read_text())


def provider_for(
    hass: HomeAssistant, state: str, point: tuple[float, float], **options: Any
) -> CameraCatalogueProvider:
    config = {CONF_STATE: state, "latitude": point[0], "longitude": point[1], **options}
    return CameraCatalogueProvider(hass, MagicMock(), config)


# --- catalogue parsers ----------------------------------------------------------------


def test_qldtraffic_flood_cameras_from_fixture() -> None:
    """Every recorded flood camera is read; GDA2020 (EPSG:7844) points are used as WGS84."""
    payload = load("qldtraffic_floodcameras.geojson")
    assert {f["geometry"]["crs"]["properties"]["name"] for f in payload["features"]} == {"EPSG:7844"}
    cameras = parse_qldtraffic(payload, CAMERA_NETWORK_QLDTRAFFIC_FLOOD)
    assert len(cameras) == len(payload["features"])
    first = cameras[0]
    assert first.id == "qldtraffic_flood_326"
    assert first.name == "Karana Downs - Mt Crosby Rd near Colleges Crossing"
    assert first.suburb == "Karana Downs"
    assert (first.latitude, first.longitude) == (
        payload["features"][0]["geometry"]["coordinates"][1],
        payload["features"][0]["geometry"]["coordinates"][0],
    )
    assert first.source_key == "qldtraffic_cameras"
    assert first.image_url.startswith("https://cameras.qldtraffic.qld.gov.au/")
    assert first.owner is None
    owned = next(c for c in cameras if c.owner)
    assert owned.owner == "Department of Transport and Main Roads"
    assert all(c.direction for c in cameras)


def test_qldtraffic_web_cameras_from_fixture() -> None:
    """Web cameras share the flood camera schema; their IDs do not collide with flood camera IDs."""
    cameras = parse_qldtraffic(load("qldtraffic_webcameras.geojson"), CAMERA_NETWORK_QLDTRAFFIC_WEB)
    assert len(cameras) == 7
    assert all(c.id.startswith("qldtraffic_web_") for c in cameras)


def test_qldtraffic_skips_bad_features_and_rejects_bad_documents() -> None:
    """Features without a usable point, image or ID are skipped; a non-GeoJSON document is an outage."""

    def feature(**changes: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [153.0, -27.5]},
            "properties": {"id": 1, "description": "Cam", "image_url": "https://cameras.example/1.jpg"},
        }
        for key, value in changes.items():
            if key in base["properties"] or key in {"locality", "direction"}:
                base["properties"][key] = value
            else:
                base[key] = value
        return base

    features = [
        feature(),
        feature(
            geometry={
                "type": "Point",
                "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
                "coordinates": [1, 2],
            }
        ),
        feature(geometry={"type": "Point", "crs": "EPSG:4326", "coordinates": [153.0, -27.5]}),
        feature(
            geometry={
                "type": "Point",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "coordinates": [153.1, -27.5],
            }
        ),
        feature(geometry={"type": "LineString", "coordinates": [[153.0, -27.5], [153.1, -27.6]]}),
        feature(geometry={"type": "Point", "coordinates": [153.0]}),
        feature(geometry={"type": "Point", "coordinates": [-0.1, 51.5]}),
        feature(image_url="http://insecure.example/1.jpg"),
        feature(image_url=None),
        feature(id=None),
        feature(id={"nested": 1}),
        feature(description=None, locality="Goodna"),
        feature(description="  ", locality=None),
        {"type": "Feature", "properties": None, "geometry": None},
        "not a feature",
    ]
    cameras = parse_qldtraffic({"type": "FeatureCollection", "features": features}, "net")
    assert [c.name for c in cameras] == ["Cam", "Cam", "Goodna", "Camera 1"]
    with pytest.raises(ProviderUnavailableError):
        parse_qldtraffic({"type": "Feature"}, "net")
    with pytest.raises(ProviderUnavailableError):
        parse_qldtraffic("<html>", "net")
    with pytest.raises(ProviderUnavailableError):
        parse_qldtraffic({"type": "FeatureCollection", "features": None}, "net")


def test_nzta_cameras_from_fixture() -> None:
    """Offline cameras and cameras under maintenance are skipped; relative image URLs become absolute."""
    payload = load("nzta_cameras.json")
    entries = payload["response"]["camera"]
    assert any(e["offline"] for e in entries)
    assert any(e["underMaintenance"] for e in entries)
    cameras = parse_nzta(payload, CAMERA_NETWORK_NZTA)
    online = [e for e in entries if not e["offline"] and not e["underMaintenance"]]
    assert [c.id for c in cameras] == [f"nzta_{e['id']}" for e in online]
    first, entry = cameras[0], online[0]
    assert first.image_url == f"https://trafficnz.info{entry['imageUrl']}"
    assert first.name == entry["name"].strip()
    assert first.suburb == entry["region"]["name"]
    assert first.description == entry["description"]
    assert first.direction == entry["direction"]
    assert first.source_key == "nzta_cameras"


def test_nzta_edge_cases() -> None:
    """A single camera object, missing fields and bad documents."""
    camera = {"id": 1, "name": "", "latitude": -41.3, "longitude": 174.8, "offline": False, "imageUrl": "/camera/1.jpg"}
    (only,) = parse_nzta({"response": {"camera": camera}}, "nzta")
    assert (only.name, only.suburb) == ("Camera 1", None)
    skipped = [
        {**camera, "offline": None},
        {**camera, "underMaintenance": True},
        {**camera, "latitude": None},
        {**camera, "imageUrl": "//evil.example/x.jpg"},
        {**camera, "imageUrl": None},
        {**camera, "id": None},
        "bad",
    ]
    assert parse_nzta({"response": {"camera": skipped}}, "nzta") == []
    # Kermadec-side longitudes west of the antimeridian are still in the region
    assert parse_nzta({"response": {"camera": [{**camera, "longitude": -177.9, "latitude": -29.2}]}}, "nzta")
    for bad in ({}, {"response": None}, {"response": {"camera": "x"}}, []):
        with pytest.raises(ProviderUnavailableError):
            parse_nzta(bad, "nzta")


# --- networks per jurisdiction and provider selection -------------------------------------


def test_networks_per_state() -> None:
    """QLDTraffic for QLD and NSW (border cameras), NZTA for NZ, nothing where no open catalogue exists."""
    assert camera_networks_for_state("qld") == (CAMERA_NETWORK_QLDTRAFFIC_FLOOD, CAMERA_NETWORK_QLDTRAFFIC_WEB)
    assert camera_networks_for_state("NSW") == (CAMERA_NETWORK_QLDTRAFFIC_FLOOD, CAMERA_NETWORK_QLDTRAFFIC_WEB)
    assert camera_networks_for_state("NZ") == (CAMERA_NETWORK_NZTA,)
    assert camera_networks_for_state("VIC") == ()
    assert enabled_networks({CONF_STATE: "QLD"}) == []
    assert enabled_networks({CONF_STATE: "QLD", CONF_CAMERA_NETWORKS: "qldtraffic_web"}) == []
    assert enabled_networks({CONF_STATE: "QLD", CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_NZTA, "qldtraffic_web"]}) == [
        CAMERA_NETWORK_QLDTRAFFIC_WEB
    ]


def test_provider_only_when_a_network_is_enabled(hass: HomeAssistant) -> None:
    """Existing entries get no camera provider; one is added only for an enabled, applicable network."""
    assert not any(
        isinstance(p, CameraCatalogueProvider) for p in get_providers_for_config(hass, MagicMock(), {CONF_STATE: "QLD"})
    )
    vic = {CONF_STATE: "VIC", CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_FLOOD]}
    assert not any(isinstance(p, CameraCatalogueProvider) for p in get_providers_for_config(hass, MagicMock(), vic))
    qld = {CONF_STATE: "QLD", CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_FLOOD]}
    providers = get_providers_for_config(hass, MagicMock(), qld)
    (camera_provider,) = [p for p in providers if isinstance(p, CameraCatalogueProvider)]
    assert isinstance(providers[0], QueenslandHazardProvider)
    assert camera_provider.state_code == "QLD"
    assert camera_provider.data_sources == (DATA_SOURCES["qldtraffic_cameras"],)
    assert "CC BY 4.0" in (camera_provider.attribution or "")
    nz = provider_for(hass, "NZ", WELLINGTON, **{CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_NZTA]})
    assert nz.data_sources == (DATA_SOURCES["nzta_cameras"],)


# --- provider ------------------------------------------------------------------------------


async def test_provider_radius_cap_and_nearest_first(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Cameras inside the camera radius only, nearest first, capped; no hazards of its own."""
    aioclient_mock.get(QLDTRAFFIC_FLOOD_CAMERAS_URL, json=load("qldtraffic_floodcameras.geojson"))
    aioclient_mock.get(QLDTRAFFIC_WEB_CAMERAS_URL, json=load("qldtraffic_webcameras.geojson"))
    provider = provider_for(
        hass,
        "QLD",
        BRISBANE,
        **{CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_WEB, CAMERA_NETWORK_QLDTRAFFIC_FLOOD]},
    )
    provider.session = async_session(hass)
    assert await provider.async_fetch_hazards() == []
    cameras = await provider.async_fetch_cameras()
    # Default radius 25 km: six web cameras within 7.1 km and the flood camera at 23.6 km
    assert len(cameras) == 7
    distances = [c.distance_km for c in cameras]
    assert distances == sorted(distances)
    assert all(d is not None and d <= 25 for d in distances)
    assert cameras[-1].id == "qldtraffic_flood_326"

    capped = provider_for(
        hass,
        "QLD",
        BRISBANE,
        **{CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_WEB], CONF_CAMERA_RADIUS: 100, CONF_CAMERA_MAX: 2},
    )
    capped.session = provider.session
    near = await capped.async_fetch_cameras()
    assert [c.distance_km for c in near] == distances[:2]

    # No location yet: no cameras and no request
    calls = aioclient_mock.call_count
    unlocated = CameraCatalogueProvider(
        hass, provider.session, {CONF_STATE: "QLD", CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_WEB]}
    )
    assert await unlocated.async_fetch_cameras() == []
    assert aioclient_mock.call_count == calls


async def test_nzta_requested_as_json(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The NZTA service is asked for JSON (it answers XML otherwise)."""
    aioclient_mock.get(NZTA_CAMERAS_URL, json=load("nzta_cameras.json"))
    provider = provider_for(
        hass, "NZ", WELLINGTON, **{CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_NZTA], CONF_CAMERA_RADIUS: 10}
    )
    provider.session = async_session(hass)
    cameras = await provider.async_fetch_cameras()
    assert [c.id for c in cameras] == ["nzta_828", "nzta_230", "nzta_282", "nzta_228", "nzta_227", "nzta_226"]
    assert aioclient_mock.mock_calls[0][3]["Accept"] == "application/json"


async def test_catalogue_cached_for_six_hours(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """A catalogue is fetched at most every six hours; an outage keeps the last good copy for a day."""
    aioclient_mock.get(QLDTRAFFIC_WEB_CAMERAS_URL, json=load("qldtraffic_webcameras.geojson"))
    provider = provider_for(hass, "QLD", BRISBANE, **{CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_WEB]})
    provider.session = async_session(hass)
    first = await provider.async_fetch_cameras()
    assert first
    freezer.tick(timedelta(hours=5))
    assert await provider.async_fetch_cameras() == first
    assert aioclient_mock.call_count == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(QLDTRAFFIC_WEB_CAMERAS_URL, text="<html>maintenance</html>")
    freezer.tick(timedelta(hours=2))
    assert await provider.async_fetch_cameras() == first  # stale but recent: kept
    assert aioclient_mock.call_count == 1
    freezer.tick(timedelta(hours=23))
    assert await provider.async_fetch_cameras() == []  # too old: gone, not "still there"


# --- coordinator, entities and nearest camera ---------------------------------------------


def _hazard(hazard_id: str, lat: float, lon: float) -> CanonicalHazard:
    return CanonicalHazard(
        id=hazard_id,
        source="QFD",
        title=f"Hazard {hazard_id}",
        hazard_type=HazardType.FLOOD,
        warning_level=WarningLevel.ADVICE,
        latitude=lat,
        longitude=lon,
    )


async def test_nearest_camera_on_hazards(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A hazard lists the nearest camera entity within 5 km; none further away or without an entity."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    cameras = [
        DisasterCameraItem(id="far", name="Far", image_url="https://x/far.jpg", latitude=-27.50, longitude=153.00),
        DisasterCameraItem(id="near", name="Near", image_url="https://x/near.jpg", latitude=-27.47, longitude=153.03),
        DisasterCameraItem(id="unlocated", name="Unlocated", image_url="https://x/u.jpg"),
        DisasterCameraItem(id="ghost", name="Ghost", image_url="https://x/g.jpg", latitude=-28.0, longitude=153.4),
    ]
    coordinator.data = DisasterCoordinatorData(cameras=cameras)
    registry = er.async_get(hass)
    entry_id = mock_config_entry.entry_id
    for camera_id in ("far", "near"):
        registry.async_get_or_create(
            "camera",
            DOMAIN,
            f"{entry_id}_camera_{camera_id}",
            suggested_object_id=camera_id,
            config_entry=mock_config_entry,
        )

    def event(hazard: CanonicalHazard) -> AustralianDisasterWatchGeolocationEvent:
        entity = AustralianDisasterWatchGeolocationEvent(coordinator, entry_id, hazard.id, hazard)
        entity.hass = hass
        return entity

    near = event(_hazard("a", -27.4698, 153.0251)).extra_state_attributes["nearest_camera"]
    assert near == {"entity_id": "camera.near", "name": "Near", "distance_km": 0.5}
    # Camera "ghost" is close to this hazard but has no entity (not added yet): nothing listed
    assert "nearest_camera" not in event(_hazard("b", -28.0, 153.41)).extra_state_attributes
    assert "nearest_camera" not in event(_hazard("c", -30.0, 150.0)).extra_state_attributes
    detached = AustralianDisasterWatchGeolocationEvent(coordinator, entry_id, "d", _hazard("d", -27.4698, 153.0251))
    assert "nearest_camera" not in detached.extra_state_attributes


async def test_coordinator_drops_cameras_listed_twice(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A council dashboard and QLDTraffic listing the same image give one camera entity."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    council = DisasterCameraItem(id="council_1", name="Council", image_url="https://cameras.example/1.jpg")
    agency = DisasterCameraItem(id="qldtraffic_web_1", name="Agency", image_url="https://cameras.example/1.jpg")
    other = DisasterCameraItem(id="qldtraffic_web_2", name="Other", image_url="https://cameras.example/2.jpg")
    first = MagicMock(spec=CameraCatalogueProvider)
    first.async_fetch_cameras = AsyncMock(return_value=[council])
    second = MagicMock(spec=CameraCatalogueProvider)
    second.async_fetch_cameras = AsyncMock(return_value=[agency, other])
    for provider in (first, second):
        for hook in (
            "async_fetch_power_outages",
            "async_fetch_road_closures",
            "async_fetch_relief_facilities",
            "async_fetch_weather_warnings",
            "async_fetch_emergency_news",
            "async_fetch_weather_telemetry",
            "async_fetch_air_quality",
            "async_fetch_nearby_councils",
            "async_fetch_fire_danger",
        ):
            setattr(provider, hook, AsyncMock(return_value=[] if hook != "async_fetch_fire_danger" else None))
    coordinator.providers = [first, second]
    coordinator.fire_service = MagicMock(async_update=AsyncMock(), outlook=None, season=None)
    feeds = await coordinator._async_fetch_composite_feeds()
    assert [c.id for c in feeds["cameras"]] == ["council_1", "qldtraffic_web_2"]


# --- options flow --------------------------------------------------------------------------


async def test_options_cameras_step(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """QLD entries get the cameras step: off by default, saved as ints, other options kept."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RADIUS: 75})
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    menu = result["menu_options"]
    assert menu.index("cameras") == menu.index("national_feeds") + 1
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "cameras"})
    assert result["type"] is FlowResultType.FORM
    schema = {str(key): key for key in result["data_schema"].schema}
    assert set(schema) == {CONF_CAMERA_NETWORKS, CONF_CAMERA_RADIUS, CONF_CAMERA_MAX}
    assert schema[CONF_CAMERA_NETWORKS].default() == []
    assert schema[CONF_CAMERA_RADIUS].default() == 25
    assert schema[CONF_CAMERA_MAX].default() == 12
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_FLOOD],
            CONF_CAMERA_RADIUS: 10.0,
            CONF_CAMERA_MAX: 5.0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(mock_config_entry.options) == {
        CONF_RADIUS: 75,
        CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_FLOOD],
        CONF_CAMERA_RADIUS: 10,
        CONF_CAMERA_MAX: 5,
    }
    await hass.async_block_till_done()

    # Reopening shows the saved values
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "cameras"})
    schema = {str(key): key for key in result["data_schema"].schema}
    assert schema[CONF_CAMERA_NETWORKS].default() == [CAMERA_NETWORK_QLDTRAFFIC_FLOOD]
    assert schema[CONF_CAMERA_RADIUS].default() == 10


async def test_options_cameras_menu_only_where_a_network_exists(hass: HomeAssistant) -> None:
    """VIC has no open camera catalogue: no cameras step."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STATE: "VIC", "latitude": -37.8, "longitude": 144.9})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "cameras" not in result["menu_options"]


async def test_options_cameras_drops_networks_of_other_states(hass: HomeAssistant) -> None:
    """A saved network that the entry's state does not offer (after a reconfigure) is not preselected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: "NZ", "latitude": -41.3, "longitude": 174.8},
        options={CONF_CAMERA_NETWORKS: [CAMERA_NETWORK_QLDTRAFFIC_WEB, CAMERA_NETWORK_NZTA]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "cameras"})
    schema = {str(key): key for key in result["data_schema"].schema}
    assert schema[CONF_CAMERA_NETWORKS].default() == [CAMERA_NETWORK_NZTA]


def async_session(hass: HomeAssistant) -> Any:
    """Return the shared aiohttp session (patched by aioclient_mock)."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: PLC0415

    return async_get_clientsession(hass)
