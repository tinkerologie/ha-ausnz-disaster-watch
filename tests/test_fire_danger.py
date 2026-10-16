"""Tests for the fire danger outlook, total fire bans and NZ fire season (#28).

Fixtures in ``fixtures/fire_danger`` are live payloads captured on 2026-10-16 (trimmed to a
few districts); ``wa_total_fire_bans.json`` is an archived Emergency WA response from
2025-04-03, the most recent one with bans in force.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import defusedxml.ElementTree as ET
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.binary_sensor import TotalFireBanBinarySensor
from custom_components.ausnz_disaster_watch.const import (
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    STATE_NZ,
)
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator, fire_danger_today
from custom_components.ausnz_disaster_watch.fire_districts import (
    FIRE_DISTRICTS,
    district_name,
    find_district,
    load_fire_districts,
)
from custom_components.ausnz_disaster_watch.models import FireDangerDay, FireDangerOutlook, FireDangerRating
from custom_components.ausnz_disaster_watch.providers import fire_bans, fire_danger
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.fire_danger import (
    FIRE_REFRESH_INTERVAL,
    FIRE_RETRY_INTERVAL,
    FireDangerService,
    district_time_zone,
    merge_outlooks,
    normalise_rating,
    parse_bom_fire_danger,
    parse_nz_fire_season,
)
from custom_components.ausnz_disaster_watch.sensor import FireDangerRatingSensor, FireSeasonSensor
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

FIXTURES = Path(__file__).parent / "fixtures" / "fire_danger"
SYDNEY = (-33.87, 151.21)
CANBERRA = (-35.2809, 149.13)
WODONGA = (-36.1218, 146.888)
ADELAIDE = (-34.93, 138.60)
GERALDTON = (-28.77, 114.61)
BRISBANE = (-27.47, 153.03)
CHRISTCHURCH = (-43.53, 172.63)
# 12:00 AEDT / 11:00 AEST on Friday 16 October 2026
NOON_16_OCT = "2026-10-16T01:00:00+00:00"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _json(name: str) -> Any:
    return json.loads(_text(name))


def _xml(name: str, text: str | None = None) -> Any:
    return ET.fromstring(text if text is not None else _text(name))


def _bom_product(aac: str, description: str, days: list[tuple[str, str, int]], offset: str = "+10:00") -> str:
    """Return a minimal BoM fire danger product (service WSF) for one district."""
    periods = "".join(
        f'<forecast-period index="{i}" start-time-local="{day}T00:00:00{offset}">'
        f'<element type="fire_behaviour_index">{fbi}</element><text type="fire_danger">{rating}</text>'
        "</forecast-period>"
        for i, (day, rating, fbi) in enumerate(days)
    )
    return (
        "<product><amoc><issue-time-utc>2026-10-15T18:30:00Z</issue-time-utc></amoc><forecast>"
        f'<area aac="{aac}" description="{description}" type="fire-district">{periods}</area>'
        "</forecast></product>"
    )


# --- Districts ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (-36.0737, 146.9135, "NSW_FW017"),  # Albury: Eastern Riverina
        (-36.1218, 146.888, "VIC_FW004"),  # Wodonga: North East (across the Murray)
        (-35.3533, 149.2343, "NSW_FW009"),  # Queanbeyan: Southern Ranges
        (-35.2809, 149.13, "NSW_FW008"),  # Canberra: the ACT
        (-28.1787, 153.5413, "NSW_FW001"),  # Tweed Heads
        (-28.1676, 153.5364, "QLD_FW015"),  # Coolangatta
        (-33.8915, 151.2767, "NSW_FW004"),  # Bondi (coast)
        (-42.8821, 147.3272, "TAS_FW006"),
        (-12.4634, 130.8456, "NT_FW001"),
        (-34.9285, 138.6007, "SA_FW001"),
        (-36.8485, 174.7633, None),  # Auckland
    ],
)
def test_national_fire_district_lookup(lat: float, lon: float, expected: str | None) -> None:
    """Border and coastal locations resolve to the district they are in (#28)."""
    assert find_district(load_fire_districts(FIRE_DISTRICTS), lat, lon) == expected


def test_district_name() -> None:
    """Bundled district names are returned, unknown AACs echo back."""
    assert district_name(FIRE_DISTRICTS, "NSW_FW008") == "Australian Capital Territory"
    assert district_name(FIRE_DISTRICTS, "XX_FW999") == "XX_FW999"


# --- BoM fire danger forecast -------------------------------------------------------------


def test_parse_bom_fire_danger_nsw() -> None:
    """The BoM product gives four dated days with rating and FBI for the district."""
    outlook = parse_bom_fire_danger(_text("bom_IDN10016.xml"), "NSW_FW008", "fallback")
    assert outlook is not None
    assert outlook.district_name == "The Australian Capital Territory"
    assert outlook.time_zone == "Australia/Sydney"
    assert outlook.issued_at == datetime.fromisoformat("2026-10-15T18:05:00+00:00")
    assert outlook.source == "Bureau of Meteorology"
    assert [(d.date.isoformat(), d.rating, d.fire_behaviour_index) for d in outlook.days] == [
        ("2026-10-16", "Moderate", 13),
        ("2026-10-17", "Moderate", 14),
        ("2026-10-18", "Moderate", 14),
        ("2026-10-19", "Moderate", 14),
    ]
    sydney = parse_bom_fire_danger(_text("bom_IDN10016.xml"), "NSW_FW004", "x")
    assert sydney is not None
    assert sydney.days[0].rating == "No Rating"
    assert parse_bom_fire_danger(_text("bom_IDN10016.xml"), "NSW_FW021", "x") is None


def test_parse_bom_fire_danger_skips_bad_periods_and_rejects_bad_documents() -> None:
    """A malformed period is skipped; a non-product document is a feed failure."""
    text = _bom_product("VIC_FW007", "Central", [("2026-10-16", "HIGH", 30), ("not-a-date", "High", 1)])
    text = text.replace(">30<", "> <")
    outlook = parse_bom_fire_danger(text, "VIC_FW007", "Central")
    assert outlook is not None
    assert [(d.rating, d.fire_behaviour_index) for d in outlook.days] == [("High", None)]
    assert outlook.time_zone == "Australia/Melbourne"
    with pytest.raises(ProviderUnavailableError):
        parse_bom_fire_danger("<html>not xml", "VIC_FW007", "Central")
    with pytest.raises(ProviderUnavailableError):
        parse_bom_fire_danger("<html/>", "VIC_FW007", "Central")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("  ", None),
        ("EXTREME", "Extreme"),
        ("No Rating", "No Rating"),
        ("NONE", "No Rating"),
        ("catastrophic", "Catastrophic"),
        ("very odd", "Very Odd"),
    ],
)
def test_normalise_rating(raw: str | None, expected: str | None) -> None:
    """Feed ratings map to AFDRS display names."""
    assert normalise_rating(raw) == expected


def test_district_time_zone() -> None:
    """Days are dated in the district's state time zone."""
    assert district_time_zone("WA_FW091") == "Australia/Perth"
    assert district_time_zone("NSW_FW008") == "Australia/Sydney"
    assert district_time_zone("XX_FW001") == "Australia/Sydney"


def _outlook(aac: str, days: list[tuple[date, str]], tz: str = "Australia/Brisbane") -> FireDangerOutlook:
    return FireDangerOutlook(
        district_number=aac,
        district_name=aac,
        time_zone=tz,
        source="test",
        days=[FireDangerDay(date=day, rating=rating) for day, rating in days],
    )


def test_evening_issue_keeps_today(freezer: FrozenDateTimeFactory) -> None:
    """QLD's 4 pm issue starts tomorrow: today's rating comes from the morning issue (#28)."""
    freezer.move_to("2026-10-15T08:00:00+00:00")  # 18:00 AEST, 15 Oct
    evening = parse_bom_fire_danger(_text("bom_IDQ13016_evening.xml"), "QLD_FW015", "x")
    assert evening is not None
    assert evening.days[0].date == date(2026, 10, 16)
    assert evening.day(date(2026, 10, 15)) is None

    morning = _outlook("QLD_FW015", [(date(2026, 10, 14), "High"), (date(2026, 10, 15), "Extreme")])
    merged = merge_outlooks(morning, evening)
    assert merged is not None
    assert [d.date.isoformat() for d in merged.days][:2] == ["2026-10-15", "2026-10-16"]
    today = merged.day(date(2026, 10, 15))
    assert today is not None
    assert today.rating == "Extreme"

    # Nothing to carry over: another district, no previous issue, or no new issue
    assert merge_outlooks(_outlook("QLD_FW001", [(date(2026, 10, 15), "High")]), evening) is evening
    assert merge_outlooks(None, evening) is evening
    assert merge_outlooks(morning, None) is None
    stale = _outlook("QLD_FW015", [(date(2026, 10, 14), "High")])
    assert merge_outlooks(stale, evening) is evening


# --- Total fire bans ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Yes", True),
        ("true", True),
        ("1", True),
        ("YES - TOTAL FIRE BAN", True),
        ("No", False),
        ("false", False),
        ("0", False),
        ("NO - RESTRICTIONS MAY APPLY", False),
        (None, None),
        ("", None),
        ("maybe", None),
    ],
)
def test_parse_ban_flag(raw: Any, expected: bool | None) -> None:
    """Ban flags are tri-state: unknown is never read as no ban."""
    assert fire_bans.parse_ban_flag(raw) is expected


