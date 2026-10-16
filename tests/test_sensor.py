"""Unit tests for Australian Emergency Hazards sensor platform."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.council_registry import own_council_link
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCoordinatorData,
    FireDangerRating,
    HazardType,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WarningLevel,
    WeatherStationObservation,
    WeatherWarningItem,
)
from custom_components.ausnz_disaster_watch.providers.qld import QueenslandHazardProvider
from custom_components.ausnz_disaster_watch.sensor import (
    AirQualityIndexSensor,
    FireDangerRatingSensor,
    HighestWarningLevelSensor,
    PowerOutagesCountSensor,
    PowerOutagesCustomersAffectedSensor,
    PrimaryWeatherObservationSensor,
    ReliefFacilitiesCountSensor,
    RoadClosuresCountSensor,
    WeatherWarningsCountSensor,
)
from homeassistant.core import HomeAssistant


async def test_sensors_telemetry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_advice: CanonicalHazard,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Test distance, active count, highest severity and title sensors."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = [
        mock_hazard_emergency_warning,
        mock_hazard_advice,
    ]

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"

    # Nearest Distance sensor: closest is mock_hazard_advice (~10.9 km)
    dist_state = hass.states.get(f"{prefix}_nearest_hazard_distance")
    assert dist_state is not None
    assert float(dist_state.state) == 10.9
    assert dist_state.attributes["unit_of_measurement"] == "km"
    assert dist_state.attributes["title"] == "Hazard: Road closed to all traffic"

    # Active count sensor: 2
    count_state = hass.states.get(f"{prefix}_active_hazards_count")
    assert count_state is not None
    assert int(count_state.state) == 2
    assert count_state.attributes["unit_of_measurement"] == "hazards"

    # Highest warning level sensor: "Emergency Warning"
    level_state = hass.states.get(f"{prefix}_highest_warning_level")
    assert level_state is not None
    assert level_state.state == "emergency_warning"
    assert level_state.attributes["device_class"] == "enum"

    # Nearest hazard title sensor
    title_state = hass.states.get(f"{prefix}_nearest_hazard_title")
    assert title_state is not None
    assert title_state.state == "Hazard: Road closed to all traffic"


async def test_sensors_clear_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors report clean default values when no hazards exist."""
    mock_config_entry.add_to_hass(hass)

    mock_provider = AsyncMock()
    mock_provider.async_fetch_hazards.return_value = []

    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[mock_provider],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    prefix = "sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"

    dist_state = hass.states.get(f"{prefix}_nearest_hazard_distance")
    assert dist_state is not None
    assert dist_state.state in {"unknown", "unavailable"} or dist_state.state is None

    count_state = hass.states.get(f"{prefix}_active_hazards_count")
    assert count_state is not None
    assert int(count_state.state) == 0

    level_state = hass.states.get(f"{prefix}_highest_warning_level")
    assert level_state is not None
    assert level_state.state == "all_clear"


