"""NSW road events from the Live Traffic NSW hazard feeds (Transport for NSW, CC BY 4.0).

Keyless GeoJSON, verified 2026-10-16: ``/traffic/hazards/{incident,flood,fire,alpine}.json``
plus council-reported events in ``regional/lga-incidents.json``. ``roadwork.json`` and
``majorevent.json`` are fetched only when planned roadworks are included. Each feature has a
numeric ``id`` (sometimes a float such as ``164430.0``), a Point geometry and ``properties``
with ``mainCategory``, ``displayName``, ``incidentKind`` (Planned/Unplanned), ``ended``,
``lastUpdated`` (epoch ms), ``adviceA/B/C`` and ``roads[]`` (``mainStreet``, ``crossStreet``,
``suburb``, ``impactedLanes[].extent`` of ``Closed``, ``Lanes closed`` or ``Affected``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_NSW
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory

from .base import BaseRoadProvider, first_point, is_minor_incident, text

LIVE_TRAFFIC_URL = "https://www.livetraffic.com/traffic/hazards/{}.json"
LIVE_TRAFFIC_SOURCE = "Transport for NSW (Live Traffic NSW)"

# (feed path, ID prefix); hazard feeds are always read
NSW_HAZARD_FEEDS: tuple[tuple[str, str], ...] = (
    ("incident", "NSW"),
    ("flood", "NSW"),
    ("fire", "NSW"),
    ("alpine", "NSW"),
    ("regional/lga-incidents", "NSW_LGA"),
)
NSW_PLANNED_FEEDS: tuple[tuple[str, str], ...] = (("roadwork", "NSW"), ("majorevent", "NSW"))


def _upstream_id(value: Any) -> str:
    """Return the feature ID as text, without the ``.0`` some features carry."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if value is None or isinstance(value, bool) or not text(value):
        raise ValueError("feature without id")
    return text(value)


class NSWRoadProvider(BaseRoadProvider):
    """Road closures, flooding and hazards from Live Traffic NSW."""

    local_tz: ClassVar[str] = "Australia/Sydney"
    feed_name: ClassVar[str] = "Live Traffic NSW"

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_NSW

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch the Live Traffic hazard feeds concurrently."""
        feeds = NSW_HAZARD_FEEDS + (NSW_PLANNED_FEEDS if self.include_roadworks else ())
        return await self.async_collect_road_sources(self._source(path, prefix) for path, prefix in feeds)

    def _source(
        self, path: str, prefix: str
    ) -> tuple[str, Callable[[], Awaitable[Any]], Callable[[Any], list[RoadClosureItem]]]:
        """Return the (label, fetch, parse) triple for one Live Traffic feed."""
        label = f"Live Traffic NSW {path}"

        async def fetch() -> Any:
            return await self.async_fetch_feed_json(LIVE_TRAFFIC_URL.format(path), label)

        def parse(payload: Any) -> list[RoadClosureItem]:
            features = self.require_list(self.require_dict(payload, label), "features", label)
            return self.collect(features, lambda feature: self._parse_feature(feature, path, prefix))

        return label, fetch, parse

    def _parse_feature(self, feature: dict[str, Any], path: str, prefix: str) -> RoadClosureItem | None:
        props = feature["properties"]
        if props.get("ended") is True:
            return None
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        main_category = text(props.get("mainCategory")).upper()
        display = text(props.get("displayName")) or main_category.title()
        roads = [r for r in props.get("roads") or [] if isinstance(r, dict)]
        road = roads[0] if roads else {}
        extents = [
            text(lane.get("extent")).lower()
            for r in roads
            for lane in r.get("impactedLanes") or []
            if isinstance(lane, dict)
        ]
        closed = "closed" in extents
        planned = text(props.get("incidentKind")).lower() == "planned"

        if path == "flood" or "FLOOD" in main_category:
            category = RoadEventCategory.FLOODING
        elif "EVENT" in main_category and planned:
            category = RoadEventCategory.SPECIAL_EVENT
        elif planned or path == "roadwork":
            category = RoadEventCategory.ROADWORKS
        elif closed:
            category = RoadEventCategory.CLOSURE
        elif is_minor_incident(main_category, display):
            return None
        else:
            category = RoadEventCategory.HAZARD

        main_street = text(road.get("mainStreet"))
        cross = text(road.get("crossStreet"))
        qualifier = text(road.get("locationQualifier"))
        location = " ".join(part for part in (main_street, qualifier, cross) if part) if cross else main_street
        sub_category = text(props.get("subCategoryA"))
        advice = ". ".join(a for a in (text(props.get(k)) for k in ("adviceA", "adviceB", "adviceC")) if a)
        source = LIVE_TRAFFIC_SOURCE
        if prefix == "NSW_LGA" and (org := text(props.get("OrgName"))):
            source = f"{org} (Live Traffic NSW)"
        return RoadClosureItem(
            id=f"{prefix}_{_upstream_id(feature.get('id'))}",
            road=main_street or display,
            suburb=text(road.get("suburb")),
            status="Closed" if closed else (next((e for e in extents if e), "") or display).capitalize(),
            reason=display.capitalize() + (f" ({sub_category})" if sub_category and sub_category != "null" else ""),
            description=text(props.get("headline")) or location or None,
            advice=advice or None,
            source=source,
            updated_at=self.parse_datetime(props.get("lastUpdated")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )
