"""Victorian road events from the DTP "Unplanned Disruptions - Road" API v3 (CC BY 4.0).

The API needs a free key from the DTP open data portal (opendata.transport.vic.gov.au), sent
in a ``KeyID`` header; without a key the endpoint answers 401 (verified 2026-10-16). The key
is an optional options-flow field: without it no request is made. Per the published OpenAPI
document the response is ``{meta{page, total_pages}, data: FeatureCollection, links}`` with
Point or LineString geometry and ``properties`` ``id``, ``eventId``, ``impactId``,
``eventLocationStatus`` (Pending/Active/Reopened/Inactive), ``status``, ``eventType``,
``eventSubType``, ``impact{impactType}``, ``closedRoadName``, ``declaredRoadName``,
``reference{localRoadName, startIntersectionLocality}``, ``description`` and ``lastUpdated``.
Rate limit: 10 calls a minute; this provider makes at most a few every four minutes.
"""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlencode

from custom_components.ausnz_disaster_watch.const import CONF_VIC_API_KEY, STATE_VIC
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory

from .base import BaseRoadProvider, first_point, is_minor_incident, mapping, text

VIC_UNPLANNED_URL = "https://api.opendata.transport.vic.gov.au/api/opendata/roads/disruptions/unplanned/v3"
VIC_LABEL = "DTP unplanned road disruptions"
VIC_SOURCE = "Department of Transport and Planning Victoria"
VIC_PAGE_SIZE = 500
VIC_MAX_PAGES = 4
_INACTIVE = {"inactive", "reopened", "cleared", "closed"}


class VictoriaRoadProvider(BaseRoadProvider):
    """Unplanned road closures, flooding and hazards from DTP Victoria (needs an API key)."""

    local_tz: ClassVar[str] = "Australia/Melbourne"
    feed_name: ClassVar[str] = VIC_LABEL

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_VIC

    @property
    def api_key(self) -> str | None:
        """Return the configured DTP key, or None when blank."""
        key = self.config.get(CONF_VIC_API_KEY)
        return key.strip() if isinstance(key, str) and key.strip() else None

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch every page of unplanned disruptions; no key means no request and no events."""
        if (key := self.api_key) is None:
            return []
        features: list[Any] = []
        for page in range(1, VIC_MAX_PAGES + 1):
            url = f"{VIC_UNPLANNED_URL}?{urlencode({'page': page, 'limit': VIC_PAGE_SIZE})}"
            payload = self.require_dict(
                await self.async_fetch_feed_json(url, VIC_LABEL, headers={"KeyID": key}), VIC_LABEL
            )
            data = payload.get("data")
            collection: dict[str, Any] = data if isinstance(data, dict) else payload
            features.extend(self.require_list(collection, "features", VIC_LABEL))
            total_pages = mapping(payload.get("meta")).get("total_pages")
            if not isinstance(total_pages, int) or page >= total_pages:
                break
        return self.collect(features, self._parse_feature)

    def _parse_feature(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        location_status = text(props.get("eventLocationStatus")).lower()
        if location_status in _INACTIVE or text(props.get("status")).lower() in _INACTIVE:
            return None
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        raw_id = text(props.get("id")) or "_".join(
            part for part in (text(props.get("eventId")), text(props.get("impactId"))) if part
        )
        if not raw_id:
            raise ValueError("disruption without id")
        event_type = text(props.get("eventType"))
        subtype = text(props.get("eventSubType"))
        impact_type = text(mapping(props.get("impact")).get("impactType"))
        reference = mapping(props.get("reference"))

        if "flood" in f"{event_type} {subtype}".lower():
            category = RoadEventCategory.FLOODING
        elif "road closed" in impact_type.lower() or impact_type.lower() in ("closed", "road closure"):
            # "Lanes closed" is a hazard on an open road, not a closure
            category = RoadEventCategory.CLOSURE
        elif is_minor_incident(event_type, subtype):
            return None
        else:
            category = RoadEventCategory.HAZARD

        return RoadClosureItem(
            id=f"VIC_{raw_id}",
            road=text(props.get("closedRoadName"))
            or text(props.get("declaredRoadName"))
            or text(reference.get("localRoadName"))
            or event_type
            or "Road",
            suburb=text(reference.get("startIntersectionLocality")),
            status=impact_type or text(props.get("status")) or event_type or "Hazard",
            reason=subtype or event_type or None,
            description=text(props.get("description")) or None,
            source=VIC_SOURCE,
            updated_at=self.parse_datetime(props.get("lastUpdated")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )
