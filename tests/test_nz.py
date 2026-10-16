"""New Zealand provider (#11): NEMA CAP-in-Atom alerts, MetService CAP warnings, GeoNet levels."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from xml.sax.saxutils import escape

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.const import STATE_NZ
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.geonet import GEONET_QUAKE_URL, GEONET_VOLCANO_URL
from custom_components.ausnz_disaster_watch.providers.nz import (
    METSERVICE_ALERTS_URL,
    METSERVICE_SHARED_KEY,
    METSERVICE_WEB_URL,
    NEMA_ALERTHUB_URL,
    NEMA_WEB_URL,
    NZHazardProvider,
    _quake_level,
)
from homeassistant.core import HomeAssistant


def feature_collection(*features: dict[str, Any]) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": list(features)}


NOW = datetime(2026, 10, 15, 20, 0, tzinfo=UTC)
HOME = {"latitude": -41.29, "longitude": 174.78}  # Wellington
WELLINGTON_POLY = "-41.2,174.7 -41.2,174.9 -41.4,174.9 -41.4,174.7 -41.2,174.7"
PORTERS_PASS_POLY = "-43.25,171.70 -43.25,171.75 -43.30,171.75 -43.30,171.70 -43.25,171.70"


def cap(
    identifier: str,
    *,
    msg_type: str = "Alert",
    status: str = "Actual",
    sent: str = "2026-10-15T19:00:00+00:00",
    expires: str = "2026-10-16T06:00:00+00:00",
    severity: str = "Severe",
    event: str = "Severe Weather",
    headline: str = "",
    polygon: str | None = None,
    circle: str | None = None,
    colour: str | None = None,
    references: str = "",
    description: str = "",
) -> str:
    """Build a CAP 1.2 document."""
    shapes = (f"<polygon>{polygon}</polygon>" if polygon else "") + (f"<circle>{circle}</circle>" if circle else "")
    param = (
        f"<parameter><valueName>ColourCode</valueName><value>{colour}</value></parameter>" if colour is not None else ""
    )
    refs = f"<references>{references}</references>" if references else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?><alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">'
        f"<identifier>{identifier}</identifier><sender>nz</sender><sent>{sent}</sent><status>{status}</status>"
        f"<msgType>{msg_type}</msgType><scope>Public</scope>{refs}<info><event>{event}</event>"
        f"<urgency>Immediate</urgency><severity>{severity}</severity><expires>{expires}</expires>"
        f"<headline>{headline}</headline><description>{description}</description>{param}"
        f"<area><areaDesc>Wellington Region</areaDesc>{shapes}</area></info></alert>"
    )


def atom(*entries: tuple[str, str, str]) -> str:
    """NEMA AlertHub feed from (id, title, CAP document) tuples; CAP is escaped inside <content>."""
    body = "".join(
        f"<entry><id>{entry_id}</id><title>{title}</title><updated>2026-10-15T19:00:00Z</updated>"
        f'<content type="text">{escape(document)}</content></entry>'
        for entry_id, title, document in entries
    )
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>EMA</title>{body}</feed>'


def rss(*items: tuple[str, str, str]) -> str:
    """MetService RSS from (guid, title, link) tuples."""
    body = "".join(
        f"<item><title>{title}</title><guid>{guid}</guid><description>Forecast prose</description>"
        f"<link>{link}</link></item>"
        for guid, title, link in items
    )
    return f"<rss version='2.0'><channel><title>MetService</title>{body}</channel></rss>"


type MakeProvider = Callable[..., tuple[NZHazardProvider, AsyncMock]]


@pytest.fixture
def make_provider(feed_routes: Any) -> MakeProvider:
    """Return a factory for providers with routed fetches."""
    return lambda hass, texts, json=None: _make_provider(hass, feed_routes, texts, json)


def _make_provider(
    hass: HomeAssistant, feed_routes: Any, texts: dict[str, str], json: dict[str, object] | None = None
) -> tuple[NZHazardProvider, AsyncMock]:
    """Provider whose fetches are routed to ``texts``/``json`` (missing URL -> network error).

    GeoNet JSON goes through the feed libraries via a fake session; other JSON through the base fetcher.
    """
    json_docs = {GEONET_QUAKE_URL: feature_collection(), GEONET_VOLCANO_URL: feature_collection(), **(json or {})}
    provider = NZHazardProvider(hass, feed_routes(json_docs), {"state": STATE_NZ, **HOME})

    async def fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
        if url not in texts:
            raise aiohttp.ClientError(f"no route for {url}")
        return texts[url]

    async def fetch_json(url: str, headers: dict[str, str] | None = None) -> object:
        if url not in json_docs:
            raise aiohttp.ClientError(f"no route for {url}")
        return json_docs[url]

    provider.async_fetch_text = AsyncMock(side_effect=fetch_text)
    provider.async_fetch_json = AsyncMock(side_effect=fetch_json)
    return provider, provider.async_fetch_text


@pytest.fixture(autouse=True)
def fixed_now():
    """Freeze the provider's clock."""
    with patch("custom_components.ausnz_disaster_watch.providers.nz.dt_util.utcnow", return_value=NOW):
        yield


