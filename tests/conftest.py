"""Shared fixtures for Australian Emergency Hazards integration tests."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

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
    STATE_QLD,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .deprecations import HANDLER as DEPRECATION_REPORTS  # noqa: TID251 - test helper, not production code


@pytest.fixture(autouse=True)
def fail_on_ha_deprecation_reports() -> Generator[None]:
    """Fail when Home Assistant logs deprecated use by this integration (#121).

    Requested by ``auto_enable_custom_integrations`` so it is set up before ``hass``
    and checks after ``hass`` has stopped, which catches reports logged during setup,
    the test and shutdown. Reports logged while modules were imported surface on the
    first test. Fix the call in the integration; do not silence the check.
    """
    yield
    if reports := DEPRECATION_REPORTS.pop_reports():
        pytest.fail(
            f"Home Assistant reported deprecated use by {DOMAIN}:\n" + "\n".join(reports),
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(fail_on_ha_deprecation_reports: None, enable_custom_integrations: None) -> None:
    """Enable custom integration discovery in all tests."""


@pytest.fixture(autouse=True)
def no_fire_danger_network(request: pytest.FixtureRequest) -> Generator[None]:
    """Stop the coordinator's fire danger service reaching the network (#28).

    Tests of the service itself opt out with ``@pytest.mark.real_fire_service``.
    """
    if request.node.get_closest_marker("real_fire_service"):
        yield
        return
    with patch(
        "custom_components.ausnz_disaster_watch.providers.fire_danger.FireDangerService.async_update",
        AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture(autouse=True)
def no_statewide_road_feeds() -> Iterator[None]:
    """Keep the statewide road feeds (#29) off the network; road tests patch in their own providers."""
    with patch("custom_components.ausnz_disaster_watch.coordinator.get_road_providers_for_config", return_value=[]):
        yield


@pytest.fixture(autouse=True)
def feeds_reachable(request: pytest.FixtureRequest) -> Iterator[AsyncMock]:
    """Let the config flow's feed check (#21) pass without the network.

    Tests of the check itself opt out with ``@pytest.mark.real_feed_probe``; the others can
    set ``feeds_reachable.return_value = False`` to see cannot_connect.
    """
    if request.node.get_closest_marker("real_feed_probe"):
        yield AsyncMock()
        return
    with patch(
        "custom_components.ausnz_disaster_watch.config_flow.async_feeds_reachable",
        AsyncMock(return_value=True),
    ) as probe:
        yield probe


ICONS: dict[str, Any] = json.loads(
    (Path(__file__).parent.parent / "custom_components" / DOMAIN / "icons.json").read_text(encoding="utf-8")
)


@pytest.fixture
def entity_icon(hass: HomeAssistant) -> Callable[[str], str | None]:
    """Return the icon the frontend shows for an entity: its icons.json icon for its state (#21)."""

    def _icon(entity_id: str) -> str | None:
        entry = er.async_get(hass).async_get(entity_id)
        state = hass.states.get(entity_id)
        if entry is None or entry.translation_key is None or state is None:
            return None
        icons = ICONS["entity"].get(entry.domain, {}).get(entry.translation_key)
        if icons is None:
            return None
        return icons.get("state", {}).get(state.state, icons["default"])

    return _icon


@pytest.fixture
def mock_hazard_emergency_warning() -> CanonicalHazard:
    """Return a mock Emergency Warning hazard (AWS Level 3)."""
    return CanonicalHazard(
        id="QLD_QFD_WARN_101",
        source="Queensland Fire Department",
        title="EMERGENCY WARNING - Bushfire at Caboolture",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-27.0800,
        longitude=152.9500,
        updated_at=datetime.now(UTC),
        location_name="Caboolture, Moreton Bay",
        is_hazard_reduction=False,
        status="Going",
        responsible_agency="QFD",
        web_url="https://www.fire.qld.gov.au",
        raw_properties={"OBJECTID": 101, "LGA": "City of Moreton Bay"},
    )


@pytest.fixture
def mock_hazard_watch_and_act() -> CanonicalHazard:
    """Return a mock Watch and Act hazard (AWS Level 2)."""
    return CanonicalHazard(
        id="QLD_QFD_WARN_102",
        source="Queensland Fire Department",
        title="WATCH AND ACT - Prepare to Leave at Morayfield",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.WATCH_AND_ACT,
        latitude=-27.1000,
        longitude=152.9400,
        updated_at=datetime.now(UTC),
        location_name="Morayfield, Moreton Bay",
        is_hazard_reduction=False,
        status="Going",
        responsible_agency="QFD",
        web_url="https://www.fire.qld.gov.au",
    )


@pytest.fixture
def mock_hazard_advice() -> CanonicalHazard:
    """Return a mock Advice hazard (AWS Level 1)."""
    return CanonicalHazard(
        id="QLD_COUNCIL_ROAD_555",
        source="QLDTraffic / Council",
        title="Hazard: Road closed to all traffic",
        hazard_type=HazardType.ROAD_INCIDENT,
        warning_level=WarningLevel.ADVICE,
        latitude=-27.2000,
        longitude=152.9000,
        updated_at=datetime.now(UTC),
        location_name="Samford Valley",
        is_hazard_reduction=False,
        status="Published",
        responsible_agency="Department of Transport and Main Roads",
        web_url="https://qldtraffic.qld.gov.au",
    )


@pytest.fixture
def mock_hazard_hazard_reduction() -> CanonicalHazard:
    """Return a mock planned burn hazard."""
    return CanonicalHazard(
        id="QLD_QFD_BURN_999",
        source="Queensland Fire Department",
        title="Planned Burn - Hazard Reduction at D'Aguilar",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.INFORMATION,
        latitude=-27.0500,
        longitude=152.8000,
        updated_at=datetime.now(UTC),
        location_name="D'Aguilar National Park",
        is_hazard_reduction=True,
        status="Under Control",
        responsible_agency="Queensland Parks and Wildlife Service",
    )


@pytest.fixture
def mock_hazard_distant_emergency_warning() -> CanonicalHazard:
    """Return an Emergency Warning hazard located 220 km away."""
    return CanonicalHazard(
        id="QLD_QFD_WARN_DISTANT",
        source="Queensland Fire Department",
        title="EMERGENCY WARNING - Distant Bushfire",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-25.2000,  # Far away (~220 km north)
        longitude=152.8000,
        updated_at=datetime.now(UTC),
        location_name="Wide Bay",
        is_hazard_reduction=False,
        status="Going",
        responsible_agency="QFD",
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry configured for Moreton Bay, Queensland."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Australia and New Zealand Disaster Watch (QLD - City of Moreton Bay)",
        data={
            CONF_STATE: STATE_QLD,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_LOCATION_NAME: "City of Moreton Bay",
            CONF_LATITUDE: -27.2657,
            CONF_LONGITUDE: 152.9818,
            CONF_RADIUS: 50,
            CONF_OVERRIDE_EMERGENCY: True,
            CONF_EXCLUDE_HAZARD_REDUCTION: True,
            CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
        },
        unique_id="ausnz_disaster_watch_qld_city_of_moreton_bay",
    )


class FeedRoutes:
    """Routes for feeds fetched through Home Assistant's shared session (the aio_geojson libraries, #35).

    Call it with ``{url: body}`` to add routes and get the session. A dict/list body is served as
    JSON, a str as-is, an int as that HTTP status, an exception is raised. Assigning to ``routes``
    changes a route. Unrouted URLs fail with a connection error.
    """

    def __init__(self, hass: HomeAssistant, mocker: AiohttpClientMocker) -> None:
        """Bind the routes to the test's aiohttp mocker."""
        self._hass = hass
        self._mocker = mocker
        self.routes = _Routes(self._register)

    def __call__(self, routes: dict[str, Any] | None = None) -> aiohttp.ClientSession:
        """Add routes and return the shared session."""
        self.routes.update(routes or {})
        return async_get_clientsession(self._hass)

    @property
    def requested(self) -> list[str]:
        """Return the requested URLs."""
        return [str(call[1]) for call in self._mocker.mock_calls]

    def _register(self) -> None:
        self._mocker.clear_requests()
        for url, body in self.routes.items():
            if isinstance(body, Exception):
                self._mocker.get(url, exc=body)
            elif isinstance(body, int):
                self._mocker.get(url, status=body)
            elif isinstance(body, str):
                self._mocker.get(url, text=body)
            else:
                self._mocker.get(url, json=body)
        self._mocker.get(re.compile(".*"), exc=aiohttp.ClientConnectionError("no route"))


class _Routes(dict[str, Any]):
    """Route table that re-registers the mocks on every change."""

    def __init__(self, on_change: Callable[[], None]) -> None:
        super().__init__()
        self._on_change = on_change

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self._on_change()

    def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Add routes."""
        super().update(*args, **kwargs)
        self._on_change()


@pytest.fixture
def feed_routes(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> FeedRoutes:
    """Route requests made through the shared aiohttp session."""
    return FeedRoutes(hass, aioclient_mock)
