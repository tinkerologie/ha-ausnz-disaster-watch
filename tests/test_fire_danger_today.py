"""Today's fire danger rating after BoM's afternoon issue and across restarts (#89).

BoM's afternoon fire danger issue starts tomorrow. Today's rating then comes from the
earlier issue (kept in a Store, so a restart keeps it) or, failing that, from the state
agency that publishes it. Fixtures are the live captures in ``fixtures/fire_danger``.
"""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import defusedxml.ElementTree as ET
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator, fire_danger_today
from custom_components.ausnz_disaster_watch.models import FireDangerDay, FireDangerOutlook
from custom_components.ausnz_disaster_watch.providers import fire_bans
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.fire_danger import (
    FIRE_STORAGE_KEY,
    FireDangerService,
    fill_from_agency,
    outlook_from_dict,
    outlook_to_dict,
)
from custom_components.ausnz_disaster_watch.sensor import FireDangerRatingSensor
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

FIXTURES = Path(__file__).parent / "fixtures" / "fire_danger"
SYDNEY = (-33.87, 151.21)
GERALDTON = (-28.77, 114.61)


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _json(name: str) -> Any:
    return json.loads(_text(name))


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


def _bom_product(aac: str, description: str, days: list[tuple[str, str, int]], offset: str) -> str:
    """Return a minimal BoM fire danger product (service WSF) for one district."""
    periods = "".join(
        f'<forecast-period index="{i}" start-time-local="{day}T00:00:00{offset}">'
        f'<element type="fire_behaviour_index">{fbi}</element><text type="fire_danger">{rating}</text>'
        "</forecast-period>"
        for i, (day, rating, fbi) in enumerate(days)
    )
    return (
        "<product><amoc><issue-time-utc>2026-10-16T05:15:00Z</issue-time-utc></amoc><forecast>"
        f'<area aac="{aac}" description="{description}" type="fire-district">{periods}</area>'
        "</forecast></product>"
    )


BOM_NSW = ("https://www.bom.gov.au/fwo/IDN10016.xml", _text("bom_IDN10016.xml"))

# 16:00 AEDT on 16 October 2026, after BoM's afternoon NSW issue
AFTERNOON_16_OCT = "2026-10-16T05:00:00+00:00"
SYDNEY_TZ = dt_util.get_time_zone("Australia/Sydney")
PERTH_TZ = dt_util.get_time_zone("Australia/Perth")
TODAY = date(2026, 10, 16)


def _afternoon_nsw() -> str:
    """Return the NSW product as the afternoon issue: every district starts tomorrow."""
    return re.sub(r'<forecast-period index="0".*?</forecast-period>\s*', "", _text("bom_IDN10016.xml"), flags=re.DOTALL)


def _service(hass: HomeAssistant, state: str, location: tuple[float, float], entry_id: str | None, **feeds: Any) -> Any:
    service = FireDangerService(
        hass, AsyncMock(), {"state": state, "latitude": location[0], "longitude": location[1]}, entry_id=entry_id
    )
    mapping = dict(feeds.values())
    service.async_fetch_feed_text = _feeds(mapping)
    service.async_fetch_feed_json = _feeds(mapping)
    return service


# --- Agency rating parsers -----------------------------------------------------------------


def test_nsw_rfs_v2_ratings() -> None:
    """RFS v2 ratings are dated like its bans (from ``lastUpdatedIso``)."""
    payload = _json("nsw_rfs_fire_danger_v2.json")
    ratings = fire_bans.parse_nsw_rfs_v2_ratings(payload, "NSW_FW004", TODAY)
    assert ratings == {
        date(2026, 10, 16): "NONE",
        date(2026, 10, 17): "MODERATE",
        date(2026, 10, 18): "MODERATE",
        date(2026, 10, 19): "MODERATE",
    }
    payload["fireWeatherAreaRatings"][3]["ratingDay4"] = "  "
    assert fire_bans.parse_nsw_rfs_v2_ratings(payload, "NSW_FW004", TODAY)[date(2026, 10, 19)] is None
    assert fire_bans.parse_nsw_rfs_v2_ratings(payload, "NSW_FW099", TODAY) == {}


def test_fdr_toban_ratings() -> None:
    """``DangerLevelToday``/``Tomorrow`` from ``fdrToban.xml`` and the ACT ESA feed."""
    nsw = fire_bans.parse_fdr_toban_ratings(
        ET.fromstring(_text("nsw_rfs_fdr_toban.xml")), "NSW_FW004", TODAY, SYDNEY_TZ
    )
    assert nsw[TODAY] is not None
    act = fire_bans.parse_fdr_toban_ratings(
        ET.fromstring(_text("act_esa_fire_danger.xml")), "NSW_FW008", date(2026, 10, 15), SYDNEY_TZ
    )
    assert act == {TODAY: "Moderate", date(2026, 10, 17): "Moderate"}


