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
from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import (
    AustralianDisasterWatchCoordinator,
    OptionalFeedTimeoutError,
)
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    DisasterCoordinatorData,
    FireDangerOutlook,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    caplog.set_level(logging.DEBUG, logger=coordinator_module.__name__)
    feed = SlowFeed([STATION])
    mock_config_entry.add_to_hass(hass)
    with patch(PROVIDERS, return_value=[provider_with(feed)]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        state = hass.states.get(f"sensor.{PREFIX}_air_quality")
        assert state is not None
        assert state.state == "unknown"
        assert not any(
            record.levelno >= logging.WARNING and "Optional feed" in record.message for record in caplog.records
        )
        assert any(record.levelno == logging.DEBUG and "at startup" in record.message for record in caplog.records)

        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        # The late answer triggered a refresh, which used it without calling the feed again
        state = hass.states.get(f"sensor.{PREFIX}_air_quality")
        assert state is not None
        assert state.state == "Fair"
        assert feed.calls == 1
        assert "is answering again" not in caplog.text
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_timeout_uses_last_good_and_logs_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later timeout keeps the last good reading, then reads as unknown once it is too old."""
    feed = SlowFeed([STATION])
    feed.release.set()
    mock_config_entry.add_to_hass(hass)
    entity_id = f"sensor.{PREFIX}_air_quality"

    async def poll() -> str:
        """Run a coordinator refresh (as the update interval would) and return the sensor state."""
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        return state.state

    with patch(PROVIDERS, return_value=[provider_with(feed)]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "Fair"

        feed.release.clear()
        caplog.set_level(logging.WARNING)
        assert await poll() == "Fair"
        # Still busy: the same call is waited on again (no second request), and nothing new is logged
        assert await poll() == "Fair"
        assert feed.calls == 2
        warnings = [record for record in caplog.records if "did not answer within" in record.message]
        assert len(warnings) == 1
        assert warnings[0].levelno == logging.WARNING
        assert "using its last result" in warnings[0].message

        # Once the last good reading is older than the stale age, the sensor reads as unknown
        with patch.object(coordinator_module, "LAST_GOOD_MAX_AGE", timedelta(0)):
            assert await poll() == "unknown"
            # The late answer then requests a refresh, which fills the sensor in again
            feed.release.set()
            await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(entity_id).state == "Fair"
        assert feed.calls == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


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


async def test_slow_fire_outlook_does_not_block(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """A startup timeout is DEBUG only and its late fire outlook is published (#116)."""
    caplog.set_level(logging.DEBUG, logger=coordinator_module.__name__)
    mock_config_entry.add_to_hass(hass)
    release = asyncio.Event()
    outlook = FireDangerOutlook(
        district_number="QLD_FW015", district_name="Southeast Coast", time_zone="Australia/Brisbane", source="test"
    )
    with patch(PROVIDERS, return_value=[]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    async def slow_update() -> None:
        await release.wait()
        coordinator.fire_service.outlook = outlook

    with (
        patch.object(coordinator.fire_service, "async_update", slow_update),
        patch.object(coordinator, "async_request_refresh") as refresh,
    ):
        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data.fire_outlook is None
        records = [record for record in caplog.records if "Optional feed" in record.message]
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        assert "at startup" in records[0].message
        assert "FireDangerService.async_update" in records[0].message
        assert not coordinator._optional_timed_out
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        refresh.assert_awaited_once()
        assert (await coordinator._async_update_data()).fire_outlook == outlook
        assert "is answering again" not in caplog.text


@pytest.mark.parametrize("log_timeout", [True, False])
async def test_startup_timeout_then_sustained_outage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture, log_timeout: bool
) -> None:
    """The same slow call warns only after startup, accurately, once, unless logging is disabled."""
    caplog.set_level(logging.DEBUG, logger=coordinator_module.__name__)
    mock_config_entry.add_to_hass(hass)
    feed = SlowFeed([STATION])
    owner = provider_with(feed)
    with patch(PROVIDERS, return_value=[]):
        coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    with patch.object(coordinator, "async_request_refresh"):
        with pytest.raises(OptionalFeedTimeoutError):
            await coordinator._async_optional(owner, "async_fetch_air_quality", log_timeout=log_timeout)
        assert not coordinator._optional_timed_out
        assert not any(
            record.levelno >= logging.WARNING and "Optional feed" in record.message for record in caplog.records
        )
        coordinator.data = DisasterCoordinatorData()
        for _ in range(2):
            with pytest.raises(OptionalFeedTimeoutError):
                await coordinator._async_optional(owner, "async_fetch_air_quality", log_timeout=log_timeout)
        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == int(log_timeout)
        if log_timeout:
            assert "did not answer within" in warnings[0].message
            assert "has no recent result" in warnings[0].message
            assert "using its last result" not in warnings[0].message
        assert feed.calls == 1
        feed.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert await coordinator._async_optional(owner, "async_fetch_air_quality", log_timeout=log_timeout) == [STATION]
        recovery = [record for record in caplog.records if "is answering again" in record.message]
        assert len(recovery) == int(log_timeout)
        if log_timeout:
            assert recovery[0].levelno == logging.INFO


async def test_location_change_uses_only_the_new_points_result(hass: HomeAssistant) -> None:
    """After the home location moves, a slow call for the old point is never shown, and the new one is.

    The old call finishing late must not use its result, request a refresh, or stop the new call's
    late answer from filling the sensor in.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={"state": "QLD", "location_mode": "home", "radius": 50},
        unique_id="ausnz_disaster_watch_qld_home",
    )
    entry.add_to_hass(hass)
    hass.config.latitude, hass.config.longitude = -27.47, 153.03
    releases: list[asyncio.Event] = []
    results = [
        [AirQualityStationData(station_id="old", station_name="Old point", overall_rating="Poor")],
        [AirQualityStationData(station_id="new", station_name="New point", overall_rating="Fair")],
    ]

    async def per_call_feed() -> list[AirQualityStationData]:
        release = asyncio.Event()
        releases.append(release)
        result = results[len(releases) - 1]
        await release.wait()
        return result

    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_air_quality = per_call_feed

    def aq_state() -> str:
        entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_air_quality_rating")
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state.state

    with patch(PROVIDERS, return_value=[provider]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert aq_state() == "unknown"  # the old point's call is still running

        hass.config.latitude, hass.config.longitude = -33.87, 151.21
        await entry.runtime_data.async_refresh()  # the next poll asks again for the new point
        await hass.async_block_till_done()
        assert len(releases) == 2
        assert aq_state() == "unknown"

        releases[0].set()  # the old point answers late: its result is not shown
        for _ in range(5):
            await asyncio.sleep(0)
        await hass.async_block_till_done()
        assert aq_state() == "unknown"

        releases[1].set()  # the new point answers late: its refresh fills the sensor in
        await hass.async_block_till_done(wait_background_tasks=True)
        assert aq_state() == "Fair"
    assert await hass.config_entries.async_unload(entry.entry_id)
