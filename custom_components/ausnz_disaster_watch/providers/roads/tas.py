"""Tasmanian road closures from TasALERT (Department of Premier and Cabinet).

``https://alert.tas.gov.au/proxy/road-closures`` (keyless) is a GeoJSON FeatureCollection,
empty on 2026-10-16. An archived populated response (November 2025) has LineString features
without IDs and ``properties`` ``RoadName``, ``AffectedLocation``, ``Status`` ("No Access",
"Authorised Access (incl. Local Access)"), ``AccessLevel``, ``Reason``, ``ExpectedOpening``
and ``DateReviewed`` (epoch ms). Every feature is a closure to general traffic.

Reuse terms for this endpoint are unverified (TasALERT publishes no data licence page).
"""

from __future__ import annotations

from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_TAS
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory
from custom_components.ausnz_disaster_watch.providers.base import stable_id

from .base import BaseRoadProvider, first_point, text

TAS_ROAD_CLOSURES_URL = "https://alert.tas.gov.au/proxy/road-closures"
TAS_LABEL = "TasALERT road closures"
TAS_SOURCE = "TasALERT"


class TasmaniaRoadProvider(BaseRoadProvider):
    """Road closures from TasALERT."""

    local_tz: ClassVar[str] = "Australia/Hobart"
    feed_name: ClassVar[str] = TAS_LABEL

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_TAS

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch and parse the TasALERT road closure layer."""
        payload = self.require_dict(await self.async_fetch_feed_json(TAS_ROAD_CLOSURES_URL, TAS_LABEL), TAS_LABEL)
        return self.collect(self.require_list(payload, "features", TAS_LABEL), self._parse_feature)

    def _parse_feature(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        road = text(props.get("RoadName"))
        location = " ".join(text(props.get("AffectedLocation")).split())
        reason = " ".join(text(props.get("Reason")).split())
        status = text(props.get("Status"))
        raw_id = text(feature.get("id")) or text(props.get("id"))
        if not raw_id and not (road or location):
            raise ValueError("closure without id or road")

        if "flood" in f"{reason} {status}".lower():
            category = RoadEventCategory.FLOODING
        elif "event" in reason.lower():
            category = RoadEventCategory.SPECIAL_EVENT
        else:
            category = RoadEventCategory.CLOSURE

        expected = text(props.get("ExpectedOpening"))
        return RoadClosureItem(
            id=f"TAS_{raw_id}" if raw_id else stable_id("TAS", road, location),
            road=road or "Road",
            suburb=location,
            status=status or "Closed",
            reason=reason or None,
            description=f"Expected opening: {expected}" if expected else None,
            source=TAS_SOURCE,
            updated_at=self.parse_datetime(props.get("DateReviewed")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )
