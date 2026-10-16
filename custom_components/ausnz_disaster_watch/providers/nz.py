"""New Zealand hazard provider: GeoNet quakes and volcanoes, NEMA Civil Defence alerts, MetService warnings, NZTA roads.

NEMA's AlertHub Atom feed embeds each CAP 1.2 alert as escaped XML inside ``<content>``, and
MetService's RSS items only point at CAP documents. Both are read through the shared CAP
parser so that lifecycle (``msgType``, ``expires``), level (MetService ``ColourCode``) and area
geometry are available (#11).

GeoNet quakes and volcanic alert levels come from the ``aio_geojson_geonetnz_*`` libraries
(#35). Quakes GeoNet has issued a CAP alert for (``/cap/1.2/GPA1.0/feed/atom1.0/quake``) carry
that alert, and their distance is measured to its felt-intensity area (#24). Road closures
come from NZTA's Traffic Application Server (``nzta.py``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import CONF_RADIUS, DEFAULT_RADIUS, LAST_GOOD_MAX_AGE, STATE_NZ
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    HazardType,
    RoadClosureItem,
    WarningLevel,
    WeatherWarningItem,
)
from homeassistant.util import dt as dt_util

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, stable_id
from .cap import CapAlert, CapDocumentCache, area_distance_km, cap_from_element, parse_cap, representative_point
from .geojson_feed import async_feed_entries
from .geonet import (
    GEONET_AGENCY,
    GEONET_CAP_FEED_URL,
    GeoNetQuakeEntry,
    GeoNetQuakesFeed,
    GeoNetVolcanoEntry,
    GeoNetVolcanoFeed,
)
from .nzta import NZTA_HEADERS, events_url, is_disruption, road_closure_item, road_events

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

_LOGGER = logging.getLogger(__name__)

QUAKE_MAX_AGE = timedelta(hours=48)
# Below this depth a quake's magnitude says little about shaking at the surface
QUAKE_SHALLOW_KM = 70.0
NEMA_ALERTHUB_URL = "https://alerthub.civildefence.govt.nz/atom/pwp"
NEMA_WEB_URL = "https://www.civildefence.govt.nz"
# MetService CAP Code of Practice: poll no more often than every two minutes (#62)
METSERVICE_MIN_POLL_INTERVAL = timedelta(minutes=2)
# hass.data key of the MetService poll state shared by every NZ entry (survives entry reloads)
METSERVICE_SHARED_KEY = "ausnz_disaster_watch_metservice"


@dataclass(slots=True)
class MetServiceShared:
    """The last MetService fetch and the lock that serialises fetches across NZ entries (#62)."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last: tuple[datetime, list[tuple[Element, CapAlert]]] | None = None


METSERVICE_ALERTS_URL = "https://alerts.metservice.com/cap/rss"
METSERVICE_WEB_URL = "https://www.metservice.com/warnings/home"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
CAP_CONTENT_TYPE = "application/cap+xml"

_COLOUR_LEVELS = {
    "red": WarningLevel.EMERGENCY_WARNING,
    "orange": WarningLevel.WATCH_AND_ACT,
    "yellow": WarningLevel.ADVICE,
}
_SEVERITY_LEVELS = {
    "extreme": WarningLevel.EMERGENCY_WARNING,
    "severe": WarningLevel.WATCH_AND_ACT,
    "moderate": WarningLevel.ADVICE,
    "minor": WarningLevel.ADVICE,
}


class NZHazardProvider(BaseHazardProvider):
    """Provider for New Zealand natural hazards and civil defence emergencies."""

    local_tz = "Pacific/Auckland"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_NZ

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider with GeoNet feeds and CAP document caches that persist across polls."""
        super().__init__(*args, **kwargs)
        # The libraries only use home for distance filtering, which the coordinator does instead
        home = self._home() or (0.0, 0.0)
        self._quake_feed = GeoNetQuakesFeed(self.session, home)
        self._volcano_feed = GeoNetVolcanoFeed(self.session, home)
        self._geonet_cap_documents = CapDocumentCache("GeoNet CAP document")
        self._geonet_cap: dict[str, CapAlert] = {}
        self._geonet_cap_at: datetime | None = None
        self._metservice_documents = CapDocumentCache("MetService CAP document")
        # Unlocated MetService warnings from the last successful poll, with each alert's expiry
        self._weather_warnings: list[tuple[datetime | None, WeatherWarningItem]] = []
        self._weather_warnings_at: datetime | None = None

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch and aggregate New Zealand hazards from GeoNet, NEMA and MetService."""
        return await self.async_collect_sources(
            [
                ("GeoNet quakes", self._async_fetch_quakes, self._parse_geonet_quakes),
                (
                    "GeoNet volcanoes",
                    lambda: async_feed_entries(self._volcano_feed, "GeoNet volcanoes"),
                    self._parse_geonet_volcanoes,
                ),
                (
                    "NEMA AlertHub",
                    lambda: self.async_fetch_feed_text(NEMA_ALERTHUB_URL, "NEMA AlertHub"),
                    self._parse_nema_atom,
                ),
                ("MetService", self._async_fetch_metservice, self._parse_metservice),
            ]
        )

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Return current MetService warnings without area geometry (from the latest hazard poll).

        Located warnings are hazards. During an outage the last good list is kept for
        ``LAST_GOOD_MAX_AGE``, minus warnings that have expired since.
        """
        now = dt_util.utcnow()
        if self._weather_warnings_at is None or now - self._weather_warnings_at > LAST_GOOD_MAX_AGE:
            return []
        return [item for expires, item in self._weather_warnings if expires is None or expires > now]

    def _parse_geonet_quakes(
        self, payload: tuple[list[GeoNetQuakeEntry], dict[str, CapAlert]]
    ) -> list[CanonicalHazard]:
        """Map GeoNet quake entries to hazards, enriched with GeoNet's CAP alert where one exists."""
        entries, cap_alerts = payload
        hazards: list[CanonicalHazard] = []
        now = datetime.now(UTC)

        for entry in entries:
            try:
                if entry.quality == "deleted":
                    continue

                updated_at = entry.origin_time or self.parse_datetime(entry.raw_time)
                if updated_at and (now - updated_at > QUAKE_MAX_AGE):
                    continue

                centroid = entry.coordinates
                if not centroid or centroid[0] is None or centroid[1] is None:
                    continue

                lat, lon = centroid
                public_id = str(entry.external_id or "")
                mag = float(entry.magnitude if entry.magnitude is not None else 0.0)
                mmi = int(entry.mmi if entry.mmi is not None else -1)
                depth = entry.depth
                locality = entry.locality or "New Zealand"
                level = _quake_level(mag, mmi, float(depth) if depth is not None else None)
                raw: dict[str, Any] = {"magnitude": mag, "mmi": mmi, "depth": depth, "quality": entry.quality}
                distance_km: float | None = None
                status = "Active"
                if (alert := cap_alerts.get(public_id)) is not None:
                    # GeoNet issued a CAP alert: measure distance to its felt area (0 inside it)
                    if (home := self._home()) is not None:
                        distance_km = area_distance_km(home[0], home[1], alert.areas)
                    status = "Alert"
                    raw |= {
                        "cap_identifier": alert.identifier,
                        "headline": alert.headline or None,
                        "description": alert.description or None,
                        "intensity": alert.parameter("Intensity") or None,
                        "expires": alert.expires.isoformat() if alert.expires else None,
                    }

                hazards.append(
                    CanonicalHazard(
                        id=f"nz_quake_{public_id}",
                        source="GeoNet New Zealand",
                        title=f"M{mag:.1f} Earthquake - {locality}",
                        hazard_type=HazardType.EARTHQUAKE,
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=updated_at,
                        location_name=locality,
                        distance_km=distance_km,
                        status=status,
                        responsible_agency=GEONET_AGENCY,
                        web_url=f"https://www.geonet.org.nz/earthquake/{public_id}",
                        raw_properties=raw,
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed GeoNet quake item: %s", err)

        return hazards

    def _parse_geonet_volcanoes(self, entries: list[GeoNetVolcanoEntry]) -> list[CanonicalHazard]:
        """Map GeoNet volcanic alert level entries to hazards."""
        hazards: list[CanonicalHazard] = []

        for entry in entries:
            try:
                centroid = entry.coordinates
                if not centroid or centroid[0] is None or centroid[1] is None:
                    continue

                lat, lon = centroid
                volcano_id = str(entry.external_id or "")
                title_name = entry.title or volcano_id.capitalize()
                level_num = int(entry.alert_level or 0)
                acc = entry.aviation_colour_code or "Green"
                activity = entry.activity or "No volcanic unrest."

                # Determine AWS Warning Level mapping
                if level_num >= 3:
                    level = WarningLevel.EMERGENCY_WARNING
                elif level_num == 2:
                    level = WarningLevel.WATCH_AND_ACT
                elif level_num == 1:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                hazards.append(
                    CanonicalHazard(
                        id=f"nz_volcano_{volcano_id}",
                        source="GeoNet New Zealand",
                        title=f"Volcano Level {level_num} ({acc}) - {title_name}",
                        hazard_type=HazardType.VOLCANO,
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=None,  # the VAL payload carries no timestamp
                        location_name=title_name,
                        status=activity,
                        responsible_agency=GEONET_AGENCY,
                        web_url=f"https://www.geonet.org.nz/volcano/{volcano_id}",
                        raw_properties={
                            "volcanoID": volcano_id,
                            "level": level_num,
                            "acc": acc,
                            "activity": activity,
                            "hazards": entry.hazards or "",
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed GeoNet volcano item: %s", err)

        return hazards

    async def _async_fetch_quakes(self) -> tuple[list[GeoNetQuakeEntry], dict[str, CapAlert]]:
        """Fetch GeoNet quakes, plus the CAP alerts GeoNet has issued for some of them (keyed by publicID)."""
        entries = await async_feed_entries(self._quake_feed, "GeoNet quakes")
        return entries, await self._async_geonet_cap_alerts()

    async def _async_geonet_cap_alerts(self) -> dict[str, CapAlert]:
        """Return current GeoNet quake CAP alerts by publicID.

        The CAP feed only enriches quakes, so its failure never fails the quake source: the
        last good set is used for up to ``LAST_GOOD_MAX_AGE``, then none.
        """
        now = dt_util.utcnow()
        try:
            xml_text = await self.async_fetch_feed_text(GEONET_CAP_FEED_URL, "GeoNet CAP")
            try:
                root = ET.fromstring(xml_text)
            except (ET.ParseError, ValueError) as err:
                raise ProviderUnavailableError(f"GeoNet CAP returned invalid XML: {err}") from err
            self.require_xml_root(root, "atom", "GeoNet CAP")
            entries = [(url, url, url) for entry in root.findall("atom:entry", ATOM_NS) if (url := _cap_link(entry))]
            self._geonet_cap_documents.prune({key for _, key, _ in entries})
            loaded = await self._geonet_cap_documents.async_load(
                lambda url: self.async_fetch_feed_text(url, "GeoNet CAP document"), entries
            )
        except ProviderUnavailableError as err:
            _LOGGER.debug("GeoNet CAP feed unavailable, using the last good alerts: %s", err)
            if self._geonet_cap_at is None or now - self._geonet_cap_at > LAST_GOOD_MAX_AGE:
                return {}
            return {key: alert for key, alert in self._geonet_cap.items() if _is_current(alert, now)}
        alerts: dict[str, CapAlert] = {}
        for _, alert in loaded:
            public_id = alert.parameter("PublicID")
            if public_id and _is_current(alert, now):
                alerts[public_id] = alert
        self._geonet_cap, self._geonet_cap_at = alerts, now
        return alerts

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Fetch NZTA road closures, hazards and unplanned warnings in a box around home (#24).

        The coordinator applies the radius; events without a location are dropped here, since
        an unlocated item would count as nearby for every NZ entry.
        """
        home = self._home()
        if home is None:
            return []
        radius = _float(self.config.get(CONF_RADIUS)) or DEFAULT_RADIUS
        payload = await self.async_fetch_feed_json(
            events_url(home[0], home[1], radius), "NZTA road events", headers=NZTA_HEADERS
        )
        closures: dict[str, RoadClosureItem] = {}
        for event in road_events(payload):
            try:
                if not is_disruption(event):
                    continue
                item = road_closure_item(event, home, self.parse_datetime)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed NZTA road event: %s", err)
                continue
            if item is not None:
                closures.setdefault(item.id, item)
        return list(closures.values())

    def _home(self) -> tuple[float, float] | None:
        """Return the configured home location, or None if it is not usable."""
        lat, lon = _float(self.config.get("latitude")), _float(self.config.get("longitude"))
        return (lat, lon) if lat is not None and lon is not None else None

    def _parse_nema_atom(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse the NEMA Emergency Mobile Alert Atom feed; each entry's content is a CAP alert."""
        if not xml_text.strip():
            # Even "no alerts" is a well-formed XML document; a blank body is a broken feed (#16)
            raise ProviderUnavailableError("NEMA AlertHub returned an empty response")
        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"NEMA AlertHub returned invalid XML: {err}") from err
        self.require_xml_root(root, "atom", "NEMA AlertHub")

        now = dt_util.utcnow()
        hazards: list[CanonicalHazard] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            try:
                alert = _entry_cap(entry)
                if alert is None:
                    _LOGGER.debug("NEMA AlertHub entry without a CAP alert skipped")
                    continue
                if not _is_current(alert, now):
                    continue
                title = (entry.findtext("atom:title", "", ATOM_NS) or alert.headline or alert.event).strip()
                entry_id = alert.identifier or (entry.findtext("atom:id", "", ATOM_NS) or "").strip()
                hazard = self._located_hazard(
                    hazard_id=f"nz_nema_{entry_id}" if entry_id else stable_id("nz_nema", title),
                    source="NEMA New Zealand Civil Defence",
                    agency="NEMA",
                    title=title or "Civil Defence Emergency Mobile Alert",
                    level=_nema_level(title, alert),
                    alert=alert,
                    web_url=alert.web or NEMA_WEB_URL,
                    updated_at=alert.sent or self.parse_datetime(entry.findtext("atom:updated", "", ATOM_NS)),
                )
                if hazard is None:
                    _LOGGER.debug("NEMA alert %s has no area geometry; skipped", entry_id)
                    continue
                hazards.append(hazard)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed NEMA AlertHub item: %s", err)
        return hazards

    async def _async_fetch_metservice(self) -> list[tuple[Element, CapAlert]]:
        """Fetch MetService's RSS and the CAP document each item points at (cached by guid).

        MetService's CAP Code of Practice asks consumers not to poll more often than every two
        minutes; the coordinator polls every minute during a threat, so a result younger than
        METSERVICE_MIN_POLL_INTERVAL is reused (the alerts are re-evaluated for expiry) (#62).
        """
        shared = self._metservice_shared()
        async with shared.lock:
            # Re-checked under the lock, so concurrent refreshes of several entries fetch once
            now = dt_util.utcnow()
            if shared.last is not None and now - shared.last[0] < METSERVICE_MIN_POLL_INTERVAL:
                return shared.last[1]
            alerts = await self._async_fetch_metservice_now()
            shared.last = (now, alerts)
            return alerts

    def _metservice_shared(self) -> MetServiceShared:
        """Return the integration-wide MetService poll state (per-provider without a real hass)."""
        data = getattr(self.hass, "data", None)
        if isinstance(data, dict):
            return data.setdefault(METSERVICE_SHARED_KEY, MetServiceShared())
        if not hasattr(self, "_metservice_local"):
            self._metservice_local = MetServiceShared()
        return self._metservice_local

    async def _async_fetch_metservice_now(self) -> list[tuple[Element, CapAlert]]:
        """Fetch the MetService RSS and its CAP documents."""
        rss_text = await self.async_fetch_feed_text(METSERVICE_ALERTS_URL, "MetService")
        try:
            root = ET.fromstring(rss_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"MetService returned invalid XML: {err}") from err
        self.require_xml_root(root, "rss", "MetService")
        items = root.findall("channel/item")
        entries = [
            (item, (item.findtext("guid") or "").strip(), (item.findtext("link") or "").strip()) for item in items
        ]
        self._metservice_documents.prune({key for _, key, _ in entries})
        return await self._metservice_documents.async_load(
            lambda url: self.async_fetch_feed_text(url, "MetService CAP document"), entries
        )

    def _parse_metservice(self, alerts: list[tuple[Element, CapAlert]]) -> list[CanonicalHazard]:
        """Turn current MetService alerts into hazards (with area) or weather warnings (without)."""
        now = dt_util.utcnow()
        referenced = {ref for _, alert in alerts for ref in alert.references}
        hazards: list[CanonicalHazard] = []
        weather_warnings: list[tuple[datetime | None, WeatherWarningItem]] = []
        for item, alert in alerts:
            try:
                if alert.identifier in referenced or not _is_current(alert, now):
                    continue  # superseded by an update in the feed, cancelled or expired
                title = (alert.headline or item.findtext("title") or alert.event).strip()
                hazard = self._located_hazard(
                    hazard_id=f"nz_metservice_{alert.identifier or stable_id('metservice', title)}",
                    source="MetService",
                    agency="MetService (CC BY 4.0)",
                    title=title,
                    level=_metservice_level(alert),
                    alert=alert,
                    web_url=alert.web or METSERVICE_WEB_URL,
                    updated_at=alert.sent,
                )
                if hazard is not None:
                    hazards.append(hazard)
                    continue
                warning = WeatherWarningItem(
                    title=title,
                    link=alert.web or (item.findtext("link") or "").strip() or METSERVICE_WEB_URL,
                    locations=alert.area_description or None,
                    pub_date=alert.sent,
                )
                weather_warnings.append((alert.expires, warning))
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed MetService alert: %s", err)
        self._weather_warnings = weather_warnings
        self._weather_warnings_at = now
        return hazards

    def _located_hazard(
        self,
        *,
        hazard_id: str,
        source: str,
        agency: str,
        title: str,
        level: WarningLevel,
        alert: CapAlert,
        web_url: str,
        updated_at: datetime | None,
    ) -> CanonicalHazard | None:
        """Build a hazard placed inside its CAP area, or None when the alert has no geometry."""
        lat, lon = _float(self.config.get("latitude")), _float(self.config.get("longitude"))
        location = representative_point(alert.areas, lat, lon)
        if location is None:
            return None
        colour = alert.parameter("ColourCode")
        return CanonicalHazard(
            id=hazard_id,
            source=source,
            title=title,
            hazard_type=HazardType.from_str(f"{title} {alert.event}"),
            warning_level=level,
            latitude=location[0],
            longitude=location[1],
            updated_at=updated_at,
            location_name=alert.area_description[:120] or "New Zealand",
            distance_km=area_distance_km(lat, lon, alert.areas) if lat is not None and lon is not None else None,
            status=alert.msg_type or "Alert",
            responsible_agency=agency,
            web_url=web_url,
            raw_properties={
                "cap_identifier": alert.identifier,
                "event": alert.event,
                "severity": alert.severity,
                "urgency": alert.urgency,
                "colour_code": colour or None,
                "description": alert.description or None,
                "onset": alert.onset.isoformat() if alert.onset else None,
                "expires": alert.expires.isoformat() if alert.expires else None,
            },
        )


def _entry_cap(entry: Element) -> CapAlert | None:
    """Return the CAP alert in an Atom entry's content, escaped text or inline XML."""
    content = entry.find("atom:content", ATOM_NS)
    if content is None:
        return None
    return cap_from_element(content) or parse_cap(content.text or "")


def _cap_link(entry: Element) -> str:
    """Return the URL of the CAP document an Atom entry links to (``type="application/cap+xml"``)."""
    links = entry.findall("atom:link", ATOM_NS)
    for link in links:
        if (link.get("type") or "").lower() == CAP_CONTENT_TYPE and link.get("href"):
            return str(link.get("href")).strip()
    return ""


def _is_current(alert: CapAlert, now: datetime) -> bool:
    """Return True if the alert is an actual, uncancelled, unexpired message."""
    if alert.status.lower() != "actual" or alert.msg_type.lower() == "cancel":
        return False
    return alert.expires is None or alert.expires > now


def _nema_level(title: str, alert: CapAlert) -> WarningLevel:
    """Red (or Extreme) Civil Defence alerts are emergency warnings; Severe is Watch and Act."""
    text = f"{title} {alert.headline} {alert.event}".upper()
    if "RED" in text.split() or "(RED)" in text or alert.severity.lower() == "extreme":
        return WarningLevel.EMERGENCY_WARNING
    if alert.severity.lower() == "severe":
        return WarningLevel.WATCH_AND_ACT
    return WarningLevel.ADVICE


def _metservice_level(alert: CapAlert) -> WarningLevel:
    """MetService colour code (Red/Orange/Yellow), else the CAP severity."""
    colour = alert.parameter("ColourCode").lower()
    if colour in _COLOUR_LEVELS:
        return _COLOUR_LEVELS[colour]
    return _SEVERITY_LEVELS.get(alert.severity.lower(), WarningLevel.ADVICE)


def _quake_level(magnitude: float, mmi: int, depth_km: float | None) -> WarningLevel:
    """Warning level from felt intensity (MMI); magnitude only when MMI is unknown and the quake is shallow."""
    if mmi >= 0:
        if mmi >= 6:
            return WarningLevel.EMERGENCY_WARNING
        if mmi >= 5:
            return WarningLevel.WATCH_AND_ACT
        if mmi >= 4:
            return WarningLevel.ADVICE
        return WarningLevel.INFORMATION
    if depth_km is not None and depth_km > QUAKE_SHALLOW_KM:
        return WarningLevel.INFORMATION
    if magnitude >= 6.0:
        return WarningLevel.WATCH_AND_ACT
    if magnitude >= 5.0:
        return WarningLevel.ADVICE
    return WarningLevel.INFORMATION


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