def test_nsw_rfs_v2_bans() -> None:
    """``areaId`` matches the BoM district number; days start at the NSW local date."""
    payload = _json("nsw_rfs_fire_danger_v2.json")
    today = date(2026, 10, 16)
    bans = fire_bans.parse_nsw_rfs_v2(payload, "NSW_FW004", today)
    assert bans == {today + timedelta(days=i): False for i in range(4)}

    payload["fireWeatherAreaRatings"][3]["tobanTomorrow"] = "Yes"
    payload["fireWeatherAreaRatings"][3]["tobanDay4"] = None
    payload["fireWeatherAreaRatings"].insert(0, "junk")
    bans = fire_bans.parse_nsw_rfs_v2(payload, "NSW_FW004", today)
    assert bans[date(2026, 10, 17)] is True
    assert bans[date(2026, 10, 19)] is None
    assert fire_bans.parse_nsw_rfs_v2(payload, "NSW_FW099", today) == {}

    # Polled after midnight, before RFS rolled the feed over: days follow lastUpdatedIso
    stale = {**payload, "lastUpdatedIso": "2026-10-15T17:05:00+11:00"}
    bans = fire_bans.parse_nsw_rfs_v2(stale, "NSW_FW004", today)
    assert min(bans) == date(2026, 10, 15)
    assert bans[date(2026, 10, 16)] is True  # the feed's "tomorrow"
    # Missing, unreadable or naive timestamps fall back to the poll date
    for value in (None, "soon", "2026-10-15T17:05:00"):
        assert min(fire_bans.parse_nsw_rfs_v2({**payload, "lastUpdatedIso": value}, "NSW_FW004", today)) == today
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_nsw_rfs_v2({"fireWeatherAreaRatings": None}, "NSW_FW004", today)
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_nsw_rfs_v2(["not", "a", "dict"], "NSW_FW004", today)


def test_fdr_toban_xml_nsw_and_act() -> None:
    """``fdrToban.xml`` (NSW) and the ACT ESA feed share a shape; the ACT is region 8."""
    tz = dt_util.get_time_zone("Australia/Sydney")
    fallback = date(2026, 10, 16)
    nsw = fire_bans.parse_fdr_toban_xml(_xml("nsw_rfs_fdr_toban.xml"), "NSW_FW004", fallback, tz)
    assert nsw == {date(2026, 10, 16): False, date(2026, 10, 17): False}
    assert fire_bans.parse_fdr_toban_xml(_xml("nsw_rfs_fdr_toban.xml"), "NSW_FW099", fallback, tz) == {}

    # The ACT feed dates "today" by its pubDate, not the poll time
    act = fire_bans.parse_fdr_toban_xml(_xml("act_esa_fire_danger.xml"), "NSW_FW008", date(2026, 10, 15), tz)
    assert act == {date(2026, 10, 16): False, date(2026, 10, 17): False}

    banned = _text("act_esa_fire_danger.xml").replace("<FireBanTomorrow>No", "<FireBanTomorrow>Yes")
    for pub, expected_today in (
        ("Fri, 16 Oct 2026 9:24:05 +1100", date(2026, 10, 16)),
        ("not a date", fallback),
        ("Fri, 16 Oct 2026 9:24:05 -0000", date(2026, 10, 16)),
    ):
        text = banned.replace("Fri, 16 Oct 2026 9:24:05 +1100", pub)
        act = fire_bans.parse_fdr_toban_xml(_xml("", text), "NSW_FW008", fallback, tz)
        assert act[expected_today + timedelta(days=1)] is True
    no_dates = banned.replace("<pubDate>Fri, 16 Oct 2026 9:24:05 +1100</pubDate>", "").replace(
        "<lastBuildDate>Fri, 16 Oct 2026 9:24:05 +1100</lastBuildDate>", ""
    )
    assert fire_bans.parse_fdr_toban_xml(_xml("", no_dates), "NSW_FW008", date(2026, 10, 20), tz) == {
        date(2026, 10, 20): False,
        date(2026, 10, 21): True,
    }
    naive = banned.replace("Fri, 16 Oct 2026 9:24:05 +1100", "Fri, 16 Oct 2026 9:24:05")
    assert date(2026, 10, 21) in fire_bans.parse_fdr_toban_xml(_xml("", naive), "NSW_FW008", date(2026, 10, 20), tz)
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_fdr_toban_xml(_xml("", "<rss><channel/></rss>"), "NSW_FW008", fallback, tz)


def test_vic_cfa_bans() -> None:
    """CFA items are dated by title and list each district's ban before the ratings."""
    bans = fire_bans.parse_vic_cfa_rss(_xml("cfa_tfb_fdr_forecast.xml"), "North East")
    assert sorted(bans) == [date(2026, 10, d) for d in range(16, 21)]
    assert set(bans.values()) == {False}

    text = _text("cfa_tfb_fdr_forecast.xml").replace(
        "Central: NO - RESTRICTIONS MAY APPLY", "Central: YES - TOTAL FIRE BAN IN FORCE", 1
    )
    text = text.replace("<title>Tuesday, 20 October 2026</title>", "<title>Someday</title>")
    bans = fire_bans.parse_vic_cfa_rss(_xml("", text), "Central")
    assert bans[date(2026, 10, 16)] is True
    assert bans[date(2026, 10, 17)] is False
    assert date(2026, 10, 20) not in bans
    # The ratings paragraph ("Central: MODERATE") is never read as a ban
    assert fire_bans.parse_vic_cfa_rss(_xml("", text), "Nowhere") == {}
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_vic_cfa_rss(_xml("", "<feed/>"), "Central")


