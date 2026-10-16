"""Optional feeds never hold up a refresh or entry setup (#75)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import coordinator as coordinator_module
from custom_components.ausnz_disaster_watch.const import LAST_GOOD_MAX_AGE
from custom_components.ausnz_disaster_watch.coordinator import (
    AustralianDisasterWatchCoordinator,
    OptionalFeedTimeoutError,
)
from custom_components.ausnz_disaster_watch.models import AirQualityStationData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

PREFIX = "australia_and_new_zealand_disaster_watch_qld_city_of_moreton_bay"
STATION = AirQualityStationData(station_id="s1", station_name="Station", overall_rating="Fair")
PROVIDERS = "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config"


@pytest.fixture(autouse=True)
def short_timeouts() -> Any:
    """Shrink the optional-feed timeouts so tests run fast."""
    with (
        patch.object(coordinator_module, "FIRST_REFRESH_OPTIONAL_TIMEOUT", 0.05),
        patch.object(coordinator_module, "OPTIONAL_FEED_TIMEOUT", 0.05),
    ):
        yield


class SlowFeed:
    """An air quality collector that answers only when released."""

    def __init__(self, result: list[AirQualityStationData] | Exception) -> None:
        self.release = asyncio.Event()
        self.result = result
        self.calls = 0

    async def __call__(self) -> list[AirQualityStationData]:
        self.calls += 1
        await self.release.wait()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def provider_with(feed: SlowFeed) -> AsyncMock:
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_air_quality = feed
    return provider


async def test_slow_optional_feed_does_not_block_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Setup finishes while an optional feed is still busy; its entity fills in when it answers."""
    feed = SlowFeed([STATION])
    mock_config_entry.add_to_hass(hass)
    with patch(PROVIDERS, return_value=[provider_with(feed)]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        state = hass.states.get(f"sensor.{PREFIX}_air_quality")
        assert state is not None
        assert state.state == "unknown"
        assert caplog.text.count("did not answer within") == 1

        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        # The late answer triggered a refresh, which used it without calling the feed again
        state = hass.states.get(f"sensor.{PREFIX}_air_quality")
        assert state is not None
        assert state.state == "Fair"
        assert feed.calls == 1
        assert "is answering again" in caplog.text
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_timeout_uses_last_good_and_logs_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later timeout keeps the last good result for a while, then reads as unavailable."""
    mock_config_entry.add_to_hass(hass)
    feed = SlowFeed([STATION])
    feed.release.set()
    provider = provider_with(feed)
    with patch(PROVIDERS, return_value=[provider]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.data.air_quality_stations == [STATION]

    feed.release.clear()
    caplog.set_level(logging.WARNING)
    assert (await coordinator._async_update_data()).air_quality_stations == [STATION]
    # Still busy: the same call is awaited again (no second request), and nothing new is logged
    assert (await coordinator._async_update_data()).air_quality_stations == [STATION]
    assert feed.calls == 2
    assert caplog.text.count("did not answer within") == 1

    # Once the last good result is too old, the feed reads as unavailable
    coordinator._optional_last_good = {
        key: (when - LAST_GOOD_MAX_AGE - timedelta(minutes=1), value)
        for key, (when, value) in coordinator._optional_last_good.items()
    }
    assert (await coordinator._async_update_data()).air_quality_stations == []

    with patch.object(coordinator, "async_request_refresh"):
        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    assert (await coordinator._async_update_data()).air_quality_stations == [STATION]


async def test_late_failure_is_reported_on_next_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A call that fails after timing out does not request a refresh; the next refresh sees the error."""
    mock_config_entry.add_to_hass(hass)
    feed = SlowFeed(RuntimeError("boom"))
    with patch(PROVIDERS, return_value=[provider_with(feed)]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    with patch.object(coordinator, "async_request_refresh") as refresh:
        assert (await coordinator._async_update_data()).air_quality_stations == []
        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        refresh.assert_not_called()
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.data.air_quality_stations == []
    assert feed.calls == 1


async def test_cancelled_late_call_requests_nothing(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A timed-out call cancelled by unload does not request a refresh."""
    mock_config_entry.add_to_hass(hass)
    feed = SlowFeed([STATION])
    with patch(PROVIDERS, return_value=[provider_with(feed)]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    with patch.object(coordinator, "async_request_refresh") as refresh:
        await coordinator._async_update_data()
        for task in coordinator._optional_tasks.values():
            task.cancel()
        await hass.async_block_till_done(wait_background_tasks=True)
        refresh.assert_not_called()
    # The next refresh treats the cancelled call as unavailable, then calls the feed again
    assert (await coordinator._async_update_data()).air_quality_stations == []
    feed.release.set()
    assert (await coordinator._async_update_data()).air_quality_stations == [STATION]


async def test_timeout_without_result_raises(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """With no earlier result a timed-out feed raises OptionalFeedTimeoutError."""
    mock_config_entry.add_to_hass(hass)
    feed = SlowFeed([STATION])
    owner = AsyncMock()
    owner.async_fetch_air_quality = feed
    with patch(PROVIDERS, return_value=[]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    with patch.object(coordinator, "async_request_refresh") as refresh:
        with pytest.raises(OptionalFeedTimeoutError):
            await coordinator._async_optional(owner, "async_fetch_air_quality")
        # A second timeout of the same call does not add a second late-answer refresh
        with pytest.raises(OptionalFeedTimeoutError):
            await coordinator._async_optional(owner, "async_fetch_air_quality")
        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    refresh.assert_called_once()
    assert await coordinator._async_optional(owner, "async_fetch_air_quality") == [STATION]


async def test_slow_fire_outlook_does_not_block(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A slow fire danger outlook update is skipped for this refresh."""
    mock_config_entry.add_to_hass(hass)
    release = asyncio.Event()

    async def slow_update() -> None:
        await release.wait()

    with patch(PROVIDERS, return_value=[provider_with(SlowFeed([]))]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    with patch.object(coordinator.fire_service, "async_update", slow_update):
        data = await coordinator._async_update_data()
    assert data.fire_outlook is None
    release.set()
    for task in coordinator._optional_tasks.values():
        task.cancel()
    await hass.async_block_till_done(wait_background_tasks=True)