def test_vic_cfa_ratings() -> None:
    """CFA ratings come from the "Fire Danger Ratings" paragraph, never the ban lines."""
    root = ET.fromstring(_text("cfa_tfb_fdr_forecast.xml"))
    ratings = fire_bans.parse_vic_cfa_ratings(root, "Northern Country")
    assert ratings[TODAY] == "NO RATING"
    assert fire_bans.parse_vic_cfa_ratings(root, "Central")[TODAY] == "MODERATE"
    text = _text("cfa_tfb_fdr_forecast.xml").replace("<title>Friday, 16 October 2026</title>", "<title>Someday</title>")
    assert TODAY not in fire_bans.parse_vic_cfa_ratings(ET.fromstring(text), "Central")
    # An item without a ratings paragraph gives no rating
    no_ratings = _text("cfa_tfb_fdr_forecast.xml").replace("Fire Danger Ratings", "Notes")
    assert fire_bans.parse_vic_cfa_ratings(ET.fromstring(no_ratings), "Central") == {}
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_vic_cfa_ratings(ET.fromstring("<feed/>"), "Central")


def test_sa_cfs_ratings() -> None:
    """SA CFS ratings: the first rated period for each date."""
    root = ET.fromstring(_text("sa_cfs_fire_danger.xml"))
    ratings = fire_bans.parse_sa_cfs_ratings(root, "Adelaide Metropolitan")
    assert ratings[TODAY] == "No Rating"
    text = _text("sa_cfs_fire_danger.xml")
    start = text.index('description="Adelaide Metropolitan"')
    tail = text[start:].replace('start-time-local="2026-10-18T00:00:00+10:30"', 'start-time-local="bad"', 1)
    assert date(2026, 10, 18) not in fire_bans.parse_sa_cfs_ratings(
        ET.fromstring(text[:start] + tail), "Adelaide Metropolitan"
    )
    assert fire_bans.parse_sa_cfs_ratings(root, "Nowhere") == {}
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_sa_cfs_ratings(ET.fromstring("<product/>"), "Adelaide Metropolitan")


def test_wa_fdr_ratings() -> None:
    """Emergency WA ratings are offset from the district's issue time, as a Perth date."""
    payload = _json("wa_fire_danger_ratings.json")
    ratings = fire_bans.parse_wa_fdr_ratings(payload, "WA_FW053", PERTH_TZ)
    # Issued 2026-10-15T20:35Z = 04:35 AWST on 16 October
    assert ratings == {date(2026, 10, d): "Moderate" for d in range(16, 20)}
    assert fire_bans.parse_wa_fdr_ratings(payload, "WA_FW099", PERTH_TZ) == {}
    item = payload["fireDangerRatings"][0]
    for issued in ("soon", "2026-10-15T20:35:00"):
        item["issueDateTime"] = issued
        assert fire_bans.parse_wa_fdr_ratings(payload, item["area"], PERTH_TZ) == {}
    item["issueDateTime"] = "2026-10-15T20:35:00Z"
    item["forecasts"] = {"0": {"fireDanger": "High"}, "x": {}, "1": "junk"}
    assert fire_bans.parse_wa_fdr_ratings(payload, item["area"], PERTH_TZ) == {TODAY: "High"}
    payload["fireDangerRatings"].insert(0, "junk")
    assert fire_bans.parse_wa_fdr_ratings(payload, item["area"], PERTH_TZ) == {TODAY: "High"}
    with pytest.raises(ProviderUnavailableError):
        fire_bans.parse_wa_fdr_ratings({"fireDangerRatings": None}, "WA_FW053", PERTH_TZ)


# --- Filling today and persistence ---------------------------------------------------------


def _outlook(days: list[FireDangerDay]) -> FireDangerOutlook:
    return FireDangerOutlook(
        district_number="NSW_FW004",
        district_name="Greater Sydney Region",
        time_zone="Australia/Sydney",
        issued_at=datetime.fromisoformat("2026-10-16T05:15:00+00:00"),
        source="Bureau of Meteorology",
        days=days,
    )


def test_fill_from_agency_only_today(freezer: FrozenDateTimeFactory) -> None:
    """The agency fills only today, only when BoM has no day for it, and only with an AFDRS rating."""
    freezer.move_to(AFTERNOON_16_OCT)
    tomorrow = FireDangerDay(date=date(2026, 10, 17), rating="High")
    outlook = _outlook([tomorrow])
    fill_from_agency(outlook, {TODAY: None, date(2026, 10, 20): "EXTREME"}, "Agency")
    assert [d.date for d in outlook.days] == [date(2026, 10, 17)]
    fill_from_agency(outlook, {TODAY: "EXTREME", date(2026, 10, 17): "LOW"}, "Agency")
    assert [(d.date, d.rating, d.source) for d in outlook.days] == [
        (TODAY, "Extreme", "Agency"),
        (date(2026, 10, 17), "High", None),
    ]
    fill_from_agency(outlook, {TODAY: "MODERATE"}, "Other")
    assert outlook.days[0].rating == "Extreme"  # an existing day is never replaced


def test_outlook_round_trip() -> None:
    """Stored outlooks survive the Store's JSON; anything else is ignored."""
    outlook = _outlook(
        [FireDangerDay(date=TODAY, rating="High", fire_behaviour_index=30, total_fire_ban=True, source="Agency")]
    )
    outlook.total_fire_ban_source = "NSW Rural Fire Service"
    assert outlook_from_dict(outlook_to_dict(outlook)) == outlook
    no_issue = outlook_to_dict(outlook) | {"issued_at": None}
    restored = outlook_from_dict(no_issue)
    assert restored is not None
    assert restored.issued_at is None
    assert outlook_from_dict(None) is None
    assert outlook_from_dict({"district_number": "NSW_FW004"}) is None
    assert outlook_from_dict(outlook_to_dict(outlook) | {"days": [{"date": "soon"}]}) is None


