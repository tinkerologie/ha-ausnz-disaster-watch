"""Total fire ban parsers for each Australian fire agency's public feed (#28).

Each parser returns ``{local date: banned}`` for one BoM fire weather district. A parser
raises ProviderUnavailableError when the document is not the expected feed, so a broken
response is never read as "no ban". Days a feed does not cover are simply absent.

Sources (all verified live on 2026-10-16):

- NSW: RFS ``fire-danger-ratings-v2`` (4 days, ``areaId`` is the BoM district number),
  falling back to ``fdrToban.xml`` (today and tomorrow).
- ACT: ESA ``firedangerrating.xml`` (same shape as ``fdrToban.xml``, region 8).
- VIC: CFA ``tfbfdrforecast_rss.xml`` (one dated item per day, a line per CFA district).
- SA: CFS ``fireDangerRating.xml`` (dated forecast periods per district).
- WA: Emergency WA ``total-fire-bans`` (bans per local government area).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
import html
import re
from typing import TYPE_CHECKING, Any

from .base import ProviderUnavailableError

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

NSW_RFS_FDR_URL = "https://www.rfs.nsw.gov.au/_designs/xml/fire-danger-ratings/fire-danger-ratings-v2"
NSW_RFS_TOBAN_URL = "https://www.rfs.nsw.gov.au/feeds/fdrToban.xml"
ACT_ESA_FDR_URL = "https://www.esa.act.gov.au/feeds/firedangerrating.xml"
VIC_CFA_TFB_URL = "https://www.cfa.vic.gov.au/cfa/rssfeed/tfbfdrforecast_rss.xml"
SA_CFS_FDR_URL = "https://data.eso.sa.gov.au/prod/cfs/criimson/fireDangerRating.xml"
WA_TFB_URL = "https://api.emergency.wa.gov.au/v1/total-fire-bans"

# v2 day suffixes in order, starting today (NSW local date)
_NSW_DAY_KEYS = ("Today", "Tomorrow", "Day3", "Day4")


def parse_ban_flag(value: Any) -> bool | None:
    """Return True/False for an agency ban flag, or None when it is missing or unrecognised."""
    text = str(value if value is not None else "").strip().lower()
    if text in {"yes", "true", "1", "y"} or text.startswith("yes"):
        return True
    if text in {"no", "false", "0", "n"} or text.startswith("no"):
        return False
    return None


def normalise_name(name: str) -> str:
    """Return a name reduced to lower-case letters and digits, for matching across feeds."""
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def district_number(aac: str) -> int | None:
    """Return the numeric part of a BoM district AAC (``NSW_FW008`` -> 8)."""
    match = re.search(r"(\d+)$", aac)
    return int(match.group(1)) if match else None


def parse_nsw_rfs_v2(payload: Any, aac: str, today: date) -> dict[date, bool | None]:
    """Parse the NSW RFS 4-day fire danger and total fire ban feed.

    ``areaId`` equals the BoM district number. The days are relative to the feed's
    ``lastUpdatedIso`` (NSW local time), so a poll after midnight but before RFS rolls the
    feed over does not shift every day by one. ``today`` (the NSW local date) is used only
    when that field is missing or unreadable.
    """
    areas = payload.get("fireWeatherAreaRatings") if isinstance(payload, dict) else None
    if not isinstance(areas, list):
        raise ProviderUnavailableError("NSW RFS fire danger feed returned an unexpected payload")
    today = _iso_local_date(payload.get("lastUpdatedIso"), today)
    number = district_number(aac)
    for area in areas:
        if not isinstance(area, dict) or str(area.get("areaId", "")).strip() != str(number):
            continue
        return {
            today + timedelta(days=offset): parse_ban_flag(area.get(f"toban{key}"))
            for offset, key in enumerate(_NSW_DAY_KEYS)
        }
    return {}


def _iso_local_date(value: Any, fallback: date) -> date:
    """Return the local calendar date of an ISO timestamp with an offset, else the fallback."""
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return fallback
    return stamp.date() if stamp.tzinfo is not None else fallback


def _toban_today(root: Element, fallback: date, tz: Any) -> date:
    """Return the local date the ``Today`` fields refer to: the feed's pubDate, else the fallback."""
    pub = root.findtext("channel/pubDate") or root.findtext("channel/lastBuildDate")
    if pub:
        try:
            published = parsedate_to_datetime(pub.strip())
        except (TypeError, ValueError, IndexError):
            return fallback
        if published.tzinfo is not None:
            return published.astimezone(tz).date()
    return fallback


