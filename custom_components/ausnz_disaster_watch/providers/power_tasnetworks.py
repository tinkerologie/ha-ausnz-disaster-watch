"""TasNetworks (Tasmania) outages from the JSON behind its outage map (#36).

``/api/odata/GetPowerOutages`` (a few kB) lists the outages in effect now, verified on
2026-10-16: ``jobId``, ``dispatchStatus``, ``reason`` (``Planned maintenance work``,
``Emergency repairs``, ...), ``affectedAreas`` (comma-separated localities),
``customersAffected`` (a string), ``createdOn`` (ISO 8601 with offset),
``estimatedTimeOfRestoration`` (free text such as ``Friday 4:00 PM`` or ``This Afternoon``,
kept as published), ``outagePolygon_WKT`` and ``outageCentroid_WKT``. No terms restrict
the feed; robots.txt only disallows ``/config/admin/``.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from custom_components.ausnz_disaster_watch.models import PowerOutageItem

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError
from .power import PowerOutageSource, Ring

TASNETWORKS_OUTAGES_URL = "https://www.tasnetworks.com.au/api/odata/GetPowerOutages"

_WKT_RING = re.compile(r"\(([^()]+)\)")
_WKT_POINT = re.compile(r"POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", re.IGNORECASE)


def wkt_rings(text: Any) -> tuple[Ring, ...]:
    """Return the rings of a WKT POLYGON/MULTIPOLYGON as (lat, lon) points."""
    rings: list[Ring] = []
    for group in _WKT_RING.findall(str(text or "")):
        ring = tuple(
            (float(pair[1]), float(pair[0])) for pair in (p.split() for p in group.split(",")) if len(pair) >= 2
        )
        if len(ring) >= 3:
            rings.append(ring)
    return tuple(rings)


class TasNetworksOutageSource(PowerOutageSource):
    """TasNetworks outages."""

    key = "tasnetworks_outages"
    distributor = "TasNetworks"
    local_tz = "Australia/Hobart"
    service_area = (-43.8, 143.5, -39.4, 148.6)

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        label = "TasNetworks outages"
        payload = await self.async_fetch_feed_json(TASNETWORKS_OUTAGES_URL, label)
        if not isinstance(payload, list):
            raise ProviderUnavailableError(f"{label} returned an unexpected payload")
        outages: list[PowerOutageItem] = []
        for item in payload:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                outages.append(self._parse(item))
        return outages

    def _parse(self, item: dict[str, Any]) -> PowerOutageItem:
        reason = str(item.get("reason") or "").strip()
        point = _WKT_POINT.search(str(item.get("outageCentroid_WKT") or ""))
        lat, lon, dist = self.located(
            lat=float(point.group(2)) if point else None,
            lon=float(point.group(1)) if point else None,
            rings=wkt_rings(item.get("outagePolygon_WKT")),
        )
        areas = [a.strip() for a in str(item.get("affectedAreas") or "").split(",") if a.strip()]
        restore = str(item.get("estimatedTimeOfRestoration") or "").strip()
        return PowerOutageItem(
            id=str(item["jobId"]),
            distributor=self.distributor,
            planned="planned" in reason.lower() and "unplanned" not in reason.lower(),
            status=str(item.get("dispatchStatus") or "").strip() or None,
            suburb=", ".join(areas),
            cause=reason or "Under Investigation",
            customers_affected=int(str(item.get("customersAffected") or "0").strip() or 0),
            start_time=self.time_text(self.parse_datetime(item.get("createdOn"))),
            restore_time=restore or None,
            latitude=lat,
            longitude=lon,
            distance_km=dist,
        )
