"""Unit tests for Australian Emergency Hazards sensor platform."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_ENABLE_REGIONAL_ALERTS,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.council_registry import own_council_link
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCoordinatorData,
    EmergencyNewsItem,
    FireDangerRating,
    HazardType,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    SatelliteHotspots,
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
from homeassistant.helpers import entity_registry as er


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


async def test_oversized_bulletins_remain_live(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
) -> None:
    """Keep complete live bulletins and restrict only their recorder policy (#114).

    The pinned custom-component harness does not provide recorder_mock or
    async_wait_recording_done, so check Core's live state exclusion metadata.
    """
    mock_config_entry.add_to_hass(hass)
    text = "Long emergency bulletin. " * 1000
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = [mock_hazard_emergency_warning]
    provider.async_fetch_emergency_news.return_value = [
        EmergencyNewsItem(id=str(i), title=f"Bulletin {i}", description=text) for i in range(25)
    ]
    provider.async_fetch_weather_warnings.return_value = [
        WeatherWarningItem(title=f"Warning {i}: {text}", locations=text) for i in range(25)
    ]
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    baseline_exclusions = []
    for key in ("active_hazards_count", "power_outages_count"):
        entity_id = registry.async_get_entity_id(
            "sensor", "ausnz_disaster_watch", f"{mock_config_entry.entry_id}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        baseline_exclusions.append(state.state_info["unrecorded_attributes"])
    assert baseline_exclusions[0] == baseline_exclusions[1]
    assert not baseline_exclusions[0] & {"warnings", "emergency_news"}
    for key, expected, excluded in (
        ("highest_warning_level", "emergency_warning", {"emergency_news"}),
        ("weather_warnings_count", "25", {"warnings", "emergency_news"}),
    ):
        entity_id = registry.async_get_entity_id(
            "sensor", "ausnz_disaster_watch", f"{mock_config_entry.entry_id}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected
        assert len(state.attributes["emergency_news"]) == 20
        assert all(item["description"] == text for item in state.attributes["emergency_news"])
        assert state.state_info["unrecorded_attributes"] == baseline_exclusions[0] | excluded
        assert "council" not in state.state_info["unrecorded_attributes"]
        assert "inside_warning_area" not in state.state_info["unrecorded_attributes"]
        assert "inside_warning_level" not in state.state_info["unrecorded_attributes"]
        if key == "weather_warnings_count":
            assert len(state.attributes["warnings"]) == 20
            assert state.attributes["warnings"][0]["title"] == f"Warning 0: {text}"
            assert state.attributes["warnings"][0]["locations"] == text
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_weather_warning_unit_override_and_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Native units and identity survive reload; explicit user overrides remain user-owned (#115)."""
    mock_config_entry.add_to_hass(hass)
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_weather_warnings.return_value = [WeatherWarningItem(title="Storm warning")]
    registry = er.async_get(hass)
    unique_id = f"{mock_config_entry.entry_id}_weather_warnings_count"
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = registry.async_get_entity_id("sensor", "ausnz_disaster_watch", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "1"
        assert state.attributes["unit_of_measurement"] == "warnings"
        assert state.attributes["state_class"] == "measurement"

        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert registry.async_get_entity_id("sensor", "ausnz_disaster_watch", unique_id) == entity_id
        assert registry.async_get(entity_id).unique_id == unique_id
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["unit_of_measurement"] == "warnings"
        assert state.attributes["state_class"] == "measurement"

        registry.async_update_entity_options(entity_id, "sensor", {"unit_of_measurement": None})
        await hass.async_block_till_done()
        # Core 2026.10.2 ignores a null unit override for a sensor with no unit converter.
        # Unlike the plan's hypothesis, this does not make a noun-unit sensor unitless.
        assert registry.async_get(entity_id).options["sensor"]["unit_of_measurement"] is None
        assert hass.states.get(entity_id).attributes["unit_of_measurement"] == "warnings"
        registry.async_update_entity_options(entity_id, "sensor", None)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).attributes["unit_of_measurement"] == "warnings"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("key", "unit"),
    [
        ("active_hazards_count", "hazards"),
        ("power_outages_count", "outages"),
        ("power_outages_customers_affected", "customers"),
        ("road_closures_count", "closures"),
        ("weather_warnings_count", "warnings"),
        ("relief_facilities_count", "facilities"),
        ("satellite_hotspots_nearby", "hotspots"),
        ("regional_disaster_alerts", "alerts"),
    ],
)
async def test_count_sensor_metadata(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, key: str, unit: str
) -> None:
    """Preserve effective count noun units for existing long-term statistics (#115)."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_SATELLITE_HOTSPOTS: True, CONF_ENABLE_REGIONAL_ALERTS: True}
    )
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_satellite_hotspots.return_value = SatelliteHotspots(items=[], min_confidence=50)
    provider.async_fetch_regional_alerts.return_value = []
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ausnz_disaster_watch", f"{mock_config_entry.entry_id}_{key}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["state_class"] == "measurement"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
