"""Coordinator isolation, entities and options for the opt-in national feeds (#37)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.binary_sensor import TsunamiWarningBinarySensor
from custom_components.ausnz_disaster_watch.const import (
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_REGIONAL_ALERTS,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_TSUNAMI,
    CONF_ENABLE_UV,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
    NATIONAL_FEED_OPTIONS,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    HazardType,
    HeatwaveArea,
    HeatwaveStatus,
    RegionalAlertItem,
    SatelliteHotspotItem,
    SatelliteHotspots,
    TsunamiStatus,
    UVObservation,
    WarningLevel,
)
from custom_components.ausnz_disaster_watch.national_options import national_feed_options
from custom_components.ausnz_disaster_watch.providers import ACTHazardProvider
from custom_components.ausnz_disaster_watch.sensor import (
    HeatwaveSeveritySensor,
    RegionalDisasterAlertsSensor,
    SatelliteHotspotsSensor,
    UVIndexSensor,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

PREFIX = "australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"
NOW = datetime(2026, 10, 16, 1, tzinfo=UTC)

TSUNAMI = TsunamiStatus(
    active=True,
    threat_level="land",
    headline="Tsunami Warning - Land Inundation Threat for Queensland",
    issued=NOW,
    expires=NOW,
    products=["IDY68027"],
    source="JATWC",
    checked_at=NOW,
)
HOTSPOTS = SatelliteHotspots(
    items=[
        SatelliteHotspotItem(id="DEA_1", latitude=-27.3, longitude=153.0, confidence=80, distance_km=4.0),
        SatelliteHotspotItem(id="DEA_2", latitude=-27.4, longitude=153.0, confidence=None, distance_km=9.0),
    ],
    min_confidence=50,
    truncated=False,
)
HEATWAVE = HeatwaveStatus(
    severity="severe",
    areas=[HeatwaveArea(name="Queensland: Southeast Coast", severity="severe")],
    headline="Severe heatwave warning for Queensland",
    issued=NOW,
    expires=NOW,
    product_id="IDQ21013",
)
UV = UVObservation(
    station_id="brisbane", station_name="Brisbane", index=7.5, observed_at=NOW, distance_km=30.1, forecast="UV 10"
)
GDACS = [RegionalAlertItem(id="gdacs_TC1", title="Cyclone", alert_level="Red", latitude=-15.0, longitude=150.0)]


def national_mock(**values: Any) -> AsyncMock:
    """Return a provider mock that contributes only national data."""
    mock = AsyncMock()
    mock.provides_hazards = False
    mock.async_fetch_tsunami_status.return_value = values.get("tsunami")
    mock.async_fetch_satellite_hotspots.return_value = values.get("hotspots")
    mock.async_fetch_heatwave.return_value = values.get("heatwave")
    mock.async_fetch_uv.return_value = values.get("uv")
    mock.async_fetch_regional_alerts.return_value = values.get("regional")
    mock.async_fetch_air_quality.return_value = values.get("air_quality", [])
    return mock


def hazard_mock(hazards: list[CanonicalHazard] | None = None) -> AsyncMock:
    mock = AsyncMock()
    mock.async_fetch_hazards.return_value = hazards or []
    return mock


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry, providers: list[Any], **options: Any) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={**ALL_OPTIONS_ON, **options})
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=providers,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


ALL_OPTIONS_ON = dict.fromkeys(NATIONAL_FEED_OPTIONS, True)


async def test_national_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, entity_icon: Callable[[str], str | None]
) -> None:
    """Each enabled feed has an entity with its state, attributes and attribution."""
    national = national_mock(tsunami=TSUNAMI, hotspots=HOTSPOTS, heatwave=HEATWAVE, uv=UV, regional=GDACS)
    await setup_entry(hass, mock_config_entry, [hazard_mock(), national])

    tsunami = hass.states.get(f"binary_sensor.{PREFIX}_tsunami_warning")
    assert tsunami is not None
    assert tsunami.state == STATE_ON
    assert tsunami.attributes["threat_level"] == "land"
    assert tsunami.attributes["products"] == ["IDY68027"]
    assert "icon" not in tsunami.attributes
    assert entity_icon(tsunami.entity_id) == "mdi:tsunami"

    hotspots = hass.states.get(f"sensor.{PREFIX}_satellite_hotspots_nearby")
    assert hotspots is not None
    assert hotspots.state == "2"
    assert hotspots.attributes["nearest_distance_km"] == 4.0
    assert hotspots.attributes["max_confidence"] == 80
    # Each national entity credits only the sources behind its own feed (#34)
    assert hotspots.attributes["attribution"] == "Digital Earth Australia Hotspots, Geoscience Australia, CC BY 4.0"
    assert "Bureau of Meteorology" in tsunami.attributes["attribution"]

    heat = hass.states.get(f"sensor.{PREFIX}_heatwave_severity")
    assert heat is not None
    assert heat.state == "severe"
    assert heat.attributes["options"] == ["none", "low_intensity", "severe", "extreme"]
    assert heat.attributes["areas"] == [{"name": "Queensland: Southeast Coast", "severity": "severe"}]

    uv = hass.states.get(f"sensor.{PREFIX}_uv_index")
    assert uv is not None
    assert uv.state == "7.5"
    assert uv.attributes["station_name"] == "Brisbane"
    assert uv.attributes["attribution"].startswith("UV observations courtesy of ARPANSA")

    regional = hass.states.get(f"sensor.{PREFIX}_regional_disaster_alerts")
    assert regional is not None
    assert regional.state == "1"
    assert regional.attributes["alerts"][0]["id"] == "gdacs_TC1"

    # Regional alerts and national data never become hazards
    assert hass.states.get(f"sensor.{PREFIX}_active_hazards_count").state == "0"
    assert hass.states.get(f"binary_sensor.{PREFIX}_emergency_warning_nearby").state == STATE_OFF


async def test_undetermined_feeds_are_unavailable(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A feed that returns None makes its entity unavailable instead of clear."""
    await setup_entry(hass, mock_config_entry, [hazard_mock(), national_mock()])
    for entity_id in (
        f"binary_sensor.{PREFIX}_tsunami_warning",
        f"sensor.{PREFIX}_satellite_hotspots_nearby",
        f"sensor.{PREFIX}_heatwave_severity",
        f"sensor.{PREFIX}_uv_index",
        f"sensor.{PREFIX}_regional_disaster_alerts",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == STATE_UNAVAILABLE, entity_id


async def test_entities_absent_when_disabled(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Without the options no national entity is created."""
    await setup_entry(hass, mock_config_entry, [hazard_mock()], **dict.fromkeys(NATIONAL_FEED_OPTIONS, False))
    assert hass.states.get(f"binary_sensor.{PREFIX}_tsunami_warning") is None
    assert hass.states.get(f"sensor.{PREFIX}_uv_index") is None


async def test_new_zealand_has_no_australian_entities(hass: HomeAssistant) -> None:
    """NZ entries get tsunami and regional alerts only."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NZ",
        data={CONF_STATE: "NZ", "location_name": "Auckland", "latitude": -36.85, "longitude": 174.76, CONF_RADIUS: 50},
        unique_id="nz_auckland",
    )
    await setup_entry(hass, entry, [hazard_mock(), national_mock(tsunami=TSUNAMI.model_copy(update={"active": False}))])
    nz = "australia_and_new_zealand_disaster_watch_nz_auckland"
    assert hass.states.get(f"binary_sensor.{nz}_tsunami_warning").state == STATE_OFF
    assert hass.states.get(f"sensor.{nz}_regional_disaster_alerts") is not None
    assert hass.states.get(f"sensor.{nz}_uv_index") is None
    assert hass.states.get(f"sensor.{nz}_heatwave_severity") is None
    assert hass.states.get(f"sensor.{nz}_satellite_hotspots_nearby") is None


@pytest.mark.parametrize("undetermined", [False, True])
async def test_tsunami_hazard_turns_sensor_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, undetermined: bool
) -> None:
    """A retained tsunami hazard (e.g. an official NEMA alert) turns the sensor on, even while the feed is down."""
    hazard = CanonicalHazard(
        id="NZ_NEMA_1",
        source="NEMA",
        title="Tsunami Warning",
        hazard_type=HazardType.TSUNAMI,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-27.27,
        longitude=152.98,
        updated_at=NOW,
    )
    inactive = TSUNAMI.model_copy(update={"active": False, "threat_level": None})
    national = national_mock(tsunami=None if undetermined else inactive)
    await setup_entry(hass, mock_config_entry, [hazard_mock([hazard]), national])
    state = hass.states.get(f"binary_sensor.{PREFIX}_tsunami_warning")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["tsunami_hazards"] == ["Tsunami Warning"]