def parse_fdr_toban_xml(root: Element, aac: str, today: date, tz: Any) -> dict[date, bool | None]:
    """Parse the ``FireDangerMap`` XML used by NSW RFS ``fdrToban.xml`` and ACT ESA.

    ``RegionNumber`` equals the BoM district number (the ACT is region 8).
    """
    container = root if root.tag == "FireDangerMap" else root.find("channel/FireDangerMap")
    if container is None:
        raise ProviderUnavailableError(f"Fire ban feed returned an unexpected document <{root.tag}>")
    today = _toban_today(root, today, tz)
    number = district_number(aac)
    for district in container.iterfind("District"):
        if (district.findtext("RegionNumber") or "").strip() != str(number):
            continue
        return {
            today: parse_ban_flag(district.findtext("FireBanToday")),
            today + timedelta(days=1): parse_ban_flag(district.findtext("FireBanTomorrow")),
        }
    return {}


_CFA_LINE_RE = re.compile(r"^\s*([^:<>]+?)\s*:\s*(.+?)\s*$")


def parse_vic_cfa_rss(root: Element, district_name: str) -> dict[date, bool | None]:
    """Parse the CFA total fire ban and fire danger forecast RSS.

    Each item is titled with its date (``Friday, 16 October 2026``). Its description lists
    every CFA district as ``Central: NO - RESTRICTIONS MAY APPLY`` (or ``YES - ...``) before
    the "Fire Danger Ratings" paragraph. CFA district names equal the BoM district names.
    """
    if root.tag != "rss" or root.find("channel") is None:
        raise ProviderUnavailableError(f"CFA fire ban feed returned an unexpected document <{root.tag}>")
    wanted = normalise_name(district_name)
    bans: dict[date, bool | None] = {}
    for item in root.iterfind("channel/item"):
        try:
            day = datetime.strptime((item.findtext("title") or "").strip(), "%A, %d %B %Y").date()
        except ValueError:
            continue
        description = html.unescape(item.findtext("description") or "")
        ban_section = re.split(r"fire danger ratings", description, maxsplit=1, flags=re.IGNORECASE)[0]
        for line in re.split(r"<br\s*/?>|</?p>", ban_section, flags=re.IGNORECASE):
            match = _CFA_LINE_RE.match(line)
            if match and normalise_name(match.group(1)) == wanted:
                bans[day] = parse_ban_flag(match.group(2))
                break
    return bans


def parse_sa_cfs_xml(root: Element, district_name: str) -> dict[date, bool | None]:
    """Parse the SA CFS fire danger and total fire ban XML.

    Districts carry a ``description`` equal to the BoM district name; each dated forecast
    period has ``<text type="fire_ban">true|false</text>``. A day is banned if any period
    for that date says so.
    """
    if root.tag != "product" or root.find("forecast") is None:
        raise ProviderUnavailableError(f"SA CFS fire ban feed returned an unexpected document <{root.tag}>")
    wanted = normalise_name(district_name)
    flags: dict[date, list[bool | None]] = {}
    for area in root.iterfind("forecast/area"):
        if area.get("type") != "fire-district" or normalise_name(area.get("description") or "") != wanted:
            continue
        for period in area.iterfind("forecast-period"):
            try:
                day = datetime.fromisoformat(period.get("start-time-local") or "").date()
            except ValueError:
                continue
            flags.setdefault(day, []).append(parse_ban_flag(period.findtext("text[@type='fire_ban']")))
        break
    return {day: True if True in values else (False if False in values else None) for day, values in flags.items()}


def lga_key(name: str) -> str:
    """Return the matching key for a WA local government name.

    Emergency WA writes ``GREATER GERALDTON, CITY OF``; the ABS writes ``Greater Geraldton``.
    """
    return normalise_name(name.split(",", 1)[0].split("(", 1)[0])


def parse_wa_total_fire_bans(payload: Any, lga: str, days: list[date]) -> dict[date, bool | None]:
    """Parse Emergency WA total fire bans for one local government area.

    The feed lists only current and upcoming bans, so a forecast day without a ban for the
    LGA is a day without a ban.
    """
    bans = payload.get("totalFireBans") if isinstance(payload, dict) else None
    if not isinstance(bans, list):
        raise ProviderUnavailableError("Emergency WA total fire bans returned an unexpected payload")
    wanted = lga_key(lga)
    result: dict[date, bool | None] = dict.fromkeys(days, False)
    for ban in bans:
        if not isinstance(ban, dict) or lga_key(str(ban.get("fire-ban-lga") or "")) != wanted:
            continue
        if str(ban.get("ban-level") or "").strip().lower() != "ban":
            continue
        try:
            day = date.fromisoformat(str(ban.get("date-of-ban") or "")[:10])
        except ValueError:
            continue
        # Only the forecast days: the result is a complete per-day map
        if day in result:
            result[day] = True
    return result
