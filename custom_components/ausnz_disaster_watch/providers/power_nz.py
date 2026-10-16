"""New Zealand electricity distributor outages (#36): MainPower, Powerco and Unison.

Feeds and fields, verified on 2026-10-16:

- MainPower (North Canterbury and Kaikōura): ``/jobs?source=pcc&view=external`` returns
  ``current_outages`` keyed by job ID with ``Type`` (``Outage-Planned`` or
  ``Outage-Unplanned``), ``Reason``, ``Area``, ``CustomersOff``, ``StartTime`` and
  ``EndTime`` (NZ local ``DD/MM/YYYY HH:MM``) and ``steps`` whose GeoJSON features carry the
  outage polygons and ``Lat``/``Lon``. Upcoming planned work (``planned_jobs``) is ignored.
  No terms restrict the feed.
- Powerco (Taranaki, Whanganui, Manawatū, Wairarapa, Tauranga, Coromandel): ArcGIS layer 1
  of ``Hosted/Outages`` has one point per outage with ``distributor_event_number``,
  ``planned_outage`` (0/1), ``interruption_reason``, ``interruption_start_date`` and
  ``interruption_restore_date`` (epoch ms), ``suburb``, ``town``, ``crew_status`` and
  ``number_of_detail_records`` (the affected connections, used as the customer count).
  Powerco's terms forbid using its information "for a public purpose or commercial gain",
  so the feed is opt-in (extra outage feeds).
- Unison (Hawke's Bay, Taupō, Rotorua): ``/api/outages`` lists current, recent, scheduled
  and cancelled outages (about 2.6 MB) with ``outageID``, ``isPlanned``, ``outageState``
  (``Current`` is kept), ``customersOff``, ``networkRegion``, ``interruptionReason``,
  ``startTime``/``finishTime`` (UTC ISO 8601) and ``outageWindows`` whose ``Overall`` window
  has the outage area as ``[lon, lat]`` rings. The download is large, so the feed is opt-in
  and fetched at most every 15 minutes. No terms restrict the feed.

MainPower and Unison have no spatial query, so they are only fetched when the radius
reaches their network.
"""

from __future__ import annotations

import contextlib
from typing import Any

from custom_components.ausnz_disaster_watch.models import PowerOutageItem

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError
from .power import PowerOutageSource, geojson_rings

POWERCO_OUTAGES_URL = "https://outages.powerco.co.nz/server/rest/services/Hosted/Outages/FeatureServer/1"
MAINPOWER_OUTAGES_URL = "https://outages.mainpower.co.nz/jobs?source=pcc&view=external"
UNISON_OUTAGES_URL = "https://www.unison.co.nz/api/outages"


class PowercoOutageSource(PowerOutageSource):
    """Powerco outage points."""

    key = "powerco_outages"
    distributor = "Powerco"
    local_tz = "Pacific/Auckland"
    opt_in = True

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        where = "1=1" if self.include_planned else "planned_outage=0"
        features = await self.async_fetch_arcgis(POWERCO_OUTAGES_URL, "Powerco outages", where)
        outages: list[PowerOutageItem] = []
        for feat in features:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                props = feat["properties"]
                planned = bool(int(props.get("planned_outage") or 0))
                start = self.parse_datetime(props.get("interruption_start_date"))
                restore = self.parse_datetime(props.get("interruption_restore_date"))
                if not self.in_effect(planned, start, restore):
                    continue
                lat, lon, dist = self.located(feat.get("geometry"))
                place = [str(props.get(k) or "").strip() for k in ("suburb", "town")]
                outages.append(
                    PowerOutageItem(
                        id=str(props["distributor_event_number"]),
                        distributor=self.distributor,
                        planned=planned,
                        status=_status(props.get("crew_status")),
                        suburb=", ".join(dict.fromkeys(p for p in place if p)),
                        cause=str(props.get("interruption_reason") or "").strip().strip('"') or "Under Investigation",
                        customers_affected=int(props.get("number_of_detail_records") or 0),
                        start_time=self.time_text(start),
                        restore_time=self.time_text(restore),
                        latitude=lat,
                        longitude=lon,
                        distance_km=dist,
                    )
                )
        return outages


