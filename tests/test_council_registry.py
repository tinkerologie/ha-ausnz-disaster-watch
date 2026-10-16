"""Generated council dashboard registry (#32)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from custom_components.ausnz_disaster_watch import council_registry
from custom_components.ausnz_disaster_watch.const import DOMAIN, PRESET_COUNCIL_DASHBOARDS
from custom_components.ausnz_disaster_watch.coordinator import nearest_council_dashboard
from custom_components.ausnz_disaster_watch.council_registry import (
    COUNCIL_DASHBOARDS,
    councils_for_state,
    nearest_council,
    usable_url,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

# The presets the integration had before the registry; their keys, names and points are kept
LEGACY = {
    "moreton_bay": ("City of Moreton Bay", "https://disaster.moretonbay.qld.gov.au", -27.2657, 152.9818),
    "sunshine_coast": ("Sunshine Coast", None, -26.6500, 153.0667),
    "noosa": ("Noosa Shire", "https://disaster.noosa.qld.gov.au", -26.3986, 153.0442),
    "gold_coast": ("City of Gold Coast", "https://dashboard.goldcoast.qld.gov.au", -28.0167, 153.4000),
    "cairns": ("Cairns Regional", "https://disaster.cairns.qld.gov.au", -16.9186, 145.7781),
    "townsville": ("Townsville City", "https://disaster.townsville.qld.gov.au", -19.2590, 146.8169),
    "fraser_coast": ("Fraser Coast", "https://disaster.frasercoast.qld.gov.au", -25.5398, 152.7032),
    "bundaberg": ("Bundaberg Regional", "https://disaster.bundaberg.qld.gov.au", -24.8661, 152.3489),
    "redland": ("Redland City", "https://dashboard.redland.qld.gov.au", -27.5306, 153.2500),
    "ipswich": ("Ipswich City", "https://disaster.ipswich.qld.gov.au", -27.6167, 152.7667),
    "logan": ("Logan City", "https://disaster.logan.qld.gov.au", -27.6972, 153.1111),
}


def test_registry_integrity() -> None:
    """Every council is in QLD or NSW with an https Guardian URL (or a known other platform)."""
    assert len(COUNCIL_DASHBOARDS) > 60
    for key, council in COUNCIL_DASHBOARDS.items():
        assert key == key.lower()
        assert " " not in key
        assert council["state"] in {"QLD", "NSW"}
        assert -45 < council["latitude"] < -9
        assert 138 < council["longitude"] < 154
        assert council["radius_km"] > 0
        if council["platform"] == "guardian":
            assert council["url"] is not None
            assert council["url"].startswith("https://")
            assert not council["url"].endswith("/")
            assert "disasterdashboards.com" not in council["url"]  # Demonz: no unauthorised use
        else:
            assert council["platform"] in {"brisbane_arcgis", "sunshine_hub"}
            assert council["url"] is None
    # The councils named in the issue are listed
    for key in ("toowoomba", "mackay", "rockhampton", "gladstone", "longreach", "barcaldine", "blackall_tambo"):
        assert COUNCIL_DASHBOARDS[key]["state"] == "QLD"
    assert COUNCIL_DASHBOARDS["longreach"]["url"] == "https://rapad.qitplus.com/longreach"
    for key in ("hawkesbury", "blue_mountains", "ballina", "byron", "northern_beaches"):
        assert COUNCIL_DASHBOARDS[key]["state"] == "NSW"
    assert COUNCIL_DASHBOARDS["brisbane"]["platform"] == "brisbane_arcgis"


def test_legacy_presets_keep_keys_names_and_points() -> None:
    """Entries made from an original preset get the same name (title, unique ID) and point."""
    for key, (name, url, lat, lon) in LEGACY.items():
        preset = PRESET_COUNCIL_DASHBOARDS[key]
        assert (preset["name"], preset["url"], preset["latitude"], preset["longitude"]) == (name, url, lat, lon)
        assert preset["state"] == "QLD"


def test_councils_for_state_sorted_by_name() -> None:
    """Council lists are per state and sorted by name."""
    nsw = councils_for_state("NSW")
    assert [council["name"] for _, council in nsw] == sorted(council["name"] for _, council in nsw)
    assert {key for key, _ in nsw} >= {"byron", "hawkesbury"}
    assert councils_for_state("VIC") == []


@pytest.mark.parametrize(
    ("state", "point", "expected"),
    [
        ("QLD", (-16.92, 145.77), "https://disaster.cairns.qld.gov.au"),  # Cairns
        ("QLD", (-27.56, 151.95), "https://disaster.tr.qld.gov.au"),  # Toowoomba city, not Lockyer Valley
        ("NSW", (-28.64, 153.61), "https://emergency.byron.nsw.gov.au"),  # Byron Bay
        ("QLD", (-27.56, 152.28), "https://disaster.lvrc.qld.gov.au"),  # Gatton (Lockyer Valley)
        ("QLD", (-26.65, 153.0667), "https://disaster.noosa.qld.gov.au"),  # Sunshine Coast: no dashboard, Noosa
        ("QLD", (-27.53, 153.25), "https://disaster.logan.qld.gov.au"),  # Redland: certificate rejected, Logan
        ("QLD", (-20.0, 155.0), None),  # Coral Sea
        ("NSW", (-16.92, 145.77), None),  # Cairns is not in NSW
    ],
)
def test_nearest_council_dashboard(state: str, point: tuple[float, float], expected: str | None) -> None:
    """A home-zone entry gets its own council's dashboard, or the nearest readable one."""
    assert nearest_council_dashboard(state, *point) == expected


def test_nearest_council_and_usable_url() -> None:
    """The matched council is reported even without a readable dashboard."""
    match = nearest_council("QLD", -27.47, 153.02)  # Brisbane CBD
    assert match is not None
    assert match[0] == "brisbane"
    assert usable_url(match[1]) is None
    assert usable_url(COUNCIL_DASHBOARDS["redland"]) is None  # incomplete certificate chain
    assert usable_url(COUNCIL_DASHBOARDS["cairns"]) == "https://disaster.cairns.qld.gov.au"
    assert nearest_council("QLD", -27.47, 153.02, readable_only=True) is not None


async def test_custom_step_lists_registry_councils(hass: HomeAssistant) -> None:
    """The custom location step offers every council of the state; picking one stores its dashboard."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"state": "QLD", "location_mode": "custom", "radius": 50, "override_emergency": True},
    )
    assert result["step_id"] == "location"
    options: list[Any] = result["data_schema"].schema["preset_council"].config["options"]
    labels = {option["value"]: option["label"] for option in options}
    assert labels["toowoomba"] == "Toowoomba Regional"
    assert labels["brisbane"] == "Brisbane City (no readable dashboard)"
    assert "byron" not in labels  # NSW

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"preset_council": "toowoomba", "location_name": "x", "latitude": -27.0, "longitude": 152.0},
        )
    assert result["data"]["council_dashboard_url"] == "https://disaster.tr.qld.gov.au"
    assert result["data"]["location_name"] == "Toowoomba Regional"


def test_registry_file_matches_loader() -> None:
    """The loader reads every council of the generated file."""
    assert council_registry._load() == COUNCIL_DASHBOARDS
