"""Tests for the dam storage sensors, their coordinator and the options-flow storage picker."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ausnz_disaster_watch.const import (
    CONF_DAM_STORAGES,
    CONF_LOCATION_MODE,
    CONF_RADIUS,
    CONF_STATE,
    LOCATION_MODE_HOME,
    STATE_NZ,
)
from custom_components.ausnz_disaster_watch.dam_options import offers_dam_storages, storage_label
from custom_components.ausnz_disaster_watch.dams import (
    DAM_SCAN_INTERVAL,
    OPERATOR_WATERNSW,
    DamSourceError,
    OperatorReading,
    StorageReading,
    StorageSite,
)
from custom_components.ausnz_disaster_watch.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_UNIT_OF_MEASUREMENT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

WIVENHOE = StorageSite(
    site_id="3922223",
    name="Wivenhoe",
    latitude=-27.3916,
    longitude=152.6090,
    owner="w00191",
    volume_ts=("368497010",),
    level_ts=("373853010",),
    full_volume_ml=1165238.0,
    full_level_m=67.0,
)
SOMERSET = StorageSite(
    site_id="3922255",
    name="Somerset",
    latitude=-27.1150,
    longitude=152.5574,
    owner="w00191",
    volume_ts=("368801010",),
    level_ts=("373609010",),
    full_volume_ml=379849.0,
    full_level_m=99.0,
)
# A storage reported by level only
CASCADE = StorageSite(
    site_id="3082595",
    name="Middle Cascade",
    latitude=-33.7,
    longitude=150.3,
    owner="w00231",
    volume_ts=(),
    level_ts=("373613010",),
    full_volume_ml=None,
    full_level_m=952.463,
)
PREFIX = "australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"
WIVENHOE_PERCENT = f"sensor.{PREFIX}_wivenhoe_percent_full"
WIVENHOE_VOLUME = f"sensor.{PREFIX}_wivenhoe_volume"
WIVENHOE_LEVEL = f"sensor.{PREFIX}_wivenhoe_level"
WIVENHOE_ABOVE = f"binary_sensor.{PREFIX}_wivenhoe_above_full_supply"
SOMERSET_PERCENT = f"sensor.{PREFIX}_somerset_percent_full"
SOMERSET_ABOVE = f"binary_sensor.{PREFIX}_somerset_above_full_supply"
CASCADE_LEVEL = f"sensor.{PREFIX}_middle_cascade_level"
CASCADE_ABOVE = f"binary_sensor.{PREFIX}_middle_cascade_above_full_supply"
OBSERVED = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


def _reading(
    site: StorageSite, volume: float | None = 937003.2, level: float | None = 64.686, observed: datetime = OBSERVED
) -> StorageReading:
    return StorageReading(site=site, observed_at=observed, volume_ml=volume, level_m=level, change_24h_ml=-2436.4)


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
    """Patch the coordinator's storage fetch."""
    with patch(
        "custom_components.ausnz_disaster_watch.dam_coordinator.async_fetch_readings",
        autospec=True,
    ) as fetch:
        yield fetch