async def test_coordinator_collects_national_feeds(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The first valid value wins, failures and wrong types are isolated, air quality is nearest first."""
    mock_config_entry.add_to_hass(hass)
    failing = national_mock()
    failing.async_fetch_tsunami_status.side_effect = RuntimeError("boom")
    failing.async_fetch_regional_alerts.return_value = [GDACS[0], "junk"]
    stations = [
        AirQualityStationData(station_id="guardian", station_name="Guardian"),
        AirQualityStationData(station_id="far", station_name="Far", latitude=-28.0, longitude=153.4),
        AirQualityStationData(station_id="near", station_name="Near", latitude=-27.27, longitude=152.99),
    ]
    good = national_mock(tsunami=TSUNAMI, hotspots=HOTSPOTS, air_quality=stations)
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[hazard_mock(), failing, good],
    ):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
        data = await coordinator._async_update_data()
    assert data.tsunami == TSUNAMI
    assert data.satellite_hotspots == HOTSPOTS
    assert data.regional_alerts == [GDACS[0]]
    assert data.heatwave is None
    assert data.uv is None
    assert [s.station_id for s in data.air_quality_stations] == ["near", "far", "guardian"]
    assert data.air_quality_stations[0].distance_km is not None
    assert data.hazards == {}


async def test_national_provider_does_not_mask_hazard_outage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When every hazard feed fails the update fails, even though the national provider works."""
    mock_config_entry.add_to_hass(hass)
    failing = hazard_mock()
    failing.async_fetch_hazards.side_effect = RuntimeError("down")
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[failing, national_mock(tsunami=TSUNAMI)],
    ):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
        with pytest.raises(Exception, match="unavailable"):
            await coordinator._async_update_data()


async def test_coordinator_properties_without_data(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Before the first refresh every national property is None."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[],
    ):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    assert coordinator.tsunami is None
    assert coordinator.satellite_hotspots is None
    assert coordinator.heatwave is None
    assert coordinator.uv is None
    assert coordinator.regional_alerts is None
    assert coordinator.tsunami_hazards == []


async def test_air_quality_sensor_reports_distance(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The air quality sensor reports the nearest station's distance, time and source."""
    station = AirQualityStationData(
        station_id="qld_x",
        station_name="X",
        overall_rating=None,
        latitude=-27.27,
        longitude=152.99,
        observed_at=NOW,
        source="Queensland Department of the Environment",
    )
    await setup_entry(hass, mock_config_entry, [hazard_mock(), national_mock(air_quality=[station])])
    state = hass.states.get(f"sensor.{PREFIX}_air_quality")
    assert state is not None
    assert state.state == "unknown"  # no reading is never "Good"
    assert state.attributes["source"] == "Queensland Department of the Environment"
    assert state.attributes["observed_at"] == NOW.isoformat()
    assert state.attributes["distance_km"] is not None


# Options flow


def test_national_feed_options_per_state() -> None:
    """NZ gets tsunami and GDACS; air quality only where a state feed exists."""
    assert national_feed_options("NZ") == [CONF_ENABLE_TSUNAMI, CONF_ENABLE_REGIONAL_ALERTS]
    assert CONF_ENABLE_AIR_QUALITY in national_feed_options("NSW")
    assert CONF_ENABLE_AIR_QUALITY not in national_feed_options("VIC")
    assert CONF_ENABLE_UV in national_feed_options("VIC")


async def test_options_national_feeds_step(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The national feeds step defaults to off and keeps options other steps own."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RADIUS: 75})
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "national_feeds"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "national_feeds"
    assert {str(key) for key in result["data_schema"].schema} == set(national_feed_options("QLD"))
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ENABLE_TSUNAMI: True, CONF_ENABLE_HEATWAVE: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    options = mock_config_entry.options
    assert options[CONF_RADIUS] == 75
    assert options[CONF_ENABLE_TSUNAMI] is True
    assert options[CONF_ENABLE_HEATWAVE] is True
    assert options[CONF_ENABLE_SATELLITE_HOTSPOTS] is False
    assert options[CONF_ENABLE_AIR_QUALITY] is False

    # Saving monitoring settings afterwards keeps the feed toggles
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_RADIUS: 50, "override_emergency": True, "exclude_hazard_reduction": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_RADIUS] == 50
    assert mock_config_entry.options[CONF_ENABLE_TSUNAMI] is True


async def test_entity_attributes_without_data(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Attribute getters are safe before any national data exists."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[],
    ):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    entities = [
        TsunamiWarningBinarySensor(coordinator),
        SatelliteHotspotsSensor(coordinator),
        HeatwaveSeveritySensor(coordinator),
        UVIndexSensor(coordinator),
        RegionalDisasterAlertsSensor(coordinator),
    ]
    for entity in entities:
        assert entity.extra_state_attributes == {}
    assert TsunamiWarningBinarySensor(coordinator).is_on is False


async def test_base_provider_national_hooks_default_to_none(hass: HomeAssistant) -> None:
    """Providers without national data report every national feed as undetermined."""
    provider = ACTHazardProvider(hass, AsyncMock(), {"state": "ACT"})
    assert await provider.async_fetch_tsunami_status() is None
    assert await provider.async_fetch_satellite_hotspots() is None
    assert await provider.async_fetch_heatwave() is None
    assert await provider.async_fetch_uv() is None
    assert await provider.async_fetch_regional_alerts() is None
