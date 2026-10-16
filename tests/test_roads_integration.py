"""Road closures through the coordinator, entities, options flow and diagnostics (#29)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import (
    CONF_INCLUDE_ROADWORKS,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_STATE,
    CONF_VIC_API_KEY,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.diagnostics import async_get_config_entry_diagnostics
from custom_components.ausnz_disaster_watch.models import DisasterWatchConfigModel, RoadClosureItem, RoadEventCategory
from custom_components.ausnz_disaster_watch.providers.roads import (
    NSWRoadProvider,
    NTRoadProvider,
    QueenslandRoadProvider,
    merge_road_items,
)
from custom_components.ausnz_disaster_watch.providers.roads.base import BaseRoadProvider
from homeassistant import data_entry_flow
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

FIXTURES = Path(__file__).parent / "fixtures" / "roads"
EMPTY = {"type": "FeatureCollection", "features": []}


def load(name: str) -> Any:
    """Load a recorded road feed fixture."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def road_factory(cls: type[BaseRoadProvider], routes: dict[str, Any]) -> Callable[..., list[BaseRoadProvider]]:
    """Return a get_road_providers_for_config stand-in building a real provider over fixtures."""
    built: list[BaseRoadProvider] = []

    def factory(hass: HomeAssistant, session: Any, config: dict[str, Any]) -> list[BaseRoadProvider]:
        provider = cls(hass, session, config)

        async def fetch(url: str, headers: dict[str, str] | None = None) -> Any:
            return next((payload for key, payload in routes.items() if key in url), EMPTY)

        provider.async_fetch_json = AsyncMock(side_effect=fetch)  # type: ignore[method-assign]
        built.append(provider)
        return [provider]

    factory.built = built  # type: ignore[attr-defined]
    return factory


