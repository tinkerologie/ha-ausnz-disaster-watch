"""Unit and integration tests for EmergencyDataCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import DEFAULT_SCAN_INTERVAL, DOMAIN, THREAT_SCAN_INTERVAL
from custom_components.ausnz_disaster_watch.coordinator import (
    AustralianDisasterWatchCoordinator,
    calculate_haversine_distance,
)
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCameraItem,
    EmergencyNewsItem,
    FireDangerRating,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WarningLevel,
    WeatherStationObservation,
    WeatherWarningItem,
)
from homeassistant.core import HomeAssistant


def test_haversine_distance_accuracy() -> None:
    """Test Haversine distance calculation against known Australian coordinates."""
    # Brisbane (-27.4698, 153.0251) to Gold Coast (-28.0167, 153.4000) ~ 71-72 km
    dist = calculate_haversine_distance(
        -27.4698,
        153.0251,
        -28.0167,
        153.4000,
    )
    assert 70.0 < dist < 73.0

    # Distance to same point must be 0
    assert calculate_haversine_distance(-27.2657, 152.9818, -27.2657, 152.9818) == 0.0


async def test_coordinator_filtering_and_override(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_watch_and_act: CanonicalHazard,
    mock_hazard_advice: CanonicalHazard,
    mock_hazard_hazard_reduction: CanonicalHazard,
    mock_hazard_distant_emergency_warning: CanonicalHazard,
) -> None:
    """Test spatial filtering, hazard reduction exclusion, and emergency warning override."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    # Mock provider returning 5 hazards:
    # 1. Nearby emergency warning (~21 km) -> Keep
    # 2. Nearby watch and act (~18 km) -> Keep
    # 3. Nearby advice (~10 km) -> Keep
    # 4. Nearby planned burn (~30 km) -> Exclude (exclude_hazard_reduction is True)
    # 5. Distant emergency warning (~230 km) -> Keep because override_emergency is True!
    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
        mock_hazard_watch_and_act,
        mock_hazard_advice,
        mock_hazard_hazard_reduction,
        mock_hazard_distant_emergency_warning,
    ]
    coordinator.providers = [mock_provider]

    await coordinator.async_refresh()
    data = coordinator.data

    # Verify hazard reduction burn was dropped
    assert mock_hazard_hazard_reduction.id not in data

    # Verify nearby hazards are present
    assert mock_hazard_emergency_warning.id in data
    assert mock_hazard_watch_and_act.id in data
    assert mock_hazard_advice.id in data

    # Verify distant emergency warning is kept due to override
    assert mock_hazard_distant_emergency_warning.id in data
    assert len(data) == 4

    # Verify dynamic poll interval shifted to threat mode (60 seconds)
    assert coordinator.update_interval == timedelta(seconds=THREAT_SCAN_INTERVAL)
    assert coordinator.has_emergency_warning_nearby is True
    assert coordinator.highest_warning_level == WarningLevel.EMERGENCY_WARNING
    assert coordinator.nearest_hazard is not None
    assert coordinator.nearest_hazard.id == mock_hazard_advice.id


async def test_coordinator_normal_polling_when_no_threat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test coordinator reverts to standard 5 min polling when only Advice or Information is present."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_advice]
    coordinator.providers = [mock_provider]

    await coordinator.async_refresh()
    data = coordinator.data
    assert len(data) == 1
    assert coordinator.has_emergency_warning_nearby is False
    assert coordinator.highest_warning_level == WarningLevel.ADVICE
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)


async def test_coordinator_options_take_precedence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Options override entry data when the coordinator is built (applied on reload)."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={"radius": 100})
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    assert coordinator.radius_km == 100.0
    assert coordinator.config_entry is mock_config_entry


