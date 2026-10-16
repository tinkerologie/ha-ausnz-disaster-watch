"""Endeavour Energy (Western Sydney, Blue Mountains, Illawarra) outages from its open data portal (#36).

The Opendatasoft datasets ``outagecustomerlive`` (current unplanned outages) and
``plannedoutagecustomer`` (planned work) are published under the Open Database Licence
(ODbL 1.0). Each record is one affected street address of an incident, so the integration
asks the server to group records by incident (``group_by``) and to average their
coordinates; no street address is fetched or stored. Fields, verified on 2026-10-16:
``incident_id``, ``outage_type``, ``incident_status``, ``cause``, ``customers_affected``
(the incident's total, repeated on each record), ``cityname``, ``start_date_time``,
``est_restore_time`` and ``end_date_time`` (Sydney local ``YYYY-MM-DD HH:MM``; the end is
``1970-01-01 00:00`` while unknown) and ``geom``.

ODbL: the integration keeps an attribution notice on the outage sensor; it does not
publish a derived database (the outages live only in the user's own Home Assistant).
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from custom_components.ausnz_disaster_watch.models import PowerOutageItem

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError
from .power import PowerOutageSource

_LOGGER = logging.getLogger(__name__)

ENDEAVOUR_DATASETS_URL = "https://data.endeavourenergy.com.au/api/explore/v2.1/catalog/datasets"
ENDEAVOUR_LIVE_URL = f"{ENDEAVOUR_DATASETS_URL}/outagecustomerlive/records"
ENDEAVOUR_PLANNED_URL = f"{ENDEAVOUR_DATASETS_URL}/plannedoutagecustomer/records"

_GROUP_FIELDS = (
    "incident_id",
    "outage_type",
    "incident_status",
    "cause",
    "cityname",
    "start_date_time",
    "est_restore_time",
    "end_date_time",
)
_SELECT = ",".join(
    (
        *_GROUP_FIELDS,
        "max(customers_affected) as customers",
        "avg(latitude) as lat",
        "avg(longitude) as lon",
        "count(*) as records",
    )
)
_NONE_TEXT = frozenset({"", "none", "null", "unknown"})


class EndeavourOutageSource(PowerOutageSource):
    """Endeavour Energy outages grouped by incident."""

    key = "endeavour_outages"
    distributor = "Endeavour Energy"
    local_tz = "Australia/Sydney"

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        params = {
            "select": _SELECT,
            "group_by": ",".join(_GROUP_FIELDS),
            "where": (f"within_distance(geom, geom'POINT({self.longitude} {self.latitude})', {self.radius_km:g}km)"),
        }
        records = await self.async_fetch_ods(ENDEAVOUR_LIVE_URL, "Endeavour Energy outages", params)
        if self.include_planned:
            try:
                records += await self.async_fetch_ods(ENDEAVOUR_PLANNED_URL, "Endeavour Energy planned outages", params)
            except ProviderUnavailableError as err:
                # Keep the current outages when only the planned dataset fails
                _LOGGER.debug("Endeavour Energy planned outages unavailable: %s", err)
        return self._merge(records)

    def _merge(self, records: list[dict[str, Any]]) -> list[PowerOutageItem]:
        """Merge the per-suburb groups of each incident into one outage."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for rec in records:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                groups.setdefault(str(rec["incident_id"]), []).append(rec)
        outages: list[PowerOutageItem] = []
        for incident_id, recs in groups.items():
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if (item := self._parse(incident_id, recs)) is not None:
                    outages.append(item)
        return outages

    def _parse(self, incident_id: str, recs: list[dict[str, Any]]) -> PowerOutageItem | None:
        first = recs[0]
        planned = str(first.get("outage_type") or "").strip().upper() == "PLANNED"
        start = self.parse_datetime(first.get("start_date_time"))
        restore = self.parse_datetime(first.get("est_restore_time"))
        end = self.parse_datetime(first.get("end_date_time"))
        if end is not None and end.year < 2000:
            end = None
        if not self.in_effect(planned, start, end or restore):
            return None
        weight = sum(int(r.get("records") or 1) for r in recs)
        lat = sum(float(r["lat"]) * int(r.get("records") or 1) for r in recs) / weight
        lon = sum(float(r["lon"]) * int(r.get("records") or 1) for r in recs) / weight
        lat_, lon_, dist = self.located(lat=lat, lon=lon)
        suburbs = sorted({str(r.get("cityname") or "").strip().title() for r in recs} - {""})
        cause = str(first.get("cause") or "").strip()
        status = str(first.get("incident_status") or "").strip()
        return PowerOutageItem(
            id=incident_id,
            distributor=self.distributor,
            planned=planned,
            status=status.capitalize() or None,
            suburb=", ".join(suburbs),
            cause=cause if cause.lower() not in _NONE_TEXT else "Under Investigation",
            customers_affected=max(int(r.get("customers") or 0) for r in recs),
            start_time=self.time_text(start),
            restore_time=self.time_text(restore),
            latitude=lat_,
            longitude=lon_,
            distance_km=dist,
        )
