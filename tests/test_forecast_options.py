"""Options flow tests for the Open-Meteo forecast features (#38, #39, #40)."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import (
    CONF_AI_ENSEMBLE,
    CONF_AI_WEATHERNEXT,
    CONF_GUST_THRESHOLD,
    CONF_HEAT_THRESHOLD,
    CONF_HEAVY_RAIN_THRESHOLD,
    CONF_RADIUS,
    CONF_RIVER_POINTS,
    CONF_WEATHER_SIGNALS,
    DOMAIN,
)
from custom_components.ausnz_disaster_watch.providers.open_meteo import OpenMeteoError, RiverDay, RiverForecast
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant

POINT = {"id": "p1", "name": "Brisbane River", "latitude": -27.47, "longitude": 153.02, "threshold": 300.0}
WET = RiverForecast(-27.475, 153.025, [RiverDay(date(2026, 10, 15), 25.0, 29.0, 26.0)])
WETTER = RiverForecast(-27.425, 153.075, [RiverDay(date(2026, 10, 15), 80.0, 90.0, 85.0)])
DRY = RiverForecast(-41.275, 174.775, [RiverDay(date(2026, 10, 15), None, None, None)])
# 20 years of a peak equal to the year number minus 2000 (median 15.5)
HISTORY = [(date(year, 1 + d // 28, 1 + d % 28), float(year - 2000)) for year in range(2006, 2026) for d in range(300)]


@pytest.fixture
def client() -> Generator[MagicMock]:
    """Patch the client used by the options flow."""
    instance = MagicMock()
    instance.async_get_river_forecasts = AsyncMock(return_value=[WET])
    instance.async_get_river_history = AsyncMock(return_value=HISTORY)
    with patch("custom_components.ausnz_disaster_watch.forecast_options.OpenMeteoClient", return_value=instance):
        yield instance


@pytest.fixture(autouse=True)
async def no_setup(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Keep the reload that follows an options save from setting up real feeds, and let it finish."""
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        yield
        await hass.async_block_till_done()


def _entry(hass: HomeAssistant, base: MockConfigEntry, options: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=base.title, data=dict(base.data), options=options, unique_id="x")
    entry.add_to_hass(hass)
    return entry


async def _open(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> dict[str, Any]:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.MENU
    return await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": step})


async def _add(hass: HomeAssistant, entry: MockConfigEntry, name: str = "Brisbane River") -> dict[str, Any]:
    result = await _open(hass, entry, "add_river_point")
    assert result["step_id"] == "add_river_point"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": name, "location": {"latitude": -27.47, "longitude": 153.02}}
    )


