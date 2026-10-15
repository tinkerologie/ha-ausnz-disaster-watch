"""Feed failure signalling (#16): unavailable feeds raise, malformed items are skipped, and
the coordinator tracks feed health and fails the update only when every feed is down."""

from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from xml.sax.saxutils import escape

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import LAST_GOOD_MAX_AGE
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import (
    ACTHazardProvider,
    NSWHazardProvider,
    NTHazardProvider,
    NZHazardProvider,
    QueenslandHazardProvider,
    SAHazardProvider,
    TasmaniaHazardProvider,
    VictoriaHazardProvider,
    WAHazardProvider,
)
from custom_components.ausnz_disaster_watch.providers.base import BaseHazardProvider, ProviderUnavailableError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

GOOD_LAT, BAD_LAT = -27.5, 999.0  # 999 fails CanonicalHazard validation -> malformed item


def _point(lat: float, lon: float = 153.0) -> dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}


async def test_act_skips_malformed_item(hass: HomeAssistant) -> None:
    """One bad ACT item is skipped; the rest of the feed survives."""
    provider = ACTHazardProvider(hass, AsyncMock(), {"state": "ACT"})
    xml = f"""<rss xmlns:georss="http://www.georss.org/georss"><channel>
      <item><title>GRASS FIRE - Good</title><guid>G1</guid><georss:point>-35.3 149.1</georss:point></item>
      <item><title>GRASS FIRE - Bad</title><guid>B1</guid><georss:point>{BAD_LAT} 149.1</georss:point></item>
    </channel></rss>"""
    assert [h.id for h in provider._parse_act_feed(xml)] == ["act_esa_G1"]


async def test_tas_skips_malformed_item(hass: HomeAssistant) -> None:
    """One bad TasALERT item is skipped."""
    provider = TasmaniaHazardProvider(hass, AsyncMock(), {"state": "TAS"})
    xml = f"""<rss xmlns:georss="http://www.georss.org/georss"><channel>
      <item><title>Bushfire - Good</title><guid>G1</guid><georss:point>-42.9 147.3</georss:point></item>
      <item><title>Bushfire - Bad</title><guid>B1</guid><georss:point>{BAD_LAT} 147.3</georss:point></item>
    </channel></rss>"""
    assert len(provider._parse_tasalert_feed(xml)) == 1


async def test_sa_skips_malformed_item(hass: HomeAssistant) -> None:
    """One bad SA CAP entry is skipped."""
    provider = SAHazardProvider(hass, AsyncMock(), {"state": "SA"})

    def entry(entry_id: str, lat: float) -> str:
        return f"""<entry><id>{entry_id}</id><title>Grass Fire</title>
          <cap:alert><cap:info><cap:area><cap:circle>{lat},138.6 1</cap:circle></cap:area></cap:info></cap:alert></entry>"""

    xml = f"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
      {entry("good", -34.9)}{entry("bad", BAD_LAT)}</feed>"""
    assert len(provider._parse_cap_feed(xml)) == 1


async def test_nt_skips_malformed_item(hass: HomeAssistant) -> None:
    """One bad NT feature is skipped."""
    provider = NTHazardProvider(hass, AsyncMock(), {"state": "NT"})
    features = [
        {"geometry": _point(-12.5, 131.0), "properties": {"_eventtype": "Grass Fire", "_location": "Good"}},
        {"geometry": _point(BAD_LAT, 131.0), "properties": {"_eventtype": "Grass Fire", "_location": "Bad"}},
    ]
    assert len(provider._parse_nt_incidents({"incidents": features})) == 1

    provider.async_fetch_json = AsyncMock(return_value=[])
    with pytest.raises(ProviderUnavailableError, match="unexpected payload"):
        await provider.async_fetch_hazards()


@pytest.mark.parametrize("provider_cls", [NSWHazardProvider, VictoriaHazardProvider])
async def test_nsw_vic_skip_malformed_feature(hass: HomeAssistant, provider_cls: type[BaseHazardProvider]) -> None:
    """A feature whose parser raises is skipped; good features are kept."""
    provider = provider_cls(hass, AsyncMock(), {"state": "NSW"})
    good = MagicMock(spec=CanonicalHazard)
    parse_name = "_parse_nsw_feature" if provider_cls is NSWHazardProvider else "_parse_vic_feature"
    setattr(provider, parse_name, MagicMock(side_effect=[ValueError("bad"), good]))
    provider.async_fetch_json = AsyncMock(return_value={"features": [{}, {}]})
    assert await provider.async_fetch_hazards() == [good]


async def test_wa_partial_and_malformed(hass: HomeAssistant) -> None:
    """WA returns the working endpoint's data and skips malformed records."""
    provider = WAHazardProvider(hass, AsyncMock(), {"state": "WA"})
    warnings = {
        "warnings": [
            {"id": "w1", "title": "Bushfire Advice", "location": {"latitude": -31.9, "longitude": 115.9}},
            {"id": "w2", "title": "Bushfire Advice", "location": {"latitude": BAD_LAT, "longitude": 115.9}},
        ]
    }
    incidents = {
        "incidents": [
            {"id": "i1", "incident-type": "Bushfire", "location": {"latitude": -31.9, "longitude": 115.9}},
            {"id": "i2", "incident-type": "Bushfire", "location": {"latitude": BAD_LAT, "longitude": 115.9}},
        ]
    }
    assert [h.id for h in provider._parse_warnings(warnings)] == ["wa_warn_w1"]
    assert [h.id for h in provider._parse_incidents(incidents)] == ["wa_inc_i1"]

    # Warnings endpoint down, incidents up: partial result, no error
    provider.async_fetch_json = AsyncMock(side_effect=[aiohttp.ClientError("down"), incidents])
    assert [h.id for h in await provider.async_fetch_hazards()] == ["wa_inc_i1"]

    # Unexpected payload shape counts as a failed source
    provider.async_fetch_json = AsyncMock(side_effect=[[], []])
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()


async def test_nz_skips_malformed_items(hass: HomeAssistant) -> None:
    """Bad GeoNet quake/volcano records and NEMA entries are skipped individually."""
    provider = NZHazardProvider(hass, AsyncMock(), {"state": "NZ"})
    now = datetime.now(UTC).isoformat()
    quakes = {
        "features": [
            {
                "geometry": _point(-41.3, 174.8),
                "properties": {"publicID": "q1", "time": now, "magnitude": 4.1, "mmi": 4},
            },
            {"geometry": _point(-41.3, 174.8), "properties": {"publicID": "q2", "time": now, "magnitude": "abc"}},
        ]
    }
    volcanoes = {
        "features": [
            {"geometry": _point(-39.3, 175.6), "properties": {"volcanoID": "ruapehu", "level": 1}},
            {"geometry": _point(-39.3, 175.6), "properties": {"volcanoID": "taupo", "level": "high"}},
        ]
    }
    assert len(provider._parse_geonet_quakes(quakes)) == 1
    assert len(provider._parse_geonet_volcanoes(volcanoes)) == 1

    cap = (
        '<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>{id}</identifier>'
        "<status>Actual</status><msgType>Alert</msgType><info><event>Flood</event>"
        "<area><areaDesc>Wellington</areaDesc><circle>-41.3,174.8 1</circle></area></info></alert>"
    )
    nema = f"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>good</id><title>Flood</title><content>{escape(cap.format(id="good"))}</content></entry>
      <entry><id>bad</id><title>Flood</title><content>{escape(cap.format(id="bad"))}</content></entry>
    </feed>"""
    with patch.object(
        NZHazardProvider,
        "_located_hazard",
        side_effect=[MagicMock(spec=CanonicalHazard, id="nz_nema_good"), KeyError("bad")],
    ):
        assert [h.id for h in provider._parse_nema_atom(nema)] == ["nz_nema_good"]

    # Quakes up, volcanoes payload malformed, NEMA down: partial result
    provider.async_fetch_json = AsyncMock(side_effect=[quakes, []])
    provider.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("down"))
    assert len(await provider.async_fetch_hazards()) == 1


async def test_qld_skips_malformed_item_and_council_rescues(hass: HomeAssistant) -> None:
    """QLD skips bad QFD features; a reachable council feed keeps the provider available."""
    provider = QueenslandHazardProvider(
        hass, AsyncMock(), {"state": "QLD", "council_dashboard_url": "https://disaster.example.qld.gov.au"}
    )
    good = MagicMock(spec=CanonicalHazard, id="qfd_good")
    provider._parse_qfd_feature = MagicMock(side_effect=[KeyError("bad"), good])
    provider._fetch_council_hazards = AsyncMock(return_value=([], 0))
    provider.async_fetch_json = AsyncMock(return_value={"features": [{}, {}]})
    assert await provider.async_fetch_hazards() == [good]

    # QFD down but one council endpoint answered: available with the council data
    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("down"))
    provider._fetch_council_hazards = AsyncMock(return_value=([], 1))
    assert await provider.async_fetch_hazards() == []


async def test_base_collect_and_require_dict(hass: HomeAssistant) -> None:
    """Shared helpers: no sources is unavailable; require_dict rejects non-objects."""
    provider = ACTHazardProvider(hass, AsyncMock(), {"state": "ACT"})
    with pytest.raises(ProviderUnavailableError, match="no sources configured"):
        await provider.async_collect_sources([])
    assert BaseHazardProvider.require_dict({"a": 1}, "x") == {"a": 1}
    with pytest.raises(ProviderUnavailableError, match="unexpected payload"):
        BaseHazardProvider.require_dict([], "x")
    provider.async_fetch_json = AsyncMock(side_effect=ValueError("bad json"))
    with pytest.raises(ProviderUnavailableError, match="bad json"):
        await provider.async_fetch_feed_json("https://example.invalid", "Example")


def _hazard(hazard_id: str) -> CanonicalHazard:
    return CanonicalHazard(
        id=hazard_id,
        source="test",
        title=hazard_id,
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-27.27,
        longitude=152.98,
    )


async def test_coordinator_feed_health_transitions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failures keep last-good data, transitions log once, and all-down raises UpdateFailed."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    class PrimaryProvider:
        async_fetch_hazards = AsyncMock()

    class SecondaryProvider:
        async_fetch_hazards = AsyncMock()

    primary, secondary = PrimaryProvider(), SecondaryProvider()
    coordinator.providers = [primary, secondary]  # type: ignore[list-item]
    names = ["PrimaryProvider", "SecondaryProvider"]

    # 1. Both healthy
    primary.async_fetch_hazards.return_value = [_hazard("a")]
    secondary.async_fetch_hazards.return_value = [_hazard("b")]
    assert {h.id for h in await coordinator._async_fetch_all_hazards()} == {"a", "b"}
    assert coordinator._feeds_failed == []

    # 2. Primary fails: its last good hazard is retained, warning logged once
    primary.async_fetch_hazards.side_effect = ProviderUnavailableError("timeout")
    with caplog.at_level(logging.DEBUG):
        hazards = await coordinator._async_fetch_all_hazards()
        await coordinator._async_fetch_all_hazards()
    assert {h.id for h in hazards} == {"a", "b"}
    assert coordinator._feeds_failed == [names[0]]
    assert caplog.text.count(f"Hazard feed {names[0]} is unavailable") == 1
    assert f"Hazard feed {names[0]} still unavailable" in caplog.text

    # 3. Primary recovers: info logged
    primary.async_fetch_hazards.side_effect = None
    caplog.clear()
    with caplog.at_level(logging.INFO):
        await coordinator._async_fetch_all_hazards()
    assert f"Hazard feed {names[0]} is available again" in caplog.text

    # 4. Unexpected exception types also count as a failure (traceback at debug only)
    secondary.async_fetch_hazards.side_effect = RuntimeError("boom")
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        await coordinator._async_fetch_all_hazards()
    assert f"Unexpected error from {names[1]}" in caplog.text

    # 5. Everything down: UpdateFailed (entities become unavailable)
    primary.async_fetch_hazards.side_effect = ProviderUnavailableError("down")
    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_fetch_all_hazards()
    assert err.value.translation_key == "feeds_unavailable"

    # 6. BaseException (e.g. cancellation) is re-raised, never swallowed
    class _Abort(BaseException):
        pass

    primary.async_fetch_hazards.side_effect = _Abort()
    with pytest.raises(_Abort):
        await coordinator._async_fetch_all_hazards()


async def test_update_data_reports_feed_health(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The coordinator data exposes which feeds succeeded and failed."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    ok = AsyncMock()
    ok.async_fetch_hazards.return_value = []
    down = AsyncMock()
    down.async_fetch_hazards.side_effect = ProviderUnavailableError("down")
    for aux in ("power_outages", "road_closures", "relief_facilities", "weather_warnings", "emergency_news"):
        for provider in (ok, down):
            getattr(provider, f"async_fetch_{aux}").return_value = []
    for provider in (ok, down):
        provider.async_fetch_weather_telemetry.return_value = []
        provider.async_fetch_air_quality.return_value = []
        provider.async_fetch_cameras.return_value = []
        provider.async_fetch_nearby_councils.return_value = []
        provider.async_fetch_fire_danger.return_value = None
    coordinator.providers = [ok, down]

    data = await coordinator._async_update_data()
    assert data.feeds_ok == ["AsyncMock"]
    assert data.feeds_failed == ["AsyncMock"]


async def test_last_good_hazards_expire(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed feed's cached hazards bridge short outages but are dropped after LAST_GOOD_MAX_AGE."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    class FlakyProvider:
        async_fetch_hazards = AsyncMock(return_value=[_hazard("emergency")])

    class SteadyProvider:
        async_fetch_hazards = AsyncMock(return_value=[])

    flaky = FlakyProvider()
    coordinator.providers = [flaky, SteadyProvider()]  # type: ignore[list-item]
    start = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    with patch("custom_components.ausnz_disaster_watch.coordinator.dt_util.utcnow", return_value=start):
        await coordinator._async_fetch_all_hazards()

    flaky.async_fetch_hazards.side_effect = ProviderUnavailableError("down")
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.dt_util.utcnow",
        return_value=start + LAST_GOOD_MAX_AGE,
    ):
        assert [h.id for h in await coordinator._async_fetch_all_hazards()] == ["emergency"]
    with patch(
        "custom_components.ausnz_disaster_watch.coordinator.dt_util.utcnow",
        return_value=start + LAST_GOOD_MAX_AGE + timedelta(seconds=1),
    ):
        assert await coordinator._async_fetch_all_hazards() == []


async def test_non_list_collections_are_unavailable(hass: HomeAssistant) -> None:
    """features/warnings: null is a broken source; other sources are still fetched."""
    assert BaseHazardProvider.require_list({"features": [1]}, "features", "x") == [1]
    with pytest.raises(ProviderUnavailableError, match="is not a list"):
        BaseHazardProvider.require_list({"features": None}, "features", "x")

    nsw = NSWHazardProvider(hass, AsyncMock(), {"state": "NSW"})
    nsw.async_fetch_json = AsyncMock(return_value={"features": None})
    with pytest.raises(ProviderUnavailableError):
        await nsw.async_fetch_hazards()

    qld = QueenslandHazardProvider(hass, AsyncMock(), {"state": "QLD"})
    qld.async_fetch_json = AsyncMock(return_value={"features": None})
    with pytest.raises(ProviderUnavailableError):
        await qld.async_fetch_hazards()

    # WA: warnings payload broken, incidents fine -> incidents still returned
    wa = WAHazardProvider(hass, AsyncMock(), {"state": "WA"})
    incidents = {
        "incidents": [{"id": "i1", "incident-type": "Bushfire", "location": {"latitude": -31.9, "longitude": 115.9}}]
    }
    wa.async_fetch_json = AsyncMock(side_effect=[{"warnings": None}, incidents])
    assert [h.id for h in await wa.async_fetch_hazards()] == ["wa_inc_i1"]

    # A parser that trips over a malformed document fails only its own source
    provider = ACTHazardProvider(hass, AsyncMock(), {"state": "ACT"})

    async def _fetch() -> dict[str, Any]:
        return {}

    def _broken(_payload: Any) -> list[CanonicalHazard]:
        raise TypeError("broken document")

    good = _hazard("ok")
    result = await provider.async_collect_sources([("broken", _fetch, _broken), ("ok", _fetch, lambda _p: [good])])
    assert result == [good]


async def test_qld_counts_only_well_formed_council_responses(hass: HomeAssistant) -> None:
    """A council endpoint answering with the wrong shape does not count as a working source."""
    provider = QueenslandHazardProvider(
        hass, AsyncMock(), {"state": "QLD", "council_dashboard_url": "https://disaster.example.qld.gov.au"}
    )
    # fireDetailed/tmrRoadData expect lists, bom/imsBulletin expect objects: all wrong here
    provider.async_fetch_json = AsyncMock(return_value="unexpected")
    _hazards, fetched_ok = await provider._fetch_council_hazards("https://disaster.example.qld.gov.au", set())
    assert fetched_ok == 0
    # Objects without their collection do not count either
    provider.async_fetch_json = AsyncMock(side_effect=[[], [], {}, {"item": None}])
    _hazards, fetched_ok = await provider._fetch_council_hazards("https://disaster.example.qld.gov.au", set())
    assert fetched_ok == 2
    # Right shapes (even if empty) count
    provider.async_fetch_json = AsyncMock(side_effect=[[], [], {"item": []}, {"features": []}])
    _hazards, fetched_ok = await provider._fetch_council_hazards("https://disaster.example.qld.gov.au", set())
    assert fetched_ok == 4


@pytest.mark.parametrize(
    ("provider_cls", "parse_name", "valid_empty"),
    [
        (ACTHazardProvider, "_parse_act_feed", "<rss><channel><title>ACT</title></channel></rss>"),
        (TasmaniaHazardProvider, "_parse_tasalert_feed", "<rss><channel/></rss>"),
        (SAHazardProvider, "_parse_cap_feed", '<feed xmlns="http://www.w3.org/2005/Atom"><title>SA</title></feed>'),
        (NZHazardProvider, "_parse_nema_atom", '<feed xmlns="http://www.w3.org/2005/Atom"/>'),
    ],
)
async def test_xml_feeds_reject_wrong_documents(
    hass: HomeAssistant, provider_cls: type[BaseHazardProvider], parse_name: str, valid_empty: str
) -> None:
    """A well-formed error page is unavailable; a valid empty feed is a genuine all-clear."""
    parse = getattr(provider_cls(hass, AsyncMock(), {"state": "QLD"}), parse_name)
    assert parse(valid_empty) == []
    for wrong in ("<html><body>Service unavailable</body></html>", "<rss><title>no channel</title></rss>"):
        with pytest.raises(ProviderUnavailableError, match="unexpected document"):
            parse(wrong)


async def test_json_feeds_reject_missing_collections(hass: HomeAssistant) -> None:
    """A missing required collection is a broken response; an explicit empty list is valid."""
    with pytest.raises(ProviderUnavailableError, match="is not a list"):
        BaseHazardProvider.require_list({}, "features", "x")
    assert BaseHazardProvider.require_list({"features": []}, "features", "x") == []

    nsw = NSWHazardProvider(hass, AsyncMock(), {"state": "NSW"})
    nsw.async_fetch_json = AsyncMock(return_value={"error": "maintenance"})
    with pytest.raises(ProviderUnavailableError):
        await nsw.async_fetch_hazards()

    nt = NTHazardProvider(hass, AsyncMock(), {"state": "NT"})
    for payload in ({}, {"incidents": None}, {"incidents": "error"}, {"incidents": {"error": "bad"}}, []):
        nt.async_fetch_json = AsyncMock(return_value=payload)
        with pytest.raises(ProviderUnavailableError, match="unexpected payload"):
            await nt.async_fetch_hazards()
    nt.async_fetch_json = AsyncMock(return_value={"incidents": {"type": "FeatureCollection", "features": []}})
    assert await nt.async_fetch_hazards() == []
    nt.async_fetch_json = AsyncMock(return_value={"features": []})
    assert await nt.async_fetch_hazards() == []
    nt.async_fetch_json = AsyncMock(return_value={"incidents": []})
    assert await nt.async_fetch_hazards() == []
