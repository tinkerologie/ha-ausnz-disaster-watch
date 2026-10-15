"""BoM provider (#10): CAP lifecycle, product grouping, area geometry and the CAP helpers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import defusedxml.ElementTree as ET
import pytest

from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.bom import (
    BOM_WARNINGS_PAGE,
    BOM_WMO_FEED_URL,
    BoMHazardProvider,
    _web_url,
)
from custom_components.ausnz_disaster_watch.providers.cap import (
    CapArea,
    area_distance_km,
    distance_to_polygon_km,
    haversine_km,
    parse_cap,
    point_in_polygon,
    representative_point,
)
from homeassistant.core import HomeAssistant

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
HOME = {"latitude": -27.47, "longitude": 153.02}  # Brisbane
# Square around Brisbane, and one ~200 km west near Dalby (CAP order is lat,lon)
BRISBANE_POLY = "-27.3,152.9 -27.3,153.2 -27.6,153.2 -27.6,152.9 -27.3,152.9"
WEST_POLY = "-27.0,150.9 -27.0,151.3 -27.4,151.3 -27.4,150.9 -27.0,150.9"


def cap(
    identifier: str,
    *,
    msg_type: str = "Alert",
    status: str = "Actual",
    sent: str = "2026-10-15T09:00:00+00:00",
    expires: str = "2026-10-15T12:00:00+00:00",
    severity: str = "Severe",
    event: str = "Thunderstorm",
    polygon: str | None = None,
    circle: str | None = None,
    references: str = "",
    geocode: str = "QLD_PW015",
) -> str:
    """Build a CAP 1.2 document."""
    shapes = (f"<polygon>{polygon}</polygon>" if polygon else "") + (f"<circle>{circle}</circle>" if circle else "")
    refs = f"<references>{references}</references>" if references else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>{identifier}</identifier><sender>CAP.Message@bom.gov.au</sender><sent>{sent}</sent>
  <status>{status}</status><msgType>{msg_type}</msgType><scope>Public</scope>{refs}
  <info><language>en-AU</language><event>{event}</event><urgency>Expected</urgency><severity>{severity}</severity>
    <expires>{expires}</expires><headline>{event} warning</headline><web>http://www.bom.gov.au/qld/warnings/</web>
    <area><areaDesc>Queensland: Southeast Coast</areaDesc>{shapes}
      <geocode><valueName>AMOC-AreaCode</valueName><value>{geocode}</value></geocode></area>
  </info>
</alert>"""


def rss(*items: tuple[str, str, str, str]) -> str:
    """Build the WMO RSS feed from (guid, title, link, pubDate) tuples."""
    body = "".join(
        f"<item><title>{title}</title><link>{link}</link><guid>{guid}</guid><pubDate>{pub}</pubDate></item>"
        for guid, title, link, pub in items
    )
    return f"<rss version='2.0'><channel><title>BoM</title>{body}</channel></rss>"


def make_provider(
    hass: HomeAssistant, documents: dict[str, str], state: str = "QLD"
) -> tuple[BoMHazardProvider, MagicMock]:
    """Provider whose text fetches are routed to ``documents`` (missing URL -> network error)."""
    provider = BoMHazardProvider(hass, MagicMock(), {"state": state, **HOME})

    async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
        if url not in documents:
            raise aiohttp.ClientError(f"no route for {url}")
        return documents[url]

    provider.async_fetch_text = AsyncMock(side_effect=fetch)
    return provider, provider.async_fetch_text


@pytest.fixture(autouse=True)
def fixed_now():
    """Freeze the provider's clock."""
    with patch("custom_components.ausnz_disaster_watch.providers.bom.dt_util.utcnow", return_value=NOW):
        yield


