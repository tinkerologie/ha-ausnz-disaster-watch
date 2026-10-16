"""Queensland road events from the keyless QLDTraffic GeoJSON feed (TMR, CC BY 4.0).

``https://data.qldtraffic.qld.gov.au/events_v2.geojson`` (verified 2026-10-16, ~490 events,
gzip ~440 KB) is a FeatureCollection; each feature's ``properties`` has ``id``,
``status`` (Published), ``event_type`` (Roadworks, Hazard, Flooding, Crash, Congestion,
Special event), ``event_subtype``, ``event_due_to``, ``impact{impact_type, impact_subtype}``,
``road_summary{road_name, locality}``, ``description``, ``advice``, ``last_updated`` (ISO
with offset) and ``source{provided_by}``. Geometry is MultiLineString, MultiPoint or a
GeometryCollection.

Council Guardian dashboards republish the same QLDTraffic events (``tmrRoadData``) as
``TMR_<id>``; this feed uses the same IDs so the coordinator drops the duplicates.
"""

from __future__ import annotations

from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_QLD
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory

from .base import BaseRoadProvider, first_point, is_minor_incident, mapping, text

QLDTRAFFIC_EVENTS_URL = "https://data.qldtraffic.qld.gov.au/events_v2.geojson"
QLDTRAFFIC_LABEL = "QLDTraffic events"


def _known(value: Any) -> str:
    """Return the field as text, with QLDTraffic's "N/A" placeholder read as empty."""
    value_text = text(value)
    return "" if value_text.upper() == "N/A" else value_text


class QueenslandRoadProvider(BaseRoadProvider):
    """Road closures, flooding and hazards from QLDTraffic."""

    local_tz: ClassVar[str] = "Australia/Brisbane"
    feed_name: ClassVar[str] = QLDTRAFFIC_LABEL

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_QLD

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch and parse the statewide QLDTraffic event feed."""
        payload = self.require_dict(
            await self.async_fetch_feed_json(QLDTRAFFIC_EVENTS_URL, QLDTRAFFIC_LABEL), QLDTRAFFIC_LABEL
        )
        return self.collect(self.require_list(payload, "features", QLDTRAFFIC_LABEL), self._parse_feature)

    def _parse_feature(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        status = text(props.get("status"))
        if status and status != "Published":
            return None
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        raw_id = props.get("id") if props.get("id") is not None else feature.get("id")
        if raw_id is None or not text(raw_id):
            raise ValueError("event without id")
        event_type = _known(props.get("event_type"))
        subtype = _known(props.get("event_subtype"))
        impact = mapping(props.get("impact"))
        impact_type = _known(impact.get("impact_type"))
        impact_subtype = _known(impact.get("impact_subtype"))
        kind = event_type.lower()

        if kind == "flooding":
            category = RoadEventCategory.FLOODING
        elif kind == "roadworks":
            category = RoadEventCategory.ROADWORKS
        elif kind == "special event":
            category = RoadEventCategory.SPECIAL_EVENT
        elif impact_type.lower() == "closures" or impact_subtype.lower().startswith("road closed"):
            category = RoadEventCategory.CLOSURE
        elif kind == "congestion" or is_minor_incident(subtype, _known(props.get("event_due_to"))):
            return None
        else:
            category = RoadEventCategory.HAZARD

        summary = mapping(props.get("road_summary"))
        due_to = _known(props.get("event_due_to"))
        provided_by = text(mapping(props.get("source")).get("provided_by"))
        return RoadClosureItem(
            id=f"TMR_{text(raw_id)}",
            road=text(summary.get("road_name")) or event_type or "Road",
            suburb=text(summary.get("locality")),
            status=impact_subtype or impact_type or event_type or "Hazard",
            reason=", ".join(part for part in (subtype, due_to) if part) or event_type,
            description=text(props.get("description")) or None,
            advice=text(props.get("advice")) or None,
            source=f"QLDTraffic ({provided_by})" if provided_by else "QLDTraffic (TMR)",
            updated_at=self.parse_datetime(props.get("last_updated")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )
