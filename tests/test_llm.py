"""Read-only LLM tools for Assist (#72)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import llm as llm_platform
from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    FireDangerDay,
    FireDangerOutlook,
    FireDangerRating,
    FireSeasonStatus,
    HazardType,
    PowerOutageItem,
    RoadClosureItem,
    WarningLevel,
    WeatherWarningItem,
)
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.fire_danger import local_today
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ASSISTANT = "conversation"
TOOL_NAMES = [
    f"{DOMAIN}__get_disaster_situation",
    f"{DOMAIN}__get_fire_danger",
    f"{DOMAIN}__list_hazards",
]


class _Provider:
    """Hazard provider stub with a class name the register knows."""

    provides_hazards = True

    def __init__(self) -> None:
        self.hazards: list[CanonicalHazard] = []
        self.error: Exception | None = None
        self.roads: list[RoadClosureItem] = []
        self.outages: list[PowerOutageItem] = []
        self.warnings: list[WeatherWarningItem] = []

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        if self.error:
            raise self.error
        return self.hazards

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        return self.roads

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        return self.outages

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        return self.warnings

    def __getattr__(self, name: str) -> Any:
        # Every other provider hook returns nothing
        return AsyncMock(return_value=None)


QueenslandHazardProvider = type("QueenslandHazardProvider", (_Provider,), {})


@pytest.fixture
def provider() -> Generator[_Provider]:
    """Patch provider construction with one Queensland stub provider."""
    stub = QueenslandHazardProvider()
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[stub],
    ):
        yield stub


def _hazard(hazard_id: str, level: WarningLevel, hazard_type: HazardType, lat: float, **kwargs: Any) -> CanonicalHazard:
    return CanonicalHazard(
        id=hazard_id,
        source="Queensland Fire Department",
        title=f"{level.value} {hazard_type.value} {hazard_id}",
        hazard_type=hazard_type,
        warning_level=level,
        latitude=lat,
        longitude=152.9818,
        updated_at=dt_util.utcnow(),
        **kwargs,
    )


def _context() -> llm.LLMContext:
    return llm.LLMContext(platform="test", context=Context(), language="en", assistant=ASSISTANT, device_id=None)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, *, expose: bool = True) -> None:
    """Set up the entry and expose (or hide) all its entities to Assist."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        async_expose_entity(hass, ASSISTANT, entity.entity_id, expose)


async def _call(hass: HomeAssistant, name: str, args: dict[str, Any] | None = None) -> llm.ToolResult:
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    result = await api.async_call_tool(llm.ToolInput(tool_name=name, tool_args=args or {}))
    json.dumps(result.data)  # every answer is JSON-serialisable
    return result


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_tools_offered_to_assist_only_when_exposed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """The tools are prefixed, tagged and read-only; other APIs and hidden entries get none."""
    await _setup(hass, mock_config_entry)

    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    ours = [tool for tool in api.tools if tool.integration == DOMAIN]
    assert [tool.name for tool in ours] == TOOL_NAMES
    for tool in ours:
        assert tool.annotations == llm.ToolAnnotations(
            read_only=True, destructive=False, idempotent=True, open_world=False
        )
        assert tool.title
        assert probatio.to_openapi(tool.parameters)["properties"]["entry"]["type"] == "string"
    assert "never describe the situation as all clear" in api.api_prompt
    assert "000" in api.api_prompt
    assert "111" in api.api_prompt

    assert llm_platform.async_get_tools(hass, _context(), "other_api") is None

    for entity in er.async_entries_for_config_entry(er.async_get(hass), mock_config_entry.entry_id):
        async_expose_entity(hass, ASSISTANT, entity.entity_id, False)
    assert llm_platform.async_get_tools(hass, _context(), llm.LLM_API_ASSIST) is None


