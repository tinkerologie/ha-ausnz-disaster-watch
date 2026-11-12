"""GDACS (Global Disaster Alert and Coordination System) alerts around Australia and New Zealand.

Uses ``aio_georss_gdacs`` (the library behind Home Assistant's ``gdacs`` integration) with
the shared aiohttp session. ``GdacsFeed.update()`` is called directly, not through the feed
manager, because the manager reports every entry as removed when a fetch fails.

GDACS alerts are regional context (for example a cyclone before BoM issues warnings), not
local warnings: they never become hazards, so they cannot change counts, warning levels or
polling. Only current Orange and Red alerts inside the region box are kept. GDACS content
is (c) European Union / JRC and is indicative only.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from aio_georss_client.consts import UPDATE_OK
from aio_georss_gdacs import GdacsFeed

from custom_components.ausnz_disaster_watch.models import RegionalAlertItem

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError

if TYPE_CHECKING:
    from aio_georss_gdacs.feed_entry import GdacsFeedEntry
    import aiohttp

GDACS_ALERT_LEVELS = ("Orange", "Red")
GDACS_REPORT_URL = "https://www.gdacs.org/report.aspx?eventtype={type}&eventid={id}"
# Episode geometry (GeoJSON: tropical cyclone track, wind buffers and cone), fetched by the
# map card in the browser (#71), never by the integration: about 300 kB per cyclone.
GDACS_GEOMETRY_URL = (
    "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype={type}&eventid={id}&episodeid={episode}"
)
XML_TAG_GDACS_EPISODE_ID = "gdacs:episodeid"

# Region box: Australia, New Zealand and nearby seas. The NZ region crosses the
# antimeridian (Kermadec Islands, Tonga), so longitudes down to -170 are included too.
REGION_LAT = (-50.0, -9.0)
REGION_LON = (110.0, 180.0)
REGION_LON_EAST_OF_ANTIMERIDIAN = (-180.0, -170.0)


def in_region(lat: float, lon: float) -> bool:
    """Return True if a point is inside the Australia/New Zealand region box."""
    if not REGION_LAT[0] <= lat <= REGION_LAT[1]:
        return False
    return REGION_LON[0] <= lon <= REGION_LON[1] or (
        REGION_LON_EAST_OF_ANTIMERIDIAN[0] <= lon <= REGION_LON_EAST_OF_ANTIMERIDIAN[1]
    )


def episode_id(entry: GdacsFeedEntry) -> int | None:
    """Return the entry's GDACS episode ID (``gdacs:episodeid``), or None."""
    # aio-georss-gdacs has no accessor for the episode, so read the raw RSS item it wraps.
    rss_entry = getattr(entry, "_rss_entry", None)
    if rss_entry is None:
        return None
    value = rss_entry.get_additional_attribute(XML_TAG_GDACS_EPISODE_ID)
    if not isinstance(value, str) or not value.strip().isdigit():
        return None
    return int(value)


def regional_alert(entry: GdacsFeedEntry) -> RegionalAlertItem | None:
    """Return a regional alert for a current Orange/Red entry inside the region, else None."""
    if entry.is_current is not True or entry.alert_level not in GDACS_ALERT_LEVELS:
        return None
    coordinates = entry.coordinates
    if coordinates is None or not in_region(*coordinates):
        return None
    return _event(entry, coordinates)


def _event(entry: GdacsFeedEntry, coordinates: tuple[float, float]) -> RegionalAlertItem:
    url = geometry_url = None
    episode = episode_id(entry)
    if entry.event_type_short and entry.event_id is not None:
        url = GDACS_REPORT_URL.format(type=entry.event_type_short, id=entry.event_id)
        if episode is not None:
            geometry_url = GDACS_GEOMETRY_URL.format(type=entry.event_type_short, id=entry.event_id, episode=episode)
    return RegionalAlertItem(
        id=f"gdacs_{entry.external_id}",
        title=entry.title or entry.event_name or "GDACS alert",
        event_type=entry.event_type,
        alert_level=entry.alert_level or "Unknown",
        severity=entry.severity,
        country=entry.country,
        latitude=coordinates[0],
        longitude=coordinates[1],
        from_date=entry.from_date,
        to_date=entry.to_date,
        url=url,
        distance_km=round(entry.distance_to_home, 1),
        event_type_code=entry.event_type_short,
        event_id=entry.event_id,
        episode_id=episode,
        geometry_url=geometry_url,
    )


def cyclone_events(entries: list[GdacsFeedEntry]) -> list[RegionalAlertItem]:
    """Select current cyclone centres in the Australian and southwest Pacific basins."""
    current: dict[int, RegionalAlertItem] = {}
    for entry in entries:
        try:
            if entry.event_type_short != "TC" or not entry.is_current or entry.event_id is None:
                continue
            coordinates = entry.coordinates
            if coordinates is None:
                continue
            lat, lon = coordinates
            if not (-40 <= lat <= 0 and (90 <= lon <= 180 or -180 <= lon <= -120)):
                continue
            event = _event(entry, coordinates)
            raw = getattr(entry, "_rss_entry", None)
            updated = (
                BaseHazardProvider.parse_datetime(raw.get_additional_attribute("gdacs:datemodified")) if raw else None
            )
            event = replace(
                event,
                id=f"gdacs_TC{entry.event_id}",
                title=entry.event_name or event.title,
                updated_at=updated or event.from_date,
            )
            previous = current.get(entry.event_id)
            if previous is None or (event.episode_id or 0) > (previous.episode_id or 0):
                current[entry.event_id] = event
        except MALFORMED_ITEM_ERRORS:
            continue
    return sorted(current.values(), key=lambda event: event.distance_km or 0.0)


async def async_fetch_entries(session: aiohttp.ClientSession, lat: float, lon: float) -> list[GdacsFeedEntry]:
    """Fetch one shared GDACS feed for the two projections."""
    status, entries = await GdacsFeed(session, (lat, lon)).update()
    if status != UPDATE_OK or entries is None:
        raise ProviderUnavailableError(f"GDACS feed unavailable ({status})")
    return entries


def regional_alerts(entries: list[GdacsFeedEntry]) -> list[RegionalAlertItem]:
    """Project the existing Orange/Red regional alerts."""
    alerts: list[RegionalAlertItem] = []
    for entry in entries:
        try:
            if (alert := regional_alert(entry)) is not None:
                alerts.append(alert)
        except MALFORMED_ITEM_ERRORS:
            continue
    return sorted(alerts, key=lambda alert: alert.distance_km or 0.0)


async def async_fetch_regional_alerts(
    session: aiohttp.ClientSession, lat: float, lon: float
) -> list[RegionalAlertItem]:
    """Fetch the regional alerts projection."""
    return regional_alerts(await async_fetch_entries(session, lat, lon))
