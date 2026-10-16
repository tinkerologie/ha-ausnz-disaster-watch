"""NationalHazardProvider, its caches and transports (#37). No real network requests are made."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import ftplib
import json
import pathlib
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock, patch

from aio_georss_client.xml_parser import XmlParser
import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.ausnz_disaster_watch.const import (
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_REGIONAL_ALERTS,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_TSUNAMI,
    CONF_ENABLE_UV,
    NATIONAL_FEED_OPTIONS,
)
from custom_components.ausnz_disaster_watch.models import RegionalAlertItem
from custom_components.ausnz_disaster_watch.providers import (
    BoMHazardProvider,
    NationalHazardProvider,
    bom_ftp,
    gdacs,
    get_providers_for_config,
)
from custom_components.ausnz_disaster_watch.providers.base import FeedCache, ProviderUnavailableError
from homeassistant.core import HomeAssistant

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "national"
ALL_ON = dict.fromkeys(NATIONAL_FEED_OPTIONS, True)
NATIONAL = "custom_components.ausnz_disaster_watch.providers.national"


def provider(hass: HomeAssistant, state: str = "QLD", **overrides: Any) -> NationalHazardProvider:
    config = {"state": state, "latitude": -27.47, "longitude": 153.03, "radius": 50, **ALL_ON, **overrides}
    return NationalHazardProvider(hass, AsyncMock(), config)


# FeedCache


async def test_feed_cache_lifecycle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fresh values are reused, expired values refetched, failures bridged up to the stale age."""
    cache = FeedCache[int]("test", timedelta(minutes=10), timedelta(minutes=30))
    fetch = AsyncMock(return_value=1)
    assert await cache.async_get(fetch) == 1
    assert cache.fetched_at is not None
    assert await cache.async_get(fetch) == 1
    assert fetch.await_count == 1

    freezer.tick(timedelta(minutes=11))
    fetch.side_effect = ProviderUnavailableError("down")
    assert await cache.async_get(fetch) == 1  # stale but within 30 minutes
    freezer.tick(timedelta(minutes=25))
    assert await cache.async_get(fetch) is None  # too old: undetermined

    fetch.side_effect = KeyError("broken document")
    assert await FeedCache[int]("t", timedelta(0), timedelta(0)).async_get(fetch) is None


# FTP


def _ftp(listing: dict[str, list[str] | Exception], files: dict[str, bytes]) -> MagicMock:
    ftp = MagicMock()
    ftp.__enter__.return_value = ftp

    def nlst(pattern: str) -> list[str]:
        result = listing[pattern]
        if isinstance(result, Exception):
            raise result
        return result

    def retr(command: str, callback: Any) -> None:
        callback(files[command.removeprefix("RETR ")])

    ftp.nlst.side_effect = nlst
    ftp.retrbinary.side_effect = retr
    return ftp


def test_fetch_products_lists_and_retrieves_wanted_files() -> None:
    """One connection lists the patterns and downloads only wanted files; 550 means none."""
    ftp = _ftp(
        {"IDY68*": ["/anon/gen/fwo/IDY68027.cap.xml", "IDY68027.html"], "IDQ*": ftplib.error_perm("550 No files")},
        {"IDY68027.cap.xml": b"cap"},
    )
    with patch.object(bom_ftp.ftplib, "FTP", return_value=ftp) as factory:
        files = bom_ftp.fetch_products(("IDY68*", "IDQ*"), lambda name: name.endswith(".cap.xml"))
    assert files == {"IDY68027.cap.xml": b"cap"}
    factory.assert_called_once_with(bom_ftp.BOM_FTP_HOST, timeout=bom_ftp.BOM_FTP_TIMEOUT)
    ftp.login.assert_called_once_with()
    ftp.cwd.assert_called_once_with(bom_ftp.BOM_FTP_DIR)