async def test_no_entries_offers_no_tools(hass: HomeAssistant) -> None:
    """Without a loaded entry nothing is offered."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert llm_platform.async_get_tools(hass, _context(), llm.LLM_API_ASSIST) is None


async def test_situation_reports_hazards_and_healthy_feeds(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """The situation lists hazards nearest first (capped), roads, outages, warnings and feed health."""
    provider.hazards = [
        _hazard(f"far_{index}", WarningLevel.ADVICE, HazardType.FLOOD, -27.2657 - index * 0.01)
        for index in range(1, 12)
    ] + [
        _hazard(
            "near",
            WarningLevel.EMERGENCY_WARNING,
            HazardType.BUSHFIRE,
            -27.2657,
            responsible_agency="QFD",
            web_url="https://www.fire.qld.gov.au",
            call_to_action="Leave now. " * 50,
        )
    ]
    provider.roads = [
        RoadClosureItem(id="r1", road="Bruce Hwy", status="Closed", reason="Flooded", latitude=-27.3, longitude=152.98),
        RoadClosureItem(id="r2", road="Unlocated Rd", status="Closed"),
    ]
    provider.outages = [
        PowerOutageItem(suburb="Strathpine", customers_affected=120, latitude=-27.3, longitude=152.99),
        PowerOutageItem(suburb="Unknown"),
    ]
    provider.warnings = [WeatherWarningItem(title="Flood Watch", locations="Moreton Bay", link="https://bom.gov.au")]
    await _setup(hass, mock_config_entry)

    result = await _call(hass, TOOL_NAMES[0])
    data = result.data
    assert result.error is False
    assert data["entry"] == mock_config_entry.title
    assert data["highest_warning_level"] == "Emergency Warning"
    assert data["hazard_count"] == 12
    assert len(data["hazards"]) == llm_platform.MAX_SITUATION_HAZARDS
    first = data["hazards"][0]
    assert first["title"].endswith("near")
    assert first["category"] == "fire"
    assert first["agency"] == "QFD"
    assert first["distance_km"] == 0.0
    assert len(first["call_to_action"]) == llm_platform.MAX_TEXT_LENGTH
    assert first["attribution"]
    assert data["hazards"][1]["agency"] == "Queensland Fire Department"
    assert data["road_closure_count"] == 2
    assert data["road_closures"][0]["road"] == "Bruce Hwy"
    assert data["road_closures"][1]["distance_km"] is None
    assert data["power_outage_count"] == 2
    assert data["power_outages"][0]["suburb"] == "Strathpine"
    assert data["power_outages"][0]["distance_km"] is not None
    assert data["power_outages"][1]["distance_km"] is None
    assert data["weather_warnings"][0]["agency"] == "Bureau of Meteorology"
    assert data["fire_danger"]["today"]["rating"] is None
    health = data["feed_health"]
    assert health["complete"] is True
    assert "notice" not in health
    assert health["feeds"][0]["feed"] == "QueenslandHazardProvider"
    assert health["feeds"][0]["status"] == "ok"
    assert health["feeds"][0]["last_success"] is not None
    assert "Queensland Fire Department" in health["feeds"][0]["sources"]


async def test_failed_feed_is_never_an_all_clear(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """A failed or stale feed is reported; zero hazards then is not complete."""
    second = type("BoMHazardProvider", (_Provider,), {})()
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[provider, second],
    ):
        await _setup(hass, mock_config_entry)
    second.error = ProviderUnavailableError("down")
    await _refresh(hass, mock_config_entry)

    data = (await _call(hass, TOOL_NAMES[0])).data
    assert data["hazard_count"] == 0
    assert data["highest_warning_level"] is None
    health = data["feed_health"]
    assert health["complete"] is False
    # The feed worked once, so its last good (empty) result still stands in
    assert {feed["feed"]: feed["status"] for feed in health["feeds"]} == {
        "QueenslandHazardProvider": "ok",
        "BoMHazardProvider": "stale",
    }
    assert "BoMHazardProvider (stale)" in health["notice"]
    assert "not an all-clear" in health["notice"]

    # Past the last-good window the feed is failed
    coordinator = mock_config_entry.runtime_data
    when, hazards = coordinator._last_good_hazards["BoMHazardProvider"]
    coordinator._last_good_hazards["BoMHazardProvider"] = (when - timedelta(hours=1), hazards)
    health = (await _call(hass, TOOL_NAMES[2])).data["feed_health"]
    assert {feed["feed"]: feed["status"] for feed in health["feeds"]}["BoMHazardProvider"] == "failed"

    # When every feed fails the whole update fails and even "ok" feeds are stale
    provider.error = ProviderUnavailableError("down")
    await _refresh(hass, mock_config_entry)
    assert coordinator.last_update_success is False
    provider.error = None
    coordinator._feeds_ok, coordinator._feeds_failed = ["QueenslandHazardProvider"], []
    health = (await _call(hass, TOOL_NAMES[1])).data["feed_health"]
    assert health["complete"] is False
    assert health["feeds"][0]["status"] == "stale"


async def test_no_data_yet_is_unknown(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """Without data the situation is unknown, not all clear."""
    await _setup(hass, mock_config_entry)
    mock_config_entry.runtime_data.data = None
    health = (await _call(hass, TOOL_NAMES[0])).data["feed_health"]
    assert health["complete"] is False
    assert "unknown" in health["notice"]


async def test_list_hazards_filters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """Category, distance and level filters; roads and outages under their categories."""
    provider.hazards = [
        _hazard("fire", WarningLevel.WATCH_AND_ACT, HazardType.GRASS_FIRE, -27.2657),
        _hazard("flood", WarningLevel.ADVICE, HazardType.FLOOD, -27.4),
        _hazard("crash", WarningLevel.INFORMATION, HazardType.ROAD_INCIDENT, -27.27),
        _hazard("gas", WarningLevel.ADVICE, HazardType.HAZMAT, -27.3),
    ]
    provider.roads = [RoadClosureItem(id="r1", road="Bruce Hwy", latitude=-27.3, longitude=152.98)]
    provider.outages = [PowerOutageItem(suburb="Strathpine", latitude=-27.3, longitude=152.99)]
    await _setup(hass, mock_config_entry)

    data = (await _call(hass, TOOL_NAMES[2])).data
    assert data["total"] == 4
    assert data["truncated"] is False

    data = (await _call(hass, TOOL_NAMES[2], {"category": "fire"})).data
    assert [item["title"].split()[-1] for item in data["items"]] == ["fire"]
    assert [item["category"] for item in (await _call(hass, TOOL_NAMES[2], {"category": "other"})).data["items"]] == [
        "other"
    ]

    data = (await _call(hass, TOOL_NAMES[2], {"category": "road"})).data
    assert [item["category"] for item in data["items"]] == ["road", "road"]
    data = (await _call(hass, TOOL_NAMES[2], {"category": "road", "min_level": "advice"})).data
    assert data["items"] == []
    data = (await _call(hass, TOOL_NAMES[2], {"category": "power"})).data
    assert data["items"][0]["suburb"] == "Strathpine"

    data = (await _call(hass, TOOL_NAMES[2], {"min_level": "watch_and_act"})).data
    assert [item["warning_level"] for item in data["items"]] == ["Watch and Act"]

    data = (await _call(hass, TOOL_NAMES[2], {"max_distance_km": "5"})).data
    assert data["filters"]["max_distance_km"] == 5.0
    assert {item["title"].split()[-1] for item in data["items"]} == {"fire", "crash", "gas"}

    result = await _call(hass, TOOL_NAMES[2], {"category": "volcano"})
    assert result.error is True
    assert "Invalid arguments" in result.data["error"]


async def test_list_hazards_caps_output(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """At most MAX_LISTED_ITEMS items are returned, with the total."""
    provider.hazards = [
        _hazard(f"h{index}", WarningLevel.ADVICE, HazardType.FLOOD, -27.2657 - index * 0.001) for index in range(30)
    ]
    await _setup(hass, mock_config_entry)
    data = (await _call(hass, TOOL_NAMES[2])).data
    assert data["total"] == 30
    assert data["truncated"] is True
    assert len(data["items"]) == llm_platform.MAX_LISTED_ITEMS


async def test_fire_danger_days(hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider) -> None:
    """Fire danger comes from the outlook by local day, else today's single rating, else nothing."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    today = local_today("Australia/Brisbane")
    coordinator.data.fire_outlook = FireDangerOutlook(
        district_number="QLD_FW010",
        district_name="Southeast Coast",
        time_zone="Australia/Brisbane",
        source="Bureau of Meteorology",
        days=[
            FireDangerDay(date=today, rating="High", fire_behaviour_index=30, total_fire_ban=False),
            FireDangerDay(date=today + timedelta(days=1), rating="Extreme", total_fire_ban=True),
        ],
    )
    data = (await _call(hass, TOOL_NAMES[1], {"day": "tomorrow"})).data
    assert data["fire_danger"]["rating"] == "Extreme"
    assert data["fire_danger"]["total_fire_ban"] is True
    assert data["fire_danger"]["district"] == "Southeast Coast"
    data = (await _call(hass, TOOL_NAMES[1])).data
    assert data["fire_danger"]["rating"] == "High"
    data = (await _call(hass, TOOL_NAMES[1], {"day": "day4"})).data
    assert data["fire_danger"]["rating"] is None

    coordinator.data.fire_outlook = None
    coordinator.data.fire_danger = FireDangerRating(district_name="Southeast Coast", rating="Moderate")
    data = (await _call(hass, TOOL_NAMES[1])).data
    assert data["fire_danger"]["rating"] == "Moderate"
    data = (await _call(hass, TOOL_NAMES[1], {"day": "tomorrow"})).data
    assert "notice" in data["fire_danger"]

    coordinator.data.fire_season = FireSeasonStatus(season="restricted", zone="Canterbury")
    data = (await _call(hass, TOOL_NAMES[1])).data
    assert data["fire_danger"]["fire_season"] == "restricted"
    assert data["fire_danger"]["agency"] == "Fire and Emergency New Zealand"