async def test_lifecycle_newest_message_per_product(hass: HomeAssistant) -> None:
    """Only the newest message per product counts: updates replace, cancellations remove, expired drop."""
    feed = rss(
        ("AusBoM-IDQ21033-1", "Severe Thunderstorm Warning (old)", "https://cap/1", "Thu, 15 Oct 2026 08:00:00 +0000"),
        ("AusBoM-IDQ21033-2", "Severe Thunderstorm Warning", "https://cap/2", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDQ20085-1", "Strong Wind Warning", "https://cap/3", "Thu, 15 Oct 2026 08:00:00 +0000"),
        (
            "AusBoM-IDQ20085-2",
            "Cancellation of Strong Wind Warning",
            "https://cap/4",
            "Thu, 15 Oct 2026 09:30:00 +0000",
        ),
        ("AusBoM-IDQ10090-1", "Fire Weather Warning", "https://cap/5", "Thu, 15 Oct 2026 01:00:00 +0000"),
        ("AusBoM-IDQ99999-1", "Exercise Warning", "https://cap/6", "Thu, 15 Oct 2026 09:00:00 +0000"),
    )
    provider, fetch = make_provider(
        hass,
        {
            BOM_WMO_FEED_URL: feed,
            "https://cap/1": cap("AusBoM-IDQ21033-1", polygon=BRISBANE_POLY),
            "https://cap/2": cap(
                "AusBoM-IDQ21033-2", msg_type="Update", polygon=BRISBANE_POLY, references="CAP,AusBoM-IDQ21033-1,x"
            ),
            "https://cap/3": cap("AusBoM-IDQ20085-1", polygon=BRISBANE_POLY),
            "https://cap/4": cap("AusBoM-IDQ20085-2", msg_type="Cancel", polygon=BRISBANE_POLY),
            "https://cap/5": cap("AusBoM-IDQ10090-1", expires="2026-10-15T06:00:00+00:00", polygon=BRISBANE_POLY),
            "https://cap/6": cap("AusBoM-IDQ99999-1", status="Exercise", polygon=BRISBANE_POLY),
        },
    )
    hazards = await provider.async_fetch_hazards()

    assert [h.id for h in hazards] == ["BOM_IDQ21033"]
    hazard = hazards[0]
    assert hazard.title == "Severe Thunderstorm Warning"
    assert hazard.raw_properties["cap_identifier"] == "AusBoM-IDQ21033-2"
    assert hazard.hazard_type is HazardType.SEVERE_STORM
    assert hazard.warning_level is WarningLevel.WATCH_AND_ACT  # from CAP severity "Severe"
    assert hazard.updated_at == datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    assert hazard.web_url == "https://www.bom.gov.au/qld/warnings/"
    # Older messages of the same product are never fetched
    assert "https://cap/1" not in [call.args[0] for call in fetch.await_args_list]


async def test_area_geometry_drives_location_and_distance(hass: HomeAssistant) -> None:
    """Home inside the polygon: distance 0, located at the area centre (never at home)."""
    feed = rss(
        ("AusBoM-IDQ21033-1", "Severe Thunderstorm Warning", "https://cap/in", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDQ21034-1", "Severe Thunderstorm Warning", "https://cap/far", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDQ21035-1", "Flood Watch", "https://cap/circle", "Thu, 15 Oct 2026 09:00:00 +0000"),
    )
    provider, _ = make_provider(
        hass,
        {
            BOM_WMO_FEED_URL: feed,
            "https://cap/in": cap("in", polygon=BRISBANE_POLY),
            "https://cap/far": cap("far", polygon=WEST_POLY),
            "https://cap/circle": cap("circle", event="Flood", circle="-27.47,153.02 5"),
        },
    )
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}

    inside = hazards["BOM_IDQ21033"]
    assert inside.distance_km == 0.0
    assert (inside.latitude, inside.longitude) == pytest.approx((-27.45, 153.05))
    assert (inside.latitude, inside.longitude) != (HOME["latitude"], HOME["longitude"])
    assert hazards["BOM_IDQ21034"].distance_km > 150
    assert hazards["BOM_IDQ21035"].distance_km == 0.0
    assert hazards["BOM_IDQ21035"].hazard_type is HazardType.FLOOD


async def test_warnings_without_geometry_are_weather_warnings(hass: HomeAssistant) -> None:
    """BoM warnings identified only by AMOC area codes are not placed on the map."""
    feed = rss(("AusBoM-IDQ21033-1", "Severe Thunderstorm Warning", "https://cap/1", "Thu, 15 Oct 2026 09:00:00 +0000"))
    provider, _ = make_provider(hass, {BOM_WMO_FEED_URL: feed, "https://cap/1": cap("AusBoM-IDQ21033-1")})

    assert await provider.async_fetch_hazards() == []
    warnings = await provider.async_fetch_weather_warnings()
    assert [(w.title, w.locations) for w in warnings] == [
        ("Severe Thunderstorm Warning", "Queensland: Southeast Coast")
    ]
    assert warnings[0].pub_date == datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


async def test_state_selection_and_act(hass: HomeAssistant) -> None:
    """Other states' products are ignored; ACT accepts NSW (IDN) products."""
    feed = rss(
        ("AusBoM-IDN21001-1", "Severe Thunderstorm Warning", "https://cap/n", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDV21001-1", "Severe Thunderstorm Warning", "https://cap/v", "Thu, 15 Oct 2026 09:00:00 +0000"),
    )
    docs = {BOM_WMO_FEED_URL: feed, "https://cap/n": cap("n"), "https://cap/v": cap("v")}
    act, act_fetch = make_provider(hass, docs, state="ACT")
    await act.async_fetch_hazards()
    assert len(await act.async_fetch_weather_warnings()) == 1
    assert "https://cap/v" not in [call.args[0] for call in act_fetch.await_args_list]

    every_state, _ = make_provider(hass, docs, state="ALL")
    await every_state.async_fetch_hazards()
    assert len(await every_state.async_fetch_weather_warnings()) == 2


async def test_cap_cache_and_fetch_failures(hass: HomeAssistant) -> None:
    """CAP documents are fetched once; failures are retried next poll; unusable documents are cached."""
    feed = rss(
        ("AusBoM-IDQ21033-1", "Severe Thunderstorm Warning", "https://cap/1", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDQ21034-1", "Severe Thunderstorm Warning", "https://cap/down", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("AusBoM-IDQ21035-1", "Severe Thunderstorm Warning", "https://cap/junk", "Thu, 15 Oct 2026 09:00:00 +0000"),
        ("no-product-no-link", "Marine Wind Warning", "", "Thu, 15 Oct 2026 09:00:00 +0000"),
    )
    docs = {BOM_WMO_FEED_URL: feed, "https://cap/1": cap("one", polygon=BRISBANE_POLY), "https://cap/junk": "<not cap"}
    provider, fetch = make_provider(hass, docs)

    assert [h.id for h in await provider.async_fetch_hazards()] == ["BOM_IDQ21033"]
    await provider.async_fetch_hazards()
    urls = [call.args[0] for call in fetch.await_args_list]
    assert urls.count("https://cap/1") == 1  # cached
    assert urls.count("https://cap/junk") == 1  # unusable document cached as such
    assert urls.count("https://cap/down") == 2  # network failure retried

    # Items that leave the feed are forgotten
    docs[BOM_WMO_FEED_URL] = rss()
    await provider.async_fetch_hazards()
    assert provider._cap_cache == {}


async def test_feed_level_failures(hass: HomeAssistant) -> None:
    """Unreachable feed, invalid XML or no channel make the provider unavailable."""
    provider, _ = make_provider(hass, {})
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()
    for body in ("<rss><channel>", "<rss></rss>"):
        provider, _ = make_provider(hass, {BOM_WMO_FEED_URL: body})
        with pytest.raises(ProviderUnavailableError):
            await provider.async_fetch_hazards()


async def test_titles_levels_and_unlocated_config(hass: HomeAssistant) -> None:
    """Title-derived AWS level wins; without a configured location the distance is left to the coordinator."""
    feed = rss(
        ("AusBoM-IDQ21033-1", "Emergency Warning: Tropical Cyclone", "https://cap/1", "Thu, 15 Oct 2026 09:00:00 +0000")
    )
    provider, _ = make_provider(
        hass,
        {BOM_WMO_FEED_URL: feed, "https://cap/1": cap("x", severity="Minor", event="Cyclone", polygon=BRISBANE_POLY)},
    )
    provider.config.pop("latitude")
    hazard = (await provider.async_fetch_hazards())[0]
    assert hazard.warning_level is WarningLevel.EMERGENCY_WARNING
    assert hazard.hazard_type is HazardType.CYCLONE
    assert hazard.distance_km is None

    # Unknown CAP severity falls back to Advice; a malformed item is skipped
    provider, _ = make_provider(
        hass, {BOM_WMO_FEED_URL: feed, "https://cap/1": cap("x", severity="Unknown", polygon=BRISBANE_POLY)}
    )
    assert (await provider.async_fetch_hazards())[0].warning_level is WarningLevel.EMERGENCY_WARNING
    feed2 = rss(("AusBoM-IDQ21033-1", "Thunderstorm", "https://cap/1", "Thu, 15 Oct 2026 09:00:00 +0000"))
    provider, _ = make_provider(
        hass, {BOM_WMO_FEED_URL: feed2, "https://cap/1": cap("x", severity="Unknown", polygon=BRISBANE_POLY)}
    )
    assert (await provider.async_fetch_hazards())[0].warning_level is WarningLevel.ADVICE
    with patch.object(provider, "_build_hazard", side_effect=ValueError("bad")):
        assert await provider.async_fetch_hazards() == []


def test_parse_cap_fields_and_malformed_input() -> None:
    """parse_cap reads lifecycle, info and areas; tolerates bad coordinates; rejects non-CAP."""
    alert = parse_cap(
        cap(
            "AusBoM-IDQ21033-2",
            msg_type="Update",
            references="CAP.Message@bom.gov.au,AusBoM-IDQ21033-1,2026-10-15T06:00:00+00:00 junk",
            polygon="-27.3,152.9 bad -27.3,153.2 -27.6,153.2 99,0",
            circle="-27.47,153.02 5",
        )
    )
    assert alert is not None
    assert alert.msg_type == "Update"
    assert alert.references == ("AusBoM-IDQ21033-1",)
    assert alert.expires == datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    assert alert.area_description == "Queensland: Southeast Coast"
    assert alert.areas[0].polygons == (((-27.3, 152.9), (-27.3, 153.2), (-27.6, 153.2)),)
    assert alert.areas[0].circles == ((-27.47, 153.02, 5.0),)
    assert alert.areas[0].geocodes == (("AMOC-AreaCode", "QLD_PW015"),)
    assert alert.has_geometry

    assert parse_cap("<oops") is None
    assert parse_cap("<rss/>") is None
    # A two-point "polygon" and malformed circles are ignored
    sparse = parse_cap(cap("x", polygon="-27,153 -28,153", circle="nonsense"))
    assert sparse is not None and not sparse.has_geometry
    assert parse_cap(cap("x", circle="-27,153 -1")).areas[0].circles == ()  # type: ignore[union-attr]
    # Wrapped alerts (e.g. EDXL) are found too
    wrapped = parse_cap(f"<edxl>{cap('w').split('?>', 1)[1]}</edxl>")
    assert wrapped is not None and wrapped.identifier == "w"


def test_area_geometry_helpers() -> None:
    """Containment, edge distance, circle distance, union semantics and representative point."""
    ring = ((-27.3, 152.9), (-27.3, 153.2), (-27.6, 153.2), (-27.6, 152.9), (-27.3, 152.9))
    assert point_in_polygon(-27.47, 153.02, ring)
    assert not point_in_polygon(-27.0, 153.02, ring)
    assert distance_to_polygon_km(-27.47, 153.02, ring) == 0.0
    # 0.3 degrees of latitude north of the top edge is ~33 km
    assert distance_to_polygon_km(-27.0, 153.05, ring) == pytest.approx(33.4, abs=0.5)
    assert haversine_km(-27.47, 153.02, -27.47, 153.02) == 0.0

    near_circle = CapArea("c", (), ((-27.47, 153.30, 10.0),), ())
    far_poly = CapArea("p", (ring,), (), ())
    # Union: inside the polygon wins over the circle
    assert area_distance_km(-27.47, 153.02, (near_circle, far_poly)) == 0.0
    assert area_distance_km(-27.47, 153.02, (near_circle,)) == pytest.approx(17.7, abs=0.5)
    assert area_distance_km(-27.47, 153.02, (CapArea("none", (), (), ()),)) is None

    assert representative_point((far_poly, near_circle), -27.47, 153.02) == pytest.approx((-27.45, 153.05))
    assert representative_point((near_circle,)) == (-27.47, 153.30)
    assert representative_point(()) is None


async def test_link_fallbacks_and_bad_config(hass: HomeAssistant) -> None:
    """Non-BoM CAP web pages fall back to the RSS link, then the BoM warnings page; bad coordinates are ignored."""
    no_web = cap("x", polygon=BRISBANE_POLY).replace(
        "<web>http://www.bom.gov.au/qld/warnings/</web>", "<web>https://example.org</web>"
    )
    feed = rss(("AusBoM-IDQ21033-1", "Severe Thunderstorm Warning", "https://cap/1", "Thu, 15 Oct 2026 09:00:00 +0000"))
    provider, _ = make_provider(hass, {BOM_WMO_FEED_URL: feed, "https://cap/1": no_web})
    provider.config["latitude"] = "not-a-number"
    hazard = (await provider.async_fetch_hazards())[0]
    assert hazard.web_url == "https://cap/1"
    assert hazard.distance_km is None  # invalid configured latitude: coordinator computes distance

    item_without_link = ET.fromstring("<item><title>t</title></item>")
    assert _web_url(item_without_link, parse_cap(no_web)) == BOM_WARNINGS_PAGE  # type: ignore[arg-type]


def test_parse_cap_without_info() -> None:
    """An alert without <info> still parses (no areas, empty info fields)."""
    alert = parse_cap(
        '<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>i</identifier>'
        "<status>Actual</status><msgType>Alert</msgType></alert>"
    )
    assert alert is not None
    assert alert.areas == ()
    assert alert.event == "" and alert.expires is None
