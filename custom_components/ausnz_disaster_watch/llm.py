"""Read-only LLM tools for Assist and LLM conversation agents (#72).

The ``llm`` integration discovers this platform and calls ``async_get_tools`` for every
request. The tools are offered to the built-in Assist API only, and only for config
entries with at least one entity exposed to the requesting assistant, so they respect the
user's exposure choices. They read the coordinators' in-memory data and do no I/O.

Every answer carries feed health: a stale or failed feed is reported with the time of its
last good fetch, and the answer is then never complete, so it cannot read as an all-clear.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, override

import probatio

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext, Tool, ToolAnnotations, ToolInput, ToolResult
from homeassistant.util.json import JsonValueType

from .const import DOMAIN
from .coordinator import calculate_haversine_distance
from .models import CanonicalHazard, HazardType, WarningLevel
from .providers.fire_danger import local_today
from .providers.sources import sources_for_provider

if TYPE_CHECKING:
    from .coordinator import AustralianDisasterWatchCoordinator

PROMPT: Final = (
    "Use the Australia and New Zealand Disaster Watch tools for emergencies, warnings, fire danger, "
    "road closures and power outages in Australia and New Zealand. Always name the issuing agency. "
    "If any feed is stale or failed, say so and never describe the situation as all clear. "
    "Tell the user to follow official advice and call 000 (Australia) or 111 (New Zealand) in an emergency."
)

# Longest lists a tool returns; the totals say how many there were
MAX_SITUATION_HAZARDS: Final = 10
MAX_LISTED_ITEMS: Final = 20
MAX_SITUATION_ITEMS: Final = 5
MAX_TEXT_LENGTH: Final = 300

CATEGORIES: Final = ("fire", "flood", "storm", "earthquake", "tsunami", "road", "power", "other")
HAZARD_CATEGORY: Final[dict[HazardType, str]] = {
    HazardType.BUSHFIRE: "fire",
    HazardType.GRASS_FIRE: "fire",
    HazardType.METROPOLITAN_FIRE: "fire",
    HazardType.FLOOD: "flood",
    HazardType.SEVERE_STORM: "storm",
    HazardType.CYCLONE: "storm",
    HazardType.EARTHQUAKE: "earthquake",
    HazardType.TSUNAMI: "tsunami",
    HazardType.ROAD_INCIDENT: "road",
}
MIN_LEVELS: Final[dict[str, WarningLevel]] = {
    "advice": WarningLevel.ADVICE,
    "watch_and_act": WarningLevel.WATCH_AND_ACT,
    "emergency_warning": WarningLevel.EMERGENCY_WARNING,
}
FIRE_DAYS: Final[dict[str, int]] = {"today": 0, "tomorrow": 1, "day3": 2, "day4": 3}
READ_ONLY: Final = ToolAnnotations(read_only=True, destructive=False, idempotent=True, open_world=False)
ENTRY_FIELD: Final = probatio.Optional(
    "entry", description="Title of the monitored location (config entry); only needed when there are several"
)


def _iso(value: datetime | None) -> str | None:
    """Return an ISO 8601 string, or None."""
    return value.isoformat() if value is not None else None


def _text(value: str | None) -> str | None:
    """Return text cut to a length an LLM context can afford."""
    return value[:MAX_TEXT_LENGTH] if value else None


def _km(value: float | None) -> float | None:
    """Return a distance rounded to 0.1 km."""
    return round(value, 1) if value is not None else None


def hazard_category(hazard: CanonicalHazard) -> str:
    """Return the tool category of a hazard."""
    return HAZARD_CATEGORY.get(hazard.hazard_type, "other")


def hazard_summary(hazard: CanonicalHazard) -> dict[str, Any]:
    """Return the JSON-safe facts an LLM needs about one hazard."""
    return {
        "title": hazard.title,
        "category": hazard_category(hazard),
        "hazard_type": hazard.hazard_type.value,
        "warning_level": hazard.warning_level.value,
        "distance_km": _km(hazard.distance_km),
        "inside_warning_area": hazard.inside_area,
        "location": hazard.location_name or None,
        "status": hazard.status,
        "agency": hazard.responsible_agency or hazard.source,
        "updated_at": _iso(hazard.updated_at),
        "expires": _iso(hazard.expires),
        "call_to_action": _text(hazard.call_to_action),
        "link": hazard.web_url,
        "attribution": hazard.attribution,
    }


def _nearest_first(hazards: list[CanonicalHazard]) -> list[CanonicalHazard]:
    """Order hazards nearest first, then most severe; unknown distances last."""
    return sorted(
        hazards,
        key=lambda h: (h.distance_km is None, h.distance_km or 0.0, -h.warning_level.severity_rank),
    )


def feed_health(coordinator: AustralianDisasterWatchCoordinator) -> dict[str, Any]:
    """Return per-feed health and whether the answer covers every feed.

    ``complete`` is False when there is no data yet, the last update failed, or any feed is
    stale or failed: the answer must then never be read as an all-clear.
    """
    feeds = [
        {
            "feed": key,
            "sources": [source.owner for source in sources_for_provider(key)],
            "status": status,
            "last_success": _iso(last),
        }
        for key, (status, last) in coordinator.feed_health.items()
    ]
    has_data = coordinator.data is not None
    complete = has_data and coordinator.last_update_success and all(feed["status"] == "ok" for feed in feeds)
    result: dict[str, Any] = {"complete": complete, "feeds": feeds}
    if not has_data:
        result["notice"] = "No data has been fetched yet. The situation is unknown, not all clear."
    elif not complete:
        down = ", ".join(f"{feed['feed']} ({feed['status']})" for feed in feeds if feed["status"] != "ok")
        result["notice"] = (
            f"Some feeds are not up to date: {down or 'the last update failed'}. "
            "Hazards from those feeds may be missing or out of date; this is not an all-clear."
        )
    return result


def _road_closures(coordinator: AustralianDisasterWatchCoordinator) -> list[dict[str, Any]]:
    """Return road closures and flooded roads nearest first."""
    items = sorted(coordinator.road_closures, key=lambda item: (item.distance_km is None, item.distance_km or 0.0))
    return [
        {
            "category": "road",
            "road": item.road or None,
            "suburb": item.suburb or None,
            "status": item.status,
            "reason": item.reason,
            "advice": _text(item.advice),
            "distance_km": _km(item.distance_km),
            "agency": item.source,
            "updated_at": _iso(item.updated_at),
        }
        for item in items
    ]


def _power_outages(coordinator: AustralianDisasterWatchCoordinator) -> list[dict[str, Any]]:
    """Return power outages nearest first, with their distance from the monitored point."""
    items: list[dict[str, Any]] = []
    for item in coordinator.power_outages:
        distance = None
        if item.latitude is not None and item.longitude is not None:
            distance = calculate_haversine_distance(
                coordinator.latitude, coordinator.longitude, item.latitude, item.longitude
            )
        items.append(
            {
                "category": "power",
                "suburb": item.suburb or None,
                "cause": item.cause,
                "customers_affected": item.customers_affected,
                "restore_time": item.restore_time,
                "distance_km": _km(distance),
            }
        )
    return sorted(items, key=lambda item: (item["distance_km"] is None, item["distance_km"] or 0.0))


def _fire_day(coordinator: AustralianDisasterWatchCoordinator, day: str) -> dict[str, Any]:
    """Return the fire danger rating and total fire ban for one forecast day."""
    if (season := coordinator.fire_season) is not None:
        return {
            "fire_season": season.season,
            "zone": season.zone,
            "section_52_prohibition": season.section_52,
            "agency": "Fire and Emergency New Zealand",
        }
    outlook = coordinator.fire_outlook
    if outlook is not None:
        on = local_today(outlook.time_zone) + timedelta(days=FIRE_DAYS[day])
        forecast = outlook.day(on)
        return {
            "day": day,
            "date": on.isoformat(),
            "district": outlook.district_name,
            "rating": forecast.rating if forecast else None,
            "fire_behaviour_index": forecast.fire_behaviour_index if forecast else None,
            "total_fire_ban": forecast.total_fire_ban if forecast else None,
            "issued_at": _iso(outlook.issued_at),
            "agency": outlook.source,
            "total_fire_ban_agency": outlook.total_fire_ban_source,
        }
    if day == "today" and (rating := coordinator.fire_danger) is not None:
        return {
            "day": day,
            "district": rating.district_name,
            "rating": rating.rating,
            "total_fire_ban": rating.total_fire_ban,
        }
    return {"day": day, "rating": None, "notice": "No fire danger forecast is available for this day."}


class _EntryTool(Tool):
    """Base for tools that answer for one monitored location (config entry)."""

    annotations = READ_ONLY
    integration = DOMAIN

    def __init__(self, entries: list[ConfigEntry]) -> None:
        """Bind the tool to the entries the assistant may see."""
        self._entries = entries

    def _select(self, tool_input: ToolInput) -> ConfigEntry | ToolResult:
        """Return the requested entry, or a result asking the LLM to choose one."""
        wanted = tool_input.tool_args.get("entry")
        if wanted:
            needle = str(wanted).strip().casefold()
            for entry in self._entries:
                if needle in {entry.title.casefold(), entry.entry_id.casefold()}:
                    return entry
        elif len(self._entries) == 1:
            return self._entries[0]
        titles: list[JsonValueType] = [entry.title for entry in self._entries]
        message = (
            f"No monitored location is called {wanted!r}."
            if wanted
            else "Several locations are monitored; call the tool again with entry set to one of them."
        )
        return ToolResult(data={"error": message, "entries": titles}, error=True)

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> ToolResult:
        """Validate the arguments and answer for the selected entry."""
        try:
            args = self.parameters(tool_input.tool_args)
        except probatio.Invalid as err:
            return ToolResult(data={"error": f"Invalid arguments: {err}"}, error=True)
        selected = self._select(tool_input)
        if isinstance(selected, ToolResult):
            return selected
        if selected.state is not ConfigEntryState.LOADED:
            return ToolResult(data={"error": f"{selected.title} is not loaded; try again shortly."}, error=True)
        coordinator: AustralianDisasterWatchCoordinator = selected.runtime_data
        data = self._answer(coordinator, args)
        return ToolResult(
            data={"entry": selected.title, **data, "feed_health": feed_health(coordinator)},
        )

    def _answer(self, coordinator: AustralianDisasterWatchCoordinator, args: dict[str, Any]) -> dict[str, Any]:
        """Return the tool's answer for one entry."""
        raise NotImplementedError


class GetDisasterSituationTool(_EntryTool):
    """Summarise everything the integration knows about one location."""

    name = f"{DOMAIN}__get_disaster_situation"
    title = "Get disaster situation"
    description = (
        "Get the current emergency situation near a monitored location in Australia or New Zealand: the highest "
        "Australian Warning System level, active warnings and incidents nearest first, weather warnings, fire "
        "danger today and tomorrow, total fire ban, road closures, power outages and the health of each feed."
    )
    parameters = probatio.Schema({ENTRY_FIELD: str})

    @override
    def _answer(self, coordinator: AustralianDisasterWatchCoordinator, args: dict[str, Any]) -> dict[str, Any]:
        hazards = _nearest_first(coordinator.active_hazards)
        roads = _road_closures(coordinator)
        outages = _power_outages(coordinator)
        warnings = coordinator.weather_warnings
        return {
            "highest_warning_level": coordinator.highest_warning_level.value if hazards else None,
            "inside_warning_area": coordinator.is_inside_warning_area,
            "radius_km": coordinator.radius_km,
            "hazard_count": len(hazards),
            "hazards": [hazard_summary(hazard) for hazard in hazards[:MAX_SITUATION_HAZARDS]],
            "weather_warning_count": len(warnings),
            "weather_warnings": [
                {
                    "title": warning.title,
                    "areas": _text(warning.locations),
                    "issued_at": _iso(warning.pub_date),
                    "link": warning.link,
                    "agency": "MetService" if coordinator.state_code == "NZ" else "Bureau of Meteorology",
                }
                for warning in warnings[:MAX_SITUATION_HAZARDS]
            ],
            "fire_danger": {"today": _fire_day(coordinator, "today"), "tomorrow": _fire_day(coordinator, "tomorrow")},
            "road_closure_count": len(roads),
            "road_closures": roads[:MAX_SITUATION_ITEMS],
            "power_outage_count": len(outages),
            "power_outages": outages[:MAX_SITUATION_ITEMS],
            "attribution": coordinator.attribution,
        }


