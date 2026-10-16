"""Tests for the opt-in Geoscience Australia earthquake provider (#23).

``fixtures/ga_earthquakes_seven_days.json`` is a trimmed live WFS response captured on
2026-10-16, including one of the layer's placeholder rows (no event ID, dated 2100).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import (
    CONF_INCLUDE_EARTHQUAKES,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    STATE_NZ,
)
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import GAEarthquakeProvider, get_providers_for_config
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.ga_earthquakes import GA_EARTHQUAKES_URL, quake_level
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant

FIXTURE = Path(__file__).parent / "fixtures" / "ga_earthquakes_seven_days.json"


def _payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _provider(hass: HomeAssistant, payload: Any) -> GAEarthquakeProvider:
    provider = GAEarthquakeProvider(hass, AsyncMock(), {"state": "WA"})
    provider.async_fetch_json = AsyncMock(return_value=payload)
    return provider


@pytest.mark.parametrize(
    ("magnitude", "level"),
    [
        (9.1, WarningLevel.WATCH_AND_ACT),
        (6.0, WarningLevel.WATCH_AND_ACT),
        (5.9, WarningLevel.ADVICE),
        (4.5, WarningLevel.ADVICE),
        (4.4, WarningLevel.INFORMATION),
        (3.0, WarningLevel.INFORMATION),
    ],
)
def test_quake_level(magnitude: float, level: WarningLevel) -> None:
    """Levels follow magnitude (GA publishes no felt intensity)."""
    assert quake_level(magnitude) is level


async def test_ga_earthquakes_parse_recent_significant_quakes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """M3+ quakes from the last 48 hours become hazards.

    Old quakes, rows GA hides from its map (``display_flag`` "N", e.g. the M4.7 Chile quake
    and the placeholder row) and small quakes do not.
    """
    freezer.move_to("2026-10-15T14:00:00+00:00")
    payload = _payload()
    by_id = {f["properties"]["event_id"]: f for f in payload["features"]}
    # A small quake in WA, recent enough, made M4.7 to check the Advice level
    by_id["ga2026uhunoc"]["properties"]["preferred_magnitude"] = 4.7
    payload["features"].append({"type": "Feature"})  # malformed: skipped, not fatal
    provider = _provider(hass, payload)
    assert provider.state_code == "AU"

    hazards = {h.id: h for h in await provider.async_fetch_hazards()}
    provider.async_fetch_json.assert_awaited_once_with(GA_EARTHQUAKES_URL, headers=None)
    assert sorted(hazards) == [
        "ga_quake_ga2026uhunoc",
        "ga_quake_ga2026uhvtmh",
        "ga_quake_ga2026ukjmsp",
        "ga_quake_ga2026ukndhi",
    ]
    wa = hazards["ga_quake_ga2026uhunoc"]
    assert wa.title == "M4.7 Earthquake - Great Victoria Desert, WA"
    assert wa.hazard_type is HazardType.EARTHQUAKE
    assert wa.warning_level is WarningLevel.ADVICE
    assert wa.source == wa.responsible_agency == "Geoscience Australia"
    assert wa.web_url == "https://earthquakes.ga.gov.au/event/ga2026uhunoc"
    assert wa.updated_at is not None
    assert wa.updated_at.isoformat() == "2026-10-13T18:08:04.410000+00:00"
    assert wa.raw_properties["located_in_australia"] is True
    assert wa.raw_properties["magnitude"] == 4.7
    assert wa.raw_properties["depth_km"] == 6.9
    assert hazards["ga_quake_ga2026ukndhi"].warning_level is WarningLevel.ADVICE  # M5.1
    assert hazards["ga_quake_ga2026ukndhi"].status == "Confirmed"


async def test_ga_earthquakes_edge_cases(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Unknown depth/status and future-dated rows; broken payloads are a feed failure."""
    freezer.move_to("2026-10-15T14:00:00+00:00")
    payload = _payload()
    quake = next(f for f in payload["features"] if f["properties"]["event_id"] == "ga2026ukndhi")
    quake["properties"].update(depth=None, evaluation_status=None, description=None)
    future = copy.deepcopy(quake)
    future["properties"].update(event_id="ga2099future", origin_time="2026-10-16T14:00:00Z")
    payload["features"] = [quake, future]
    hazards = await _provider(hass, payload).async_fetch_hazards()
    assert len(hazards) == 1
    assert hazards[0].raw_properties["depth_km"] is None
    assert hazards[0].status is None
    assert hazards[0].location_name == "Unknown location"

    with pytest.raises(ProviderUnavailableError):
        await _provider(hass, ["not", "a", "dict"]).async_fetch_hazards()

    # Every displayed event malformed (e.g. a renamed field) is a feed failure, not an all-clear
    broken = _payload()
    for feature in broken["features"]:
        feature["properties"].pop("preferred_magnitude")
    with pytest.raises(ProviderUnavailableError, match="malformed"):
        await _provider(hass, broken).async_fetch_hazards()
    # A missing display flag is a format change too, not a hidden row
    no_flag = _payload()
    for feature in no_flag["features"]:
        feature["properties"].pop("display_flag")
    with pytest.raises(ProviderUnavailableError, match="malformed"):
        await _provider(hass, no_flag).async_fetch_hazards()
    # Only hidden rows, or nothing at all: a genuinely quiet feed
    hidden = {"features": [f for f in _payload()["features"] if f["properties"]["display_flag"] == "N"]}
    assert await _provider(hass, hidden).async_fetch_hazards() == []
    assert await _provider(hass, {"features": []}).async_fetch_hazards() == []
    with pytest.raises(ProviderUnavailableError):
        await _provider(hass, {"features": None}).async_fetch_hazards()


@pytest.mark.parametrize(
    ("state", "include", "expected"),
    [("QLD", True, True), ("QLD", False, False), ("WA", None, False), (STATE_NZ, True, False)],
)
def test_ga_earthquakes_are_opt_in(hass: HomeAssistant, state: str, include: bool | None, expected: bool) -> None:
    """The provider is added only for Australian entries that opt in."""
    config: dict[str, Any] = {"state": state}
    if include is not None:
        config[CONF_INCLUDE_EARTHQUAKES] = include
    providers = get_providers_for_config(hass, AsyncMock(), config)
    assert any(isinstance(p, GAEarthquakeProvider) for p in providers) is expected


async def test_options_flow_earthquake_toggle(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Australian entries opt in from their own options menu step; it defaults to off."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RADIUS: 75})
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert "earthquakes" in result["menu_options"]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "earthquakes"})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "earthquakes"
    field = next(key for key in result["data_schema"].schema if key == CONF_INCLUDE_EARTHQUAKES)
    assert field.default() is False

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_INCLUDE_EARTHQUAKES: True})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_INCLUDE_EARTHQUAKES] is True
    # Options other steps own are kept
    assert mock_config_entry.options[CONF_RADIUS] == 75


async def test_options_flow_has_no_earthquake_toggle_for_nz(hass: HomeAssistant) -> None:
    """New Zealand entries already get GeoNet quakes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATE: STATE_NZ,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_LOCATION_NAME: "Wellington",
            CONF_LATITUDE: -41.29,
            CONF_LONGITUDE: 174.78,
            CONF_RADIUS: 50,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert "earthquakes" not in result["menu_options"]