def entry_for(state: str, name: str, lat: float, lon: float, radius: int = 100, **options: Any) -> MockConfigEntry:
    """Build a custom-location entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Australia and New Zealand Disaster Watch ({state} - {name})",
        data={
            CONF_STATE: state,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_LOCATION_NAME: name,
            CONF_LATITUDE: lat,
            CONF_LONGITUDE: lon,
            CONF_RADIUS: radius,
        },
        options=options,
        unique_id=f"{DOMAIN}_{state.lower()}_{name.lower()}",
    )


async def setup_with_roads(hass: HomeAssistant, entry: MockConfigEntry, factory: Callable[..., Any]) -> None:
    """Set up an entry with a quiet hazard provider and the given road provider factory."""
    entry.add_to_hass(hass)
    hazards = AsyncMock()
    hazards.async_fetch_hazards.return_value = []
    hazards.async_fetch_road_closures.return_value = []
    with (
        patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[hazards]),
        patch("custom_components.ausnz_disaster_watch.coordinator.get_road_providers_for_config", side_effect=factory),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def entity(state: str, name: str, key: str, platform: str = "binary_sensor") -> str:
    """Return an entity ID of this integration."""
    return f"{platform}.australia_and_new_zealand_disaster_watch_{state}_{name}_{key}"


# --- models and merging --------------------------------------------------------------------


def test_category_inference_for_council_items() -> None:
    """Items without a category (council feeds) are classified from status and reason."""
    assert RoadClosureItem(id="a").category == RoadEventCategory.CLOSURE  # default status "Closed"
    assert RoadClosureItem(id="b", status="Road closed", reason="Flooding").is_flooding
    assert RoadClosureItem(id="c", status="Lane or lanes reduced", reason="Planned roadworks").is_planned
    assert RoadClosureItem(id="d", status="Special event").category == RoadEventCategory.SPECIAL_EVENT
    assert RoadClosureItem(id="e", status="All lanes affected", reason="Road damage").category == (
        RoadEventCategory.HAZARD
    )
    explicit = RoadClosureItem(id="g", status="Closed", category=RoadEventCategory.ROADWORKS)
    assert explicit.category == RoadEventCategory.ROADWORKS
    assert RoadEventCategory.infer("Impassable") == RoadEventCategory.CLOSURE
    assert RoadEventCategory.infer(None, "water over road") == RoadEventCategory.FLOODING
    assert RoadEventCategory.infer("Closed", "Unplanned closure") == RoadEventCategory.CLOSURE


def test_config_model_road_options() -> None:
    """The roadworks option defaults off; a blank VIC key is no key."""
    cfg = DisasterWatchConfigModel.model_validate({})
    assert cfg.include_roadworks is False
    assert cfg.vic_api_key is None
    assert DisasterWatchConfigModel.model_validate({"vic_api_key": "  "}).vic_api_key is None
    assert DisasterWatchConfigModel.model_validate({"vic_api_key": " k "}).vic_api_key == "k"


def test_merge_road_items() -> None:
    """Planned items drop by default; council copies of statewide events drop; IDs stay unique."""
    flood = RoadClosureItem(
        id="TMR_717127", road="Dugandan Road", suburb="Bunya", category="flooding", latitude=-27.35, longitude=152.95
    )
    works = RoadClosureItem(id="TMR_548467", road="Cunningham Hwy", category="roadworks", latitude=-28, longitude=152)
    statewide = [flood, works, flood]
    council = [
        RoadClosureItem(id="TMR_717127", road="Dugandan Road", status="Road closed", reason="Flooding"),
        RoadClosureItem(id="COUNCIL_717127", road="Dugandan Rd", reason="Flooding", latitude=-27.36, longitude=152.95),
        RoadClosureItem(id="COUNCIL_717127", road="Far", reason="Flooding", latitude=-20.0, longitude=150.0),
        RoadClosureItem(
            id="COUNCIL_9", road="dugandan road", suburb="BUNYA", reason="Flooding", latitude=-27.351, longitude=152.95
        ),
        RoadClosureItem(id="COUNCIL_10", road="Dugandan Road", suburb="Bunya", status="Closed", latitude=-27.35),
        RoadClosureItem(id="COUNCIL_11", road="Other Road", status="Lane closed", reason="Planned roadworks"),
        RoadClosureItem(id="COUNCIL_12", road="", status="Closed"),
        # A signal fault the statewide feed skips is not let in through the council copy
        RoadClosureItem(
            id="TMR_834569", road="Bribie Island Rd", status="All lanes affected", reason="Lights flashing"
        ),
    ]
    merged = merge_road_items(statewide, council, include_roadworks=False)
    assert [item.id for item in merged] == ["TMR_717127", "COUNCIL_717127", "COUNCIL_10", "COUNCIL_12"]
    assert merged[1].road == "Far"  # same event ID but 800 km away: a different event

    with_works = merge_road_items(statewide, council, include_roadworks=True)
    assert "TMR_548467" in {item.id for item in with_works}
    assert "COUNCIL_11" in {item.id for item in with_works}


# --- coordinator ---------------------------------------------------------------------------


async def test_coordinator_road_feeds(hass: HomeAssistant) -> None:
    """Road providers get the resolved location and radius; roadworks are dropped by default."""
    entry = entry_for("QLD", "Moreton", -27.27, 152.98, radius=50)
    factory = road_factory(QueenslandRoadProvider, {"events_v2": load("qld_events_v2")})
    entry.add_to_hass(hass)
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_road_providers_for_config", side_effect=factory):
        coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    (provider,) = factory.built  # type: ignore[attr-defined]
    assert provider.config["latitude"] == -27.27
    assert provider.config["radius"] == 50.0
    hazards = AsyncMock()
    hazards.async_fetch_hazards.return_value = []
    hazards.async_fetch_road_closures.return_value = [
        RoadClosureItem(id="TMR_717127", road="Dugandan Road", reason="Flooding", latitude=-27.35, longitude=152.95),
        RoadClosureItem(id="COUNCIL_1", road="Local St", status="Closed"),
    ]
    coordinator.providers = [hazards]
    await coordinator.async_refresh()

    ids = [item.id for item in coordinator.road_closures]
    assert ids == ["TMR_717127", "COUNCIL_1"]  # statewide first, council copy dropped, distant events out
    assert coordinator.road_closures[0].source == "QLDTraffic (City of Moreton Bay)"
    assert coordinator.road_closures[0].distance_km is not None


async def test_coordinator_includes_roadworks_when_enabled(hass: HomeAssistant) -> None:
    """With the option on, planned roadworks within the radius are listed."""
    entry = entry_for("QLD", "Warwick", -28.06, 152.41, radius=20, **{CONF_INCLUDE_ROADWORKS: True})
    factory = road_factory(QueenslandRoadProvider, {"events_v2": load("qld_events_v2")})
    entry.add_to_hass(hass)
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_road_providers_for_config", side_effect=factory):
        coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    coordinator.providers = []
    assert coordinator.include_roadworks is True
    await coordinator.async_refresh()
    assert [item.id for item in coordinator.road_closures] == ["TMR_548467"]


async def test_road_feed_outage_is_reported(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, caplog: pytest.LogCaptureFixture
) -> None:
    """A road feed outage is logged once, makes the road sensors unavailable, and recovers."""
    entry = entry_for("NT", "Daly River", -14.30, 131.50, radius=25)
    routes: dict[str, Any] = {"GetAll": None}
    await setup_with_roads(hass, entry, road_factory(NTRoadProvider, routes))
    coordinator = entry.runtime_data
    assert coordinator.last_update_success
    assert coordinator.road_feeds_failed == ["NTRoadProvider"]
    assert caplog.text.count("Road feed NTRoadProvider is unavailable") == 1
    for key in ("road_closure_nearby", "flooded_road_nearby"):
        state = hass.states.get(entity("nt", "daly_river", key))
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=5))
    await coordinator.async_refresh()
    assert caplog.text.count("Road feed NTRoadProvider is unavailable") == 1  # not repeated

    routes["GetAll"] = load("nt_obstructions")
    freezer.tick(timedelta(minutes=5))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.road_feeds_failed == []
    assert "Road feed NTRoadProvider is available again" in caplog.text
    state = hass.states.get(entity("nt", "daly_river", "flooded_road_nearby"))
    assert state is not None
    assert state.state == STATE_ON
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["coordinator"]["road_feeds_failed"] == []


async def test_road_items_are_sorted_nearest_first(hass: HomeAssistant) -> None:
    """Statewide and council items are ordered by distance; unlocated items come last."""
    entry = entry_for("NSW", "Sydney", -33.87, 151.21, radius=100)
    entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, entry)
    roads = AsyncMock()
    roads.async_fetch_road_closures.return_value = [
        RoadClosureItem(id="far", road="A", category="closure", latitude=-34.5, longitude=151.0),
        RoadClosureItem(id="near", road="B", category="closure", latitude=-33.88, longitude=151.2),
    ]
    council = AsyncMock()
    council.async_fetch_hazards.return_value = []
    council.async_fetch_road_closures.return_value = [
        RoadClosureItem(id="unlocated", road="C", status="Closed"),
        RoadClosureItem(id="middle", road="D", status="Closed", latitude=-34.0, longitude=151.2),
    ]
    coordinator.road_providers = [roads]
    coordinator.providers = [council]
    await coordinator.async_refresh()
    assert [item.id for item in coordinator.road_closures] == ["near", "middle", "far", "unlocated"]


# --- entities ------------------------------------------------------------------------------


async def test_flooded_road_nearby_nsw(hass: HomeAssistant) -> None:
    """A Live Traffic flood within the radius turns on the flooded road and closure sensors."""
    entry = entry_for("NSW", "Milparinka", -29.40, 141.60)
    factory = road_factory(
        NSWRoadProvider,
        {
            "flood.json": load("nsw_flood"),
            "incident.json": load("nsw_incident"),
            "lga-incidents": load("nsw_lga_incidents"),
        },
    )
    await setup_with_roads(hass, entry, factory)

    flooded = hass.states.get(entity("nsw", "milparinka", "flooded_road_nearby"))
    assert flooded is not None
    assert flooded.state == STATE_ON
    assert flooded.attributes["device_class"] == "safety"
    assert flooded.attributes["icon"] == "mdi:home-flood"
    assert flooded.attributes["flooded_count"] == 1
    assert flooded.attributes["nearest"][0]["road"] == "Hewart Downs Road"
    assert flooded.attributes["nearest"][0]["distance_km"] < 10

    closure = hass.states.get(entity("nsw", "milparinka", "road_closure_nearby"))
    assert closure is not None
    assert closure.state == STATE_ON
    assert closure.attributes["flooding_count"] == 1

    from homeassistant.helpers import entity_registry as er  # noqa: PLC0415

    registry_entry = er.async_get(hass).async_get(entity("nsw", "milparinka", "flooded_road_nearby"))
    assert registry_entry is not None
    assert registry_entry.unique_id == f"{entry.entry_id}_flooded_road_nearby"


async def test_flooded_road_nearby_qld(hass: HomeAssistant) -> None:
    """A QLDTraffic flooding event near Bunya turns the flooded road sensor on."""
    entry = entry_for("QLD", "Bunya", -27.36, 152.94, radius=10)
    await setup_with_roads(hass, entry, road_factory(QueenslandRoadProvider, {"events_v2": load("qld_events_v2")}))
    state = hass.states.get(entity("qld", "bunya", "flooded_road_nearby"))
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["nearest"][0]["source"] == "QLDTraffic (City of Moreton Bay)"


async def test_flooded_road_nearby_nt(hass: HomeAssistant) -> None:
    """An NT Road Report flooded crossing (given as [lat, lon]) is found near Daly River."""
    entry = entry_for("NT", "Daly River", -14.30, 131.50, radius=25)
    await setup_with_roads(hass, entry, road_factory(NTRoadProvider, {"GetAll": load("nt_obstructions")}))
    state = hass.states.get(entity("nt", "daly_river", "flooded_road_nearby"))
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["nearest"][0]["road"] == "Dorisvale Road"


async def test_roadworks_never_turn_on_road_sensors(hass: HomeAssistant) -> None:
    """Listed roadworks (option on) count in the sensor but leave both binary sensors off."""
    entry = entry_for("QLD", "Warwick", -28.06, 152.41, radius=20, **{CONF_INCLUDE_ROADWORKS: True})
    await setup_with_roads(hass, entry, road_factory(QueenslandRoadProvider, {"events_v2": load("qld_events_v2")}))

    count = hass.states.get(entity("qld", "warwick", "road_closures_count", "sensor"))
    assert count is not None
    assert count.state == "1"
    assert count.attributes["closures"][0]["category"] == "roadworks"
    closure = hass.states.get(entity("qld", "warwick", "road_closure_nearby"))
    assert closure is not None
    assert closure.state == STATE_OFF
    assert closure.attributes["roadworks_count"] == 1
    flooded = hass.states.get(entity("qld", "warwick", "flooded_road_nearby"))
    assert flooded is not None
    assert flooded.state == STATE_OFF
    assert flooded.attributes["icon"] == "mdi:road-variant"
    assert flooded.attributes["nearest"] == []


# --- options flow and diagnostics -------------------------------------------------------------


async def open_roads_step(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    """Open the options menu and pick the road closures step."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["menu_options"][1] == "roads"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "roads"})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "roads"
    return dict(result)


async def test_options_flow_road_step(hass: HomeAssistant) -> None:
    """VIC shows the key field; the roadworks option is saved; other options are kept; a cleared key goes."""
    entry = entry_for("VIC", "Melbourne", -37.81, 144.96, **{CONF_VIC_API_KEY: "old", "override_emergency": False})
    entry.add_to_hass(hass)
    result = await open_roads_step(hass, entry)
    assert {str(key) for key in result["data_schema"].schema} == {CONF_INCLUDE_ROADWORKS, CONF_VIC_API_KEY}
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_INCLUDE_ROADWORKS: True, CONF_VIC_API_KEY: " new "}
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options == {"override_emergency": False, CONF_INCLUDE_ROADWORKS: True, CONF_VIC_API_KEY: " new "}

    # Clearing the field (omitted or blank) removes the stored key
    for cleared in ({CONF_INCLUDE_ROADWORKS: False}, {CONF_INCLUDE_ROADWORKS: False, CONF_VIC_API_KEY: "  "}):
        result = await open_roads_step(hass, entry)
        with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
            await hass.config_entries.options.async_configure(result["flow_id"], user_input=cleared)
        assert entry.options == {"override_emergency": False, CONF_INCLUDE_ROADWORKS: False}
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_VIC_API_KEY: "old"})

    nsw = entry_for("NSW", "Sydney", -33.87, 151.21)
    nsw.add_to_hass(hass)
    result = await open_roads_step(hass, nsw)
    assert {str(key) for key in result["data_schema"].schema} == {CONF_INCLUDE_ROADWORKS}

    for state in ("ACT", "NZ"):
        other = entry_for(state, "Somewhere", -35.3, 149.1)
        other.add_to_hass(hass)
        result = await hass.config_entries.options.async_init(other.entry_id)
        assert "roads" not in result["menu_options"]


async def test_diagnostics_redact_vic_key(hass: HomeAssistant) -> None:
    """The DTP key never appears in diagnostics; road provider names do."""
    entry = entry_for("VIC", "Melbourne", -37.81, 144.96, **{CONF_VIC_API_KEY: "secret"})
    await setup_with_roads(hass, entry, lambda *_: [MagicMock(spec=BaseRoadProvider, __class__=NSWRoadProvider)])
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["options"][CONF_VIC_API_KEY] == "**REDACTED**"
    assert diag["coordinator"]["road_providers"] == ["NSWRoadProvider"]
    assert diag["coordinator"]["include_roadworks"] is False
    assert "secret" not in json.dumps(diag, default=str)
