"""Bureau of Meteorology (BoM) weather warnings via the WMO CAP syndication of BoM's CAP feed.

The WMO RSS feed is a rolling archive (~500 messages over ~10 days) of every CAP message BoM
issued, including superseded and cancelled ones. Each RSS item only points at its CAP 1.2
document, which holds the lifecycle (``msgType``, ``references``, ``expires``) and area.
This provider keeps the newest message per BoM product (e.g. ``IDQ21033``), drops cancelled,
expired and non-``Actual`` messages, and never places a warning at the user's location (#10).

BoM CAP documents currently identify their area only by AMOC area codes (no polygons), so
warnings without geometry are exposed as weather warnings, not as located hazards.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
import re
from typing import TYPE_CHECKING, Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import LAST_GOOD_MAX_AGE, STATE_ACT
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel, WeatherWarningItem
from homeassistant.util import dt as dt_util

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, stable_id
from .cap import CapAlert, area_distance_km, parse_cap, representative_point

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

_LOGGER = logging.getLogger(__name__)

BOM_WMO_FEED_URL = "https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/rss.xml"
BOM_WARNINGS_PAGE = "https://www.bom.gov.au/australia/warnings"
CAP_FETCH_CONCURRENCY = 4
_EPOCH = datetime.min.replace(tzinfo=UTC)

_PRODUCT_RE = re.compile(r"\bID[A-Z]\d{5}\b")

# BoM product prefix per jurisdiction. ACT warnings are issued under the NSW prefix.
STATE_PRODUCT_PREFIXES: dict[str, tuple[str, ...]] = {
    "QLD": ("IDQ",),
    "NSW": ("IDN",),
    STATE_ACT: ("IDN",),
    "VIC": ("IDV",),
    "WA": ("IDW",),
    "SA": ("IDS",),
    "TAS": ("IDT",),
    "NT": ("IDD",),
}

_SEVERITY_LEVELS = {
    "extreme": WarningLevel.EMERGENCY_WARNING,
    "severe": WarningLevel.WATCH_AND_ACT,
    "moderate": WarningLevel.ADVICE,
    "minor": WarningLevel.ADVICE,
}


class BoMHazardProvider(BaseHazardProvider):
    """Provider for Bureau of Meteorology (BoM) weather warnings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider with a CAP document cache that persists across polls."""
        super().__init__(*args, **kwargs)
        self._cap_cache: dict[str, CapAlert | None] = {}  # guid -> parsed alert (None = unusable)
        # Unlocated warnings from the last successful poll, with each alert's expiry
        self._weather_warnings: list[tuple[datetime | None, WeatherWarningItem]] = []
        self._weather_warnings_at: datetime | None = None

    @property
    def state_code(self) -> str:
        """Return state code from config or national."""
        return str(self.config.get("state", "ALL")).upper()

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch current BoM warnings; located ones become hazards, the rest weather warnings."""
        xml_text = await self.async_fetch_feed_text(BOM_WMO_FEED_URL, "BoM CAP feed")
        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"BoM CAP feed returned invalid XML: {err}") from err
        channel = root.find("channel")
        if channel is None:
            raise ProviderUnavailableError("BoM CAP feed has no channel")

        items = channel.findall("item")
        self._prune_cache({(item.findtext("guid") or "").strip() for item in items})
        candidates = self._candidate_items_per_product(items)
        alerts = _newest_message_per_product(await self._async_load_alerts(candidates))
        now = dt_util.utcnow()

        hazards: list[CanonicalHazard] = []
        weather_warnings: list[tuple[datetime | None, WeatherWarningItem]] = []
        for product_id, item, alert in alerts:
            try:
                if not _is_current(alert, now):
                    continue
                hazard = self._build_hazard(product_id, item, alert)
                if hazard is not None:
                    hazards.append(hazard)
                else:
                    weather_warnings.append((alert.expires, self._build_weather_warning(item, alert)))
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed BoM item %s: %s", product_id, err)
        self._weather_warnings = weather_warnings
        self._weather_warnings_at = now
        return hazards

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Return current BoM warnings that have no area geometry (from the latest hazard poll).

        While the feed is failing, the last good list is kept for ``LAST_GOOD_MAX_AGE`` like
        hazards are, and warnings that have since expired are dropped.
        """
        now = dt_util.utcnow()
        if self._weather_warnings_at is None or now - self._weather_warnings_at > LAST_GOOD_MAX_AGE:
            return []
        return [item for expires, item in self._weather_warnings if expires is None or expires > now]

    def _accepts_product(self, product_id: str | None) -> bool:
        """Return True if the product belongs to the configured jurisdiction."""
        prefixes = STATE_PRODUCT_PREFIXES.get(self.state_code)
        if prefixes is None or product_id is None:
            return True  # "ALL"/unknown state, or an item without a product id
        return product_id.startswith(prefixes)

    def _candidate_items_per_product(self, items: list[Element]) -> list[tuple[str, Element]]:
        """Group items by BoM product and keep the newest by RSS pubDate.

        Items that tie on the newest pubDate, or whose pubDate cannot be parsed, are all kept so
        the CAP lifecycle (``sent`` and ``references``) can decide between them.
        """
        groups: dict[str, list[tuple[datetime | None, Element]]] = {}
        for item in items:
            guid = (item.findtext("guid") or "").strip()
            title = (item.findtext("title") or "").strip()
            match = _PRODUCT_RE.search(f"{guid} {item.findtext('link') or ''} {title}")
            product_id = match.group(0) if match else None
            if not self._accepts_product(product_id):
                continue
            key = product_id or stable_id("BOM", guid or title)
            groups.setdefault(key, []).append((self.parse_datetime(item.findtext("pubDate")), item))
        candidates: list[tuple[str, Element]] = []
        for key, group in groups.items():
            newest = max((published for published, _ in group if published is not None), default=None)
            candidates.extend((key, item) for published, item in group if published in (None, newest))
        return candidates

    async def _async_load_alerts(self, candidates: list[tuple[str, Element]]) -> list[tuple[str, Element, CapAlert]]:
        """Fetch (or reuse cached) CAP documents for each product's candidate items."""
        semaphore = asyncio.Semaphore(CAP_FETCH_CONCURRENCY)
        failed: list[str] = []

        async def load(product_id: str, item: Element) -> tuple[str, Element, CapAlert] | None:
            guid = (item.findtext("guid") or "").strip()
            link = (item.findtext("link") or "").strip()
            if guid not in self._cap_cache:
                if not link:
                    return None
                async with semaphore:
                    try:
                        document = await self.async_fetch_feed_text(link, "BoM CAP document")
                    except ProviderUnavailableError as err:
                        # Not cached: retried on the next poll
                        _LOGGER.debug("BoM CAP document %s unavailable: %s", link, err)
                        failed.append(link)
                        return None
                self._cap_cache[guid] = parse_cap(document)
            alert = self._cap_cache[guid]
            return (product_id, item, alert) if alert is not None else None

        results = await asyncio.gather(*(load(product_id, item) for product_id, item in candidates))
        if failed:
            # A missing document could be a product's newest message (an update or a cancellation),
            # so this poll is incomplete; let the coordinator keep the last good data (#16).
            raise ProviderUnavailableError(f"{len(failed)} BoM CAP document(s) unavailable")
        return [result for result in results if result is not None]

    def _prune_cache(self, live_guids: set[str]) -> None:
        """Forget CAP documents whose RSS items have left the feed."""
        for guid in list(self._cap_cache):
            if guid not in live_guids:
                del self._cap_cache[guid]

    def _build_hazard(self, product_id: str, item: Element, alert: CapAlert) -> CanonicalHazard | None:
        """Return a located hazard, or None if the alert has no area geometry."""
        if not alert.has_geometry:
            return None
        lat, lon = _float(self.config.get("latitude")), _float(self.config.get("longitude"))
        location = representative_point(alert.areas, lat, lon)
        if location is None:  # pragma: no cover - has_geometry guarantees a shape
            return None
        title = (item.findtext("title") or alert.headline or alert.event).strip()
        return CanonicalHazard(
            id=f"BOM_{product_id}",
            source="Bureau of Meteorology",
            title=title,
            hazard_type=HazardType.from_str(f"{title} {alert.event}"),
            warning_level=_warning_level(title, alert),
            latitude=location[0],
            longitude=location[1],
            updated_at=alert.sent,
            location_name=alert.area_description[:120] or "Australia",
            distance_km=area_distance_km(lat, lon, alert.areas) if lat is not None and lon is not None else None,
            responsible_agency="Bureau of Meteorology",
            web_url=_web_url(item, alert),
            raw_properties={
                "product_id": product_id,
                "cap_identifier": alert.identifier,
                "msg_type": alert.msg_type,
                "severity": alert.severity,
                "urgency": alert.urgency,
                "event": alert.event,
                "onset": alert.onset.isoformat() if alert.onset else None,
                "expires": alert.expires.isoformat() if alert.expires else None,
            },
        )

    def _build_weather_warning(self, item: Element, alert: CapAlert) -> WeatherWarningItem:
        """Return the summary entry for an alert without area geometry."""
        return WeatherWarningItem(
            title=(item.findtext("title") or alert.headline or alert.event).strip(),
            link=_web_url(item, alert),
            locations=alert.area_description or None,
            pub_date=alert.sent,
        )


def _newest_message_per_product(
    alerts: list[tuple[str, Element, CapAlert]],
) -> list[tuple[str, Element, CapAlert]]:
    """Keep one CAP message per product: never one a sibling updates or cancels, else the latest sent."""
    groups: dict[str, list[tuple[str, Element, CapAlert]]] = {}
    for entry in alerts:
        groups.setdefault(entry[0], []).append(entry)
    result: list[tuple[str, Element, CapAlert]] = []
    for group in groups.values():
        referenced = {ref for _, _, alert in group for ref in alert.references}
        live = [entry for entry in group if entry[2].identifier not in referenced] or group
        result.append(max(live, key=lambda entry: (entry[2].sent or _EPOCH, entry[2].identifier)))
    return result


def _is_current(alert: CapAlert, now: datetime) -> bool:
    """Return True if the alert is an actual, uncancelled, unexpired message."""
    if alert.status.lower() != "actual" or alert.msg_type.lower() == "cancel":
        return False
    return alert.expires is None or alert.expires > now


def _warning_level(title: str, alert: CapAlert) -> WarningLevel:
    """Australian Warning System level from the title, else from CAP severity."""
    level = WarningLevel.from_str(title)
    if level is WarningLevel.UNKNOWN:
        level = _SEVERITY_LEVELS.get(alert.severity.lower(), WarningLevel.ADVICE)
    return level


def _web_url(item: Element, alert: CapAlert) -> str:
    """Prefer BoM's own warning page from the CAP document, then the RSS link."""
    if alert.web.startswith(("http://www.bom.gov.au", "https://www.bom.gov.au")):
        return alert.web.replace("http://", "https://", 1)
    return (item.findtext("link") or "").strip() or BOM_WARNINGS_PAGE


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
