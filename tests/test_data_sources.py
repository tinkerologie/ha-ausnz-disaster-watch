"""Data source register and attribution (#34)."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch import providers as providers_module
from custom_components.ausnz_disaster_watch.camera import AustralianDisasterWatchCamera
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.diagnostics import async_get_config_entry_diagnostics
from custom_components.ausnz_disaster_watch.geo_location import AustralianDisasterWatchGeolocationEvent
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, DisasterCameraItem
from custom_components.ausnz_disaster_watch.providers import (
    BaseHazardProvider,
    BoMHazardProvider,
    NZHazardProvider,
    QueenslandHazardProvider,
    get_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.sources import (
    DATA_SOURCES,
    PROVIDER_SOURCES,
    REGISTER_PATH,
    LicenceStatus,
    attribution_for,
    sources_for_fire,
    sources_for_provider,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "custom_components" / "ausnz_disaster_watch"
# XML namespace URIs are identifiers, not endpoints
NAMESPACES = ("http://www.w3.org/2005/Atom", "http://www.georss.org/georss", "http://purl.org/dc/elements/1.1/")
_URL_RE = re.compile(r"https?://[^\s\"'`)<>{]+")


class _StubProvider(BaseHazardProvider):
    """Provider returning fixed hazards, registered under its own name for the test."""

    def __init__(self, hass: HomeAssistant, session: Any, config: dict[str, Any], hazards: list[CanonicalHazard]):
        super().__init__(hass, session, config)
        self._hazards = hazards

    @property
    def state_code(self) -> str:
        return "QLD"

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        return self._hazards


def _code_urls() -> set[str]:
    """Return every URL literal in the provider modules, const.py and config_flow.py (templates cut at '{')."""
    files = [*sorted((PACKAGE / "providers").glob("*.py")), PACKAGE / "const.py", PACKAGE / "config_flow.py"]
    urls: set[str] = set()
    for file in files:
        text = file.read_text(encoding="utf-8")
        # Join implicitly concatenated string literals ("https://host" "/path")
        text = re.sub(r'"\s*\n\s*"', "", text)
        urls.update(url.rstrip(".,/}") for url in _URL_RE.findall(text))
    return {url for url in urls if not url.startswith(NAMESPACES)}


def test_register_lists_every_url_the_code_uses() -> None:
    """Every URL in the providers and config appears in docs/development/DATA_SOURCES.md."""
    register = (ROOT / REGISTER_PATH).read_text(encoding="utf-8")
    missing = sorted(url for url in _code_urls() if url not in register)
    assert not missing, f"Add these URLs to {REGISTER_PATH}: {missing}"
    # Council dashboard endpoints are fetched by name through GuardianDashboard.fetch
    endpoints = set()
    for file in (PACKAGE / "providers").glob("*.py"):
        endpoints.update(re.findall(r'\.fetch\(f?"(\w+)', file.read_text(encoding="utf-8")))
    assert endpoints
    assert not sorted(e for e in endpoints if f"`/dashboard/{e}" not in register)


def test_register_entries_are_consistent() -> None:
    """Every provider maps to known sources; only open sources claim a licence in their attribution."""
    provider_names = {
        name
        for name in providers_module.__all__
        if isinstance(cls := getattr(providers_module, name), type)
        and issubclass(cls, BaseHazardProvider)
        and cls is not BaseHazardProvider
    }
    assert provider_names == set(PROVIDER_SOURCES)
    register = (ROOT / REGISTER_PATH).read_text(encoding="utf-8")
    for keys in PROVIDER_SOURCES.values():
        assert keys
        assert all(key in DATA_SOURCES for key in keys)
    for key, source in DATA_SOURCES.items():
        assert source.key == key
        assert f"`{key}`" in register
        assert source.terms_url in register
        assert source.attribution
        claims_licence = "CC BY" in source.attribution or "licence" in source.attribution.lower()
        assert claims_licence == (source.status is LicenceStatus.OPEN), key
        assert source.as_dict()["status"] == source.status.value


def test_attribution_helpers(hass: HomeAssistant) -> None:
    """Attribution joins distinct texts in order; unknown providers have none."""
    assert attribution_for([]) is None
    assert sources_for_provider("UnknownProvider") == ()
    qld = DATA_SOURCES["qfd_incidents"]
    assert attribution_for([qld, qld]) == qld.attribution
    providers = get_providers_for_config(hass, AsyncMock(), {"state": "QLD"})
    assert [type(p) for p in providers] == [QueenslandHazardProvider, BoMHazardProvider]
    assert providers[0].attribution == attribution_for(providers[0].data_sources)
    assert "Bureau of Meteorology" in (providers[1].attribution or "")
    nz = NZHazardProvider(hass, AsyncMock(), {"state": "NZ"})
    assert "GeoNet" in (nz.attribution or "")


async def test_entities_and_diagnostics_expose_attribution(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hazard_emergency_warning: CanonicalHazard,
    mock_hazard_advice: CanonicalHazard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensors, binary sensors, cameras and map pins carry attribution; diagnostics list the sources."""
    mock_config_entry.add_to_hass(hass)
    qld = _StubProvider(hass, AsyncMock(), {}, [mock_hazard_emergency_warning])
    bom = _StubProvider(hass, AsyncMock(), {}, [mock_hazard_advice])
    mock_hazard_advice.attribution = "Upstream credit"
    monkeypatch.setitem(PROVIDER_SOURCES, "_StubProvider", ("qfd_incidents",))
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config",
        return_value=[qld, bom],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: AustralianDisasterWatchCoordinator = mock_config_entry.runtime_data
    # Two providers of one type list their sources once
    assert coordinator.data_sources == [DATA_SOURCES["qfd_incidents"]]
    expected = DATA_SOURCES["qfd_incidents"].attribution
    assert coordinator.attribution == expected

    entries = er.async_entries_for_config_entry(er.async_get(hass), mock_config_entry.entry_id)
    assert {entry.domain for entry in entries} == {"sensor", "binary_sensor", "geo_location"}
    # Fire entities credit the fire danger sources for the district instead (#28)
    fire_keys = ("_fire_danger_rating", "_total_fire_ban")
    fire_attribution = attribution_for(sources_for_fire("QLD"))
    for entry in entries:
        if entry.domain == "geo_location":
            continue  # checked below
        state = hass.states.get(entry.entity_id)
        assert state is not None
        want = fire_attribution if entry.unique_id.endswith(fire_keys) else expected
        assert state.attributes["attribution"] == want, entry.entity_id
    camera = AustralianDisasterWatchCamera(
        coordinator, DisasterCameraItem(id="cam", name="Cam", image_url="https://example.invalid/cam.jpg")
    )
    assert camera.attribution == expected

    # Map pins credit the provider that returned the hazard; an upstream value is kept
    pins = {
        s.attributes["title"]: s.attributes["attribution"]
        for s in hass.states.async_all("geo_location")
        if "title" in s.attributes
    }
    assert pins[mock_hazard_emergency_warning.title] == expected
    assert pins[mock_hazard_advice.title] == "Upstream credit"

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diag["coordinator"]["attribution"] == expected
    assert [s["key"] for s in diag["coordinator"]["data_sources"]] == ["qfd_incidents"]
    assert all(s["status"] in {"open", "restricted", "unverified"} for s in diag["coordinator"]["data_sources"])


def test_geolocation_attribution_falls_back_to_entry(mock_hazard_advice: CanonicalHazard) -> None:
    """A map pin whose hazard has no attribution shows the entry's attribution."""
    coordinator = MagicMock()
    coordinator.attribution = "Entry credit"
    event = AustralianDisasterWatchGeolocationEvent(coordinator, "entry", mock_hazard_advice.id, mock_hazard_advice)
    assert event.attribution == "Entry credit"
