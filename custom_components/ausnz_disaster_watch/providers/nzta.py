"""NZ Transport Agency Waka Kotahi road events from the Traffic Application Server (#24).

``trafficnz.info/service/traffic/rest/4`` is NZTA's open, keyless successor to InfoConnect.
Events are requested for a bounding box around home (``events/withinbounds``), so a poll
transfers only nearby events instead of the whole country (~370 kB). With
``Accept: application/json`` the body is ``{"response": {"roadevent": [...]}}``; a single
event is an object instead of a list, and no events is ``{"response": ""}``.

Only current disruptions are kept: closures (``impact`` "Road Closed"), road hazards
(crashes, slips, fallen trees) and unplanned area warnings (flooding, snow, washouts).
Planned roadworks with only caution or delays, and resolved or scheduled events, are dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import math
import re
from typing import Any

from custom_components.ausnz_disaster_watch.models import RoadClosureItem

from .base import ProviderUnavailableError, stable_id
from .cap import haversine_km

NZTA_EVENTS_URL = (
    "https://trafficnz.info/service/traffic/rest/4/events/withinbounds/{min_lon}/{min_lat}/{max_lon}/{max_lat}/10"
)
NZTA_SOURCE = "NZ Transport Agency Waka Kotahi"
NZTA_HEADERS = {"Accept": "application/json"}

_HAZARD_EVENT_TYPES = {"road hazard", "road closure"}
_INACTIVE_STATUSES = {"resolved", "scheduled"}
_NOT_APPLICABLE = {"", "not applicable", "n/a", "na", "none"}
_WKT_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")

type LatLon = tuple[float, float]


def events_url(lat: float, lon: float, radius_km: float) -> str:
    """Return the events URL for a box that contains the circle of ``radius_km`` around home."""
    d_lat = radius_km / 111.0
    d_lon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return NZTA_EVENTS_URL.format(
        min_lon=round(lon - d_lon, 4),
        min_lat=round(lat - d_lat, 4),
        max_lon=round(lon + d_lon, 4),
        max_lat=round(lat + d_lat, 4),
    )


def road_events(payload: Any) -> list[dict[str, Any]]:
    """Return the event objects in a response; raise ProviderUnavailableError for a foreign document."""
    response = payload.get("response") if isinstance(payload, dict) else None
    if response is None:
        raise ProviderUnavailableError("NZTA road events returned an unexpected payload")
    if not response:
        return []  # "" or {}: no events in the box
    if not isinstance(response, dict):
        raise ProviderUnavailableError("NZTA road events returned an unexpected payload")
    events = response.get("roadevent") or []
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list):
        raise ProviderUnavailableError("NZTA road events returned an unexpected payload")
    return [event for event in events if isinstance(event, dict)]


def is_disruption(event: dict[str, Any]) -> bool:
    """Return True for a current closure, road hazard or unplanned warning."""
    if str(event.get("status") or "").strip().lower() in _INACTIVE_STATUSES:
        return False
    if "closed" in str(event.get("impact") or "").lower():
        return True
    if str(event.get("eventType") or "").strip().lower() in _HAZARD_EVENT_TYPES:
        return True
    return event.get("planned") is False


def wkt_points(geometry: Any) -> list[LatLon]:
    """Return the ``(lat, lon)`` vertices of a WKT POINT, LINESTRING or MULTILINESTRING."""
    if not isinstance(geometry, str):
        return []
    points: list[LatLon] = []
    for lon_s, lat_s in _WKT_PAIR.findall(geometry):
        lat, lon = float(lat_s), float(lon_s)
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            points.append((lat, lon))
    return points


def _location(points: list[LatLon], home: LatLon | None) -> LatLon | None:
    """The vertex nearest home (a long closure can start inside the radius), else the first."""
    if not points:
        return None
    if home is None:
        return points[0]
    return min(points, key=lambda point: haversine_km(home[0], home[1], point[0], point[1]))


def _name(value: Any) -> str:
    """Return a ``journey``/``way``/``region`` name, which the API nests as ``{"name": ...}``."""
    if isinstance(value, dict):
        value = value.get("name")
    return str(value).strip() if value else ""


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return None if text.lower().rstrip(".") in _NOT_APPLICABLE else text


def road_closure_item(
    event: dict[str, Any], home: LatLon | None, parse_datetime: Callable[[Any], datetime | None]
) -> RoadClosureItem | None:
    """Map one road event to a RoadClosureItem, or None when it has no usable location."""
    location = _location(wkt_points(event.get("geometry")), home)
    if location is None:
        return None
    event_id = event.get("id") or event.get("eventId")
    area = str(event.get("locationArea") or "").strip()
    return RoadClosureItem(
        id=f"NZTA_{event_id}"
        if event_id
        else stable_id("NZTA", event.get("eventType"), event.get("geometry"), event.get("startDate")),
        road=_name(event.get("journey")) or _name(event.get("way")) or area or str(event.get("eventType") or ""),
        suburb=area or _name(event.get("region")),
        status=str(event.get("impact") or event.get("status") or "Active"),
        reason=_text(event.get("eventDescription")) or _text(event.get("eventType")),
        description=_text(event.get("eventComments")),
        advice=_text(event.get("alternativeRoute")),
        source=NZTA_SOURCE,
        updated_at=parse_datetime(event.get("eventModified")) or parse_datetime(event.get("startDate")),
        latitude=location[0],
        longitude=location[1],
    )
