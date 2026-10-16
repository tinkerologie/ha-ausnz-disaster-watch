"""West Australian road events from Main Roads WA WebEOC feature layers (CC BY 4.0).

``services2.arcgis.com/cHGEnmsJ165IBJRM/arcgis/rest/services/WebEocFeatureLayerViewPRD/FeatureServer``
(keyless, verified 2026-10-16; the data behind the Main Roads Travel Map; attribution to the
Commissioner of Main Roads):

- layer 1 RoadIncidents (points) and layer 4 RoadClosures (lines), filtered with
  ``publishExt='Yes'``: ``Id`` (shared by an incident and its closure line), ``IncidentTy``
  (e.g. "Pothole / Road Surface Damage", "Flooding", "Break Down / Tow Away"), ``ClosureTyp``
  ("Road closed", "Road open with caution", ...), ``TrafficCon``, ``Road``,
  ``LocalRoadName``, ``Suburb``, ``Region``, ``Location``, ``TrafficImp`` and ``UpdateDate``
  (``dd/mm/yyyy HH:MM:SS``, Perth time);
- layer 2 Roadworks (``WorkType``, ``Descriptio``, ``DateStarte``, ``EstimatedC``) and layer 0
  Events (``EventName``, ``EventType``, ``EventDescr``, ``DateTimeSt``, ``DateTimeEn``), only
  when planned roadworks are included.

DFES ``api.emergency.wa.gov.au/v1/outages-closures`` is not used: it lists facility and park
closures, not roads, and its reuse terms are unverified.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_WA
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory
from homeassistant.util import dt as dt_util

from .base import BaseRoadProvider, first_point, is_minor_incident, text

WA_WEBEOC_URL = (
    "https://services2.arcgis.com/cHGEnmsJ165IBJRM/arcgis/rest/services/WebEocFeatureLayerViewPRD/FeatureServer"
)
WA_SOURCE = "Main Roads WA"


class WARoadProvider(BaseRoadProvider):
    """Road closures, flooding and incidents (and optionally roadworks and events) from Main Roads WA."""

    local_tz: ClassVar[str] = "Australia/Perth"
    feed_name: ClassVar[str] = "Main Roads WA"

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_WA

    def _layer(
        self, layer: int, label: str, where: str, parse: Callable[[dict[str, Any]], RoadClosureItem | None]
    ) -> tuple[str, Callable[[], Awaitable[Any]], Callable[[Any], list[RoadClosureItem]]]:
        async def fetch() -> Any:
            return await self.async_arcgis_query(f"{WA_WEBEOC_URL}/{layer}", label, where)

        return label, fetch, lambda features: self.collect(features, parse)

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Query the incident and closure layers (and planned layers if enabled) within the radius box."""
        published = "publishExt='Yes'"
        sources = [
            self._layer(1, "Main Roads WA incidents", published, self._parse_incident),
            self._layer(4, "Main Roads WA closures", published, self._parse_incident),
        ]
        if self.include_roadworks:
            sources.append(self._layer(2, "Main Roads WA roadworks", "1=1", self._parse_roadworks))
            sources.append(self._layer(0, "Main Roads WA events", "1=1", self._parse_event))
        return await self.async_collect_road_sources(sources)

    @staticmethod
    def _upstream_id(feature: dict[str, Any], props: dict[str, Any]) -> str:
        raw_id = text(props.get("Id")) or text(feature.get("id"))
        if not raw_id:
            raise ValueError("record without id")
        return raw_id

    def _parse_incident(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        incident = text(props.get("IncidentTy"))
        closure = text(props.get("ClosureTyp"))
        condition = text(props.get("TrafficCon"))
        location = " ".join(text(props.get("Location")).split())
        closure_l = closure.lower()
        # ClosureTyp ("Road closed", "Road open with caution") wins over TrafficCon, which can
        # say "Road Closure" for a road that is open with caution
        if closure:
            closed = ("closed" in closure_l or "closes" in closure_l) and "open" not in closure_l
        else:
            closed = "closure" in condition.lower()

        if "flood" in f"{incident} {location}".lower():
            category = RoadEventCategory.FLOODING
        elif closed:
            category = RoadEventCategory.CLOSURE
        elif is_minor_incident(incident):
            return None
        else:
            category = RoadEventCategory.HAZARD

        return RoadClosureItem(
            id=f"WA_{self._upstream_id(feature, props)}",
            road=text(props.get("Road")) or text(props.get("LocalRoadName")) or "Road",
            suburb=text(props.get("Suburb")) or text(props.get("Region")),
            status=closure or condition or incident or "Hazard",
            reason=incident or None,
            description=location or None,
            advice=text(props.get("TrafficImp")) or None,
            source=WA_SOURCE,
            updated_at=self.parse_datetime(props.get("UpdateDate") or props.get("EntryDate")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )

    def _current(self, start: Any, end: Any) -> bool:
        """Return True if a planned item has started and not yet finished."""
        now = dt_util.utcnow()
        start_at, end_at = self.parse_datetime(start), self.parse_datetime(end)
        return (start_at is None or start_at <= now) and (end_at is None or end_at >= now)

    def _parse_roadworks(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        point = first_point(feature.get("geometry"))
        if point is None or not self._current(props.get("DateStarte"), props.get("EstimatedC")):
            return None
        road = text(props.get("Road"))
        return RoadClosureItem(
            id=f"WA_RW_{self._upstream_id(feature, props)}",
            road=(text(props.get("LocalRoadName")) if road.upper() == "LOCAL ROAD" else road) or "Road",
            suburb=text(props.get("Suburb")) or text(props.get("Region")),
            status=text(props.get("TrafficImp")) or "Roadworks",
            reason=text(props.get("WorkType")) or "Roadworks",
            description=" ".join(text(props.get("Descriptio")).split()) or None,
            source=WA_SOURCE,
            updated_at=self.parse_datetime(props.get("EntryDate")),
            latitude=point[0],
            longitude=point[1],
            category=RoadEventCategory.ROADWORKS,
        )

    def _parse_event(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        point = first_point(feature.get("geometry"))
        if point is None or not self._current(props.get("DateTimeSt"), props.get("DateTimeEn")):
            return None
        return RoadClosureItem(
            id=f"WA_EVENT_{self._upstream_id(feature, props)}",
            road=text(props.get("Road")) or text(props.get("LocalRoadN")) or "Road",
            suburb=text(props.get("Suburb")) or text(props.get("Region")),
            status=text(props.get("TrafficImp")) or "Special event",
            reason=text(props.get("EventType")) or "Special event",
            description=" ".join(
                (text(props.get("EventName")) + ": " + text(props.get("EventDescr"))).strip(": ").split()
            )
            or None,
            source=WA_SOURCE,
            updated_at=self.parse_datetime(props.get("EntryDate")),
            latitude=point[0],
            longitude=point[1],
            category=RoadEventCategory.SPECIAL_EVENT,
        )
