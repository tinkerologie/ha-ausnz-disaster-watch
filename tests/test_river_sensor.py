"""Tests for river gauge sensors, their coordinator and the options-flow gauge picker (#31)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ausnz_disaster_watch.config_flow import gauge_field_names
from custom_components.ausnz_disaster_watch.const import (
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_LOCATION_MODE,
    CONF_OVERRIDE_EMERGENCY,
    CONF_RADIUS,
    CONF_RIVER_GAUGES,
    CONF_STATE,
    LOCATION_MODE_HOME,
    STATE_VIC,
)
from custom_components.ausnz_disaster_watch.river_coordinator import RiverGaugeCoordinator
from custom_components.ausnz_disaster_watch.rivers import RIVER_SCAN_INTERVAL, GaugeReading, GaugeSite, RiverSourceError
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

SAVAGES = GaugeSite("qld", "143001C", "Brisbane River at Savages Crossing", -27.439727, 152.668941)
DRAPERS = GaugeSite("qld", "142202A", "South Pine River at Drapers Crossing", -27.3497, 152.9191)
SAVAGES_ENTITY = (
    "sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_brisbane_river_at_savages_crossing"
    "_water_level"
)
DRAPERS_ENTITY = (
    "sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_south_pine_river_at_drapers_crossing"
    "_water_level"
)
SAVAGES_ALERT_ENTITY = (
    "binary_sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_brisbane_river_at_savages_crossing"
    "_above_alert_level"
)
DRAPERS_ALERT_ENTITY = SAVAGES_ALERT_ENTITY.replace(
    "brisbane_river_at_savages_crossing", "south_pine_river_at_drapers_crossing"
)
OBSERVED = datetime(2026, 10, 15, 22, 0, tzinfo=UTC)
OPTIONS_INPUT: dict[str, Any] = {CONF_RADIUS: 50, CONF_OVERRIDE_EMERGENCY: True, CONF_EXCLUDE_HAZARD_REDUCTION: True}


def _reading(site: GaugeSite, level: float = 1.333, observed: datetime = OBSERVED) -> GaugeReading:
    return GaugeReading(site=site, level_m=level, observed_at=observed, trend="steady", change_m=0.0)


@pytest.fixture
def mock_providers() -> Generator[AsyncMock]:
    """Patch hazard providers with one that returns no hazards."""
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[provider],
    ):
        yield provider


@pytest.fixture
def mock_fetch() -> Generator[AsyncMock]:
    """Patch the coordinator's gauge fetch."""
    with patch(
        "custom_components.ausnz_disaster_watch.river_coordinator.async_fetch_readings",
        autospec=True,
    ) as fetch:
        yield fetch


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, sites: list[GaugeSite]) -> None:
    hass.config_entries.async_update_entry(entry, options={CONF_RIVER_GAUGES: [s.as_dict() for s in sites]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_gauge_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """Each selected gauge is a water level sensor in metres; a gauge without a reading is unavailable."""
    mock_fetch.return_value = ({SAVAGES.key: _reading(SAVAGES)}, set())
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [SAVAGES, DRAPERS])

    state = hass.states.get(SAVAGES_ENTITY)
    assert state is not None
    assert state.state == "1.333"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes[ATTR_ATTRIBUTION].startswith("© State of Queensland")
    assert state.attributes["site_id"] == "143001C"
    assert state.attributes["source"] == "qld"
    assert state.attributes["observed_at"] == "2026-10-15T22:00:00+00:00"
    assert state.attributes["trend"] == "steady"
    assert state.attributes["change_1h_m"] == 0.0
    assert state.attributes["distance_km"] == pytest.approx(36.5, abs=0.1)

    assert hass.states.get(DRAPERS_ENTITY).state == STATE_UNAVAILABLE
    entry = er.async_get(hass).async_get(SAVAGES_ENTITY)
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_river_gauge_qld_143001C"
    assert entry.device_id is not None


async def test_no_gauges_no_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """Existing entries without selected gauges create no river coordinator or sensors."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.river_coordinator is None
    mock_fetch.assert_not_called()


async def test_outages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A partial outage keeps the last reading; a full outage makes the sensors unavailable."""
    freezer.move_to(OBSERVED + timedelta(minutes=30))
    mock_fetch.return_value = ({SAVAGES.key: _reading(SAVAGES), DRAPERS.key: _reading(DRAPERS, 0.5)}, set())
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [SAVAGES, DRAPERS])
    river: RiverGaugeCoordinator = mock_config_entry.runtime_data.river_coordinator
    assert river.update_interval == RIVER_SCAN_INTERVAL

    # Savages' service is down: its previous reading is kept while it is recent
    mock_fetch.return_value = ({DRAPERS.key: _reading(DRAPERS, 0.6)}, {SAVAGES.key})
    freezer.tick(RIVER_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SAVAGES_ENTITY).state == "1.333"
    assert hass.states.get(DRAPERS_ENTITY).state == "0.6"

    # Every service is down: recent readings are still kept
    mock_fetch.return_value = ({}, {SAVAGES.key, DRAPERS.key})
    freezer.tick(RIVER_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert river.last_update_success
    assert hass.states.get(SAVAGES_ENTITY).state == "1.333"

    # ...until they are older than the reading window, then the update fails
    freezer.tick(timedelta(hours=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not river.last_update_success
    assert hass.states.get(SAVAGES_ENTITY).state == STATE_UNAVAILABLE

    # Recovery, then a later outage once the kept reading is older than the window
    mock_fetch.return_value = ({SAVAGES.key: _reading(SAVAGES)}, set())
    freezer.tick(RIVER_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SAVAGES_ENTITY).state == "1.333"
    mock_fetch.return_value = ({DRAPERS.key: _reading(DRAPERS, 0.6)}, {SAVAGES.key})
    freezer.tick(timedelta(hours=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SAVAGES_ENTITY).state == STATE_UNAVAILABLE


async def test_deselected_gauge_is_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """A gauge removed from the selection loses its entity after the reload."""
    mock_fetch.return_value = ({}, set())
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [SAVAGES, DRAPERS])
    registry = er.async_get(hass)
    assert registry.async_get(DRAPERS_ENTITY) is not None

    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RIVER_GAUGES: [SAVAGES.as_dict()]})
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(DRAPERS_ENTITY) is None
    assert registry.async_get(SAVAGES_ENTITY) is not None
    # Other sensors of the entry are kept
    assert any(
        e.unique_id.endswith("_active_hazards_count")
        for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    )


async def _open_gauge_picker(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    """Open the options menu and choose the river gauge step."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert "river_gauges" in result["menu_options"]
    return await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "river_gauges"})


async def test_options_flow_picks_gauges(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """The gauge step lists nearby gauges; the chosen ones are stored and become sensors."""
    mock_fetch.return_value = ({}, set())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RADIUS: 40, "other": "kept"})
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ausnz_disaster_watch.config_flow.async_discover_gauges",
        return_value=[_reading(DRAPERS, 0.543), _reading(SAVAGES)],
    ) as discover:
        result = await _open_gauge_picker(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "river_gauges"
    assert result["errors"] == {}
    assert discover.call_args.kwargs["radius_km"] == 40.0
    options = result["data_schema"].schema[CONF_RIVER_GAUGES].config["options"]
    assert options == [
        {"value": DRAPERS.key, "label": "South Pine River at Drapers Crossing (11.2 km, 0.54 m)"},
        {"value": SAVAGES.key, "label": "Brisbane River at Savages Crossing (36.5 km, 1.33 m)"},
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_RIVER_GAUGES: [SAVAGES.key, DRAPERS.key]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "river_alert_levels"
    assert list(result["data_schema"].schema) == [SAVAGES.name, DRAPERS.name]
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={SAVAGES.name: 2.5})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert mock_config_entry.options == {
        CONF_RADIUS: 40,
        "other": "kept",
        CONF_RIVER_GAUGES: [SAVAGES.with_alert_level(2.5).as_dict(), DRAPERS.as_dict()],
    }
    assert hass.states.get(SAVAGES_ENTITY) is not None
    assert hass.states.get(SAVAGES_ALERT_ENTITY) is not None
    assert hass.states.get(DRAPERS_ALERT_ENTITY) is None

    # Reopening keeps the alert level as the suggested value; clearing it removes the alert sensor
    with patch("custom_components.ausnz_disaster_watch.config_flow.async_discover_gauges", return_value=[]):
        result = await _open_gauge_picker(hass, mock_config_entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_RIVER_GAUGES: [SAVAGES.key]}
    )
    field = next(iter(result["data_schema"].schema))
    assert field.description == {"suggested_value": 2.5}
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={})
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_RIVER_GAUGES] == [SAVAGES.as_dict()]
    assert er.async_get(hass).async_get(SAVAGES_ALERT_ENTITY) is None
    assert er.async_get(hass).async_get(DRAPERS_ENTITY) is None

    # Saving the monitoring settings keeps the selection without searching
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=OPTIONS_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_RIVER_GAUGES] == [SAVAGES.as_dict()]

    # Unticking every gauge saves straight away
    with patch("custom_components.ausnz_disaster_watch.config_flow.async_discover_gauges", return_value=[]):
        result = await _open_gauge_picker(hass, mock_config_entry)
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={CONF_RIVER_GAUGES: []})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_RIVER_GAUGES] == []


@pytest.mark.parametrize(
    ("discovered", "error"),
    [
        (RiverSourceError("down"), "rivers_unavailable"),
        (TimeoutError(), "rivers_unavailable"),
        ([], "no_river_gauges"),
    ],
)
async def test_options_flow_gauge_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    discovered: Any,
    error: str,
) -> None:
    """Without discovered gauges the form says why and the current selection can still be kept."""
    selected = [SAVAGES] if error == "rivers_unavailable" else []
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_RIVER_GAUGES: [s.as_dict() for s in selected]}
    )
    with patch(
        "custom_components.ausnz_disaster_watch.config_flow.async_discover_gauges",
        side_effect=discovered if isinstance(discovered, Exception) else None,
        return_value=discovered,
    ):
        result = await _open_gauge_picker(hass, mock_config_entry)
    assert result["errors"] == {"base": error}
    options = result["data_schema"].schema[CONF_RIVER_GAUGES].config["options"]
    assert options == [{"value": s.key, "label": f"{s.name} (selected)"} for s in selected]

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_RIVER_GAUGES: [s.key for s in selected]}
        )
        if selected:
            assert result["step_id"] == "river_alert_levels"
            result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_RIVER_GAUGES] == [s.as_dict() for s in selected]


async def test_options_menu_without_gauge_source(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """States without a gauge service do not offer the gauge step; settings keep an existing selection."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_STATE: STATE_VIC},
        options={CONF_RIVER_GAUGES: [SAVAGES.as_dict()]},
    )
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert "river_gauges" not in result["menu_options"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=OPTIONS_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_RIVER_GAUGES] == [SAVAGES.as_dict()]


async def test_gauge_picker_home_mode_follows_home(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Home-mode entries search around the current home location, not old stored coordinates."""
    hass.config.latitude, hass.config.longitude = -33.59, 150.71
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_LOCATION_MODE: LOCATION_MODE_HOME}
    )
    with patch("custom_components.ausnz_disaster_watch.config_flow.async_discover_gauges", return_value=[]) as discover:
        await _open_gauge_picker(hass, mock_config_entry)
    assert (discover.call_args.kwargs["latitude"], discover.call_args.kwargs["longitude"]) == (-33.59, 150.71)


async def test_alert_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The alert sensor is on at or above the alert level, off below it and unavailable without a reading."""
    freezer.move_to(OBSERVED + timedelta(minutes=30))
    alerted = SAVAGES.with_alert_level(1.333)
    mock_fetch.return_value = ({SAVAGES.key: _reading(SAVAGES, 1.333)}, set())
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [alerted, DRAPERS])

    state = hass.states.get(SAVAGES_ALERT_ENTITY)
    assert state.state == "on"
    assert state.attributes["device_class"] == "problem"
    assert state.attributes["alert_level_m"] == 1.333
    assert state.attributes["level_m"] == 1.333
    assert state.attributes[ATTR_ATTRIBUTION].startswith("© State of Queensland")
    assert hass.states.get(SAVAGES_ENTITY).attributes["alert_level_m"] == 1.333
    assert hass.states.get(DRAPERS_ALERT_ENTITY) is None
    entry = er.async_get(hass).async_get(SAVAGES_ALERT_ENTITY)
    assert entry.unique_id == f"{mock_config_entry.entry_id}_river_gauge_alert_qld_143001C"

    mock_fetch.return_value = ({SAVAGES.key: _reading(SAVAGES, 1.2)}, set())
    freezer.tick(RIVER_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SAVAGES_ALERT_ENTITY).state == "off"

    mock_fetch.return_value = ({}, set())
    freezer.tick(RIVER_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(SAVAGES_ALERT_ENTITY)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("level_m") is None


def test_gauge_field_names() -> None:
    """Alert-level fields are gauge names; repeated names get their site ID."""
    twin = GaugeSite("nsw", "212200", SAVAGES.name, -33.6, 150.7)
    assert gauge_field_names([SAVAGES, DRAPERS]) == [SAVAGES.name, DRAPERS.name]
    assert gauge_field_names([SAVAGES, twin]) == [f"{SAVAGES.name} (143001C)", f"{SAVAGES.name} (212200)"]


def test_alert_level_storage() -> None:
    """Alert levels round-trip through options; an unusable stored level means none."""
    assert GaugeSite.from_dict(SAVAGES.with_alert_level(3.0).as_dict()) == SAVAGES.with_alert_level(3.0)
    assert GaugeSite.from_dict({**SAVAGES.as_dict(), "alert_level_m": "high"}) == SAVAGES
    assert "alert_level_m" not in SAVAGES.as_dict()
