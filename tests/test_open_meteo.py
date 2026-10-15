"""Tests for the Open-Meteo client (#38, #39, #40). No live requests: captured samples are replayed."""

from __future__ import annotations

from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ausnz_disaster_watch.providers.open_meteo import (
    ENSEMBLE_URL,
    FLOOD_URL,
    FORECAST_URL,
    MODEL_AIFS,
    MODEL_WEATHERNEXT,
    USER_AGENT,
    OpenMeteoClient,
    OpenMeteoError,
    parse_ensemble,
    parse_forecast,
    parse_river,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> OpenMeteoClient:
    """Return a client on the mocked shared session."""
    return OpenMeteoClient(async_get_clientsession(hass))


async def test_forecast_request_and_parse(client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker) -> None:
    """One request with the verified variables; the Brisbane sample parses with UTC times."""
    aioclient_mock.get(FORECAST_URL, json=_load("forecast_brisbane.json"))
    forecast = await client.async_get_forecast(-27.47, 153.02)

    assert aioclient_mock.call_count == 1
    _, url, _, headers = aioclient_mock.mock_calls[0]
    query = url.query
    assert query["hourly"].split(",") == [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation_probability",
        "wind_speed_10m",
        "wind_gusts_10m",
        "cape",
        "weather_code",
    ]
    assert "lightning_potential" not in str(url)
    assert "models" not in query  # best match; bom_access_global/gfs_graphcast025 are all-null
    assert query["past_days"] == "20"
    assert query["forecast_days"] == "3"
    assert query["wind_speed_unit"] == "kmh"
    assert headers["User-Agent"] == USER_AGENT

    assert len(forecast.times) == 552
    assert forecast.times[0] == datetime(2026, 9, 25, 14, tzinfo=UTC)
    assert len(forecast.days) == 23
    assert forecast.daily["et0_fao_evapotranspiration"][0] == 3.95
    assert all(v is not None for v in forecast.hourly["cape"])


def test_parse_forecast_nulls_and_short_series() -> None:
    """Null, non-numeric and missing values become None; short series are padded."""
    payload = {
        "hourly": {"time": [0, 3600], "cape": [None, "x"], "wind_gusts_10m": [True, 5]},
        "daily": {"time": [0], "precipitation_sum": [1]},
    }
    forecast = parse_forecast(payload)
    assert forecast.hourly["cape"] == [None, None]
    assert forecast.hourly["wind_gusts_10m"] == [None, 5.0]
    assert forecast.hourly["temperature_2m"] == [None, None]
    assert forecast.daily["precipitation_sum"] == [1.0]
    assert forecast.daily["et0_fao_evapotranspiration"] == [None]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "unexpected payload"),
        ("nope", "unexpected payload"),
        ({"daily": {"time": [0]}}, "no time series"),
        ({"hourly": {"time": "0"}, "daily": {"time": [0]}}, "no time series"),
        ({"hourly": {"time": ["soon"]}, "daily": {"time": [0]}}, "invalid times"),
    ],
)
def test_parse_forecast_rejects_broken_payloads(payload: Any, message: str) -> None:
    """A structurally broken response is an error, not an empty forecast."""
    with pytest.raises(OpenMeteoError, match=message):
        parse_forecast(payload)


async def test_river_multi_location(client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker) -> None:
    """All points go in one request; the list answer is matched to points in order."""
    brisbane = _load("flood_brisbane.json")
    wellington = {
        "latitude": -41.274998,
        "longitude": 174.77502,
        "daily": {
            "time": brisbane["daily"]["time"],
            "river_discharge": [None] * 7,
            "river_discharge_max": [None] * 7,
            "river_discharge_p75": [None] * 7,
        },
    }
    aioclient_mock.get(FLOOD_URL, json=[brisbane, wellington])
    forecasts = await client.async_get_river_forecasts([(-27.47, 153.02), (-41.29, 174.78)])

    assert aioclient_mock.call_count == 1
    query = aioclient_mock.mock_calls[0][1].query
    assert query["latitude"] == "-27.4700,-41.2900"
    assert query["daily"] == "river_discharge,river_discharge_max,river_discharge_p75"
    assert query["timezone"] == "GMT"
    assert forecasts[0].has_data
    assert forecasts[0].days[0].day == date(2026, 10, 15)
    assert forecasts[0].days[0].mean == 25.36
    assert forecasts[0].days[6].maximum == 68.98
    assert forecasts[0].latitude == -27.474998
    assert not forecasts[1].has_data


async def test_river_location_count_mismatch(client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker) -> None:
    """An answer for fewer locations than requested is an error."""
    aioclient_mock.get(FLOOD_URL, json=_load("flood_brisbane.json"))
    with pytest.raises(OpenMeteoError, match="1 locations for 2 points"):
        await client.async_get_river_forecasts([(-27.47, 153.02), (-41.29, 174.78)])


def test_parse_river_bad_coordinates() -> None:
    """Non-numeric grid coordinates do not break parsing."""
    (forecast,) = parse_river({"latitude": "x", "daily": {"time": [0], "river_discharge": [1.0]}})
    assert forecast.latitude == 0.0
    assert forecast.longitude == 0.0
    assert forecast.days[0].mean == 1.0
    assert forecast.days[0].maximum is None


async def test_river_history(client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker) -> None:
    """The reanalysis request covers the given dates and drops null days."""
    aioclient_mock.get(FLOOD_URL, json={"daily": {"time": [1136073600, 1136160000], "river_discharge": [12.5, None]}})
    history = await client.async_get_river_history(-27.47, 153.02, date(2006, 1, 1), date(2025, 12, 31))
    query = aioclient_mock.mock_calls[0][1].query
    assert query["start_date"] == "2006-01-01"
    assert query["end_date"] == "2025-12-31"
    assert history == [(date(2006, 1, 1), 12.5)]


async def test_ensemble_two_models(client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker) -> None:
    """Both models in one request; member columns are grouped by model suffix."""
    aioclient_mock.get(ENSEMBLE_URL, json=_load("ensemble_brisbane.json"))
    runs = await client.async_get_ensemble(-27.47, 153.02, [MODEL_AIFS, MODEL_WEATHERNEXT])
    query = aioclient_mock.mock_calls[0][1].query
    assert query["models"] == f"{MODEL_AIFS},{MODEL_WEATHERNEXT}"
    assert query["hourly"] == "precipitation"
    assert len(runs[MODEL_AIFS].members) == 51
    assert len(runs[MODEL_WEATHERNEXT].members) == 64
    assert len(runs[MODEL_AIFS].times) == 96


def test_parse_ensemble_single_model_and_unknown_columns() -> None:
    """With one model the columns have no suffix; unrelated or other-model columns are ignored."""
    payload = {
        "hourly": {
            "time": [0],
            "precipitation": [1.0],
            "precipitation_member01": [2.0],
            "temperature_2m": [20.0],
        }
    }
    runs = parse_ensemble(payload, [MODEL_AIFS])
    assert runs[MODEL_AIFS].members == [[1.0], [2.0]]
    # Unsuffixed columns are ambiguous with two models, and a model without columns is left out
    assert parse_ensemble(payload, [MODEL_AIFS, MODEL_WEATHERNEXT]) == {}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"status": 400, "json": {"error": True, "reason": "Latitude must be in range"}}, "HTTP 400: Latitude"),
        ({"status": 200, "json": {"error": True, "reason": "Too many requests"}}, "HTTP 200: Too many"),
        ({"status": 429, "json": ["limit"]}, "HTTP 429: no reason given"),
        ({"status": 502, "text": "<html>Bad gateway</html>"}, "HTTP 502 with invalid JSON"),
        ({"exc": aiohttp.ClientConnectionError("reset")}, "unavailable"),
        ({"exc": TimeoutError()}, "unavailable"),
    ],
)
async def test_request_failures(
    client: OpenMeteoClient, aioclient_mock: AiohttpClientMocker, kwargs: dict[str, Any], message: str
) -> None:
    """Every failure becomes OpenMeteoError after a single attempt."""
    aioclient_mock.get(ENSEMBLE_URL, **kwargs)
    with pytest.raises(OpenMeteoError, match=message):
        await client.async_get_ensemble(-27.47, 153.02, [MODEL_AIFS])
    assert aioclient_mock.call_count == 1
