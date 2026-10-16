"""Home-zone location, council selection, camera filtering and the 1.2 entry migration (#19)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import LEGACY_CAMERA_IDS, async_migrate_entry
from custom_components.ausnz_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LONGITUDE,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    LOCATION_MODE_HOME,
)
from custom_components.ausnz_disaster_watch.coordinator import (
    AustralianDisasterWatchCoordinator,
    nearest_council_dashboard,
)
from custom_components.ausnz_disaster_watch.models import DisasterCameraItem
from custom_components.ausnz_disaster_watch.providers import QueenslandHazardProvider
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

MORETON_BAY = "https://disaster.moretonbay.qld.gov.au"


def test_nearest_council_dashboard() -> None:
    """The nearest preset in the same state within 40 km, else none."""
    assert nearest_council_dashboard("QLD", -16.92, 145.77) == "https://disaster.cairns.qld.gov.au"
    assert nearest_council_dashboard("QLD", -23.44, 144.25) == "https://rapad.qitplus.com/longreach"
    assert nearest_council_dashboard("QLD", -20.0, 155.0) is None
    assert nearest_council_dashboard("NSW", -27.27, 152.98) is None
    assert nearest_council_dashboard("QLD", None, 152.98) is None
    # Sunshine Coast has no Guardian dashboard; Noosa (about 28 km away) is used instead
    assert nearest_council_dashboard("QLD", -26.65, 153.0667) == "https://disaster.noosa.qld.gov.au"


async def test_home_mode_follows_home_location(hass: HomeAssistant) -> None:
    """Home-zone entries use the current home location at every refresh, also for providers."""
    hass.config.latitude, hass.config.longitude = -16.92, 145.77
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_HOME, CONF_LATITUDE: -27.2, CONF_LONGITUDE: 153.0},
    )
    entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    # Stored coordinates from older versions are ignored in home mode
    assert (coordinator.latitude, coordinator.longitude) == (-16.92, 145.77)
    qld = next(p for p in coordinator.providers if isinstance(p, QueenslandHazardProvider))
    assert (qld.config["latitude"], qld.config["longitude"]) == (-16.92, 145.77)

    # The user corrects the home location; the next refresh uses it
    hass.config.latitude, hass.config.longitude = 0.0, 145.0
    with (
        patch.object(coordinator, "_async_fetch_all_hazards", AsyncMock(return_value=[])),
        patch.object(coordinator, "_async_fetch_composite_feeds", AsyncMock(return_value=_empty_aux())),
    ):
        await coordinator._async_update_data()
    assert (coordinator.latitude, coordinator.longitude) == (0.0, 145.0)
    assert qld.config["latitude"] == 0.0


async def test_moving_home_drops_cached_hazard_distances(hass: HomeAssistant) -> None:
    """Last-good hazards carry distances from the old point, so a move discards them."""
    hass.config.latitude, hass.config.longitude = -16.92, 145.77
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_HOME})
    entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    coordinator._last_good_hazards["QLD"] = (MagicMock(), [])
    coordinator._update_location()  # same point: cache kept
    assert "QLD" in coordinator._last_good_hazards
    hass.config.latitude = -19.26
    coordinator._update_location()
    assert coordinator._last_good_hazards == {}


async def test_custom_mode_uses_stored_point(hass: HomeAssistant) -> None:
    """Custom entries keep their stored point; without one they fall back to home."""
    hass.config.latitude, hass.config.longitude = -16.92, 145.77
    custom = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM, CONF_LATITUDE: -27.2, CONF_LONGITUDE: 153.0},
    )
    custom.add_to_hass(hass)
    assert (AustralianDisasterWatchCoordinator(hass, custom).latitude) == -27.2

    no_point = MockConfigEntry(domain=DOMAIN, data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM})
    no_point.add_to_hass(hass)
    assert AustralianDisasterWatchCoordinator(hass, no_point).latitude == -16.92


async def test_cameras_are_radius_filtered_and_unique(hass: HomeAssistant) -> None:
    """Cameras outside the radius are dropped and each camera ID appears once."""
    hass.config.latitude, hass.config.longitude = -27.27, 152.98
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_HOME})
    entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    provider = AsyncMock()
    provider.async_fetch_cameras.return_value = [
        DisasterCameraItem(id="near", name="Near", image_url="https://x/1.jpg", latitude=-27.1, longitude=153.0),
        DisasterCameraItem(id="near", name="Duplicate", image_url="https://x/2.jpg", latitude=-27.1, longitude=153.0),
        DisasterCameraItem(id="far", name="Cairns", image_url="https://x/3.jpg", latitude=-16.9, longitude=145.7),
        DisasterCameraItem(id="nowhere", name="No location", image_url="https://x/4.jpg"),
    ]
    provider.async_fetch_fire_danger.return_value = None
    coordinator.providers = [provider]
    aux = await coordinator._async_fetch_composite_feeds()
    assert [(c.id, c.name) for c in aux["cameras"]] == [("near", "Near"), ("nowhere", "No location")]


def _empty_aux() -> dict[str, object]:
    return {
        "power_outages": [],
        "road_closures": [],
        "weather_warnings": [],
        "emergency_news": [],
        "fire_danger": None,
        "weather_stations": [],
        "air_quality_stations": [],
        "relief_facilities": [],
        "cameras": [],
        "nearby_councils": [],
    }


async def test_migration_repairs_home_council_and_removes_legacy_cameras(hass: HomeAssistant) -> None:
    """1.1 -> 1.2: the automatic Moreton Bay URL is recalculated; legacy cameras are removed."""
    hass.config.latitude, hass.config.longitude = -16.92, 145.77
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_HOME, CONF_COUNCIL_DASHBOARD_URL: MORETON_BAY},
        options={CONF_COUNCIL_DASHBOARD_URL: "https://disaster.townsville.qld.gov.au"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "camera", DOMAIN, f"{entry.entry_id}_camera_{LEGACY_CAMERA_IDS[0]}", config_entry=entry
    )
    other = registry.async_get_or_create("camera", DOMAIN, f"{entry.entry_id}_camera_other", config_entry=entry)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.minor_version == 2
    assert entry.data[CONF_COUNCIL_DASHBOARD_URL] == "https://disaster.cairns.qld.gov.au"
    # A URL chosen in the options is the user's choice and is kept
    assert entry.options[CONF_COUNCIL_DASHBOARD_URL] == "https://disaster.townsville.qld.gov.au"
    assert registry.async_get(legacy.entity_id) is None
    assert registry.async_get(other.entity_id) is not None


async def test_migration_keeps_explicit_choices(hass: HomeAssistant) -> None:
    """Custom entries, other URLs and newer versions are left alone."""
    custom = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: "QLD", CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM, CONF_COUNCIL_DASHBOARD_URL: MORETON_BAY},
    )
    custom.add_to_hass(hass)
    assert await async_migrate_entry(hass, custom) is True
    assert custom.data[CONF_COUNCIL_DASHBOARD_URL] == MORETON_BAY
    assert custom.minor_version == 2

    current = MockConfigEntry(domain=DOMAIN, version=1, minor_version=2, data={CONF_STATE: "QLD"})
    current.add_to_hass(hass)
    assert await async_migrate_entry(hass, current) is True

    future = MockConfigEntry(domain=DOMAIN, version=2, data={CONF_STATE: "QLD"})
    future.add_to_hass(hass)
    assert await async_migrate_entry(hass, future) is False