async def test_entry_selection(hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider) -> None:
    """With several entries the tool lists them; titles and entry IDs select one; hidden entries stay out."""
    await _setup(hass, mock_config_entry)
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Disaster Watch (NZ - Christchurch)",
        data={**mock_config_entry.data, "state": "NZ", "location_name": "Christchurch"},
        unique_id="second",
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    hidden = MockConfigEntry(domain=DOMAIN, title="Hidden", data=dict(mock_config_entry.data), unique_id="hidden")
    hidden.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hidden.entry_id)
    await hass.async_block_till_done()
    for entity in er.async_entries_for_config_entry(er.async_get(hass), second.entry_id):
        async_expose_entity(hass, ASSISTANT, entity.entity_id, True)
    for entity in er.async_entries_for_config_entry(er.async_get(hass), hidden.entry_id):
        async_expose_entity(hass, ASSISTANT, entity.entity_id, False)

    result = await _call(hass, TOOL_NAMES[0])
    assert result.error is True
    assert sorted(result.data["entries"]) == sorted([mock_config_entry.title, second.title])

    data = (await _call(hass, TOOL_NAMES[0], {"entry": "disaster watch (nz - christchurch)"})).data
    assert data["entry"] == second.title
    assert data["weather_warnings"] == []
    data = (await _call(hass, TOOL_NAMES[1], {"entry": mock_config_entry.entry_id})).data
    assert data["entry"] == mock_config_entry.title

    result = await _call(hass, TOOL_NAMES[0], {"entry": "Hidden"})
    assert result.error is True
    assert "Hidden" not in result.data["entries"]


async def test_unloaded_entry_reports_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, provider: _Provider
) -> None:
    """A tool built before the entry unloaded answers with an error instead of stale data."""
    await _setup(hass, mock_config_entry)
    tools = llm_platform.async_get_tools(hass, _context(), llm.LLM_API_ASSIST)
    assert tools is not None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    result = await tools.tools[0].async_call(hass, llm.ToolInput(tool_name=TOOL_NAMES[0], tool_args={}), _context())
    assert result.error is True
    assert "not loaded" in result.data["error"]


async def test_nz_weather_warnings_credit_metservice(hass: HomeAssistant, provider: _Provider) -> None:
    """New Zealand weather warnings name MetService."""
    provider.warnings = [WeatherWarningItem(title="Heavy Rain Watch")]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NZ",
        data={"state": "NZ", "location_mode": "custom", "latitude": -43.53, "longitude": 172.63, "radius": 50},
        unique_id="nz",
    )
    await _setup(hass, entry)
    data = (await _call(hass, TOOL_NAMES[0])).data
    assert data["weather_warnings"][0]["agency"] == "MetService"