async def test_forecasts_step_keeps_other_options(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Saving the forecast toggles keeps river points and monitoring settings."""
    entry = _entry(hass, mock_config_entry, {CONF_RADIUS: 80, CONF_RIVER_POINTS: [POINT]})
    result = await _open(hass, entry, "forecasts")
    assert result["step_id"] == "forecasts"
    schema = {str(k): k.default() for k in result["data_schema"].schema}
    assert schema[CONF_WEATHER_SIGNALS] is False
    assert schema[CONF_AI_ENSEMBLE] is False
    assert schema[CONF_AI_WEATHERNEXT] is False
    assert schema[CONF_GUST_THRESHOLD] == 90
    assert schema[CONF_HEAT_THRESHOLD] == 40
    assert schema[CONF_HEAVY_RAIN_THRESHOLD] == 50

    user_input = {
        CONF_WEATHER_SIGNALS: True,
        CONF_GUST_THRESHOLD: 100,
        CONF_HEAT_THRESHOLD: 42,
        CONF_AI_ENSEMBLE: True,
        CONF_AI_WEATHERNEXT: False,
        CONF_HEAVY_RAIN_THRESHOLD: 60,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_RADIUS: 80, CONF_RIVER_POINTS: [POINT], **user_input}


async def test_add_river_point(hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock) -> None:
    """A point on the river grid goes straight to the threshold, defaulting to the baseline."""
    entry = _entry(hass, mock_config_entry, {CONF_RADIUS: 80})
    result = await _add(hass, entry)
    assert result["step_id"] == "river_threshold"
    assert result["description_placeholders"] == {"name": "Brisbane River", "baseline": "15.50 m³/s"}
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {"threshold": 15.5, "horizon_days": 3}
    history_args = client.async_get_river_history.await_args.args
    assert history_args[2].month == 1
    assert history_args[3].month == 12
    assert history_args[3].year - history_args[2].year == 19

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"threshold": 20, "horizon_days": 5})
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    (point,) = entry.options[CONF_RIVER_POINTS]
    assert len(point["id"]) == 32
    assert {k: v for k, v in point.items() if k != "id"} == {
        "name": "Brisbane River",
        "latitude": -27.47,
        "longitude": 153.02,
        "baseline": 15.5,
        "threshold": 20.0,
        "horizon_days": 5,
    }
    assert entry.options[CONF_RADIUS] == 80


async def test_add_off_grid_point_accepts_suggestion(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """An off-grid point probes neighbours in one request and offers the largest river."""
    client.async_get_river_forecasts.side_effect = [[DRY], [DRY] * 14 + [WET, WETTER]]
    client.async_get_river_history.side_effect = OpenMeteoError("down")
    entry = _entry(hass, mock_config_entry, {})
    result = await _add(hass, entry)

    probe = client.async_get_river_forecasts.await_args_list[1].args[0]
    assert len(probe) == 16
    assert result["step_id"] == "river_suggestion"
    assert result["description_placeholders"]["latitude"] == "-27.425"
    assert result["description_placeholders"]["discharge"] == "80.00"
    assert float(result["description_placeholders"]["distance"]) > 0

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"use_suggestion": True})
    # Without a baseline the threshold has no default and must be entered
    assert result["step_id"] == "river_threshold"
    assert result["description_placeholders"]["baseline"] == "not available"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"threshold": 0, "horizon_days": 3})
    assert result["errors"] == {"threshold": "invalid_threshold"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"threshold": 100, "horizon_days": 3})
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    (point,) = entry.options[CONF_RIVER_POINTS]
    assert (point["latitude"], point["longitude"], point["baseline"]) == (-27.425, 153.075, None)


async def test_add_off_grid_point_declines_suggestion(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Declining the suggestion returns to the form with the original location."""
    client.async_get_river_forecasts.side_effect = [[DRY], [WET] + [DRY] * 15]
    entry = _entry(hass, mock_config_entry, {})
    result = await _add(hass, entry)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"use_suggestion": False})
    assert result["step_id"] == "add_river_point"
    assert result["errors"] == {"base": "no_river_cell"}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        ([[DRY], [DRY] * 16], "no_river_cell"),
        (OpenMeteoError("down"), "cannot_connect"),
        ([[DRY], OpenMeteoError("down")], "cannot_connect"),
    ],
)
async def test_add_point_errors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock, side_effect: Any, error: str
) -> None:
    """No nearby river cell, or Open-Meteo down, shows an error on the form."""
    client.async_get_river_forecasts.side_effect = side_effect
    entry = _entry(hass, mock_config_entry, {})
    result = await _add(hass, entry)
    assert result["step_id"] == "add_river_point"
    assert result["errors"] == {"base": error}


async def test_add_point_name_rules(hass: HomeAssistant, mock_config_entry: MockConfigEntry, client: MagicMock) -> None:
    """Names must be non-empty and unique; at most 10 points."""
    entry = _entry(hass, mock_config_entry, {CONF_RIVER_POINTS: [POINT]})
    result = await _add(hass, entry, name="brisbane river")
    assert result["errors"] == {"name": "duplicate_river_point"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "  ", "location": {"latitude": -27.47, "longitude": 153.02}}
    )
    assert result["errors"] == {"name": "duplicate_river_point"}
    client.async_get_river_forecasts.assert_not_called()

    full = _entry(hass, mock_config_entry, {CONF_RIVER_POINTS: [{**POINT, "id": str(i)} for i in range(10)]})
    result = await _open(hass, full, "add_river_point")
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "too_many_river_points"


async def test_edit_and_remove_river_points(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """With points configured the menu offers edit and remove."""
    second = {**POINT, "id": "p2", "name": "Bremer River", "baseline": 120.0}
    entry = _entry(hass, mock_config_entry, {CONF_RADIUS: 80, CONF_RIVER_POINTS: [POINT, second]})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"] == [
        "settings",
        "forecasts",
        "add_river_point",
        "edit_river_point",
        "remove_river_point",
    ]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "edit_river_point"})
    assert result["step_id"] == "edit_river_point"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"point": "p2"})
    assert result["step_id"] == "edit_river_point_details"
    assert result["description_placeholders"] == {"name": "Bremer River", "baseline": "120.00 m³/s"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"threshold": 0, "horizon_days": 2})
    assert result["errors"] == {"threshold": "invalid_threshold"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"threshold": 150, "horizon_days": 2})
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RIVER_POINTS] == [POINT, {**second, "threshold": 150.0, "horizon_days": 2}]

    result = await _open(hass, entry, "edit_river_point")
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"point": "p1"})
    assert result["description_placeholders"]["baseline"] == "not available"

    result = await _open(hass, entry, "remove_river_point")
    assert result["step_id"] == "remove_river_point"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"point": ["p1"]})
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert [p["id"] for p in entry.options[CONF_RIVER_POINTS]] == ["p2"]
    assert entry.options[CONF_RADIUS] == 80