@pytest.mark.real_fire_service
async def test_afternoon_restart_takes_today_from_the_agency(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Restarted after BoM's afternoon issue with nothing stored: NSW RFS supplies today (#89)."""
    freezer.move_to(AFTERNOON_16_OCT)
    service = _service(
        hass,
        "NSW",
        SYDNEY,
        None,
        bom=(BOM_NSW[0], _afternoon_nsw()),
        rfs=(fire_bans.NSW_RFS_FDR_URL, _json("nsw_rfs_fire_danger_v2.json")),
    )
    await service.async_update()
    outlook = service.outlook
    assert outlook is not None
    today = outlook.day(TODAY)
    assert today is not None
    assert (today.rating, today.source, today.total_fire_ban) == ("No Rating", "NSW Rural Fire Service", False)
    rating = fire_danger_today(outlook)
    assert rating is not None
    assert rating.rating == "No Rating"
    # The coming days are BoM's
    assert [d.source for d in outlook.days[1:]] == [None, None, None]

    # With the 4-day feed down, fdrToban.xml supplies today's rating instead
    fallback = _service(
        hass,
        "NSW",
        SYDNEY,
        None,
        bom=(BOM_NSW[0], _afternoon_nsw()),
        rfs=(fire_bans.NSW_RFS_FDR_URL, ProviderUnavailableError()),
        toban=(fire_bans.NSW_RFS_TOBAN_URL, _text("nsw_rfs_fdr_toban.xml")),
    )
    await fallback.async_update()
    assert fallback.outlook is not None
    assert fallback.outlook.day(TODAY) is not None


@pytest.mark.real_fire_service
async def test_restart_keeps_the_morning_issue(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """The morning issue is stored, so an afternoon restart still has BoM's rating for today (#89)."""
    freezer.move_to("2026-10-15T21:00:00+00:00")  # 08:00 AEDT, 16 Oct
    key = FIRE_STORAGE_KEY.format(entry_id="entry1")
    morning = _service(
        hass, "NSW", SYDNEY, "entry1", bom=BOM_NSW, rfs=(fire_bans.NSW_RFS_FDR_URL, ProviderUnavailableError())
    )
    await morning.async_update()
    assert hass_storage[key]["data"]["district_number"] == "NSW_FW004"

    # Restart in the afternoon: BoM starts tomorrow and every agency feed is down
    freezer.move_to(AFTERNOON_16_OCT)
    restarted = _service(hass, "NSW", SYDNEY, "entry1", bom=(BOM_NSW[0], _afternoon_nsw()))
    await restarted.async_update()
    assert restarted.outlook is not None
    today = restarted.outlook.day(TODAY)
    assert today is not None
    assert (today.rating, today.fire_behaviour_index, today.source) == ("No Rating", 9, None)
    assert hass_storage[key]["data"]["days"][0]["date"] == "2026-10-16"

    # A location outside every district has no outlook, and the stored one is dropped
    offshore = _service(hass, "NSW", (-36.85, 174.76), "entry1")
    offshore._restored = True
    await offshore.async_update()
    assert offshore.outlook is None
    assert key not in hass_storage


@pytest.mark.real_fire_service
async def test_unreadable_store_is_ignored(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """A damaged or unreadable store never blocks fire data."""
    freezer.move_to(AFTERNOON_16_OCT)
    key = FIRE_STORAGE_KEY.format(entry_id="entry2")
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": {"not": "an outlook"}}
    damaged = _service(hass, "NSW", SYDNEY, "entry2", bom=(BOM_NSW[0], _afternoon_nsw()))
    await damaged.async_update()
    assert damaged.outlook is not None
    assert damaged.outlook.day(TODAY) is None  # nothing stored, no agency feed

    unreadable = _service(hass, "NSW", SYDNEY, "entry3", bom=(BOM_NSW[0], _afternoon_nsw()))
    with patch("homeassistant.helpers.storage.Store.async_load", AsyncMock(side_effect=OSError("disk"))):
        await unreadable.async_update()
    assert unreadable.outlook is not None


@pytest.mark.real_fire_service
async def test_wa_takes_today_from_emergency_wa(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """WA reads the Emergency WA ratings feed only when BoM has no day for today."""
    freezer.move_to("2026-10-16T08:00:00+00:00")  # 16:00 AWST
    afternoon = _bom_product("WA_FW053", "Mid West", [("2026-10-17", "High", 30)], "+08:00")
    abs_lga = {"features": [{"attributes": {"lga_name_2021": "Greater Geraldton"}}]}
    common = {
        "bom": ("https://www.bom.gov.au/fwo/IDW15100.xml", afternoon),
        "abs": ("https://geo.abs.gov.au/", abs_lga),
        "tfb": (
            fire_bans.WA_TFB_URL,
            {
                "totalFireBans": [
                    {"fire-ban-lga": "GREATER GERALDTON, CITY OF", "ban-level": "Ban", "date-of-ban": "2026-10-16"}
                ]
            },
        ),
    }
    wa = _service(
        hass, "WA", GERALDTON, None, fdr=(fire_bans.WA_FDR_URL, _json("wa_fire_danger_ratings.json")), **common
    )
    await wa.async_update()
    assert wa.outlook is not None
    today = wa.outlook.day(TODAY)
    assert today is not None
    assert (today.rating, today.total_fire_ban, today.source) == (
        "Moderate",
        True,
        "Department of Fire and Emergency Services WA",
    )

    down = _service(hass, "WA", GERALDTON, None, fdr=(fire_bans.WA_FDR_URL, ProviderUnavailableError()), **common)
    await down.async_update()
    assert down.outlook is not None
    assert down.outlook.day(TODAY) is None

    # BoM covers today: the ratings feed is not read
    morning = _bom_product("WA_FW053", "Mid West", [("2026-10-16", "High", 30)], "+08:00")
    covered = _service(
        hass, "WA", GERALDTON, None, **{**common, "bom": ("https://www.bom.gov.au/fwo/IDW15100.xml", morning)}
    )
    await covered.async_update()
    urls = [c.args[0] for c in covered.async_fetch_feed_json.await_args_list]
    assert fire_bans.WA_FDR_URL not in urls


# --- Entities and lifecycle ----------------------------------------------------------------


async def test_sensor_shows_the_outlook_without_a_rating_for_today(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """With no rating for today the state is unknown but the district and coming days stay (#89)."""
    freezer.move_to(AFTERNOON_16_OCT)
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.providers = []
    await coordinator.async_refresh()
    coordinator.data.fire_danger = None
    coordinator.data.fire_outlook = _outlook([FireDangerDay(date=date(2026, 10, 17), rating="High")])
    sensor = FireDangerRatingSensor(coordinator)
    assert sensor.native_value is None
    attrs = sensor.extra_state_attributes
    assert attrs["district_number"] == "NSW_FW004"
    assert attrs["day"] is None
    assert attrs["total_fire_ban"] is None
    assert attrs["fire_behaviour_index"] is None
    assert [d["date"] for d in attrs["forecast"]] == ["2026-10-17"]
    assert attrs["source"] == "Bureau of Meteorology"

    # A day the agency supplied names the agency as its source
    coordinator.data.fire_outlook = _outlook(
        [FireDangerDay(date=TODAY, rating="High", source="NSW Rural Fire Service")]
    )
    coordinator.data.fire_danger = fire_danger_today(coordinator.data.fire_outlook)
    assert sensor.native_value == "high"
    assert sensor.extra_state_attributes["source"] == "NSW Rural Fire Service"


async def test_removing_the_entry_deletes_the_stored_outlook(
    hass: HomeAssistant, hass_storage: dict[str, Any], mock_config_entry: MockConfigEntry
) -> None:
    """Deleting an entry removes its persisted fire outlook."""
    mock_config_entry.add_to_hass(hass)
    key = FIRE_STORAGE_KEY.format(entry_id=mock_config_entry.entry_id)
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": {}}
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage
