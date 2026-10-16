"""South Australian road events from the Traffic SA open data ArcGIS service (DIT, CC BY).

``maps.sa.gov.au/arcgis/rest/services/DPTIExtTransport/TrafficSAOpenData/MapServer``
(keyless, verified 2026-10-16; ``maxRecordCount`` 1000):

- layer 0 "Roadworks and Incidents" (points): ``ROADWORKS_AND_INCIDENTS_ID``, ``REC_TYPE``
  (``ROADWORKS``, ``24HR ROADWORKS``, ``INCIDENT``), ``DESCRIPTION``, ``LOCAL_ROAD``,
  ``SUBURB``, ``LATITUDE``/``LONGITUDE``, ``START_DATE``/``END_DATE`` (epoch ms),
  ``NO_LANES_CLOSED`` (``Closure``, ``One Lane``, ...). Almost all rows are roadworks, so
  only incidents are requested unless planned roadworks are included.
- layer 1 "Road Closures and Detours" (lines): ``LOCATION_ID``, ``PLOT_TYPE``
  (``RD_CLOSURE``), ``PLOT_DETAILS`` (e.g. "Closed due to flooding over road"),
  ``LOCAL_ROAD_NAME``, ``START_SUBURB``, ``START_DATE``/``END_DATE``.

Both layers are queried with the radius bounding box.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import STATE_SA
from custom_components.ausnz_disaster_watch.models import RoadClosureItem, RoadEventCategory
from homeassistant.util import dt as dt_util

from .base import BaseRoadProvider, first_point, is_minor_incident, text, valid_point

SA_TRAFFIC_URL = "https://maps.sa.gov.au/arcgis/rest/services/DPTIExtTransport/TrafficSAOpenData/MapServer"
SA_SOURCE = "Traffic SA (Department for Infrastructure and Transport)"
# NO_LANES_CLOSED values that read badly as a status
_SA_LANES = {"closure": "Closed", "none": "No lanes closed"}


class SARoadProvider(BaseRoadProvider):
    """Road closures, flooding, incidents and (optionally) roadworks from Traffic SA."""

    local_tz: ClassVar[str] = "Australia/Adelaide"
    feed_name: ClassVar[str] = "Traffic SA"

    @property
    def state_code(self) -> str:
        """Return the state code."""
        return STATE_SA

    async def _async_fetch_road_events(self) -> list[RoadClosureItem]:
        """Query the incident and closure layers within the radius box."""
        where = "1=1" if self.include_roadworks else "REC_TYPE='INCIDENT'"

        async def incidents() -> Any:
            return await self.async_arcgis_query(f"{SA_TRAFFIC_URL}/0", "Traffic SA incidents", where)

        async def closures() -> Any:
            return await self.async_arcgis_query(f"{SA_TRAFFIC_URL}/1", "Traffic SA closures")

        return await self.async_collect_road_sources(
            (
                ("Traffic SA incidents", incidents, lambda feats: self.collect(feats, self._parse_incident)),
                ("Traffic SA closures", closures, lambda feats: self.collect(feats, self._parse_closure)),
            )
        )

    def _ended(self, props: dict[str, Any]) -> bool:
        end = self.parse_datetime(props.get("END_DATE")) if props.get("END_DATE") else None
        return isinstance(end, datetime) and end < dt_util.utcnow()

    def _parse_incident(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        if self._ended(props):
            return None
        point = valid_point(props.get("LATITUDE"), props.get("LONGITUDE")) or first_point(feature.get("geometry"))
        if point is None:
            return None
        raw_id = text(props.get("ROADWORKS_AND_INCIDENTS_ID")) or text(feature.get("id"))
        if not raw_id:
            raise ValueError("record without id")
        rec_type = text(props.get("REC_TYPE")).upper()
        description = text(props.get("DESCRIPTION"))
        lanes = text(props.get("NO_LANES_CLOSED"))

        if "ROADWORK" in rec_type:
            category = RoadEventCategory.ROADWORKS
        elif "flood" in description.lower():
            category = RoadEventCategory.FLOODING
        elif is_minor_incident(description):
            return None
        elif lanes.lower() == "closure" or "closed" in description.lower():
            category = RoadEventCategory.CLOSURE
        else:
            category = RoadEventCategory.HAZARD

        return RoadClosureItem(
            id=f"SA_{raw_id}",
            road=text(props.get("LOCAL_ROAD")) or description or "Road",
            suburb=text(props.get("SUBURB")),
            status=_SA_LANES.get(lanes.lower(), lanes) or rec_type.title(),
            reason=description or rec_type.title() or None,
            description=", ".join(p for p in (text(props.get("SIDE_STREET")), text(props.get("TRAFFIC_DIR"))) if p)
            or None,
            source=SA_SOURCE,
            updated_at=self.parse_datetime(props.get("START_DATE")),
            latitude=point[0],
            longitude=point[1],
            category=category,
        )

    def _parse_closure(self, feature: dict[str, Any]) -> RoadClosureItem | None:
        props = feature["properties"]
        if not text(props.get("PLOT_TYPE")).upper().startswith("RD_CLOSURE") or self._ended(props):
            return None
        point = first_point(feature.get("geometry"))
        if point is None:
            return None
        raw_id = text(props.get("LOCATION_ID")) or text(feature.get("id"))
        if not raw_id:
            raise ValueError("closure without id")
        details = text(props.get("PLOT_DETAILS"))
        flooded = "flood" in details.lower()
        return RoadClosureItem(
            id=f"SA_CLOSURE_{raw_id}",
            road=text(props.get("LOCAL_ROAD_NAME")).title() or "Road",
            suburb=text(props.get("START_SUBURB")).title(),
            status="Closed",
            reason="Flooding" if flooded else "Road closure",
            description=" ".join(details.split()) or None,
            source=SA_SOURCE,
            updated_at=self.parse_datetime(props.get("START_DATE")),
            latitude=point[0],
            longitude=point[1],
            category=RoadEventCategory.FLOODING if flooded else RoadEventCategory.CLOSURE,
        )
