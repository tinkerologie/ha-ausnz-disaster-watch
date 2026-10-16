"""Emergency broadcaster: bundled table, sensor, media source and options step (#73)."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.broadcaster import (
    BROADCASTER_NEAREST,
    choose_broadcaster,
    load_broadcasters,
    media_content_id,
)
from custom_components.ausnz_disaster_watch.broadcaster_sensor import EmergencyBroadcasterSensor
from custom_components.ausnz_disaster_watch.const import CONF_EMERGENCY_BROADCASTER, DOMAIN
from custom_components.ausnz_disaster_watch.media_source import async_get_media_source
from custom_components.ausnz_disaster_watch.providers.sources import (
    BROADCASTER_SOURCES,
    DATA_SOURCES,
    REGISTER_PATH,
    sources_for_broadcaster,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import BrowseMediaSource, MediaSourceItem, PlayMedia, Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "custom_components" / "ausnz_disaster_watch" / "data" / "emergency_broadcasters.json"
BRISBANE = (-27.4698, 153.0251)
CAIRNS = (-16.92, 145.77)
CHRISTCHURCH = (-43.53, 172.63)
SENSOR = "sensor.australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay_emergency_broadcaster"


@pytest.fixture(autouse=True)
def mock_providers() -> Generator[AsyncMock]:
    """Patch provider construction with one provider that returns no hazards."""
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[provider],
    ):
        yield provider


@pytest.fixture
def sensor_enabled() -> Generator[None]:
    """Create the (disabled by default) broadcaster sensor enabled."""
    with patch.object(EmergencyBroadcasterSensor, "_attr_entity_registry_enabled_default", True):
        yield


def _entry(
    base: MockConfigEntry, option: str | None = BROADCASTER_NEAREST, unique_id: str | None = None, **data: Any
) -> MockConfigEntry:
    options = {} if option is None else {CONF_EMERGENCY_BROADCASTER: option}
    return MockConfigEntry(
        domain=DOMAIN,
        title=base.title,
        data={**base.data, **data},
        options=options,
        unique_id=unique_id or base.unique_id,
        version=base.version,
        minor_version=2,
    )


async def _browse(hass: HomeAssistant, uri: str) -> BrowseMediaSource:
    source = await async_get_media_source(hass)
    return await source.async_browse_media(MediaSourceItem.from_uri(hass, uri, None))


async def _resolve(hass: HomeAssistant, uri: str) -> PlayMedia:
    source = await async_get_media_source(hass)
    return await source.async_resolve_media(MediaSourceItem.from_uri(hass, uri, None))


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def test_table_covers_every_abc_region_and_rnz_over_https() -> None:
    """52 ABC Local Radio regions and RNZ National, HTTPS HLS only, with provenance and a refresh date."""
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    assert table["refreshed"]
    assert "Radio Browser" in table["sources"]["directory"]
    stations = load_broadcasters()
    assert len([s for s in stations.values() if s.network == "ABC Local Radio"]) == 52
    assert {s.key for s in stations.values() if s.country == "NZ"} == {"rnz_national"}
    assert len({s.stream_url for s in stations.values()}) == len(stations)
    for station in stations.values():
        assert station.stream_url.startswith("https://")
        assert station.mime_type == "application/vnd.apple.mpegurl"
        assert (station.country == "NZ") == (station.state == "NZ")
        assert -48 < station.latitude < -9
    # Every stream host is in the data source register (#34)
    register = (ROOT / REGISTER_PATH).read_text(encoding="utf-8")
    for host in {urlparse(s.stream_url).netloc for s in stations.values()}:
        assert host in register
    for keys in BROADCASTER_SOURCES.values():
        assert all(key in DATA_SOURCES for key in keys)
    assert [s.key for s in sources_for_broadcaster("NZ")] == ["rnz_national", "radio_browser"]


def test_choose_broadcaster() -> None:
    """Nearest station of the entry's country, a chosen station, or none when off."""
    stations = load_broadcasters()
    assert choose_broadcaster(stations, "off", "QLD", *BRISBANE) is None
    nearest = choose_broadcaster(stations, BROADCASTER_NEAREST, "QLD", *BRISBANE)
    assert nearest is not None
    assert (nearest.station.key, nearest.selection) == ("abc_brisbane", "nearest")
    assert nearest.distance_km < 5
    far_north = choose_broadcaster(stations, BROADCASTER_NEAREST, "QLD", *CAIRNS)
    assert far_north is not None
    assert far_north.station.key == "abc_farnorth"
    # New Zealand entries only get New Zealand stations, even near Australia
    nz = choose_broadcaster(stations, BROADCASTER_NEAREST, "NZ", *BRISBANE)
    assert nz is not None
    assert nz.station.key == "rnz_national"
    chosen = choose_broadcaster(stations, "abc_sunshine", "QLD", *BRISBANE)
    assert chosen is not None
    assert (chosen.station.key, chosen.selection) == ("abc_sunshine", "chosen")
    # A station that left the table falls back to the nearest
    gone = choose_broadcaster(stations, "abc_gone", "QLD", *BRISBANE)
    assert gone is not None
    assert gone.station.key == "abc_brisbane"
    # An ABC station kept after the entry moved to New Zealand is not used there
    moved = choose_broadcaster(stations, "abc_sunshine", "NZ", *CHRISTCHURCH)
    assert moved is not None
    assert (moved.station.key, moved.selection) == ("rnz_national", "nearest")
    assert choose_broadcaster({}, BROADCASTER_NEAREST, "QLD", *BRISBANE) is None
    assert media_content_id("abc") == "media-source://ausnz_disaster_watch/emergency_broadcaster/abc"


@pytest.mark.usefixtures("sensor_enabled")
async def test_sensor(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The sensor names the station and carries the stream; it stays available when the feeds fail."""
    entry = _entry(mock_config_entry)
    await _setup(hass, entry)
    state = hass.states.get(SENSOR)
    assert state is not None
    assert state.state == "ABC Brisbane"
    assert state.attributes["stream_url"] == "https://streaming.abc-cdn.net.au/audio/hls/localbrisbane.m3u8"
    assert state.attributes["media_content_id"] == media_content_id(entry.entry_id)
    assert state.attributes["region"] == "brisbane"
    assert state.attributes["selection"] == "nearest"
    assert "ABC Local Radio" in state.attributes["attribution"]
    assert "Radio Browser" in state.attributes["attribution"]

    entry.runtime_data.last_update_success = False
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "ABC Brisbane"  # type: ignore[union-attr]


async def test_sensor_disabled_by_default_and_removed_when_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The sensor is disabled by default; turning the broadcaster off removes it."""
    entry = _entry(mock_config_entry, "abc_sunshine")
    await _setup(hass, entry)
    registry = er.async_get(hass)
    registry_entry = registry.async_get(SENSOR)
    assert registry_entry is not None
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    hass.config_entries.async_update_entry(entry, options={CONF_EMERGENCY_BROADCASTER: "off"})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(SENSOR) is None


@pytest.mark.usefixtures("sensor_enabled")
async def test_sensor_unavailable_without_station(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Without a station in the table the sensor is unavailable."""
    with patch("custom_components.ausnz_disaster_watch.broadcaster_sensor.async_load_broadcasters", return_value={}):
        await _setup(hass, _entry(mock_config_entry))
    state = hass.states.get(SENSOR)
    assert state is not None
    assert state.state == "unavailable"
    assert "stream_url" not in state.attributes
    sensor = EmergencyBroadcasterSensor(hass.config_entries.async_entries(DOMAIN)[0].runtime_data, {})
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


async def test_media_source_browse_and_resolve(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Enabled entries are listed; their media source ID resolves to the current HTTPS stream."""
    entry = _entry(mock_config_entry)
    await _setup(hass, entry)
    off = _entry(mock_config_entry, None, unique_id="off", location_name="Off")
    await _setup(hass, off)

    root = await _browse(hass, f"media-source://{DOMAIN}")
    assert root.title == "Australia and New Zealand Disaster Watch"
    assert [child.media_content_id for child in root.children] == [media_content_id(entry.entry_id)]
    assert root.children[0].title == f"Emergency broadcaster: ABC Brisbane ({entry.title})"
    assert root.children[0].can_play

    item = await _browse(hass, media_content_id(entry.entry_id))
    assert item.can_play

    resolved = await _resolve(hass, media_content_id(entry.entry_id))
    assert resolved.url == "https://streaming.abc-cdn.net.au/audio/hls/localbrisbane.m3u8"
    assert resolved.mime_type == "application/vnd.apple.mpegurl"

    # The ID follows the entry: a chosen station is resolved at play time
    hass.config_entries.async_update_entry(entry, options={CONF_EMERGENCY_BROADCASTER: "abc_goldcoast"})
    resolved = await _resolve(hass, media_content_id(entry.entry_id))
    assert resolved.url.endswith("/localgoldcoast.m3u8")

    for bad in (
        media_content_id(off.entry_id),
        media_content_id("missing"),
        f"media-source://{DOMAIN}/other/{entry.entry_id}",
    ):
        with pytest.raises(Unresolvable):
            await _resolve(hass, bad)
        with pytest.raises(BrowseError):
            await _browse(hass, bad)

    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(Unresolvable):
        await _resolve(hass, media_content_id(entry.entry_id))
    root = await _browse(hass, f"media-source://{DOMAIN}")
    assert root.children == []


async def test_media_source_rejects_other_domains_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An entry ID of another integration does not resolve."""
    await _setup(hass, _entry(mock_config_entry))
    other = MockConfigEntry(domain="other", data={})
    other.add_to_hass(hass)
    with pytest.raises(Unresolvable):
        await _resolve(hass, media_content_id(other.entry_id))


async def test_options_step(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The step is in the menu, defaults to off, lists stations nearest first and saves the choice."""
    entry = _entry(mock_config_entry, None)
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert "emergency_broadcaster" in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "emergency_broadcaster"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"nearest": "ABC Brisbane"}
    field = result["data_schema"].schema[CONF_EMERGENCY_BROADCASTER]  # type: ignore[index]
    values = [option["value"] for option in field.config["options"]]
    assert values[:3] == ["off", "nearest", "abc_brisbane"]
    assert "rnz_national" not in values
    assert result["data_schema"]({})[CONF_EMERGENCY_BROADCASTER] == "off"  # type: ignore[misc]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EMERGENCY_BROADCASTER: "abc_sunshine"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_EMERGENCY_BROADCASTER] == "abc_sunshine"


async def test_options_step_home_zone_and_stale_choice(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Home-zone NZ entries rank from the home location; a station that left the table shows as nearest."""
    hass.config.latitude, hass.config.longitude = CHRISTCHURCH
    entry = _entry(mock_config_entry, "abc_gone", state="NZ", location_mode="home")
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "emergency_broadcaster"}
    )
    assert result["description_placeholders"] == {"nearest": "RNZ National"}
    field = result["data_schema"].schema[CONF_EMERGENCY_BROADCASTER]  # type: ignore[index]
    assert [option["value"] for option in field.config["options"]] == ["off", "nearest", "rnz_national"]
    assert result["data_schema"]({})[CONF_EMERGENCY_BROADCASTER] == "nearest"  # type: ignore[misc]