async def test_coordinator_falls_back_to_home_location(hass: HomeAssistant) -> None:
    """An entry without coordinates uses the Home Assistant home location (#5).

    Before the fix the base class was initialised after reading config values, so
    ``self.hass`` did not exist yet and this raised AttributeError.
    """
    hass.config.latitude = -33.8688
    hass.config.longitude = 151.2093
    entry = MockConfigEntry(domain=DOMAIN, data={"state": "NSW", "radius": 25})
    entry.add_to_hass(hass)

    coordinator = AustralianDisasterWatchCoordinator(hass, entry)

    assert coordinator.latitude == -33.8688
    assert coordinator.longitude == 151.2093
    assert coordinator.state_code == "NSW"


async def test_coordinator_provider_exception_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
) -> None:
    """Test coordinator handles provider exceptions gracefully."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    failing_provider = AsyncMock()
    failing_provider.async_fetch_hazards.side_effect = RuntimeError("Feed offline")
    working_provider = AsyncMock()
    working_provider.async_fetch_hazards.return_value = [mock_hazard_advice]
    coordinator.providers = [failing_provider, working_provider]

    await coordinator.async_refresh()
    assert len(coordinator.data) == 1
    assert mock_hazard_advice.id in coordinator.data


async def test_coordinator_dynamic_interval_reset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test coordinator reverts interval from 60s to 300s when threat resolves."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [mock_hazard_emergency_warning]
    coordinator.providers = [mock_provider]

    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=THREAT_SCAN_INTERVAL)

    # Next refresh has no hazards -> reverts to DEFAULT_SCAN_INTERVAL
    mock_provider.async_fetch_hazards.return_value = []
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)


async def test_coordinator_empty_data_properties(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test properties when coordinator has no data or diverse structures."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = {}
    assert coordinator.active_hazards == []
    assert coordinator.highest_warning_level == WarningLevel.INFORMATION
    assert coordinator.nearest_hazard is None
    assert coordinator.has_emergency_warning_nearby is False

    # When coordinator.data is a dict with hazards
    coordinator.data = {"h1": mock_hazard_emergency_warning}  # type: ignore[assignment]
    assert len(coordinator.active_hazards) == 1
    assert coordinator.has_emergency_warning_nearby is True

    # When coordinator.data is None
    coordinator.data = None  # type: ignore[assignment]
    assert coordinator.active_hazards == []
    assert coordinator.highest_warning_level == WarningLevel.INFORMATION
    assert coordinator.nearest_hazard is None
    assert coordinator.has_emergency_warning_nearby is False
    assert coordinator.power_outages == []
    assert coordinator.road_closures == []
    assert coordinator.weather_warnings == []
    assert coordinator.emergency_news == []
    assert coordinator.fire_danger is None
    assert coordinator.weather_stations == []
    assert coordinator.air_quality_stations == []
    assert coordinator.relief_facilities == []
    assert coordinator.cameras == []
    assert coordinator.nearby_councils == []

    # When coordinator.data has no hazards
    class EmptyData:
        hazards = None

    coordinator.data = EmptyData()  # type: ignore[assignment]
    assert coordinator.active_hazards == []


async def test_coordinator_composite_data_collection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator collects all composite telemetry feeds from providers."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []
    mock_provider.async_fetch_power_outages.return_value = [
        PowerOutageItem(suburb="Caboolture", cause="Storm", customers_affected=10),
        PowerOutageItem(suburb="Nearby", cause="Tree", customers_affected=5, latitude=-27.1, longitude=152.9),
        PowerOutageItem(suburb="Far Away", cause="Lines", customers_affected=50, latitude=-10.0, longitude=120.0),
    ]

    mock_provider.async_fetch_road_closures.return_value = [
        RoadClosureItem(id="r1", road="Main St", suburb="Morayfield", status="Closed", latitude=-27.1, longitude=152.9),
        RoadClosureItem(id="r2", road="Local St", suburb="Morayfield", status="Closed", latitude=None, longitude=None),
    ]
    mock_provider.async_fetch_weather_warnings.return_value = [WeatherWarningItem(title="Storm Warning")]
    mock_provider.async_fetch_emergency_news.return_value = [EmergencyNewsItem(id="n1", title="News 1")]
    mock_provider.async_fetch_fire_danger.return_value = FireDangerRating(
        district_name="Moreton", district_number="1", rating="High", total_fire_ban=False
    )
    mock_provider.async_fetch_weather_telemetry.return_value = [
        WeatherStationObservation(station_id="w1", station_name="Station 1", temperature=22.5)
    ]
    mock_provider.async_fetch_air_quality.return_value = [
        AirQualityStationData(station_id="a1", station_name="Air 1", overall_rating="Good")
    ]
    mock_provider.async_fetch_relief_facilities.return_value = [
        ReliefFacilityItem(
            id="rf1",
            facility_type="sandbag_station",
            name="Sandbag 1",
            suburb="Caboolture",
            latitude=-27.1,
            longitude=152.9,
        ),
        ReliefFacilityItem(
            id="rf2",
            facility_type="sandbag_station",
            name="Sandbag 2",
            suburb="Caboolture",
            latitude=None,
            longitude=None,
        ),
    ]
    mock_provider.async_fetch_cameras.return_value = [
        DisasterCameraItem(id="cam1", name="Camera 1", image_url="https://example.com/cam.jpg")
    ]
    mock_provider.async_fetch_nearby_councils.return_value = [{"name": "Council 1", "url": "https://example.com"}]

    coordinator.providers = [mock_provider]
    await coordinator.async_refresh()

    assert len(coordinator.power_outages) == 2
    assert len(coordinator.road_closures) == 2
    assert coordinator.road_closures[0].distance_km is not None
    assert coordinator.road_closures[1].distance_km is None
    assert len(coordinator.weather_warnings) == 1
    assert len(coordinator.emergency_news) == 1
    assert coordinator.fire_danger is not None
    assert coordinator.fire_danger.rating == "High"
    assert len(coordinator.weather_stations) == 1
    assert len(coordinator.air_quality_stations) == 1
    assert len(coordinator.relief_facilities) == 2
    assert coordinator.relief_facilities[0].distance_km is not None
    assert coordinator.relief_facilities[1].distance_km is None
    assert len(coordinator.cameras) == 1
    assert len(coordinator.nearby_councils) == 1


async def test_coordinator_composite_exceptions_handled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator gracefully absorbs exceptions from composite provider feeds."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    failing_provider = AsyncMock()
    failing_provider.async_fetch_hazards.return_value = []
    failing_provider.async_fetch_power_outages.side_effect = RuntimeError("Outages error")
    failing_provider.async_fetch_road_closures.side_effect = RuntimeError("Roads error")
    failing_provider.async_fetch_weather_warnings.side_effect = RuntimeError("Warnings error")
    failing_provider.async_fetch_emergency_news.side_effect = RuntimeError("News error")
    failing_provider.async_fetch_fire_danger.side_effect = RuntimeError("Fire error")
    failing_provider.async_fetch_weather_telemetry.side_effect = RuntimeError("Weather error")
    failing_provider.async_fetch_air_quality.side_effect = RuntimeError("AQ error")
    failing_provider.async_fetch_relief_facilities.side_effect = RuntimeError("Relief error")
    failing_provider.async_fetch_cameras.side_effect = RuntimeError("Camera error")
    failing_provider.async_fetch_nearby_councils.side_effect = RuntimeError("Council error")

    coordinator.providers = [failing_provider]
    await coordinator.async_refresh()

    assert coordinator.power_outages == []
    assert coordinator.road_closures == []
    assert coordinator.weather_warnings == []
    assert coordinator.emergency_news == []
    assert coordinator.fire_danger is None
    assert coordinator.weather_stations == []
    assert coordinator.air_quality_stations == []
    assert coordinator.relief_facilities == []
    assert coordinator.cameras == []
    assert coordinator.nearby_councils == []
