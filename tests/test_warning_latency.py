"""Measure scheduled warning discovery and publication using the HA event clock."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util


async def test_warning_latency_through_scheduled_polls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
) -> None:
    """Measure discovery, a slow warning fetch and a slow auxiliary fetch independently."""
    freezer.move_to("2026-11-12T00:00:00Z")
    origin = dt_util.utcnow()
    provider = AsyncMock()
    phase = 0
    events: dict[str, float] = {}
    hazard_started = asyncio.Event()
    hazard_release = asyncio.Event()
    auxiliary_started = asyncio.Event()
    auxiliary_release = asyncio.Event()

    def elapsed() -> float:
        return (dt_util.utcnow() - origin).total_seconds()

    async def hazards() -> list[CanonicalHazard]:
        if phase == 0:
            return []
        events["poll"] = elapsed()
        hazard_started.set()
        if phase == 1:
            await hazard_release.wait()
        events["hazards_ready"] = elapsed()
        return [
            CanonicalHazard(
                id="timing",
                source="Fixture",
                title="Scheduled warning",
                hazard_type=HazardType.FLOOD,
                warning_level=WarningLevel.WATCH_AND_ACT if phase == 1 else WarningLevel.EMERGENCY_WARNING,
                latitude=float(mock_config_entry.data["latitude"]),
                longitude=float(mock_config_entry.data["longitude"]),
            )
        ]

    async def auxiliary() -> list:
        if phase == 1:
            auxiliary_started.set()
            await auxiliary_release.wait()
        return []

    provider.async_fetch_hazards.side_effect = hazards
    provider.async_fetch_weather_warnings.side_effect = auxiliary
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        entity = next(
            state.entity_id
            for state in hass.states.async_all("sensor")
            if state.entity_id.endswith("_highest_warning_level")
        )
        assert hass.states.get(entity).state == "all_clear"

        published = asyncio.Event()

        @callback
        def state_changed(event) -> None:
            if event.data["new_state"].state in ("watch_and_act", "emergency_warning"):
                published.set()

        unsubscribe = async_track_state_change_event(hass, [entity], state_changed)
        phase = 1
        freezer.tick(timedelta(seconds=1))
        issued = elapsed()
        freezer.tick(timedelta(seconds=297))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not hazard_started.is_set()

        freezer.tick(timedelta(seconds=2))
        async_fire_time_changed(hass)
        await asyncio.wait_for(hazard_started.wait(), timeout=2)
        assert hass.states.get(entity).state == "all_clear"
        freezer.tick(timedelta(seconds=9))
        hazard_release.set()
        await asyncio.wait_for(auxiliary_started.wait(), timeout=2)
        assert hass.states.get(entity).state == "all_clear"
        freezer.tick(timedelta(seconds=4))
        auxiliary_release.set()
        await asyncio.wait_for(published.wait(), timeout=2)
        await hass.async_block_till_done()
        first = hass.states.get(entity)
        assert first.state == "watch_and_act"
        baseline = {
            "discovery_seconds": events["poll"] - issued,
            "warning_source_seconds": events["hazards_ready"] - events["poll"],
            "publication_seconds": (first.last_updated - origin).total_seconds() - events["hazards_ready"],
        }

        phase = 2
        published.clear()
        freezer.tick(timedelta(seconds=59))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(entity).state == "watch_and_act"
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await asyncio.wait_for(published.wait(), timeout=2)
        assert hass.states.get(entity).state == "emergency_warning"
        baseline["active_interval_seconds"] = events["poll"] - (first.last_updated - origin).total_seconds()
        unsubscribe()
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert baseline == {
        "discovery_seconds": 299,
        "warning_source_seconds": 9,
        "publication_seconds": 4,
        "active_interval_seconds": 60,
    }
    (tmp_path / "warning-latency.json").write_text(json.dumps(baseline))