def test_fetch_products_errors() -> None:
    """Other permission errors propagate; oversized files are refused."""
    ftp = _ftp({"X": ftplib.error_perm("530 Login incorrect")}, {})
    with patch.object(bom_ftp.ftplib, "FTP", return_value=ftp), pytest.raises(ftplib.error_perm):
        bom_ftp.fetch_products(("X",), lambda name: True)
    big = _ftp({"X": ["X"]}, {"X": b"0" * (bom_ftp.MAX_PRODUCT_BYTES + 1)})
    with patch.object(bom_ftp.ftplib, "FTP", return_value=big), pytest.raises(ftplib.Error):
        bom_ftp.fetch_products(("X",), lambda name: True)


async def test_async_fetch_bom_products(hass: HomeAssistant) -> None:
    """The blocking client runs in the executor; failures become ProviderUnavailableError."""
    with patch.object(bom_ftp, "fetch_products", return_value={"a": b"1"}) as fetch:
        assert await bom_ftp.async_fetch_bom_products(hass, ["a"], bool) == {"a": b"1"}
    fetch.assert_called_once_with(("a",), bool)
    with (
        patch.object(bom_ftp, "fetch_products", side_effect=OSError("timed out")),
        pytest.raises(ProviderUnavailableError),
    ):
        await bom_ftp.async_fetch_bom_products(hass, ["a"], bool)


# POST helper


class _Response:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, content_type: Any = None) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)


async def test_async_post_json(hass: HomeAssistant) -> None:
    """POST sends the JSON body; HTTP and decode failures become ProviderUnavailableError."""
    session = MagicMock()
    session.post = MagicMock(return_value=_Response(200, [1]))
    national = NationalHazardProvider(hass, session, {"state": "NSW"})
    assert await national.async_post_json("https://x", {"a": 1}, "X") == [1]
    assert session.post.call_args.kwargs["json"] == {"a": 1}
    session.post = MagicMock(return_value=_Response(400, None))
    with pytest.raises(ProviderUnavailableError):
        await national.async_post_json("https://x", {}, "X")


# Registration and BoM product filter


def test_registered_only_when_a_feed_is_enabled(hass: HomeAssistant) -> None:
    """The national provider is added when any national option is on, for AU and NZ."""
    session = AsyncMock()
    assert not any(
        isinstance(p, NationalHazardProvider) for p in get_providers_for_config(hass, session, {"state": "QLD"})
    )
    nz = get_providers_for_config(hass, session, {"state": "NZ", CONF_ENABLE_TSUNAMI: True})
    assert isinstance(nz[-1], NationalHazardProvider)
    assert nz[-1].provides_hazards is False


def test_bom_accepts_jatwc_products_nationally(hass: HomeAssistant) -> None:
    """National JATWC products and the state's own bulletin pass the BoM state filter."""
    bom = BoMHazardProvider(hass, AsyncMock(), {"state": "QLD"})
    assert bom._accepts_product("IDY68020")
    assert bom._accepts_product("IDY68027")
    assert not bom._accepts_product("IDY68025")  # the WA bulletin
    assert not bom._accepts_product("IDN21033")


# Provider hooks


async def test_hazards_are_never_contributed(hass: HomeAssistant) -> None:
    """The provider contributes no hazards and reports the configured state."""
    national = provider(hass, "nsw")
    assert await national.async_fetch_hazards() == []
    assert national.state_code == "NSW"


async def test_disabled_feeds_return_none(hass: HomeAssistant) -> None:
    """With every option off each hook is undetermined and no request is made."""
    national = provider(hass, **dict.fromkeys(NATIONAL_FEED_OPTIONS, False))
    assert await national.async_fetch_tsunami_status() is None
    assert await national.async_fetch_satellite_hotspots() is None
    assert await national.async_fetch_heatwave() is None
    assert await national.async_fetch_uv() is None
    assert await national.async_fetch_regional_alerts() is None
    assert await national.async_fetch_air_quality() == []


async def test_new_zealand_skips_australian_feeds(hass: HomeAssistant) -> None:
    """Hotspots, heatwave, UV and air quality are Australian only."""
    national = provider(hass, "NZ")
    assert await national.async_fetch_satellite_hotspots() is None
    assert await national.async_fetch_heatwave() is None
    assert await national.async_fetch_uv() is None
    assert await national.async_fetch_air_quality() == []


async def test_missing_location_returns_none(hass: HomeAssistant) -> None:
    """Without coordinates the location-based feeds are undetermined."""
    national = NationalHazardProvider(hass, AsyncMock(), {"state": "QLD", **ALL_ON, "latitude": None})
    assert await national.async_fetch_satellite_hotspots() is None
    assert await national.async_fetch_uv() is None
    assert await national.async_fetch_regional_alerts() is None
    assert await national.async_fetch_air_quality() == []


async def test_jatwc_tsunami(hass: HomeAssistant) -> None:
    """Australian entries read the JATWC products over FTP."""
    content = (FIXTURES / "IDY68027.cap.xml").read_bytes()
    with (
        patch(f"{NATIONAL}.async_fetch_bom_products", return_value={"IDY68027.cap.xml": content}) as fetch,
        patch(f"{NATIONAL}.dt_util.utcnow", return_value=datetime(2026, 10, 16, 2, tzinfo=UTC)),
    ):
        status = await provider(hass).async_fetch_tsunami_status()
    assert status is not None
    assert status.active is True
    assert fetch.call_args.args[1] == ("IDY68*",)


async def test_ptwc_tsunami_for_new_zealand(hass: HomeAssistant) -> None:
    """New Zealand entries read PTWC's Atom feed and its CAP documents."""
    national = provider(hass, "NZ")
    documents = {
        "https://www.tsunami.gov/events/xml/PHEBAtom.xml": (FIXTURES / "PHEBAtom.xml").read_text(),
        "https://www.tsunami.gov/events/PHEB/2026/10/13/26286001/1/WECA42/PHEBCAP.xml": (
            FIXTURES / "PHEBCAP.xml"
        ).read_text(),
    }
    with patch.object(national, "async_fetch_feed_text", side_effect=lambda url, label: documents[url]):
        status = await national.async_fetch_tsunami_status()
    assert status is not None
    assert status.active is False
    assert status.products == ["PHEB-1-26286001"]


async def test_hotspots_hook(hass: HomeAssistant) -> None:
    """The hotspot query is bounded and its result cached for 30 minutes."""
    national = provider(hass, latitude=-20.25, longitude=128.9)
    payload = json.loads((FIXTURES / "dea_hotspots.json").read_text())
    with patch.object(national, "async_fetch_feed_json", return_value=payload) as fetch:
        first = await national.async_fetch_satellite_hotspots()
        second = await national.async_fetch_satellite_hotspots()
    assert first is second
    assert first is not None and len(first.items) == 1
    assert fetch.await_count == 1
    assert "BBOX" in fetch.call_args.args[0]


async def test_heatwave_hook(hass: HomeAssistant) -> None:
    """The state's heatwave product is fetched by exact name; absent means none."""
    national = provider(hass, "NT")
    with patch(f"{NATIONAL}.async_fetch_bom_products", return_value={}) as fetch:
        status = await national.async_fetch_heatwave()
    assert status is not None and status.severity == "none"
    assert fetch.call_args.args[1] == ("IDD21013.cap.xml",)
    wanted = fetch.call_args.args[2]
    assert wanted("IDD21013.cap.xml") and not wanted("IDD21013.pdf")


async def test_uv_hook_with_forecast(hass: HomeAssistant) -> None:
    """UV comes from the nearest ARPANSA station with the BoM forecast for that station."""
    national = provider(hass)
    forecast = (FIXTURES / "IDZ00109.xml").read_bytes()
    with (
        patch.object(national, "async_fetch_feed_text", return_value=(FIXTURES / "uvvalues.xml").read_text()),
        patch(f"{NATIONAL}.async_fetch_bom_products", return_value={"IDZ00109.xml": forecast}) as fetch,
        patch(f"{NATIONAL}.dt_util.utcnow", return_value=datetime(2026, 10, 15, 23, tzinfo=UTC)),
    ):
        obs = await national.async_fetch_uv()
    assert obs is not None
    assert obs.station_name == "Brisbane"
    assert obs.forecast_max_index is not None
    assert fetch.call_args.args[2]("IDZ00109.xml")


async def test_uv_hook_forecast_failures_are_optional(hass: HomeAssistant) -> None:
    """A missing or broken forecast leaves the observation without forecast fields."""
    uv_text = (FIXTURES / "uvvalues.xml").read_text()
    for files in ({}, {"IDZ00109.xml": b"<product"}):
        national = provider(hass)
        with (
            patch.object(national, "async_fetch_feed_text", return_value=uv_text),
            patch(f"{NATIONAL}.async_fetch_bom_products", return_value=files),
        ):
            obs = await national.async_fetch_uv()
        assert obs is not None
        assert obs.forecast is None


async def test_uv_hook_without_known_station(hass: HomeAssistant) -> None:
    """A feed with no usable station reading is undetermined."""
    national = provider(hass)
    with patch.object(national, "async_fetch_feed_text", return_value="<stations/>"):
        assert await national.async_fetch_uv() is None


async def test_regional_alerts_hook(hass: HomeAssistant) -> None:
    """GDACS alerts are fetched with the shared session and the configured location."""
    national = provider(hass)
    alert = RegionalAlertItem(id="gdacs_1", title="T", alert_level="Orange", latitude=-20, longitude=150)
    with patch(f"{NATIONAL}.gdacs.async_fetch_regional_alerts", return_value=[alert]) as fetch:
        assert await national.async_fetch_regional_alerts() == [alert]
    fetch.assert_awaited_once_with(national.session, -27.47, 153.03)


async def test_air_quality_per_state(hass: HomeAssistant) -> None:
    """Each supported state reads its agency; other states have none."""
    qld = provider(hass, "QLD")
    with patch.object(qld, "async_fetch_feed_text", return_value=(FIXTURES / "qld_air_quality.xml").read_text()):
        assert len(await qld.async_fetch_air_quality()) == 21

    act = provider(hass, "ACT")
    records = json.loads((FIXTURES / "act_air_quality.json").read_text())
    with patch.object(act, "async_fetch_feed_json", return_value=records):
        assert len(await act.async_fetch_air_quality()) == 3

    assert await provider(hass, "VIC").async_fetch_air_quality() == []


async def test_nsw_air_quality(hass: HomeAssistant) -> None:
    """NSW reads the site list (cached) and posts for the nearest sites' observations."""
    national = provider(hass, "NSW", latitude=-33.87, longitude=151.21)
    sites = json.loads((FIXTURES / "nsw_sites.json").read_text())
    observations = json.loads((FIXTURES / "nsw_observations.json").read_text())
    with (
        patch.object(national, "async_fetch_feed_json", return_value=sites),
        patch.object(national, "async_post_json", return_value=observations) as post,
    ):
        stations = await national.async_fetch_air_quality()
    assert [s.station_id for s in stations] == ["nsw_1001", "nsw_39", "nsw_33"]
    assert post.call_args.args[1]["Sites"] == [1001, 39, 33]


async def test_nsw_air_quality_failures(hass: HomeAssistant) -> None:
    """An unavailable site list is an outage; a list without located sites is empty."""
    national = provider(hass, "NSW")
    with patch.object(national, "async_fetch_feed_json", side_effect=ProviderUnavailableError("down")):
        assert await national.async_fetch_air_quality() == []
    national = provider(hass, "NSW")
    with patch.object(national, "async_fetch_feed_json", return_value=[{"Site_Id": 1}]):
        assert await national.async_fetch_air_quality() == []


# GDACS


async def test_gdacs_feed_from_fixture() -> None:
    """Only current Orange/Red alerts inside the region are kept (library parses the recorded RSS)."""
    parsed = XmlParser().parse((FIXTURES / "gdacs_rss.xml").read_text())
    with patch.object(gdacs.GdacsFeed, "_fetch", AsyncMock(return_value=("OK", parsed))):
        alerts = await gdacs.async_fetch_regional_alerts(MagicMock(), -27.47, 153.03)
    assert [a.id for a in alerts] == ["gdacs_WF1032806"]
    alert = alerts[0]
    assert alert.alert_level == "Orange"
    assert alert.country == "Australia"
    assert alert.url == "https://www.gdacs.org/report.aspx?eventtype=WF&eventid=1032806"
    assert alert.distance_km is not None and alert.distance_km > 1000
    # The map card draws the episode geometry (#71)
    assert (alert.event_type_code, alert.event_id, alert.episode_id) == ("WF", 1032806, 2)
    assert alert.geometry_url == (
        "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=WF&eventid=1032806&episodeid=2"
    )


@pytest.mark.parametrize("status", ["ERROR", "OK_NO_DATA"])
async def test_gdacs_failures_are_outages(status: str) -> None:
    """Library error statuses (including an unparsable document) raise."""
    with (
        patch.object(gdacs.GdacsFeed, "update", AsyncMock(return_value=(status, None))),
        pytest.raises(ProviderUnavailableError),
    ):
        await gdacs.async_fetch_regional_alerts(MagicMock(), -27.0, 153.0)


async def test_gdacs_skips_malformed_entries() -> None:
    """An entry whose properties raise is skipped."""
    bad = MagicMock(is_current=True, alert_level="Red", coordinates=(-20.0, 150.0))
    type(bad).external_id = property(lambda self: (_ for _ in ()).throw(ValueError("bad")))
    with patch.object(gdacs.GdacsFeed, "update", AsyncMock(return_value=("OK", [bad]))):
        assert await gdacs.async_fetch_regional_alerts(MagicMock(), -27.0, 153.0) == []


def test_gdacs_entry_filters() -> None:
    """Not-current, Green, out-of-region and unlocated entries are dropped; the antimeridian is handled."""

    def entry(**kwargs: Any) -> MagicMock:
        defaults = {
            "is_current": True,
            "alert_level": "Red",
            "coordinates": (-30.0, -178.0),
            "event_type_short": None,
            "event_id": None,
            "external_id": "EQ1",
            "title": None,
            "event_name": None,
            "event_type": "Earthquake",
            "severity": "M7",
            "country": None,
            "from_date": None,
            "to_date": None,
            "distance_to_home": 1234.56,
            "_rss_entry": None,
        }
        return MagicMock(**{**defaults, **kwargs})

    def rss(episode: str | None) -> MagicMock:
        return MagicMock(get_additional_attribute=MagicMock(return_value=episode))

    kermadec = gdacs.regional_alert(entry())
    assert kermadec is not None
    assert (kermadec.title, kermadec.url, kermadec.distance_km) == ("GDACS alert", None, 1234.6)
    assert gdacs.regional_alert(entry(is_current=False)) is None
    assert gdacs.regional_alert(entry(alert_level="Green")) is None
    assert gdacs.regional_alert(entry(coordinates=None)) is None
    assert gdacs.regional_alert(entry(coordinates=(10.0, 150.0))) is None
    assert gdacs.regional_alert(entry(coordinates=(-30.0, -100.0))) is None
    assert not gdacs.in_region(-60.0, 150.0)
    # Episode geometry needs the event type, event ID and episode ID (#71)
    assert (kermadec.episode_id, kermadec.geometry_url) == (None, None)
    cyclone = gdacs.regional_alert(entry(event_type_short="TC", event_id=1001338, _rss_entry=rss("6")))
    assert cyclone is not None
    assert cyclone.geometry_url == (
        "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid=1001338&episodeid=6"
    )
    no_episode = gdacs.regional_alert(entry(event_type_short="TC", event_id=1, _rss_entry=rss("n/a")))
    assert no_episode is not None
    assert (no_episode.url is not None, no_episode.episode_id, no_episode.geometry_url) == (True, None, None)
    no_event = gdacs.regional_alert(entry(_rss_entry=rss("6")))
    assert no_event is not None
    assert (no_event.episode_id, no_event.geometry_url) == (6, None)


def test_options_constants_cover_every_hook() -> None:
    """Every national option is a known feed toggle."""
    assert set(NATIONAL_FEED_OPTIONS) == {
        CONF_ENABLE_TSUNAMI,
        CONF_ENABLE_SATELLITE_HOTSPOTS,
        CONF_ENABLE_HEATWAVE,
        CONF_ENABLE_UV,
        CONF_ENABLE_AIR_QUALITY,
        CONF_ENABLE_REGIONAL_ALERTS,
    }
