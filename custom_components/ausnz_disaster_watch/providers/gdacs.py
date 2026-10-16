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

from typing import TYPE_CHECKING

from aio_georss_client.consts import UPDATE_OK
from aio_georss_gdacs import GdacsFeed

from custom_components.ausnz_disaster_watch.models import RegionalAlertItem

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError

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
        alert_level=entry.alert_level,
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


async def async_fetch_regional_alerts(
    session: aiohttp.ClientSession, lat: float, lon: float
) -> list[RegionalAlertItem]:
    """Fetch current regional GDACS alerts; raise ProviderUnavailableError if the feed fails."""
    status, entries = await GdacsFeed(session, (lat, lon)).update()
    # The library returns OK_NO_DATA for an unparsable document and OK without entries when
    # nothing was read: both are outages, not an empty feed.
    if status != UPDATE_OK or entries is None:
        raise ProviderUnavailableError(f"GDACS feed unavailable ({status})")
    alerts: list[RegionalAlertItem] = []
    for entry in entries:
        try:
            if (alert := regional_alert(entry)) is not None:
                alerts.append(alert)
        except MALFORMED_ITEM_ERRORS:
            continue
    alerts.sort(key=lambda alert: alert.distance_km or 0.0)
    return alerts
