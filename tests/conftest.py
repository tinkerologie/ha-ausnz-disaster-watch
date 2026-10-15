"""Shared fixtures for Australian Emergency Hazards integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.australian_disaster_watch.const import (
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
from custom_components.australian_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integration discovery in all tests."""


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
        distance_km=21.5,
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
        distance_km=18.7,
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
        distance_km=10.2,
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
        distance_km=30.0,
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
        distance_km=230.0,
        is_hazard_reduction=False,
        status="Going",
        responsible_agency="QFD",
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry configured for Moreton Bay, Queensland."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Australian Disaster Watch (QLD - City of Moreton Bay)",
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
        unique_id="australian_disaster_watch_qld_city_of_moreton_bay",
    )
