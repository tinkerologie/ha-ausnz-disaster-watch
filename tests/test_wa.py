"""Emergency WA warnings and incidents from the designated RSS feeds (#61), with warning areas (#30).

Fixtures are synthetic items in the live feeds' shape (checked 2026-10-16): non-standard
GeoRSS and W3C geo namespace URIs, ``dfes:`` elements, ``lat,lon`` polygons and the warning
type in the description's ``data-warning-type`` attribute.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import WAHazardProvider
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.geometry import area_distance
from custom_components.ausnz_disaster_watch.providers.wa import WA_INCIDENTS_URL, WA_WARNINGS_URL
from homeassistant.core import HomeAssistant

NAMESPACES = (
    'xmlns:georss="https://www.ogc.org/standard/georss/" xmlns:dfes="https://emergency.wa.gov.au/xmlns/dfes" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:geo="https://www.w3.org/2003/01/geo/wgs84_pos#"'
)
POLYGON = "-31.80,116.10 -31.90,116.10 -31.90,116.30 -31.80,116.30 -31.80,116.10"


def rss(*items: str) -> str:
    """Return an Emergency WA RSS document."""
    return f'<?xml version="1.0"?><rss {NAMESPACES} version="2.0"><channel><title>DFES</title>{"".join(items)}</channel></rss>'


def warning_item(
    guid: str | None,
    title: str,
    warning_type: str | None,
    *,
    lat: float | None = -31.85,
    lon: float | None = 116.2,
    polygon: str = POLYGON,
    link: str | None = None,
    alert_level: str = "",
    published: str = "Fri, 16 Oct 2026 08:07:45 +0800",
) -> str:
    """Return one warnings-feed item."""
    description = f'<![CDATA[<p data-warning-type="{warning_type}">x</p>]]>' if warning_type else "plain text"
    point = f"<geo:long>{lon}</geo:long><geo:lat>{lat}</geo:lat>" if lat is not None else ""
    return (
        f"<item><title>{title}</title>"
        f"<link>{link or f'https://emergency.wa.gov.au/warnings/{guid}'}</link>"
        f"<description>{description}</description><pubDate>{published}</pubDate>"
        "<dfes:region>METRO NORTH EAST</dfes:region><dfes:incidentNumber>823442</dfes:incidentNumber>"
        f"<dfes:publicationTime>{published}</dfes:publicationTime>"
        + (f'<guid isPermaLink="false">{guid}</guid>' if guid else "")
        + f"{point}<georss:alertLevel>{alert_level}</georss:alertLevel><georss:polygon>{polygon}</georss:polygon></item>"
    )


def incident_item(guid: str | None, title: str, *, lat: str = "-31.95", lon: str = "115.86") -> str:
    """Return one incidents-feed item."""
    return (
        f"<item><title>{title}</title><link>https://emergency.wa.gov.au/incidents/{guid}</link>"
        "<description><![CDATA[Fire <region>X</region>]]></description>"
        "<pubDate>Mon, 12 Oct 2026 12:54:31 +0800</pubDate>"
        + (f'<guid isPermaLink="false">{guid}</guid>' if guid else "")
        + f"<geo:long>{lon}</geo:long><geo:lat>{lat}</geo:lat><georss:polygon/></item>"
    )


@pytest.fixture
def provider(hass: HomeAssistant) -> WAHazardProvider:
    """Return a WA provider."""
    return WAHazardProvider(hass, AsyncMock(), {"state": "WA"})


def test_warnings_levels_area_and_fields(provider: WAHazardProvider) -> None:
    """Levels come from the warning type, the polygon is the area, and closures are skipped."""
    feed = rss(
        warning_item("w1", "Bushfire Emergency Warning EVACUATE NOW - GIDGEGANNUP", "Bushfire Emergency Warning"),
        warning_item("w2", "Bushfire Watch and Act - CHIDLOW", "Bushfire Watch and Act"),
        # "Emergency" in the place name does not override the Advice warning type
        warning_item("w3", "Bushfire Advice MONITOR CONDITIONS - EMERGENCY BEACH", "Bushfire Advice"),
        warning_item("w4", "Smoke Alert FOR AREAS NEAR COLLIE", "Smoke Alert", polygon=""),
        warning_item("w5", "Flood Watch and Act", None, alert_level="Watch and Act"),
        warning_item("w6", "Park Closure", None, link="https://emergency.wa.gov.au/closures/w6"),
        # No point: placed on the polygon
        warning_item("w7", "Bushfire Advice - WOOROLOO", "Bushfire Advice", lat=None),
        # Neither point nor polygon: skipped, never placed at a default location
        warning_item("w8", "Bushfire Advice - NOWHERE", "Bushfire Advice", lat=None, polygon=""),
        warning_item("w9", "Bushfire Advice - BAD", "Bushfire Advice", lat=999.0),
        # No warning type: the title's place suffix is ignored for the level
        warning_item("w10", "Bushfire Advice - EMERGENCY BEACH", None),
    )
    hazards = {h.id: h for h in provider._parse_warnings(feed)}
    assert set(hazards) == {
        "wa_warn_w1",
        "wa_warn_w2",
        "wa_warn_w3",
        "wa_warn_w4",
        "wa_warn_w5",
        "wa_warn_w7",
        "wa_warn_w9",
        "wa_warn_w10",
    }
    w1 = hazards["wa_warn_w1"]
    assert w1.warning_level is WarningLevel.EMERGENCY_WARNING
    assert w1.hazard_type is HazardType.BUSHFIRE
    assert w1.location_name == "Gidgegannup"
    assert w1.updated_at == datetime(2026, 10, 16, 0, 7, 45, tzinfo=UTC)
    assert w1.web_url == "https://emergency.wa.gov.au/warnings/w1"
    assert w1.raw_properties == {
        "warning_type": "Bushfire Emergency Warning",
        "region": "METRO NORTH EAST",
        "incident_number": "823442",
    }
    assert w1.area is not None
    assert area_distance(-31.85, 116.2, w1.area) == 0.0
    assert hazards["wa_warn_w2"].warning_level is WarningLevel.WATCH_AND_ACT
    assert hazards["wa_warn_w3"].warning_level is WarningLevel.ADVICE
    assert hazards["wa_warn_w10"].warning_level is WarningLevel.ADVICE
    assert hazards["wa_warn_w10"].location_name == "Emergency Beach"
    assert hazards["wa_warn_w4"].area is None
    assert hazards["wa_warn_w4"].location_name == "Metro North East"
    assert hazards["wa_warn_w5"].warning_level is WarningLevel.WATCH_AND_ACT
    assert hazards["wa_warn_w7"].latitude == -31.8
    # A point that is out of range is ignored; the polygon places the warning
    assert hazards["wa_warn_w9"].latitude == -31.8


def test_incidents(provider: WAHazardProvider) -> None:
    """Incident titles are split into type, locality and CAD ID; burn-offs are hazard reduction."""
    feed = rss(
        incident_item("i1", "Bushfire (BINDOON TRAINING AREA, SHIRE OF TOODYAY, GOLDFIELDS MIDLANDS, CAD-ID: 823750)"),
        incident_item("i2", "Burn Off (DENMARK, SHIRE OF DENMARK, GREAT SOUTHERN, CAD-ID: 820576)"),
        incident_item("i3", "Smell of Gas"),
        incident_item("i4", "Fire (NOWHERE)", lat="abc"),
        incident_item("i5", "Fire (ZERO)", lat="0", lon="0"),
    )
    hazards = {h.id: h for h in provider._parse_incidents(feed)}
    assert set(hazards) == {"wa_inc_i1", "wa_inc_i2", "wa_inc_i3"}
    i1 = hazards["wa_inc_i1"]
    assert i1.title == "Bushfire - Bindoon Training Area"
    assert i1.location_name == "Bindoon Training Area, Shire Of Toodyay, Goldfields Midlands"
    assert i1.raw_properties == {"cad_id": "823750", "region": "Goldfields Midlands"}
    assert i1.warning_level is WarningLevel.INFORMATION
    assert i1.hazard_type is HazardType.BUSHFIRE
    assert not i1.is_hazard_reduction
    assert i1.updated_at == datetime(2026, 10, 12, 4, 54, 31, tzinfo=UTC)
    assert i1.web_url == "https://emergency.wa.gov.au/incidents/i1"
    assert hazards["wa_inc_i2"].is_hazard_reduction
    i3 = hazards["wa_inc_i3"]
    assert i3.title == "Smell of Gas - WA"
    assert i3.raw_properties == {"cad_id": None, "region": None}


def test_ids_without_guid_are_stable(provider: WAHazardProvider) -> None:
    """Items without a GUID get a deterministic fallback that ignores the publication time (#7)."""

    def ids(published: str) -> list[str]:
        feed = rss(
            warning_item(None, "Bushfire Advice - GIDGEGANNUP", "Bushfire Advice", published=published),
            warning_item(None, "Bushfire Advice - CHIDLOW", "Bushfire Advice", lat=-31.86, published=published),
        )
        incidents = rss(
            incident_item(None, "Fire (A, B, C, CAD-ID: 1)"), incident_item(None, "Fire (D, E, F, CAD-ID: 2)")
        )
        return [h.id for h in provider._parse_warnings(feed)] + [h.id for h in provider._parse_incidents(incidents)]

    first = ids("Fri, 16 Oct 2026 08:07:45 +0800")
    assert first == ids("Fri, 16 Oct 2026 11:30:00 +0800")
    assert len(set(first)) == 4
    assert all(i.startswith(("wa_warn_wa_warn_", "wa_inc_wa_inc_")) for i in first)


def test_malformed_items_are_skipped(provider: WAHazardProvider) -> None:
    """One item that fails validation is skipped, not the feed."""
    good = incident_item("i1", "Fire (A, B, C)")
    bad = incident_item("i2", "Fire (A, B, C)", lat="-95")
    assert [h.id for h in provider._parse_incidents(rss(good, bad))] == ["wa_inc_i1"]
    warnings = rss(warning_item("w1", "Bushfire Advice - A", "Bushfire Advice"))
    provider_bad = WAHazardProvider(provider.hass, AsyncMock(), {"state": "WA"})
    provider_bad._parse_warning = lambda _item: (_ for _ in ()).throw(ValueError("bad"))  # type: ignore[method-assign]
    assert provider_bad._parse_warnings(warnings) == []
    provider_bad._parse_incident = lambda _item: (_ for _ in ()).throw(KeyError("bad"))  # type: ignore[method-assign]
    assert provider_bad._parse_incidents(rss(good)) == []


@pytest.mark.parametrize(
    "document",
    ["", "   ", "<rss", "<html><body>Error</body></html>", "<rss version='2.0'></rss>"],
)
def test_broken_documents_are_unavailable(provider: WAHazardProvider, document: str) -> None:
    """A blank body, invalid XML, an HTML page or RSS without a channel is a broken feed (#16)."""
    with pytest.raises(ProviderUnavailableError):
        provider._parse_warnings(document)
    with pytest.raises(ProviderUnavailableError):
        provider._parse_incidents(document)


async def test_fetch_uses_designated_feeds_and_isolates_sources(provider: WAHazardProvider) -> None:
    """Both RSS feeds are fetched; one failing source keeps the other; an empty channel is healthy."""
    feeds = {
        WA_WARNINGS_URL: rss(warning_item("w1", "Bushfire Advice - A", "Bushfire Advice")),
        WA_INCIDENTS_URL: rss(incident_item("i1", "Fire (A, B, C)")),
    }

    async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
        return feeds[url]

    provider.async_fetch_text = AsyncMock(side_effect=fetch)
    assert [h.id for h in await provider.async_fetch_hazards()] == ["wa_warn_w1", "wa_inc_i1"]
    assert {call.args[0] for call in provider.async_fetch_text.call_args_list} == {WA_WARNINGS_URL, WA_INCIDENTS_URL}
    assert all("/v1/rss/" in url for url in feeds)

    feeds[WA_WARNINGS_URL] = "<html>maintenance</html>"
    assert [h.id for h in await provider.async_fetch_hazards()] == ["wa_inc_i1"]
    feeds[WA_INCIDENTS_URL] = rss()
    assert await provider.async_fetch_hazards() == []

    provider.async_fetch_text = AsyncMock(side_effect=aiohttp.ClientError("down"))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()


def test_state_code(provider: WAHazardProvider) -> None:
    """The provider reports WA."""
    assert provider.state_code == "WA"
