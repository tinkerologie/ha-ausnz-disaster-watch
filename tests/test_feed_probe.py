"""Tests for the config flow's feed check (test-before-configure, #21)."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.config_flow import async_feeds_reachable
from custom_components.ausnz_disaster_watch.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_OVERRIDE_EMERGENCY,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    LOCATION_MODE_HOME,
    STATE_QLD,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.power import PowerOutageSource
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

PROVIDERS = "custom_components.ausnz_disaster_watch.config_flow.get_providers_for_config"
SETUP = "custom_components.ausnz_disaster_watch.async_setup_entry"

USER_INPUT: dict[str, Any] = {
    CONF_STATE: STATE_QLD,
    CONF_LOCATION_MODE: LOCATION_MODE_HOME,
    CONF_RADIUS: 50,
    CONF_OVERRIDE_EMERGENCY: True,
    CONF_EXCLUDE_HAZARD_REDUCTION: True,
}


class FakeProvider:
    """A hazard feed whose fetch returns ``result`` or raises it."""

    provides_hazards: ClassVar[bool] = True

    def __init__(self, result: list[CanonicalHazard] | BaseException) -> None:
        """Store what the fetch does."""
        self.result = result
        self.fetched = False

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Return or raise the stored result."""
        self.fetched = True
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class AuxiliaryProvider(FakeProvider):
    """A provider of auxiliary data only (national feeds, cameras)."""

    provides_hazards: ClassVar[bool] = False


@pytest.mark.real_feed_probe
async def test_reachable_when_one_feed_answers(hass: HomeAssistant) -> None:
    """One answering hazard feed is enough, as in the coordinator's first refresh."""
    hass.config.latitude, hass.config.longitude = -27.47, 153.03
    failing = FakeProvider(ProviderUnavailableError("down"))
    answering = FakeProvider([])
    with patch(PROVIDERS, return_value=[failing, answering]) as providers:
        assert await async_feeds_reachable(hass, {CONF_STATE: STATE_QLD}) is True
    assert failing.fetched and answering.fetched
    # Home-zone entries store no coordinates: the probe uses the home location
    config = providers.call_args.args[2]
    assert (config[CONF_LATITUDE], config[CONF_LONGITUDE]) == (-27.47, 153.03)


@pytest.mark.real_feed_probe
async def test_unreachable_when_every_feed_fails(hass: HomeAssistant) -> None:
    """Every hazard feed failing, whatever the error, means cannot_connect."""
    providers = [FakeProvider(ProviderUnavailableError("down")), FakeProvider(ValueError("bad"))]
    with patch(PROVIDERS, return_value=providers):
        assert await async_feeds_reachable(hass, {CONF_LATITUDE: -27.0, CONF_LONGITUDE: 153.0}) is False


@pytest.mark.real_feed_probe
async def test_unreachable_on_timeout(hass: HomeAssistant) -> None:
    """Feeds that do not answer within the timeout count as unreachable."""

    class Hanging(FakeProvider):
        async def async_fetch_hazards(self) -> list[CanonicalHazard]:
            await asyncio.sleep(10)
            return []  # pragma: no cover - cancelled by the timeout

    with (
        patch(PROVIDERS, return_value=[Hanging([])]),
        patch("custom_components.ausnz_disaster_watch.config_flow.FEED_PROBE_TIMEOUT", 0.01),
    ):
        assert await async_feeds_reachable(hass, {}) is False


@pytest.mark.real_feed_probe
async def test_cancellation_propagates(hass: HomeAssistant) -> None:
    """A cancelled fetch is not swallowed as a failed feed."""
    with (
        patch(PROVIDERS, return_value=[FakeProvider(asyncio.CancelledError())]),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_feeds_reachable(hass, {})


@pytest.mark.real_feed_probe
async def test_only_hazard_feeds_are_probed(hass: HomeAssistant) -> None:
    """Auxiliary and outage feeds never count; with no hazard feed there is nothing to test."""
    auxiliary = AuxiliaryProvider(ProviderUnavailableError("down"))
    outage = MagicMock(spec=PowerOutageSource)
    with patch(PROVIDERS, return_value=[auxiliary, outage]):
        assert await async_feeds_reachable(hass, {}) is True
    assert not auxiliary.fetched
    outage.async_fetch_hazards.assert_not_called()


async def test_user_step_shows_cannot_connect(hass: HomeAssistant, feeds_reachable: AsyncMock) -> None:
    """The home-zone setup shows cannot_connect and recovers once a feed answers."""
    feeds_reachable.return_value = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=USER_INPUT)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    feeds_reachable.return_value = True
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=USER_INPUT)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_location_step_shows_cannot_connect(hass: HomeAssistant, feeds_reachable: AsyncMock) -> None:
    """The custom location step checks the feeds before creating the entry."""
    location = {
        "preset_council": "custom",
        CONF_LOCATION_NAME: "Caboolture",
        CONF_LATITUDE: -27.08,
        CONF_LONGITUDE: 152.95,
        CONF_COUNCIL_DASHBOARD_URL: "",
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM}
    )
    assert result["step_id"] == "location"

    feeds_reachable.return_value = False
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=location)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "location"
    assert result["errors"] == {"base": "cannot_connect"}
    # The probe saw the custom point, not the home location
    assert feeds_reachable.call_args.args[1][CONF_LATITUDE] == -27.08

    feeds_reachable.return_value = True
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=location)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_reconfigure_shows_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, feeds_reachable: AsyncMock
) -> None:
    """Reconfigure keeps the entry unchanged while no feed answers."""
    mock_config_entry.add_to_hass(hass)
    user_input = {
        CONF_STATE: STATE_QLD,
        CONF_LOCATION_NAME: "Updated Moreton Bay",
        CONF_LATITUDE: -27.25,
        CONF_LONGITUDE: 153.0,
        CONF_RADIUS: 75,
        CONF_OVERRIDE_EMERGENCY: False,
        CONF_EXCLUDE_HAZARD_REDUCTION: False,
        CONF_COUNCIL_DASHBOARD_URL: "",
    }
    feeds_reachable.return_value = False
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data[CONF_LOCATION_NAME] != "Updated Moreton Bay"

    feeds_reachable.return_value = True
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_LOCATION_NAME] == "Updated Moreton Bay"


@pytest.mark.real_feed_probe
async def test_first_answer_is_enough(hass: HomeAssistant) -> None:
    """One answering feed passes at once; a hanging feed is cancelled, not waited for."""
    cancelled = asyncio.Event()

    class Hanging(FakeProvider):
        async def async_fetch_hazards(self) -> list[CanonicalHazard]:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return []  # pragma: no cover - cancelled once the other feed answers

    with (
        patch(PROVIDERS, return_value=[Hanging([]), FakeProvider([])]),
        patch("custom_components.ausnz_disaster_watch.config_flow.FEED_PROBE_TIMEOUT", 5),
    ):
        async with asyncio.timeout(1):
            assert await async_feeds_reachable(hass, {}) is True
    assert cancelled.is_set()