async def test_highest_warning_level_sensor_states(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Each warning level is an option; the icons for them come from icons.json (#21)."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    sensor = HighestWarningLevelSensor(coordinator)

    assert sensor.icon is None
    assert sensor.options == ["all_clear", "information", "advice", "watch_and_act", "emergency_warning"]
    coordinator.data = {}
    assert sensor.native_value == "all_clear"

    hazard_advice = CanonicalHazard(
        id="1",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"1": hazard_advice}
    assert sensor.native_value == "advice"

    hazard_wa = CanonicalHazard(
        id="2",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.WATCH_AND_ACT,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"2": hazard_wa}
    assert sensor.native_value == "watch_and_act"

    hazard_ew = CanonicalHazard(
        id="3",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-25.0,
        longitude=150.0,
        updated_at=datetime.now(UTC),
    )
    coordinator.data = {"3": hazard_ew}
    assert sensor.native_value == "emergency_warning"

    # A level that is not known has no option: the sensor is unknown
    coordinator.data = {"4": replace(hazard_ew, id="4", warning_level=WarningLevel.UNKNOWN)}
    assert sensor.native_value is None
    coordinator.data = {"5": replace(hazard_ew, id="5", warning_level=WarningLevel.INFORMATION)}
    assert sensor.native_value == "information"


async def test_expanded_disaster_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all expanded disaster sensors: power outages, roads, warnings, fire danger, AQI, weather, and relief."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    po = PowerOutageItem(suburb="Caboolture", cause="Storm", restore_time="14:00", customers_affected=25)
    rc = RoadClosureItem(
        id="rc1", road="Main St", suburb="Morayfield", status="Closed", reason="Water", distance_km=5.2
    )
    ww = WeatherWarningItem(title="Severe Thunderstorm", locations="Moreton Bay")
    fd = FireDangerRating(
        district_name="Moreton", district_number="1", rating="Catastrophic", total_fire_ban=True, day="Today"
    )
    aq = AirQualityStationData(
        station_id="s1",
        station_name="Burpengary",
        overall_rating="Fair",
        pm2_5_measurement="12.5",
        pm10_measurement="22.0",
        no2_measurement="5.0",
        o3_measurement="15.0",
    )
    ws = WeatherStationObservation(
        station_id="w1",
        station_name="Caboolture Telemetry",
        temperature=24.6,
        apparent_temperature=25.1,
        relative_humidity=65.0,
        pressure_hpa=1013.2,
        wind_speed_avg=18.0,
        wind_speed_max=28.0,
    )
    rf = ReliefFacilityItem(
        id="rf1",
        facility_type="sandbag_station",
        name="Caboolture Sandbags",
        suburb="Caboolture",
        address="123 Road",
        status="Open",
        distance_km=3.1,
    )

    coordinator.data = DisasterCoordinatorData(
        power_outages=[po],
        road_closures=[rc],
        weather_warnings=[ww],
        fire_danger=fd,
        air_quality_stations=[aq],
        weather_stations=[ws],
        relief_facilities=[rf],
    )

    po_count = PowerOutagesCountSensor(coordinator)
    assert po_count.native_value == 1
    assert "outages" in po_count.extra_state_attributes

    po_customers = PowerOutagesCustomersAffectedSensor(coordinator)
    assert po_customers.native_value == 25

    rc_count = RoadClosuresCountSensor(coordinator)
    assert rc_count.native_value == 1
    assert "closures" in rc_count.extra_state_attributes

    ww_count = WeatherWarningsCountSensor(coordinator)
    assert ww_count.native_value == 1
    assert "warnings" in ww_count.extra_state_attributes

    fd_sensor = FireDangerRatingSensor(coordinator)
    assert fd_sensor.native_value == "catastrophic"
    assert fd_sensor.icon is None  # from icons.json (#21)
    assert fd_sensor.options == ["no_rating", "moderate", "high", "extreme", "catastrophic"]
    fd_attrs = fd_sensor.extra_state_attributes
    assert fd_attrs["district_name"] == "Moreton"
    assert fd_attrs["total_fire_ban"] is True

    # AFDRS display names map to their options; anything else is unknown (#21)
    for rating, option in (
        ("Extreme", "extreme"),
        ("High", "high"),
        ("Moderate", "moderate"),
        ("No Rating", "no_rating"),
        (" no-rating ", "no_rating"),
        ("Very High", None),
        ("", None),
    ):
        coordinator.data.fire_danger.rating = rating
        assert fd_sensor.native_value == option, rating

    coordinator.data.fire_danger = None
    assert fd_sensor.native_value is None
    assert fd_sensor.extra_state_attributes == {}

    aq_sensor = AirQualityIndexSensor(coordinator)
    assert aq_sensor.native_value == "Fair"
    aq_attrs = aq_sensor.extra_state_attributes
    assert aq_attrs["station_name"] == "Burpengary"
    assert aq_attrs["pm2_5"] == "12.5"

    coordinator.data.air_quality_stations = []
    assert aq_sensor.native_value is None
    assert aq_sensor.extra_state_attributes == {}

    ws_sensor = PrimaryWeatherObservationSensor(coordinator)
    assert ws_sensor.native_value == 24.6
    ws_attrs = ws_sensor.extra_state_attributes
    assert ws_attrs["station_name"] == "Caboolture Telemetry"
    assert ws_attrs["relative_humidity"] == 65.0

    # Weather station with None temperature
    coordinator.data.weather_stations = [
        WeatherStationObservation(station_id="w2", station_name="No Temp", temperature=None)
    ]
    assert ws_sensor.native_value is None

    coordinator.data.weather_stations = []
    assert ws_sensor.native_value is None
    assert ws_sensor.extra_state_attributes == {}

    rf_count = ReliefFacilitiesCountSensor(coordinator)
    assert rf_count.native_value == 1
    assert "facilities" in rf_count.extra_state_attributes


async def test_council_attribute(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The warning sensors name the entry's own council dashboard next to the nearby ones (#94)."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = DisasterCoordinatorData(nearby_councils=[{"name": "Redland City", "url": "https://x"}])
    level = HighestWarningLevelSensor(coordinator)
    warnings = WeatherWarningsCountSensor(coordinator)

    # A moved host is followed, as the dashboard client does: the link is the dashboard it reads
    coordinator.providers = [
        AsyncMock(),
        QueenslandHazardProvider(
            hass, AsyncMock(), {"state": "QLD", CONF_COUNCIL_DASHBOARD_URL: "dashboard.cityofgoldcoast.com.au/"}
        ),
    ]
    own = {"name": "City of Gold Coast", "url": "https://dashboard.goldcoast.qld.gov.au"}
    assert level.extra_state_attributes["council"] == own
    assert warnings.extra_state_attributes["council"] == own
    assert level.extra_state_attributes["nearby_councils"] == [{"name": "Redland City", "url": "https://x"}]

    # No council dashboard: no link
    coordinator.providers = [QueenslandHazardProvider(hass, AsyncMock(), {"state": "QLD"})]
    assert level.extra_state_attributes["council"] is None
    coordinator.providers = [AsyncMock()]
    assert warnings.extra_state_attributes["council"] is None


def test_own_council_link() -> None:
    """The own link is named from the registry, or by its host when the registry does not know it (#94)."""
    assert own_council_link(None) is None
    assert own_council_link("") is None
    assert own_council_link("https://disaster.moretonbay.qld.gov.au") == {
        "name": "City of Moreton Bay",
        "url": "https://disaster.moretonbay.qld.gov.au",
    }
    assert own_council_link("https://dashboard.example.org/qld") == {
        "name": "dashboard.example.org",
        "url": "https://dashboard.example.org/qld",
    }
