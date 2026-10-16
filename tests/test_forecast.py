"""Integration tests for the opt-in Open-Meteo forecast features (#38, #39, #40)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ausnz_disaster_watch.const import (
    CONF_AI_ENSEMBLE,
    CONF_AI_WEATHERNEXT,
    CONF_GUST_THRESHOLD,
    CONF_HEAVY_RAIN_THRESHOLD,
    CONF_RIVER_POINTS,
    CONF_WEATHER_SIGNALS,
    DOMAIN,
    FORECAST_RETRY_INTERVAL,
    WEATHER_SIGNALS_INTERVAL,
)
from custom_components.ausnz_disaster_watch.forecast_coordinator import river_points
from custom_components.ausnz_disaster_watch.providers.open_meteo import (
    MODEL_AIFS,
    MODEL_WEATHERNEXT,
    OpenMeteoError,
    parse_ensemble,
    parse_forecast,
    parse_river,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"
FIXTURE_NOW = datetime(2026, 10, 15, 22, 30, tzinfo=UTC)

BRISBANE = {"id": "p1", "name": "Brisbane River", "latitude": -27.47, "longitude": 153.02, "threshold": 50.0}
WELLINGTON = {"id": "p2", "name": "Wellington CBD", "latitude": -41.29, "longitude": 174.78, "threshold": 1.0}


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def _null_river() -> dict[str, Any]:
    brisbane = _load("flood_brisbane.json")
    return {
        "latitude": -41.27,
        "longitude": 174.77,
        "daily": {"time": brisbane["daily"]["time"], "river_discharge": [None] * 7},
    }


@pytest.fixture
def client() -> Generator[MagicMock]:
    """Patch the Open-Meteo client used by the coordinators with the captured Brisbane samples."""
    instance = MagicMock()
    instance.async_get_forecast = AsyncMock(return_value=parse_forecast(_load("forecast_brisbane.json")))
    # The first point gets the Brisbane River sample, any further point an off-grid (null) cell
    instance.async_get_river_forecasts = AsyncMock(
        side_effect=lambda points: parse_river(
            [_load("flood_brisbane.json")] + [_null_river()] * (len(points) - 1), points
        )
    )
    instance.async_get_ensemble = AsyncMock(
        side_effect=lambda lat, lon, models: {
            m: r
            for m, r in parse_ensemble(_load("ensemble_brisbane.json"), [MODEL_AIFS, MODEL_WEATHERNEXT]).items()
            if m in models
        }
    )
    with patch("custom_components.ausnz_disaster_watch.forecast_coordinator.OpenMeteoClient", return_value=instance):
        yield instance


@pytest.fixture(autouse=True)
def no_hazards() -> Generator[None]:
    """Patch the hazard providers with one that returns nothing."""
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[provider],
    ):
        yield


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, options: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=entry.title, data=dict(entry.data), options=options, unique_id="x")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None, key
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_disabled_by_default(hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock) -> None:
    """Existing entries fetch nothing from Open-Meteo and get no forecast entities."""
    entry = await _setup(hass, mock_config_entry, {})
    forecasts = entry.runtime_data.forecasts
    assert (forecasts.weather, forecasts.river, forecasts.ensemble) == (None, None, None)
    client.async_get_forecast.assert_not_called()
    client.async_get_river_forecasts.assert_not_called()
    client.async_get_ensemble.assert_not_called()
    keys = {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert f"{entry.entry_id}_max_wind_gust_24h" not in keys
    assert f"{entry.entry_id}_ai_rain_outlook" not in keys


async def test_weather_signal_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Gust, heat, thunderstorm and calculated FFDI entities are labelled and attributed."""
    freezer.move_to(FIXTURE_NOW)
    entry = await _setup(hass, mock_config_entry, {CONF_WEATHER_SIGNALS: True, CONF_GUST_THRESHOLD: 30})
    client.async_get_forecast.assert_awaited_once_with(-27.2657, 152.9818)

    gust = _state(hass, entry, "sensor", "max_wind_gust_24h")
    assert float(gust.state) > 30
    assert gust.attributes["unit_of_measurement"] == "km/h"
    assert gust.attributes[ATTR_ATTRIBUTION] == "Weather data by Open-Meteo.com (CC BY 4.0)"
    assert gust.attributes["source"] == "Open-Meteo"
    assert gust.attributes["model"] == "best_match"
    assert gust.attributes["official"] is False
    assert gust.attributes["forecast_issued_at"] == FIXTURE_NOW.isoformat()
    assert gust.attributes["window_start"] == "2026-10-15T22:00:00+00:00"
    assert gust.attributes["peak_time"] is not None

    heat = _state(hass, entry, "sensor", "max_apparent_temperature_24h")
    assert heat.attributes["unit_of_measurement"] == "°C"

    storm = _state(hass, entry, "sensor", "thunderstorm_potential")
    assert storm.state in ("low", "moderate", "high", "very_high")
    assert storm.attributes["options"] == ["low", "moderate", "high", "very_high"]
    assert "not a BoM category" in storm.attributes["method"]

    ffdi = _state(hass, entry, "sensor", "calculated_fire_danger_index")
    assert ffdi.entity_id.endswith("calculated_fire_danger_index_not_official")
    assert 0 < float(ffdi.state) < 100
    assert ffdi.attributes["calculated"] is True
    assert ffdi.attributes["official"] is False
    assert "Not an official fire danger rating" in ffdi.attributes["disclaimer"]
    assert ffdi.attributes["drought_factor_method"].startswith("experimental")
    assert 0 < ffdi.attributes["drought_factor"] <= 10

    gusts_on = _state(hass, entry, "binary_sensor", "damaging_gusts_forecast")
    assert gusts_on.state == "on"
    assert gusts_on.attributes["threshold"] == 30
    assert gusts_on.attributes["device_class"] == "safety"
    heat_off = _state(hass, entry, "binary_sensor", "extreme_heat_forecast")
    assert heat_off.state == "off"
    assert heat_off.attributes["threshold"] == 40
    assert heat_off.attributes["device_class"] == "heat"

    # Signals never appear as hazards or warning levels
    assert entry.runtime_data.active_hazards == []


async def test_weather_signals_unknown_without_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A forecast with no values in the window gives unknown states, not zero or off."""
    freezer.move_to(datetime(2026, 12, 1, tzinfo=UTC))  # beyond the sample
    entry = await _setup(hass, mock_config_entry, {CONF_WEATHER_SIGNALS: True})
    assert _state(hass, entry, "sensor", "max_wind_gust_24h").state == STATE_UNKNOWN
    assert _state(hass, entry, "sensor", "thunderstorm_potential").state == STATE_UNKNOWN
    assert _state(hass, entry, "sensor", "calculated_fire_danger_index").state == STATE_UNKNOWN
    assert _state(hass, entry, "binary_sensor", "damaging_gusts_forecast").state == STATE_UNKNOWN


async def test_forecast_failure_is_isolated_and_retried(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """An Open-Meteo outage leaves setup and hazards alone, retries sooner, and recovers."""
    freezer.move_to(FIXTURE_NOW)
    forecast = client.async_get_forecast.return_value
    client.async_get_forecast.side_effect = OpenMeteoError("HTTP 503")
    entry = await _setup(hass, mock_config_entry, {CONF_WEATHER_SIGNALS: True})

    assert entry.state is ConfigEntryState.LOADED
    weather = entry.runtime_data.forecasts.weather
    assert weather is not None
    assert weather.update_interval == FORECAST_RETRY_INTERVAL
    assert _state(hass, entry, "sensor", "max_wind_gust_24h").state == STATE_UNAVAILABLE
    assert _state(hass, entry, "sensor", "active_hazards_count").state == "0"

    client.async_get_forecast.side_effect = None
    client.async_get_forecast.return_value = forecast
    freezer.tick(FORECAST_RETRY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, entry, "sensor", "max_wind_gust_24h").state != STATE_UNAVAILABLE
    assert weather.update_interval == WEATHER_SIGNALS_INTERVAL


async def test_river_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Brisbane River sample: discharge, forecast attributes and flood risk; off-grid point is unknown."""
    freezer.move_to(FIXTURE_NOW)
    points = [{**BRISBANE, "horizon_days": 7, "baseline": 290.95}, WELLINGTON, {"id": "broken"}]
    entry = await _setup(hass, mock_config_entry, {CONF_RIVER_POINTS: points})
    client.async_get_river_forecasts.assert_awaited_once_with([(-27.47, 153.02), (-41.29, 174.78)])

    discharge = _state(hass, entry, "sensor", "river_discharge_p1")
    assert discharge.entity_id.endswith("river_discharge_brisbane_river")
    assert float(discharge.state) == 25.36
    assert discharge.attributes["unit_of_measurement"] == "m³/s"
    assert discharge.attributes[ATTR_ATTRIBUTION] == "Flood data by Open-Meteo.com (GloFAS, CC BY 4.0)"
    assert len(discharge.attributes["forecast"]) == 7
    assert discharge.attributes["forecast"][6] == {"date": "2026-10-21", "mean": 37.46, "max": 68.98, "p75": 31.66}
    assert discharge.attributes["p75"] == 25.95
    assert discharge.attributes["trend"] == "rising"
    assert discharge.attributes["grid_latitude"] == -27.474998

    risk = _state(hass, entry, "binary_sensor", "river_flood_risk_p1")
    assert risk.state == "on"  # ensemble maximum 68.98 m³/s on 21 Oct > 50
    assert risk.attributes["peak_date"] == "2026-10-21"
    assert risk.attributes["baseline_median_annual_peak"] == 290.95
    assert risk.attributes["basis"] == "ensemble maximum"

    assert _state(hass, entry, "sensor", "river_discharge_p2").state == STATE_UNKNOWN
    assert _state(hass, entry, "binary_sensor", "river_flood_risk_p2").state == STATE_UNKNOWN


async def test_river_flood_risk_respects_horizon(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Within the default 3-day horizon the Brisbane sample stays below 50 m³/s."""
    freezer.move_to(FIXTURE_NOW)
    entry = await _setup(hass, mock_config_entry, {CONF_RIVER_POINTS: [BRISBANE, WELLINGTON]})
    risk = _state(hass, entry, "binary_sensor", "river_flood_risk_p1")
    assert risk.state == "off"
    assert risk.attributes["horizon_days"] == 3
    assert risk.attributes["peak_maximum"] == 29.13


def test_river_points_clamps_horizon() -> None:
    """Out-of-range horizons are clamped; malformed points are skipped."""
    points = river_points([{**BRISBANE, "horizon_days": 30}, {**BRISBANE, "horizon_days": 0}, "x", None])
    assert [p.horizon_days for p in points] == [7, 1]
    assert river_points(None) == []


async def test_ai_ensemble_entities_and_polling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Experimental labelling, both attributions, and WeatherNext 2 fetched at most every 12 h."""
    freezer.move_to(FIXTURE_NOW)
    options = {CONF_AI_ENSEMBLE: True, CONF_AI_WEATHERNEXT: True, CONF_HEAVY_RAIN_THRESHOLD: 10}
    entry = await _setup(hass, mock_config_entry, options)
    client.async_get_ensemble.assert_awaited_once_with(-27.2657, 152.9818, [MODEL_AIFS, MODEL_WEATHERNEXT])

    p24 = _state(hass, entry, "sensor", "heavy_rain_probability_24h")
    assert p24.entity_id.endswith("experimental_ai_heavy_rain_probability_24h")
    assert p24.attributes["unit_of_measurement"] == "%"
    assert p24.attributes["experimental"] is True
    assert p24.attributes["official"] is False
    assert p24.attributes["notice"] == "Experimental AI model output. Not an official warning."
    assert "Google WeatherNext 2" in p24.attributes[ATTR_ATTRIBUTION]
    assert "ECMWF AIFS (CC BY 4.0)" in p24.attributes[ATTR_ATTRIBUTION]
    assert "models" not in p24.attributes
    assert 0 <= float(_state(hass, entry, "sensor", "heavy_rain_probability_72h").state) <= 100

    outlook = _state(hass, entry, "sensor", "ai_rain_outlook")
    assert outlook.attributes["unit_of_measurement"] == "mm"
    assert set(outlook.attributes["models"]) == {MODEL_AIFS, MODEL_WEATHERNEXT}
    assert outlook.attributes["models"][MODEL_AIFS]["members"] == 51
    assert outlook.attributes["models"][MODEL_WEATHERNEXT]["members"] == 64
    assert outlook.attributes["threshold_mm_24h"] == 10
    assert outlook.attributes["agreement_24h"] in (True, False)

    # 6 h later only AIFS has a new run; 12 h later both do
    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_get_ensemble.await_args.args[2] == [MODEL_AIFS]
    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_get_ensemble.await_args.args[2] == [MODEL_AIFS, MODEL_WEATHERNEXT]

    # A manual refresh within the run interval sends nothing
    calls = client.async_get_ensemble.await_count
    await entry.runtime_data.forecasts.ensemble.async_refresh()
    assert client.async_get_ensemble.await_count == calls


async def test_ai_ensemble_aifs_only_and_no_members(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """WeatherNext 2 stays off unless its own toggle is on; no members means unavailable."""
    freezer.move_to(FIXTURE_NOW)
    client.async_get_ensemble.side_effect = None
    client.async_get_ensemble.return_value = {}
    entry = await _setup(hass, mock_config_entry, {CONF_AI_ENSEMBLE: True})
    client.async_get_ensemble.assert_awaited_once_with(-27.2657, 152.9818, [MODEL_AIFS])
    state = _state(hass, entry, "sensor", "ai_rain_outlook")
    assert state.state == STATE_UNAVAILABLE
    assert "WeatherNext" not in state.attributes.get(ATTR_ATTRIBUTION, "")


async def test_switching_features_off_removes_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Disabling a feature or removing a river point removes its entities on reload."""
    freezer.move_to(FIXTURE_NOW)
    entry = await _setup(
        hass,
        mock_config_entry,
        {CONF_WEATHER_SIGNALS: True, CONF_AI_ENSEMBLE: True, CONF_RIVER_POINTS: [BRISBANE, WELLINGTON]},
    )
    registry = er.async_get(hass)

    def unique_ids() -> set[str]:
        return {
            e.unique_id.removeprefix(f"{entry.entry_id}_")
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        }

    assert {"max_wind_gust_24h", "ai_rain_outlook", "river_discharge_p2", "river_flood_risk_p1"} <= unique_ids()

    hass.config_entries.async_update_entry(entry, options={CONF_RIVER_POINTS: [BRISBANE]})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    remaining = unique_ids()
    assert "max_wind_gust_24h" not in remaining
    assert "damaging_gusts_forecast" not in remaining
    assert "ai_rain_outlook" not in remaining
    assert "river_discharge_p2" not in remaining
    assert "river_flood_risk_p2" not in remaining
    assert {"river_discharge_p1", "river_flood_risk_p1", "active_hazards_count"} <= remaining

    hass.config_entries.async_update_entry(entry, options={})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not any(key.startswith("river_") for key in unique_ids())


async def test_ai_ensemble_due_model_without_members_drops_its_run(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A due model missing from the response stops serving its old run; with none left it is unavailable."""
    freezer.move_to(FIXTURE_NOW)
    entry = await _setup(hass, mock_config_entry, {CONF_AI_ENSEMBLE: True, CONF_AI_WEATHERNEXT: True})
    outlook = _state(hass, entry, "sensor", "ai_rain_outlook")
    assert set(outlook.attributes["models"]) == {MODEL_AIFS, MODEL_WEATHERNEXT}

    # 12 h later both models are due but WeatherNext 2 comes back without members
    full = client.async_get_ensemble.side_effect
    client.async_get_ensemble.side_effect = lambda lat, lon, models: {
        m: r for m, r in full(lat, lon, models).items() if m == MODEL_AIFS
    }
    freezer.tick(timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_get_ensemble.await_args.args[2] == [MODEL_AIFS, MODEL_WEATHERNEXT]
    outlook = _state(hass, entry, "sensor", "ai_rain_outlook")
    assert set(outlook.attributes["models"]) == {MODEL_AIFS}

    # Next poll: AIFS is due and also comes back empty, so nothing current is left
    client.async_get_ensemble.side_effect = lambda lat, lon, models: {}
    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, entry, "sensor", "ai_rain_outlook").state == STATE_UNAVAILABLE


async def test_forecasts_follow_home_location(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Home-mode entries move weather and ensemble forecasts with Home Assistant's location."""
    freezer.move_to(FIXTURE_NOW)
    await hass.config.async_update(latitude=-27.47, longitude=153.02)
    home = MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        data={**mock_config_entry.data, "location_mode": "home"},
    )
    entry = await _setup(
        hass, home, {CONF_WEATHER_SIGNALS: True, CONF_AI_ENSEMBLE: True, CONF_RIVER_POINTS: [BRISBANE]}
    )
    forecasts = entry.runtime_data.forecasts
    assert forecasts.weather is not None
    assert forecasts.ensemble is not None
    client.async_get_forecast.assert_awaited_once_with(-27.47, 153.02)
    client.async_get_ensemble.reset_mock()

    await hass.config.async_update(latitude=-28.0, longitude=153.4)
    await entry.runtime_data.async_refresh()
    freezer.tick(timedelta(seconds=11))  # past the request_refresh debounce
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (forecasts.weather.latitude, forecasts.weather.longitude) == (-28.0, 153.4)
    assert client.async_get_forecast.await_args.args == (-28.0, 153.4)
    # Cached runs for the old point are discarded, so the model is fetched again at once
    client.async_get_ensemble.assert_awaited_once_with(-28.0, 153.4, [MODEL_AIFS])
    # River points are fixed coordinates and do not move
    assert forecasts.river is not None
    assert client.async_get_river_forecasts.await_args.args[0] == [(-27.47, 153.02)]

    # An unchanged location does not trigger another fetch
    calls = client.async_get_forecast.await_count
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert client.async_get_forecast.await_count == calls