@pytest.fixture(autouse=True)
def mock_operators() -> Generator[AsyncMock]:
    """Patch the operator feeds: no operator readings, and discovery returned unchanged."""
    with (
        patch(
            "custom_components.ausnz_disaster_watch.dam_coordinator.async_fetch_operator_readings",
            AsyncMock(return_value={}),
        ) as fetch,
        patch(
            "custom_components.ausnz_disaster_watch.dam_options.async_attach_operators",
            AsyncMock(side_effect=lambda session, readings, now: readings),
        ),
    ):
        yield fetch


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, sites: list[StorageSite]) -> None:
    hass.config_entries.async_update_entry(entry, options={CONF_DAM_STORAGES: [s.as_dict() for s in sites]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_storage_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """Each selected storage has percent, volume, level and above-full-supply entities."""
    mock_fetch.return_value = {
        WIVENHOE.key: _reading(WIVENHOE),
        SOMERSET.key: _reading(SOMERSET, volume=418000.0, level=99.6),
        CASCADE.key: _reading(CASCADE, volume=None, level=952.5),
    }
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [WIVENHOE, SOMERSET, CASCADE])

    percent = hass.states.get(WIVENHOE_PERCENT)
    assert percent is not None
    assert percent.state == "80.4"
    assert percent.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert percent.attributes["state_class"] == "measurement"
    assert percent.attributes[ATTR_ATTRIBUTION].startswith("© Queensland Bulk Water Supply Authority")
    assert percent.attributes["full_supply_volume_ml"] == 1165238.0
    assert percent.attributes["full_supply_level_m"] == 67.0
    assert percent.attributes["observed_at"] == "2026-10-15T00:00:00+00:00"
    assert percent.attributes["change_24h_ml"] == -2436.4
    assert percent.attributes["above_full_supply"] is False
    assert percent.attributes["distance_km"] == pytest.approx(39.4, abs=0.1)
    assert hass.states.get(WIVENHOE_VOLUME).state == "937003.2"
    assert hass.states.get(WIVENHOE_VOLUME).attributes[ATTR_UNIT_OF_MEASUREMENT] == "ML"
    assert hass.states.get(WIVENHOE_LEVEL).state == "64.686"
    assert hass.states.get(WIVENHOE_ABOVE).state == STATE_OFF

    # Somerset is over 100%: the flood compartment is in use
    assert hass.states.get(SOMERSET_PERCENT).state == "110.0"
    assert hass.states.get(SOMERSET_ABOVE).state == STATE_ON

    # A level-only storage has a level sensor and compares against full supply level
    assert hass.states.get(CASCADE_LEVEL).state == "952.5"
    assert hass.states.get(f"sensor.{PREFIX}_middle_cascade_percent_full") is None
    assert hass.states.get(CASCADE_ABOVE).state == STATE_ON

    registry = er.async_get(hass)
    entry = registry.async_get(WIVENHOE_PERCENT)
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_dam_storage_3922223_percent_full"


async def test_no_storages_no_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """Existing entries without selected storages create no dam coordinator or entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.dam_coordinator is None
    mock_fetch.assert_not_called()


async def test_outages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An outage keeps recent readings; without any, the entities are unavailable."""
    freezer.move_to(OBSERVED + timedelta(hours=20))
    mock_fetch.return_value = {WIVENHOE.key: _reading(WIVENHOE)}
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [WIVENHOE])
    assert hass.states.get(WIVENHOE_PERCENT).state == "80.4"

    mock_fetch.side_effect = DamSourceError("down")
    freezer.tick(DAM_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(WIVENHOE_PERCENT).state == "80.4"

    # Seven days after the reading it is too old to keep
    freezer.move_to(OBSERVED + timedelta(days=7, hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(WIVENHOE_PERCENT).state == STATE_UNAVAILABLE
    assert hass.states.get(WIVENHOE_ABOVE).state == STATE_UNAVAILABLE


async def test_storage_without_reading_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """A storage missing from the readings is unavailable; the first refresh failing does not block setup."""
    mock_fetch.side_effect = DamSourceError("down")
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [WIVENHOE])
    assert hass.states.get(WIVENHOE_PERCENT).state == STATE_UNAVAILABLE
    assert hass.states.get(WIVENHOE_ABOVE).state == STATE_UNAVAILABLE
    assert "observed_at" not in hass.states.get(WIVENHOE_PERCENT).attributes


async def test_deselected_storage_is_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """A storage removed from the selection loses its entities after the reload."""
    mock_fetch.return_value = {}
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [WIVENHOE, SOMERSET])
    registry = er.async_get(hass)
    assert registry.async_get(SOMERSET_PERCENT) is not None

    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_DAM_STORAGES: [WIVENHOE.as_dict()]})
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(SOMERSET_PERCENT) is None
    assert registry.async_get(SOMERSET_ABOVE) is None
    assert registry.async_get(WIVENHOE_PERCENT) is not None
    assert registry.async_get(WIVENHOE_ABOVE) is not None

    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_DAM_STORAGES: []})
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(WIVENHOE_PERCENT) is None
    assert registry.async_get(WIVENHOE_ABOVE) is None
    # Other entities of the entry are kept
    assert any(
        e.unique_id.endswith("_active_hazards_count")
        for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    )


async def _open_picker(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    """Open the options menu and choose the storage step."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert "dam_storages" in result["menu_options"]
    return await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "dam_storages"})


async def test_options_flow_picks_storages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """The storage step lists nearby storages; the chosen ones are stored and become entities."""
    mock_fetch.return_value = {}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_RADIUS: 40, "other": "kept"})
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ausnz_disaster_watch.dam_options.async_discover_storages",
        return_value=[_reading(SOMERSET), _reading(CASCADE, volume=None, level=952.5)],
    ) as discover:
        result = await _open_picker(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dam_storages"
    assert result["errors"] == {}
    assert discover.call_args.kwargs["radius_km"] == 40.0
    options = result["data_schema"].schema[CONF_DAM_STORAGES].config["options"]
    assert [option["value"] for option in options] == [SOMERSET.key, CASCADE.key]
    assert options[0]["label"].startswith("Somerset (")
    assert options[0]["label"].endswith("% full)")
    assert options[1]["label"].endswith(", 952.50 m)")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_DAM_STORAGES: [SOMERSET.key]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_DAM_STORAGES] == [SOMERSET.as_dict()]
    assert mock_config_entry.options["other"] == "kept"
    assert hass.states.get(SOMERSET_PERCENT) is not None


@pytest.mark.parametrize(
    ("discovered", "error"),
    [
        ([], "no_dam_storages"),
        (DamSourceError("down"), "dams_unavailable"),
        (TimeoutError(), "dams_unavailable"),
    ],
)
async def test_options_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    discovered: Any,
    error: str,
) -> None:
    """Without discovered storages the form says why, and a current selection can be kept."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ausnz_disaster_watch.dam_options.async_discover_storages",
        side_effect=discovered if isinstance(discovered, Exception) else None,
        return_value=discovered,
    ):
        result = await _open_picker(hass, mock_config_entry)
    assert result["errors"] == {"base": error}

    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_DAM_STORAGES: [WIVENHOE.as_dict()]})
    with patch(
        "custom_components.ausnz_disaster_watch.dam_options.async_discover_storages",
        side_effect=DamSourceError("down"),
    ):
        result = await _open_picker(hass, mock_config_entry)
    options = result["data_schema"].schema[CONF_DAM_STORAGES].config["options"]
    assert options == [{"value": WIVENHOE.key, "label": "Wivenhoe (selected)"}]
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_DAM_STORAGES: [WIVENHOE.key]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_DAM_STORAGES] == [WIVENHOE.as_dict()]


async def test_picker_home_mode_follows_home(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Home-mode entries search around the current home location."""
    hass.config.latitude, hass.config.longitude = -33.59, 150.71
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_LOCATION_MODE: LOCATION_MODE_HOME}
    )
    with patch(
        "custom_components.ausnz_disaster_watch.dam_options.async_discover_storages", return_value=[]
    ) as discover:
        await _open_picker(hass, mock_config_entry)
    assert (discover.call_args.kwargs["latitude"], discover.call_args.kwargs["longitude"]) == (-33.59, 150.71)


async def test_menu_offers_storages_in_australia_only(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """New Zealand entries have no storage step (no open NZ source)."""
    assert offers_dam_storages("QLD")
    assert offers_dam_storages("tas")
    assert not offers_dam_storages(STATE_NZ)
    assert not offers_dam_storages("")
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, data={**mock_config_entry.data, CONF_STATE: STATE_NZ})
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert "dam_storages" not in result["menu_options"]


def test_storage_label() -> None:
    """Labels show the distance and percent full, or the level without volume data."""
    assert storage_label(_reading(WIVENHOE), -27.3916, 152.6090) == "Wivenhoe (0.0 km, 80.4% full)"
    assert storage_label(_reading(CASCADE, volume=None, level=952.5), -33.7, 150.3) == (
        "Middle Cascade (0.0 km, 952.50 m)"
    )
    # Volume data without a full supply volume, and no level reading
    no_full = StorageSite(**{**WIVENHOE.as_dict(), "volume_ts": ("v",), "level_ts": (), "full_volume_ml": None})
    assert storage_label(_reading(no_full, volume=12345.6, level=None), -27.3916, 152.6090) == (
        "Wivenhoe (0.0 km, 12,346 ML)"
    )


async def test_diagnostics_list_the_storage_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
) -> None:
    """With storages selected, diagnostics list Water Data Online; the entry attribution does not change."""
    mock_fetch.return_value = {}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert "bom_water_storages" not in [s["key"] for s in diagnostics["coordinator"]["data_sources"]]
    attribution = mock_config_entry.runtime_data.attribution

    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_DAM_STORAGES: [WIVENHOE.as_dict()]})
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    keys = [s["key"] for s in diagnostics["coordinator"]["data_sources"]]
    assert keys.count("bom_water_storages") == 1
    assert mock_config_entry.runtime_data.attribution == attribution
    assert "Water Data Online" not in (attribution or "")


TOONUMBAR = StorageSite(
    site_id="585899",
    name="TOONUMBAR DAM",
    latitude=-28.6185,
    longitude=152.7936,
    owner="w00077",
    volume_ts=("132602010",),
    level_ts=("363676010",),
    full_volume_ml=11048.902,
    full_level_m=129.626,
    operator=OPERATOR_WATERNSW,
    operator_id="203042",
)
TOONUMBAR_PERCENT = f"sensor.{PREFIX}_toonumbar_dam_percent_full"
TOONUMBAR_ABOVE = f"binary_sensor.{PREFIX}_toonumbar_dam_above_full_supply"
SPILL = OperatorReading(
    OPERATOR_WATERNSW,
    datetime(2026, 10, 16, 3, 30, tzinfo=UTC),
    level_m=129.71,
    volume_ml=11158.0,
    spill_24h_ml=32.0,
    release_24h_ml=29.0,
    totals_date="2026-10-15",
)


async def test_operator_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
    mock_operators: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A matched WaterNSW gauge gives a fresher level and the spill signal; diagnostics list the feed."""
    freezer.move_to(datetime(2026, 10, 16, 4, 0, tzinfo=UTC))
    mock_fetch.return_value = {TOONUMBAR.key: _reading(TOONUMBAR, volume=11000.0, level=129.5)}
    mock_operators.return_value = {TOONUMBAR.key: SPILL}
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [TOONUMBAR])

    percent = hass.states.get(TOONUMBAR_PERCENT)
    assert percent.state == "99.6"
    assert percent.attributes["level_m"] == 129.71
    assert percent.attributes["source"] == "waternsw"
    assert percent.attributes["spilling"] is True
    assert percent.attributes["spillway_24h_ml"] == 32.0
    assert percent.attributes["release_24h_ml"] == 29.0
    assert percent.attributes["totals_date"] == "2026-10-15"
    assert percent.attributes["operator_observed_at"] == "2026-10-16T03:30:00+00:00"
    assert percent.attributes[ATTR_ATTRIBUTION].startswith("© State Government of NSW and WaterNSW, CC BY;")
    # Spilling although the Bureau's volume is under full supply
    assert hass.states.get(TOONUMBAR_ABOVE).state == STATE_ON

    keys = [
        s["key"]
        for s in (await async_get_config_entry_diagnostics(hass, mock_config_entry))["coordinator"]["data_sources"]
    ]
    assert "bom_water_storages" in keys
    assert "waternsw_storages" in keys
    assert "hydro_tasmania_lakes" not in keys

    # Water Data Online down: the operator reading alone keeps the storage current
    mock_fetch.side_effect = DamSourceError("down")
    freezer.tick(DAM_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(TOONUMBAR_PERCENT).state == "99.6"


async def test_operator_only_when_bom_never_answered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_providers: AsyncMock,
    mock_fetch: AsyncMock,
    mock_operators: AsyncMock,
) -> None:
    """Without any Water Data Online reading, the operator's level and volume are used."""
    mock_fetch.side_effect = DamSourceError("down")
    mock_operators.return_value = {TOONUMBAR.key: SPILL}
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, [TOONUMBAR])
    assert hass.states.get(TOONUMBAR_PERCENT).state == "101.0"
    assert hass.states.get(TOONUMBAR_ABOVE).state == STATE_ON