class MainPowerOutageSource(PowerOutageSource):
    """MainPower current outages."""

    key = "mainpower_outages"
    distributor = "MainPower"
    local_tz = "Pacific/Auckland"
    service_area = (-43.5, 171.8, -41.9, 174.2)

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        label = "MainPower outages"
        payload = self.require_dict(await self.async_fetch_feed_json(MAINPOWER_OUTAGES_URL, label), label)
        jobs = payload.get("current_outages")
        if not isinstance(jobs, dict):
            jobs = {} if jobs in (None, [], "") else self.require_dict(jobs, label)
        outages: list[PowerOutageItem] = []
        for job_id, job in jobs.items():
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if (item := self._parse(str(job_id), job)) is not None:
                    outages.append(item)
        return outages

    def _parse(self, job_id: str, job: dict[str, Any]) -> PowerOutageItem | None:
        planned = "planned" in str(job.get("Type") or "").lower().replace("unplanned", "")
        start = self.parse_datetime(job.get("StartTime"))
        end = self.parse_datetime(job.get("EndTime"))
        if not self.in_effect(planned, start, end):
            return None
        steps = job.get("steps")
        features = [f for f in steps.values() if isinstance(f, dict)] if isinstance(steps, dict) else []
        rings = tuple(ring for f in features for ring in geojson_rings(f.get("geometry")))
        props = features[0].get("properties") or {} if features else {}
        lat, lon, dist = self.located(lat=_float(props.get("Lat")), lon=_float(props.get("Lon")), rings=rings)
        # "Area" can start with a street address; keep only the locality after the last comma
        area = str(job.get("Area") or "").rsplit(",", 1)[-1].strip().title()
        return PowerOutageItem(
            id=job_id,
            distributor=self.distributor,
            planned=planned,
            status=_status(job.get("CrewState")),
            suburb=area,
            cause=str(job.get("Reason") or "").strip() or "Under Investigation",
            customers_affected=int(job.get("CustomersOff") or 0),
            start_time=self.time_text(start),
            restore_time=self.time_text(end),
            latitude=lat,
            longitude=lon,
            distance_km=dist,
        )


class UnisonOutageSource(PowerOutageSource):
    """Unison current outages."""

    key = "unison_outages"
    distributor = "Unison"
    local_tz = "Pacific/Auckland"
    service_area = (-40.5, 175.5, -37.9, 177.6)
    opt_in = True
    min_interval = 900.0

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        label = "Unison outages"
        payload = await self.async_fetch_feed_json(UNISON_OUTAGES_URL, label)
        if not isinstance(payload, list):
            raise ProviderUnavailableError(f"{label} returned an unexpected payload")
        outages: list[PowerOutageItem] = []
        for item in payload:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if (outage := self._parse(item)) is not None:
                    outages.append(outage)
        return outages

    def _parse(self, item: dict[str, Any]) -> PowerOutageItem | None:
        if str(item.get("outageState") or "").lower() != "current":
            return None
        planned = bool(item.get("isPlanned"))
        start = self.parse_datetime(item.get("startTime"))
        end = self.parse_datetime(item.get("finishTime"))
        if not self.in_effect(planned, start, end):
            return None
        windows = [w for w in item.get("outageWindows") or [] if isinstance(w, dict)]
        overall = next((w for w in windows if w.get("type") == "Overall"), windows[0] if windows else {})
        area = overall.get("outageArea")
        rings = (
            geojson_rings({"type": "MultiPolygon", "coordinates": [[r] for r in area if isinstance(r, list)]})
            if isinstance(area, list)
            else ()
        )
        lat, lon, dist = self.located(rings=rings)
        return PowerOutageItem(
            id=str(item["outageID"]),
            distributor=self.distributor,
            planned=planned,
            status=_status(item.get("outageStatus")),
            suburb=str(item.get("networkRegion") or "").strip(),
            cause=str(item.get("interruptionReason") or "").strip()
            or ("Planned work" if planned else "Under Investigation"),
            customers_affected=int(item.get("customersOff") or 0),
            start_time=self.time_text(start),
            restore_time=self.time_text(end),
            latitude=lat,
            longitude=lon,
            distance_km=dist,
        )


def _status(value: Any) -> str | None:
    """Return a status text, or None for an empty or "N/A" value."""
    text = str(value or "").strip()
    return text if text.upper() not in {"", "N/A", "NA"} else None


def _float(value: Any) -> float | None:
    """Return value as a float, or None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