class GetFireDangerTool(_EntryTool):
    """Return the fire danger rating and total fire ban for a forecast day."""

    name = f"{DOMAIN}__get_fire_danger"
    title = "Get fire danger"
    description = (
        "Get the Australian Fire Danger Rating and total fire ban for a monitored location today, tomorrow or "
        "the following two days; in New Zealand, the fire season status."
    )
    parameters = probatio.Schema(
        {ENTRY_FIELD: str, probatio.Optional("day", default="today"): probatio.In(list(FIRE_DAYS))}
    )

    @override
    def _answer(self, coordinator: AustralianDisasterWatchCoordinator, args: dict[str, Any]) -> dict[str, Any]:
        return {"fire_danger": _fire_day(coordinator, args["day"])}


class ListHazardsTool(_EntryTool):
    """List hazards, road closures or power outages with filters."""

    name = f"{DOMAIN}__list_hazards"
    title = "List hazards"
    description = (
        "List active warnings and incidents near a monitored location, nearest first, optionally filtered by "
        "category, maximum distance and minimum Australian Warning System level. The road category also lists "
        "road closures and flooded roads; the power category lists power outages."
    )
    parameters = probatio.Schema(
        {
            ENTRY_FIELD: str,
            probatio.Optional("category"): probatio.In(list(CATEGORIES)),
            probatio.Optional("max_distance_km"): probatio.All(probatio.Coerce(float), probatio.Range(min=0)),
            probatio.Optional("min_level"): probatio.In(list(MIN_LEVELS)),
        }
    )

    @override
    def _answer(self, coordinator: AustralianDisasterWatchCoordinator, args: dict[str, Any]) -> dict[str, Any]:
        category: str | None = args.get("category")
        max_km: float | None = args.get("max_distance_km")
        min_level = MIN_LEVELS.get(args.get("min_level", ""))
        items: list[dict[str, Any]] = [
            hazard_summary(hazard)
            for hazard in _nearest_first(coordinator.active_hazards)
            if (category is None or hazard_category(hazard) == category)
            and (min_level is None or hazard.warning_level.severity_rank >= min_level.severity_rank)
        ]
        # Road closures and outages have no warning level, so a level filter leaves them out
        if min_level is None and category == "road":
            items += _road_closures(coordinator)
        if min_level is None and category == "power":
            items += _power_outages(coordinator)
        if max_km is not None:
            items = [item for item in items if item["distance_km"] is not None and item["distance_km"] <= max_km]
        return {
            "filters": {"category": category, "max_distance_km": max_km, "min_level": args.get("min_level")},
            "total": len(items),
            "truncated": len(items) > MAX_LISTED_ITEMS,
            "items": items[:MAX_LISTED_ITEMS],
        }


@callback
def exposed_entries(hass: HomeAssistant, assistant: str) -> list[ConfigEntry]:
    """Return loaded entries with at least one entity exposed to the assistant."""
    registry = er.async_get(hass)
    return [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if any(
            async_should_expose(hass, assistant, entity.entity_id)
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        )
    ]


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext, api_id: str) -> LLMTools | None:
    """Return the read-only tools for the Assist API when an entity of an entry is exposed."""
    if api_id != LLM_API_ASSIST:
        return None
    if not (entries := exposed_entries(hass, llm_context.assistant)):
        return None
    return LLMTools(
        tools=[GetDisasterSituationTool(entries), GetFireDangerTool(entries), ListHazardsTool(entries)],
        prompt=PROMPT,
    )
