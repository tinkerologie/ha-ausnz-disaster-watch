"""Northern Territory road events from NT Road Report (Department of Logistics and Infrastructure).

``https://roadreport.nt.gov.au/api/Obstruction/GetAll`` (keyless, verified 2026-10-16, ~80
rows) returns ``{success, message, response: [...]}``. Each row has ``recordId``,
``obstructionId``, ``status`` (CURRENT), ``roadName``, ``obstructionType`` (Flooding,
Roadworks, Road Damage, weight limits, ...), ``restrictionType`` (Road Closed, Impassable,
With Caution, High Clearance 4WD, Weight And Or Vehicle Type Restriction, ...),
``comment``, ``locationComment``, ``dateLastUpdated`` (naive ``YYYY-MM-DD HH:MM:SS``, Darwin
time) and ``startPoint``/``endPoint`` given as **[latitude, longitude]**, not GeoJSON order.

Reuse terms are unverified: the site's copyright page is a script-rendered shell.
"""

from __future__ import annotations

from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_NT
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory

from .base import BaseRoadProvider, text, valid_point

NT_ROAD_REPORT_URL = "https://roadreport.nt.gov.au/api/Obstruction/GetAll"
NT_LABEL = "NT Road Report"
NT_SOURCE = "NT Road Report"


def nt_point(value: Any) -> tuple[float, float] | None:
    """Read an NT Road Report point, which is ``[latitude, longitude]``."""
    if isinstance(value, list) and len(value) >= 2:
        return valid_point(value[0], value[1])
    return None


class NTRoadProvider(BaseRoadProvider):
    """Road closures, flooding and hazards from NT Road Report."""

    local_tz: ClassVar[str] = "Australia/Darwin"
    feed_name: ClassVar[str] = NT_LABEL

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_NT

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Fetch and parse every current obstruction."""
        payload = self.require_dict(await self.async_fetch_feed_json(NT_ROAD_REPORT_URL, NT_LABEL), NT_LABEL)
        return self.collect(self.require_list(payload, "response", NT_LABEL), self._parse_record)

    def _parse_record(self, record: dict[str, Any]) -> RoadClosureItem | None:
        status = text(record.get("status")).upper()
        if status and status != "CURRENT":
            return None
        point = nt_point(record.get("startPoint")) or nt_point(record.get("endPoint"))
        if point is None:
            return None
        raw_id = text(record.get("recordId")) or text(record.get("obstructionId"))
        if not raw_id:
            raise ValueError("obstruction without id")
        obstruction = " ".join(text(record.get("obstructionType")).split())
        restriction = text(record.get("restrictionType"))
        restriction_l = restriction.lower()

        if "flood" in obstruction.lower():
            category = RoadEventCategory.FLOODING
        elif "roadwork" in obstruction.lower():
            category = RoadEventCategory.ROADWORKS
        elif "weight" in restriction_l or "facilities" in obstruction.lower():
            # Standing heavy-vehicle limits and park facility closures are not road hazards
            return None
        elif "closed" in restriction_l or "impassable" in restriction_l:
            category = RoadEventCategory.CLOSURE
        else:
            category = RoadEventCategory.HAZARD

        comment = text(record.get("comment"))
        return RoadClosureItem(
            id=f"NT_{raw_id}",
            road=text(record.get("roadName")) or "Road",
            suburb=text(record.get("locationComment")),
            status=restriction or obstruction or "Hazard",
            reason=obstruction or None,
            description=" ".join(comment.split()) if comment and comment != "-" else None,
            source=NT_SOURCE,
            updated_at=self.parse_datetime(record.get("dateLastUpdated")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )
