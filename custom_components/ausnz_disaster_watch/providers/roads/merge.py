"""Combine statewide road feed items with council road items (#29)."""

from __future__ import annotations

from collections.abc import Iterable
import math
import re

from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory

from .base import is_minor_incident

# Guardian council dashboards republish QLDTraffic events as TMR_<id> (tmrRoadData) and
# council events as COUNCIL_<id> (imsRoad); the numeric part is the QLDTraffic event ID.
_EVENT_ID_RE = re.compile(r"^(?:TMR|COUNCIL)_(\d{4,})$")
_SAME_EVENT_KM = 5.0
_SAME_PLACE_KM = 1.0


def approx_km(a: RoadClosureItem, b: RoadClosureItem) -> float | None:
    """Return the approximate distance between two located items (equirectangular), else None."""
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return None
    mean_lat = math.radians((a.latitude + b.latitude) / 2)
    dx = math.radians(b.longitude - a.longitude) * math.cos(mean_lat)
    dy = math.radians(b.latitude - a.latitude)
    return 6371.0 * math.hypot(dx, dy)


def _event_id(item: RoadClosureItem) -> str | None:
    match = _EVENT_ID_RE.match(item.id)
    return match.group(1) if match else None


def _duplicates(council: RoadClosureItem, statewide: RoadClosureItem) -> bool:
    """Return True if a council item reports the same event as a statewide item."""
    distance = approx_km(council, statewide)
    if (event := _event_id(council)) is not None and event == _event_id(statewide):
        return distance is None or distance <= _SAME_EVENT_KM
    return (
        bool(council.road)
        and council.road.casefold() == statewide.road.casefold()
        and council.suburb.casefold() == statewide.suburb.casefold()
        and council.category == statewide.category
        and distance is not None
        and distance <= _SAME_PLACE_KM
    )


def merge_road_items(
    statewide: Iterable[RoadClosureItem],
    council: Iterable[RoadClosureItem],
    include_roadworks: bool,
) -> list[RoadClosureItem]:
    """Return statewide items, then council items that are not already reported; IDs are unique.

    Planned roadworks and special events are dropped unless ``include_roadworks``, and council
    hazards that are routine traffic noise (signal faults, breakdowns) are dropped as the
    statewide feeds drop them. A council item duplicates a statewide one when it has the same ID, the same QLDTraffic event ID
    within a few km, or the same road, suburb and category within 1 km.
    """
    kept: list[RoadClosureItem] = []
    ids: set[str] = set()
    for item in statewide:
        if (include_roadworks or not item.is_planned) and item.id not in ids:
            ids.add(item.id)
            kept.append(item)
    statewide_kept = list(kept)
    for item in council:
        if (not include_roadworks and item.is_planned) or item.id in ids:
            continue
        if item.category == RoadEventCategory.HAZARD and is_minor_incident(item.status, item.reason):
            continue
        if any(_duplicates(item, other) for other in statewide_kept):
            continue
        ids.add(item.id)
        kept.append(item)
    return kept
