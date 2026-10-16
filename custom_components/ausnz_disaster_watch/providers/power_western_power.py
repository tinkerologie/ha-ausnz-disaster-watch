"""Western Power (south-west WA) outage areas from its public ArcGIS service (#36).

``WP_Outage_Prod`` layer 0 (``Outage_Areas``) has one polygon per outage. Fields, verified
on 2026-10-16: ``INCIDENTREF``, ``OUTAGETYPE``, ``PLANNEDOUTAGE`` (``Planned`` or
``Unplanned``), ``ENARNUMBER``, ``NOCUSTOMERSIMPACTED``, ``AFFECTED_AREA``
(comma-separated suburbs) and ``OUTAGESTARTTIME``/``ESTIMATEDRESTORATIONTIME`` as Perth
local text (``16/10/2026 08:00 AM``). ``OUTAGETYPE`` is ``U`` (fault), ``P`` (planned) or
``F``: ``F`` rows say ``Unplanned`` but carry a network access permit (``ENARNUMBER``) and
scheduled working hours days ahead, so they are treated as planned work. The website's own
``/api/corp/outage/*`` routes are disallowed by robots.txt and are not used.

Western Power's terms allow use of its information only "for your own personal and
non-commercial use relating to your own energy consumption", so the feed is opt-in (extra
outage feeds).
"""

from __future__ import annotations

import contextlib
from typing import Any

from custom_components.ausnz_disaster_watch.models import PowerOutageItem

from .base import MALFORMED_ITEM_ERRORS
from .power import PowerOutageSource

_PLANNED_TYPES = frozenset({"P", "F"})

WESTERN_POWER_OUTAGES_URL = (
    "https://services2.arcgis.com/tBLxde4cxSlNUxsM/ArcGIS/rest/services/WP_Outage_Prod/FeatureServer/0"
)


class WesternPowerOutageSource(PowerOutageSource):
    """Western Power outage areas."""

    key = "western_power_outages"
    distributor = "Western Power"
    local_tz = "Australia/Perth"
    opt_in = True

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        where = "1=1" if self.include_planned else "OUTAGETYPE NOT IN ('P','F') AND PLANNEDOUTAGE<>'Planned'"
        # Outage areas are detailed polygons; outlines generalised to ~50 m cut the payload ~5x
        features = await self.async_fetch_arcgis(
            WESTERN_POWER_OUTAGES_URL,
            "Western Power outages",
            where,
            geometryPrecision="4",
            maxAllowableOffset="0.0005",
        )
        outages: list[PowerOutageItem] = []
        for feat in features:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if (item := self._parse(feat)) is not None:
                    outages.append(item)
        return outages

    def _parse(self, feat: dict[str, Any]) -> PowerOutageItem | None:
        props = feat["properties"]
        planned = (
            str(props.get("PLANNEDOUTAGE") or "").strip().lower() == "planned"
            or str(props.get("OUTAGETYPE") or "").upper() in _PLANNED_TYPES
            or bool(str(props.get("ENARNUMBER") or "").strip())
        )
        start = self.parse_datetime(props.get("OUTAGESTARTTIME"))
        restore = self.parse_datetime(props.get("ESTIMATEDRESTORATIONTIME"))
        if not self.in_effect(planned, start, restore):
            return None
        lat, lon, dist = self.located(feat.get("geometry"))
        suburbs = [s.strip().title() for s in str(props.get("AFFECTED_AREA") or "").split(",") if s.strip()]
        return PowerOutageItem(
            id=str(props["INCIDENTREF"]),
            distributor=self.distributor,
            planned=planned,
            suburb=", ".join(suburbs),
            cause="Planned work" if planned else "Under Investigation",
            customers_affected=int(props.get("NOCUSTOMERSIMPACTED") or 0),
            start_time=self.time_text(start),
            restore_time=self.time_text(restore),
            latitude=lat,
            longitude=lon,
            distance_km=dist,
        )