def test_sa_cfs_bans() -> None:
    """SA CFS districts match by name; any banned period bans that day."""
    bans = fire_bans.parse_sa_cfs_xml(_xml("sa_cfs_fire_danger.xml"), "Mount Lofty Ranges")
    assert bans == {date(2026, 10, d): False for d in range(15, 19)}

    text = _text("sa_cfs_fire_danger.xml")
    start = text.index('description="Adelaide Metropolitan"')
    head, tail = text[:start], text[start:]
    tail = tail.replace('<text type="fire_ban">false</text>', '<text type="fire_ban">true</text>', 2)
    tail = tail.replace('start-time-local="2026-10-18T00:00:00+10:30"', 'start-time-local="bad"', 1)
    tail = tail.replace('<text type="fire_ban">false</text>', '<text type="fire_ban"></text>', 1)
    bans = fire_bans.parse_sa_cfs_xml(_xml("", head + tail), "Adelaide Metropolitan")
    assert bans == {date(2026, 10, 15): True, date(2026, 10, 16): None, date(2026, 10, 17): False}
    assert fire_bans.parse_sa_cfs_xml(_xml("sa_cfs_fire_danger.xml"), "Nowhere") == {}
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_sa_cfs_xml(_xml("", "<product/>"), "Adelaide Metropolitan")


def test_wa_total_fire_bans() -> None:
    """Emergency WA bans are per LGA; a forecast day without a ban is a day without one."""
    payload = _json("wa_total_fire_bans.json")
    payload["totalFireBans"] += [
        "junk",
        {"fire-ban-lga": "MINGENEW, SHIRE OF", "ban-level": "No ban", "date-of-ban": "2025-04-04"},
        {"fire-ban-lga": "MINGENEW, SHIRE OF", "ban-level": "Ban", "date-of-ban": "soon"},
        {"fire-ban-lga": "MINGENEW, SHIRE OF", "ban-level": "Ban", "date-of-ban": "2025-04-09"},
    ]
    days = [date(2025, 4, 3), date(2025, 4, 4)]
    assert fire_bans.parse_wa_total_fire_bans(payload, "Mingenew", days) == {
        date(2025, 4, 3): True,
        date(2025, 4, 4): False,
    }
    assert fire_bans.parse_wa_total_fire_bans(payload, "Greater Geraldton", days)[date(2025, 4, 3)] is True
    assert fire_bans.parse_wa_total_fire_bans(payload, "Perth (C)", days) == dict.fromkeys(days, False)
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_wa_total_fire_bans({}, "Mingenew", days)


def test_lga_key() -> None:
    """Emergency WA and ABS spellings of an LGA match."""
    assert fire_bans.lga_key("KALGOORLIE-BOULDER, CITY OF") == fire_bans.lga_key("Kalgoorlie-Boulder")
    assert fire_bans.lga_key("Perth (C)") == "perth"
    assert fire_bans.district_number("NSW_FW008") == 8
    assert fire_bans.district_number("ACT") is None


# --- New Zealand --------------------------------------------------------------------------


def test_parse_nz_fire_season() -> None:
    """Season zone and Section 52 prohibitions at the location."""
    status = parse_nz_fire_season(_json("nz_fire_season.json"), {"features": []})
    assert status.season == "open"
    assert status.zone == "Canterbury/Christchurch Metropolitan"
    assert status.district == "Canterbury"
    assert status.last_updated is not None
    assert status.section_52 is False
    assert status.prohibited_activities == []

    status = parse_nz_fire_season(_json("nz_fire_season.json"), _json("nz_section_52.json"))
    assert status.section_52 is True
    assert status.section_52_comment is not None
    assert status.prohibited_activities == ["fireworks"]

    season = _json("nz_fire_season.json")
    season["features"][0]["attributes"].update(SEASON="Unknown", LAST_UPDATED=None)
    status = parse_nz_fire_season(season, None)
    assert status.season is None
    assert status.last_updated is None
    assert status.section_52 is None
    assert parse_nz_fire_season({"features": []}, None).zone is None
    with pytest.raises(ProviderUnavailableError):
        parse_nz_fire_season({"error": {"code": 400}}, None)


# --- Service ------------------------------------------------------------------------------


def _feeds(responses: dict[str, Any]) -> AsyncMock:
    """Return a fetch mock answering by URL prefix; an exception value is raised."""

    async def fetch(url: str, label: str, headers: dict[str, str] | None = None) -> Any:
        for prefix, value in responses.items():
            if url.startswith(prefix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise ProviderUnavailableError(f"{label} unexpected URL {url}")

    return AsyncMock(side_effect=fetch)


def _service(hass: HomeAssistant, state: str, location: tuple[float, float] | None, **responses: Any) -> Any:
    config: dict[str, Any] = {"state": state}
    if location:
        config.update(latitude=location[0], longitude=location[1])
    service = FireDangerService(hass, AsyncMock(), config)
    mapping = {value[0]: value[1] for value in responses.values()}
    service.async_fetch_feed_text = _feeds(mapping)
    service.async_fetch_feed_json = _feeds(mapping)
    return service


BOM_NSW = ("https://www.bom.gov.au/fwo/IDN10016.xml", _text("bom_IDN10016.xml"))


@pytest.mark.real_fire_service
async def test_service_nsw_outlook_with_rfs_bans(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Sydney: BoM ratings plus the RFS 4-day bans, refreshed every 30 minutes."""
    freezer.move_to(NOON_16_OCT)
    rfs = _json("nsw_rfs_fire_danger_v2.json")
    rfs["fireWeatherAreaRatings"][3]["tobanToday"] = "Yes"
    service = _service(hass, "NSW", SYDNEY, bom=BOM_NSW, rfs=(fire_bans.NSW_RFS_FDR_URL, rfs))
    assert service.state_code == "NSW"
    assert await service.async_fetch_hazards() == []

    await service.async_update()
    outlook = service.outlook
    assert outlook is not None
    assert outlook.district_number == "NSW_FW004"
    assert outlook.total_fire_ban_source == "NSW Rural Fire Service"
    assert [d.total_fire_ban for d in outlook.days] == [True, False, False, False]
    assert service.async_fetch_feed_text.await_count == 1

    # Within the refresh interval nothing is fetched
    freezer.tick(FIRE_REFRESH_INTERVAL - timedelta(minutes=1))
    await service.async_update()
    assert service.async_fetch_feed_text.await_count == 1
    freezer.tick(timedelta(minutes=2))
    await service.async_update()
    assert service.async_fetch_feed_text.await_count == 2


@pytest.mark.real_fire_service
async def test_service_failure_keeps_last_good(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A failed poll keeps the last outlook and retries sooner."""
    freezer.move_to(NOON_16_OCT)
    service = _service(hass, "NSW", SYDNEY, bom=BOM_NSW, rfs=(fire_bans.NSW_RFS_FDR_URL, ProviderUnavailableError()))
    service.async_fetch_feed_text = _feeds(
        {BOM_NSW[0]: BOM_NSW[1], fire_bans.NSW_RFS_TOBAN_URL: _text("nsw_rfs_fdr_toban.xml")}
    )
    await service.async_update()
    good = service.outlook
    assert good is not None
    # The 4-day feed failed, so bans come from fdrToban.xml (today and tomorrow only)
    assert [d.total_fire_ban for d in good.days] == [False, False, None, None]

    service.async_fetch_feed_text = AsyncMock(side_effect=RuntimeError("boom"))
    freezer.tick(FIRE_REFRESH_INTERVAL)
    await service.async_update()
    assert service.outlook is good
    calls = service.async_fetch_feed_text.await_count
    freezer.tick(FIRE_RETRY_INTERVAL - timedelta(seconds=1))
    await service.async_update()
    assert service.async_fetch_feed_text.await_count == calls
    freezer.tick(timedelta(seconds=2))
    await service.async_update()
    assert service.async_fetch_feed_text.await_count == calls + 1


@pytest.mark.real_fire_service
async def test_service_act_vic_sa_bans(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Each district reads bans from the agency that declares them."""
    freezer.move_to(NOON_16_OCT)
    act = _service(
        hass, "ACT", CANBERRA, bom=BOM_NSW, act=(fire_bans.ACT_ESA_FDR_URL, _text("act_esa_fire_danger.xml"))
    )
    await act.async_update()
    assert act.outlook is not None
    assert act.outlook.total_fire_ban_source == "ACT Emergency Services Agency"
    assert [d.total_fire_ban for d in act.outlook.days] == [False, False, None, None]

    days = [("2026-10-16", "High", 30), ("2026-10-17", "Extreme", 60)]
    vic = _service(
        hass,
        "VIC",
        WODONGA,
        bom=("https://www.bom.gov.au/fwo/IDV18555.xml", _bom_product("VIC_FW004", "North East", days, "+11:00")),
        cfa=(fire_bans.VIC_CFA_TFB_URL, _text("cfa_tfb_fdr_forecast.xml")),
    )
    await vic.async_update()
    assert vic.outlook is not None
    assert vic.outlook.total_fire_ban_source == "Country Fire Authority"
    assert [(d.rating, d.total_fire_ban) for d in vic.outlook.days] == [("High", False), ("Extreme", False)]

    sa = _service(
        hass,
        "SA",
        ADELAIDE,
        bom=("https://www.bom.gov.au/fwo/IDS10070.xml", _bom_product("SA_FW001", "Adelaide Metropolitan", days)),
        cfs=(fire_bans.SA_CFS_FDR_URL, _text("sa_cfs_fire_danger.xml")),
    )
    await sa.async_update()
    assert sa.outlook is not None
    assert [d.total_fire_ban for d in sa.outlook.days] == [False, False]

    # A ban feed that is not XML leaves bans unknown, ratings intact
    broken = _service(
        hass,
        "SA",
        ADELAIDE,
        bom=("https://www.bom.gov.au/fwo/IDS10070.xml", _bom_product("SA_FW001", "Adelaide Metropolitan", days)),
        cfs=(fire_bans.SA_CFS_FDR_URL, "<html"),
    )
    await broken.async_update()
    assert broken.outlook is not None
    assert broken.outlook.total_fire_ban_source is None
    assert [(d.rating, d.total_fire_ban) for d in broken.outlook.days] == [("High", None), ("Extreme", None)]


@pytest.mark.real_fire_service
async def test_service_wa_bans_by_lga(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """WA bans are matched to the location's LGA, looked up once per location."""
    freezer.move_to("2025-04-02T12:00:00+00:00")
    days = [("2025-04-02", "High", 30), ("2025-04-03", "Extreme", 60)]
    abs_lga = {"features": [{"attributes": {"lga_name_2021": "Greater Geraldton"}}]}
    wa = _service(
        hass,
        "WA",
        GERALDTON,
        bom=("https://www.bom.gov.au/fwo/IDW15100.xml", _bom_product("WA_FW053", "Mid West", days, "+08:00")),
        abs=("https://geo.abs.gov.au/", abs_lga),
        tfb=(fire_bans.WA_TFB_URL, _json("wa_total_fire_bans.json")),
    )
    await wa.async_update()
    assert wa.outlook is not None
    assert wa.outlook.total_fire_ban_source == "Department of Fire and Emergency Services WA"
    assert [d.total_fire_ban for d in wa.outlook.days] == [False, True]
    freezer.tick(FIRE_REFRESH_INTERVAL)
    await wa.async_update()
    abs_calls = [c for c in wa.async_fetch_feed_json.await_args_list if c.args[0].startswith("https://geo.abs")]
    assert len(abs_calls) == 1

    # No LGA at the location: bans unknown
    nolga = _service(
        hass,
        "WA",
        GERALDTON,
        bom=("https://www.bom.gov.au/fwo/IDW15100.xml", _bom_product("WA_FW053", "Mid West", days, "+08:00")),
        abs=("https://geo.abs.gov.au/", {"features": []}),
    )
    await nolga.async_update()
    assert nolga.outlook is not None
    assert [d.total_fire_ban for d in nolga.outlook.days] == [None, None]


@pytest.mark.real_fire_service
async def test_service_without_ban_source_or_district(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """QLD has no ban feed; no location, no district or no product means no outlook."""
    freezer.move_to(NOON_16_OCT)
    qld = _service(
        hass, "QLD", BRISBANE, bom=("https://www.bom.gov.au/fwo/IDQ13016.xml", _text("bom_IDQ13016_evening.xml"))
    )
    await qld.async_update()
    assert qld.outlook is not None
    assert qld.outlook.total_fire_ban_source is None
    assert {d.total_fire_ban for d in qld.outlook.days} == {None}

    no_location = _service(hass, "QLD", None)
    await no_location.async_update()
    assert no_location.outlook is None

    offshore = _service(hass, "NSW", (-36.85, 174.76))  # Auckland: no AU district
    await offshore.async_update()
    assert offshore.outlook is None

    missing = _service(hass, "NSW", (-31.95, 141.45), bom=BOM_NSW)  # Broken Hill: not in the trimmed product
    await missing.async_update()
    assert missing.outlook is None

    with patch.dict(fire_danger.BOM_FIRE_DANGER_PRODUCTS, clear=True):
        unknown = _service(hass, "NSW", SYDNEY)
        await unknown.async_update()
    assert unknown.outlook is None


@pytest.mark.real_fire_service
async def test_service_nz_fire_season(hass: HomeAssistant) -> None:
    """NZ entries read the fire season zone and Section 52 at the location."""
    nz = _service(
        hass,
        "NZ",
        CHRISTCHURCH,
        season=("https://utility.arcgis.com/", _json("nz_fire_season.json")),
        s52=("https://services1.arcgis.com/", _json("nz_section_52.json")),
    )
    await nz.async_update()
    assert nz.outlook is None
    assert nz.season is not None
    assert nz.season.season == "open"
    assert nz.season.section_52 is True

    no_s52 = _service(hass, "NZ", CHRISTCHURCH, season=("https://utility.arcgis.com/", _json("nz_fire_season.json")))
    await no_s52.async_update()
    assert no_s52.season is not None
    assert no_s52.season.section_52 is None

    nowhere = _service(hass, "NZ", None)
    await nowhere.async_update()
    assert nowhere.season is None


# --- Coordinator and entities -------------------------------------------------------------

BRISBANE_OUTLOOK = FireDangerOutlook(
    district_number="QLD_FW015",
    district_name="Southeast Coast",
    time_zone="Australia/Brisbane",
    issued_at=datetime.fromisoformat("2026-10-15T18:30:00+00:00"),
    source="Bureau of Meteorology",
    total_fire_ban_source="Test agency",
    days=[
        FireDangerDay(date=date(2026, 10, 15), rating="Moderate", fire_behaviour_index=12, total_fire_ban=False),
        FireDangerDay(date=date(2026, 10, 16), rating="Extreme", fire_behaviour_index=55, total_fire_ban=True),
        FireDangerDay(date=date(2026, 10, 17), rating="High", fire_behaviour_index=30, total_fire_ban=None),
    ],
)


def test_fire_danger_today(freezer: FrozenDateTimeFactory) -> None:
    """Today is the district's local date, so a late-evening poll still reads today (#28)."""
    freezer.move_to("2026-10-15T13:30:00+00:00")  # 23:30 AEST, 15 Oct
    rating = fire_danger_today(BRISBANE_OUTLOOK)
    assert rating is not None
    assert (rating.rating, rating.total_fire_ban, rating.day) == ("Moderate", False, "Today")
    freezer.move_to("2026-10-15T14:30:00+00:00")  # 00:30 AEST, 16 Oct
    rating = fire_danger_today(BRISBANE_OUTLOOK)
    assert rating is not None
    assert rating.rating == "Extreme"
    freezer.move_to("2026-10-20T00:00:00+00:00")  # beyond the forecast
    assert fire_danger_today(BRISBANE_OUTLOOK) is None
    assert fire_danger_today(None) is None
    no_rating = BRISBANE_OUTLOOK.model_copy(deep=True)
    no_rating.days[0].rating = None
    freezer.move_to("2026-10-15T00:00:00+00:00")
    assert fire_danger_today(no_rating) is None


async def test_coordinator_prefers_outlook_over_provider_fire_danger(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The outlook supplies today's rating; providers are only a fallback."""
    freezer.move_to(NOON_16_OCT)
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    provider.async_fetch_fire_danger.return_value = FireDangerRating(rating="Catastrophic")
    coordinator.providers = [provider]

    coordinator.fire_service.outlook = BRISBANE_OUTLOOK
    await coordinator.async_refresh()
    assert coordinator.fire_danger is not None
    assert coordinator.fire_danger.rating == "Extreme"
    assert coordinator.fire_outlook is BRISBANE_OUTLOOK
    assert coordinator.fire_season is None
    provider.async_fetch_fire_danger.assert_not_awaited()

    coordinator.fire_service.outlook = None
    await coordinator.async_refresh()
    assert coordinator.fire_danger is not None
    assert coordinator.fire_danger.rating == "Catastrophic"

    coordinator.data = None
    assert coordinator.fire_outlook is None
    assert coordinator.fire_season is None


def _entity_id(platform: str, key: str, state: str = "qld", location: str = "city_of_moreton_bay") -> str:
    return f"{platform}.australia_and_new_zealand_disaster_watch_{state}_{location}_{key}"


@pytest.mark.real_fire_service
async def test_au_entities_show_outlook_and_ban(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_icon: Callable[[str], str | None],
) -> None:
    """AU entries get a total fire ban sensor; the rating sensor carries the outlook."""
    freezer.move_to(NOON_16_OCT)
    mock_config_entry.add_to_hass(hass)
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []

    async def fake_update(self: FireDangerService) -> None:
        self.outlook = BRISBANE_OUTLOOK

    with (
        patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]),
        patch.object(FireDangerService, "async_update", fake_update),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    ban = hass.states.get(_entity_id("binary_sensor", "total_fire_ban"))
    assert ban is not None
    assert ban.state == STATE_ON
    assert "icon" not in ban.attributes
    assert entity_icon(ban.entity_id) == "mdi:fire-alert"
    assert ban.attributes["date"] == "2026-10-16"
    assert ban.attributes["tomorrow"] is None
    assert ban.attributes["district_number"] == "QLD_FW015"
    assert ban.attributes["forecast"] == [
        {"date": "2026-10-16", "total_fire_ban": True},
        {"date": "2026-10-17", "total_fire_ban": None},
    ]
    assert ban.attributes["source"] == "Test agency"

    rating = hass.states.get(_entity_id("sensor", "fire_danger_rating"))
    assert rating is not None
    assert rating.state == "Extreme"
    assert rating.attributes["day"] == "Today"
    assert rating.attributes["date"] == "2026-10-16"
    assert rating.attributes["fire_behaviour_index"] == 55
    assert rating.attributes["total_fire_ban"] is True
    assert [d["date"] for d in rating.attributes["forecast"]] == ["2026-10-16", "2026-10-17"]
    assert rating.attributes["issued_at"] == "2026-10-15T18:30:00+00:00"
    assert rating.attributes["source"] == "Bureau of Meteorology"
    assert hass.states.get(_entity_id("sensor", "fire_season")) is None


async def test_ban_sensor_unknown_without_outlook(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """No outlook (or no day for today) is unknown, never "no ban"."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.providers = []
    await coordinator.async_refresh()
    sensor = TotalFireBanBinarySensor(coordinator)
    assert sensor.is_on is None
    assert sensor.icon is None  # from icons.json (#21)
    assert sensor.extra_state_attributes == {}

    coordinator.data.fire_outlook = BRISBANE_OUTLOOK.model_copy(update={"days": []})
    assert sensor.is_on is None
    assert sensor.extra_state_attributes["tomorrow"] is None

    # A provider-only rating (no outlook) keeps the legacy attributes
    coordinator.data.fire_outlook = None
    coordinator.data.fire_danger = FireDangerRating(district_name="Moreton", rating="High", day="Today")
    attrs = FireDangerRatingSensor(coordinator).extra_state_attributes
    assert set(attrs) == {"district_name", "district_number", "total_fire_ban", "day"}


@pytest.mark.real_fire_service
async def test_nz_entities_show_fire_season(hass: HomeAssistant, entity_icon: Callable[[str], str | None]) -> None:
    """NZ entries get a fire season sensor and no total fire ban sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NZ",
        data={
            CONF_STATE: STATE_NZ,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_LOCATION_NAME: "Christchurch",
            CONF_LATITUDE: CHRISTCHURCH[0],
            CONF_LONGITUDE: CHRISTCHURCH[1],
            CONF_RADIUS: 50,
        },
        unique_id="nz_christchurch",
    )
    entry.add_to_hass(hass)
    provider = AsyncMock()
    provider.async_fetch_hazards.return_value = []
    season = parse_nz_fire_season(_json("nz_fire_season.json"), _json("nz_section_52.json"))

    async def fake_update(self: FireDangerService) -> None:
        self.season = season

    with (
        patch("custom_components.ausnz_disaster_watch.coordinator.get_providers_for_config", return_value=[provider]),
        patch.object(FireDangerService, "async_update", fake_update),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_entity_id("sensor", "fire_season", "nz", "christchurch"))
    assert state is not None
    assert state.state == "open"
    assert "icon" not in state.attributes
    assert entity_icon(state.entity_id) == "mdi:fire"
    assert state.attributes["zone"] == "Canterbury/Christchurch Metropolitan"
    assert state.attributes["section_52"] is True
    assert state.attributes["prohibited_activities"] == ["fireworks"]
    assert state.attributes["last_updated"] is not None
    assert hass.states.get(_entity_id("binary_sensor", "total_fire_ban", "nz", "christchurch")) is None

    coordinator = entry.runtime_data
    sensor = FireSeasonSensor(coordinator)
    coordinator.data.fire_season = season.model_copy(update={"season": "prohibited", "last_updated": None})
    assert sensor.icon is None  # from icons.json (#21)
    assert sensor.extra_state_attributes["last_updated"] is None
    coordinator.data.fire_season = None
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


@pytest.mark.real_fire_service
async def test_service_refreshes_when_the_location_moves(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Following the home zone to a new point refetches now, not after 30 minutes (#19, #28)."""
    freezer.move_to(NOON_16_OCT)
    service = _service(hass, "NSW", SYDNEY, bom=BOM_NSW, rfs=(fire_bans.NSW_RFS_FDR_URL, ProviderUnavailableError()))
    await service.async_update()
    assert service.outlook is not None
    assert service.outlook.district_number == "NSW_FW004"
    service.set_location(*SYDNEY)  # unchanged: no early refresh
    await service.async_update()
    assert service.async_fetch_feed_text.await_count == 2  # BoM + fdrToban fallback
    service.set_location(*CANBERRA)
    await service.async_update()
    assert service.outlook is not None
    assert service.outlook.district_number == "NSW_FW008"


@pytest.mark.real_fire_service
async def test_service_sources_follow_the_district(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """The service credits the configured state until the district is known, then the district's agency (#34)."""
    freezer.move_to(NOON_16_OCT)
    act = _service(
        hass, "NSW", CANBERRA, bom=BOM_NSW, act=(fire_bans.ACT_ESA_FDR_URL, _text("act_esa_fire_danger.xml"))
    )
    assert [s.key for s in act.data_sources] == ["bom_fire_danger", "nsw_rfs"]
    await act.async_update()
    assert [s.key for s in act.data_sources] == ["bom_fire_danger", "act_esa"]
    nowhere = _service(hass, "NSW", (-36.85, 174.76))
    await nowhere.async_update()
    assert [s.key for s in nowhere.data_sources] == ["bom_fire_danger", "nsw_rfs"]
    nz = _service(hass, "NZ", CHRISTCHURCH)
    assert [s.key for s in nz.data_sources] == ["fenz_fire_season"]