async def test_nema_alerts_are_read_from_escaped_cap_content(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """NEMA CAP alerts embedded as escaped XML are parsed, located in their area and levelled."""
    feed = atom(
        (
            "e1",
            "CIVIL DEFENCE ADVISORY: SEVERE WEATHER WARNING (RED)",
            cap("NEMA-1", polygon=WELLINGTON_POLY, description="Stay home"),
        ),
        ("e2", "Tsunami threat", cap("NEMA-2", severity="Extreme", circle="-41.3,174.8 20")),
        ("e3", "Flooding", cap("NEMA-3", severity="Severe", polygon=PORTERS_PASS_POLY)),
        ("e4", "Boil water notice", cap("NEMA-4", severity="Moderate", polygon=WELLINGTON_POLY)),
        ("e5", "Cancelled", cap("NEMA-5", msg_type="Cancel", polygon=WELLINGTON_POLY)),
        ("e6", "Expired", cap("NEMA-6", expires="2026-10-15T10:00:00+00:00", polygon=WELLINGTON_POLY)),
        ("e7", "Exercise", cap("NEMA-7", status="Exercise", polygon=WELLINGTON_POLY)),
        ("e8", "No area", cap("NEMA-8")),
    )
    provider, _ = make_provider(hass, {NEMA_ALERTHUB_URL: feed})
    assert provider.state_code == STATE_NZ
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}

    assert set(hazards) == {"nz_nema_NEMA-1", "nz_nema_NEMA-2", "nz_nema_NEMA-3", "nz_nema_NEMA-4"}
    red = hazards["nz_nema_NEMA-1"]
    assert red.warning_level is WarningLevel.EMERGENCY_WARNING  # RED beats CAP severity "Severe"
    assert red.distance_km == 0.0  # home is inside the polygon
    assert red.hazard_type is HazardType.SEVERE_STORM
    assert red.updated_at == datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    assert red.web_url == NEMA_WEB_URL
    assert red.raw_properties["description"] == "Stay home"
    assert hazards["nz_nema_NEMA-2"].warning_level is WarningLevel.EMERGENCY_WARNING  # Extreme
    assert hazards["nz_nema_NEMA-2"].distance_km == 0.0  # inside the circle
    assert hazards["nz_nema_NEMA-3"].warning_level is WarningLevel.WATCH_AND_ACT
    assert hazards["nz_nema_NEMA-3"].distance_km > 250
    assert hazards["nz_nema_NEMA-4"].warning_level is WarningLevel.ADVICE


async def test_nema_inline_cap_and_entries_without_alerts(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """Inline (unescaped) CAP content, double-escaped content and entries without CAP are handled."""
    inline = cap("INLINE", polygon=WELLINGTON_POLY).split("?>", 1)[1]
    feed = f"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>a</id><title>Inline</title><content type="application/cap+xml">{inline}</content></entry>
      <entry><id>b</id><title>Double</title><content>{escape(escape(cap("DOUBLE", polygon=WELLINGTON_POLY)))}</content></entry>
      <entry><id>c</id><title>No content</title></entry>
      <entry><id>d</id><title>Not CAP</title><content>hello</content></entry>
    </feed>"""
    provider, _ = make_provider(hass, {})
    assert sorted(h.id for h in provider._parse_nema_atom(feed)) == ["nz_nema_DOUBLE", "nz_nema_INLINE"]

    # Falls back to the Atom id, then a stable title hash, when the CAP has no identifier
    no_id = cap("", polygon=WELLINGTON_POLY)
    feed = atom(("atom-id", "Flood", no_id), ("", "Flood", no_id))
    ids = [h.id for h in provider._parse_nema_atom(feed)]
    assert ids[0] == "nz_nema_atom-id"
    assert ids[1].startswith("nz_nema_")
    assert ids[1] != "nz_nema_"


async def test_metservice_cap_colour_area_and_lifecycle(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """MetService warnings take level from ColourCode, location from the CAP area, and skip stale messages."""
    feed = rss(
        ("red", "Heavy Rain Warning", "https://ms/red"),
        ("orange", "Road Snowfall Warning", "https://ms/orange"),
        ("yellow", "Heavy Rain Watch", "https://ms/yellow"),
        ("plain", "Strong Wind Watch", "https://ms/plain"),
        ("old", "Heavy Rain Warning (old)", "https://ms/old"),
        ("expired", "Wind Warning", "https://ms/expired"),
        ("noarea", "Thunderstorm Outlook", "https://ms/noarea"),
    )
    docs = {
        METSERVICE_ALERTS_URL: feed,
        "https://ms/red": cap(
            "MS-RED",
            colour="Red",
            headline="Heavy Rain Warning",
            event="rain",
            polygon=WELLINGTON_POLY,
            msg_type="Update",
            references="ms,MS-OLD,2026-10-15T10:00:00+13:00",
        ),
        "https://ms/orange": cap("MS-ORANGE", colour="Orange", event="snow", polygon=PORTERS_PASS_POLY),
        "https://ms/yellow": cap("MS-YELLOW", colour="Yellow", event="rain", polygon=WELLINGTON_POLY),
        "https://ms/plain": cap("MS-PLAIN", colour="", severity="Minor", event="wind", polygon=WELLINGTON_POLY),
        "https://ms/old": cap("MS-OLD", colour="Orange", event="rain", polygon=WELLINGTON_POLY),
        "https://ms/expired": cap(
            "MS-EXP", colour="Orange", expires="2026-10-15T12:00:00+00:00", polygon=WELLINGTON_POLY
        ),
        "https://ms/noarea": cap("MS-NOAREA", colour="Yellow", headline="Thunderstorm Outlook"),
    }
    provider, fetch = make_provider(hass, docs)
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}

    assert set(hazards) == {
        "nz_metservice_MS-RED",
        "nz_metservice_MS-ORANGE",
        "nz_metservice_MS-YELLOW",
        "nz_metservice_MS-PLAIN",
    }
    red = hazards["nz_metservice_MS-RED"]
    assert red.warning_level is WarningLevel.EMERGENCY_WARNING
    assert red.title == "Heavy Rain Warning"
    assert red.source == "MetService"
    assert red.location_name == "Wellington Region"  # areaDesc, not forecast prose
    assert red.raw_properties["colour_code"] == "Red"
    assert red.distance_km == 0.0
    assert hazards["nz_metservice_MS-ORANGE"].warning_level is WarningLevel.WATCH_AND_ACT
    assert hazards["nz_metservice_MS-ORANGE"].distance_km > 250
    assert hazards["nz_metservice_MS-YELLOW"].warning_level is WarningLevel.ADVICE
    assert hazards["nz_metservice_MS-PLAIN"].warning_level is WarningLevel.ADVICE  # severity fallback
    assert hazards["nz_metservice_MS-PLAIN"].web_url == METSERVICE_WEB_URL

    # Unlocated warnings go to the weather warnings sensor
    warnings = await provider.async_fetch_weather_warnings()
    assert [(w.title, w.locations, w.link) for w in warnings] == [
        ("Thunderstorm Outlook", "Wellington Region", "https://ms/noarea")
    ]

    # Polled again within two minutes: MetService is not asked again (CAP Code of Practice, #62)
    rss_calls = [call.args[0] for call in fetch.await_args_list].count(METSERVICE_ALERTS_URL)
    assert {h.id for h in await provider.async_fetch_hazards()} == set(hazards)
    assert [call.args[0] for call in fetch.await_args_list].count(METSERVICE_ALERTS_URL) == rss_calls

    # Two minutes later the feed is fetched again; CAP documents are cached
    nz_now = "custom_components.ausnz_disaster_watch.providers.nz.dt_util.utcnow"
    with patch(nz_now, return_value=NOW + timedelta(minutes=2)):
        await provider.async_fetch_hazards()
    assert [call.args[0] for call in fetch.await_args_list].count(METSERVICE_ALERTS_URL) == rss_calls + 1
    assert [call.args[0] for call in fetch.await_args_list].count("https://ms/red") == 1

    # A new provider (entry reload or a second NZ entry) shares the recent result
    other, other_fetch = make_provider(hass, docs)
    with patch(nz_now, return_value=NOW + timedelta(minutes=3)):
        await other._async_fetch_metservice()
    assert METSERVICE_ALERTS_URL not in [call.args[0] for call in other_fetch.await_args_list]

    # Concurrent refreshes of two entries after the interval fetch the feed once
    with patch(nz_now, return_value=NOW + timedelta(minutes=10)):
        before = [call.args[0] for call in fetch.await_args_list + other_fetch.await_args_list].count(
            METSERVICE_ALERTS_URL
        )
        await asyncio.gather(provider._async_fetch_metservice(), other._async_fetch_metservice())
        after = [call.args[0] for call in fetch.await_args_list + other_fetch.await_args_list].count(
            METSERVICE_ALERTS_URL
        )
    assert after == before + 1
    hass.data.pop(METSERVICE_SHARED_KEY, None)

    # A CAP document that cannot be downloaded makes the MetService poll incomplete: the source
    # fails (instead of reporting fresh partial data) and the download is retried next poll
    docs[METSERVICE_ALERTS_URL] = feed.replace(
        "</channel>", "<item><title>Snow Warning</title><guid>down</guid><link>https://ms/down</link></item></channel>"
    )
    for _ in range(2):
        with pytest.raises(ProviderUnavailableError, match="1 MetService CAP document"):
            await provider._async_fetch_metservice()
    assert [call.args[0] for call in fetch.await_args_list].count("https://ms/down") == 2
    assert [w.title for w in await provider.async_fetch_weather_warnings()] == ["Thunderstorm Outlook"]


async def test_metservice_warnings_outage_and_expiry(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """Weather warnings outlive a short outage, minus expired ones, and are dropped after LAST_GOOD_MAX_AGE."""
    docs = {
        METSERVICE_ALERTS_URL: rss(("a", "Outlook A", "https://ms/a"), ("b", "Outlook B", "https://ms/b")),
        "https://ms/a": cap("A", headline="Outlook A", expires="2026-10-15T20:10:00+00:00"),
        "https://ms/b": cap("B", headline="Outlook B", expires="2026-10-16T20:00:00+00:00"),
    }
    provider, _ = make_provider(hass, docs)
    assert await provider.async_fetch_weather_warnings() == []
    await provider.async_fetch_hazards()
    assert len(await provider.async_fetch_weather_warnings()) == 2

    del docs[METSERVICE_ALERTS_URL]
    nz_now = "custom_components.ausnz_disaster_watch.providers.nz.dt_util.utcnow"
    with patch(nz_now, return_value=NOW + timedelta(minutes=20)):
        await provider.async_fetch_hazards()  # GeoNet still answers, MetService does not
        assert [w.title for w in await provider.async_fetch_weather_warnings()] == ["Outlook B"]
    with patch(nz_now, return_value=NOW + timedelta(minutes=31)):
        assert await provider.async_fetch_weather_warnings() == []


async def test_metservice_feed_failures_and_malformed_alerts(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """Invalid MetService XML fails only that source; a malformed alert is skipped."""
    for body in ("<rss><channel>", "<html/>"):
        provider, _ = make_provider(hass, {METSERVICE_ALERTS_URL: body})
        with pytest.raises(ProviderUnavailableError, match="MetService"):
            await provider._async_fetch_metservice()
        assert await provider.async_fetch_hazards() == []  # GeoNet sources still succeed

    docs = {
        METSERVICE_ALERTS_URL: rss(("a", "A", "https://ms/a")),
        "https://ms/a": cap("A", colour="Red", polygon=WELLINGTON_POLY),
    }
    provider, _ = make_provider(hass, docs)
    with patch.object(provider, "_located_hazard", side_effect=ValueError("bad")):
        assert await provider.async_fetch_hazards() == []


async def test_hazards_without_configured_location(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """Without a usable home location the distance is left to the coordinator."""
    docs = {
        METSERVICE_ALERTS_URL: rss(("a", "A", "https://ms/a")),
        "https://ms/a": cap("A", colour="Red", polygon=WELLINGTON_POLY),
    }
    provider, _ = make_provider(hass, docs)
    provider.config["latitude"] = "not-a-number"
    provider.config.pop("longitude")
    (hazard,) = await provider.async_fetch_hazards()
    assert hazard.distance_km is None
    assert hazard.location_name == "Wellington Region"


async def test_geonet_quakes_and_volcanoes(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """Quake level follows felt intensity; volcanoes carry no fake timestamp; stale and deleted quakes drop."""
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    def quake(public_id: str, mag: float, mmi: int | None, depth: float, time: str = recent, quality: str = "best"):
        props = {"publicID": public_id, "magnitude": mag, "depth": depth, "time": time, "quality": quality}
        if mmi is not None:
            props["mmi"] = mmi
        props["locality"] = "10 km east of Wellington"
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [174.9, -41.3]}, "properties": props}

    quakes = feature_collection(
        quake("strong", 6.2, 7, 12),
        quake("deep", 5.66, 4, 268),  # was Watch and Act; MMI 4 is Advice
        quake("deleted", 6.0, 7, 10, quality="deleted"),
        quake("old", 6.0, 7, 10, time=old),
        {"type": "Feature", "geometry": {}, "properties": {"publicID": "nogeo", "time": recent}},
    )
    volcanoes = feature_collection(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [175.56, -39.28]},
            "properties": {"volcanoID": "ruapehu", "volcanoTitle": "Ruapehu", "level": 2, "acc": "Yellow"},
        },
        {"type": "Feature", "geometry": {}, "properties": {"volcanoID": "nogeo", "level": 1}},
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [177.18, -37.52]},
            "properties": {"volcanoID": "whiteisland", "level": 3},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [176.1, -38.8]},
            "properties": {"volcanoID": "taupo", "level": 1},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [174.8, -36.9]},
            "properties": {"volcanoID": "auckland", "level": 0},
        },
    )
    provider, _ = make_provider(hass, {}, json={GEONET_QUAKE_URL: quakes, GEONET_VOLCANO_URL: volcanoes})
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}

    assert hazards["nz_quake_strong"].warning_level is WarningLevel.EMERGENCY_WARNING
    assert hazards["nz_quake_strong"].hazard_type is HazardType.EARTHQUAKE
    assert hazards["nz_quake_deep"].warning_level is WarningLevel.ADVICE
    assert {"nz_quake_deleted", "nz_quake_old", "nz_quake_nogeo"}.isdisjoint(hazards)

    ruapehu = hazards["nz_volcano_ruapehu"]
    assert ruapehu.warning_level is WarningLevel.WATCH_AND_ACT
    assert ruapehu.updated_at is None
    assert ruapehu.title == "Volcano Level 2 (Yellow) - Ruapehu"
    assert hazards["nz_volcano_whiteisland"].warning_level is WarningLevel.EMERGENCY_WARNING
    assert hazards["nz_volcano_taupo"].warning_level is WarningLevel.ADVICE
    assert hazards["nz_volcano_auckland"].warning_level is WarningLevel.INFORMATION
    assert "nz_volcano_nogeo" not in hazards


@pytest.mark.parametrize(
    ("magnitude", "mmi", "depth", "expected"),
    [
        (6.5, 7, 10.0, WarningLevel.EMERGENCY_WARNING),
        (5.8, 6, 20.0, WarningLevel.EMERGENCY_WARNING),
        (5.1, 5, 20.0, WarningLevel.WATCH_AND_ACT),
        (5.66, 4, 268.0, WarningLevel.ADVICE),
        (6.0, 3, 10.0, WarningLevel.INFORMATION),
        # MMI unknown (-1): magnitude counts only for shallow quakes
        (6.1, -1, 10.0, WarningLevel.WATCH_AND_ACT),
        (5.2, -1, None, WarningLevel.ADVICE),
        (4.5, -1, 10.0, WarningLevel.INFORMATION),
        (6.5, -1, 300.0, WarningLevel.INFORMATION),
    ],
)
def test_quake_level(magnitude: float, mmi: int, depth: float | None, expected: WarningLevel) -> None:
    """Felt intensity drives the level; deep quakes are not escalated by magnitude."""
    assert _quake_level(magnitude, mmi, depth) is expected


async def test_all_sources_down(hass: HomeAssistant, make_provider: MakeProvider) -> None:
    """The provider is unavailable only when every NZ source fails."""
    provider, _ = make_provider(hass, {}, json={GEONET_QUAKE_URL: 503, GEONET_VOLCANO_URL: {"error": "maintenance"}})
    with pytest.raises(ProviderUnavailableError, match="GeoNet quakes unavailable.*GeoNet volcanoes returned"):
        await provider.async_fetch_hazards()
    with pytest.raises(ProviderUnavailableError, match="empty response"):
        provider._parse_nema_atom("  ")
    with pytest.raises(ProviderUnavailableError, match="invalid XML"):
        provider._parse_nema_atom("<feed")


def test_metservice_shared_state_without_real_hass() -> None:
    """Without Home Assistant data (unit-test doubles) the poll state is kept per provider."""
    provider = NZHazardProvider(MagicMock(), MagicMock(), {"state": STATE_NZ})
    state = provider._metservice_shared()
    assert state is provider._metservice_shared()
    assert state.last is None
