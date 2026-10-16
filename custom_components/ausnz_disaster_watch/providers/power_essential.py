"""Essential Energy (regional NSW) outages from the KML file behind its outage map (#36).

``current.kml`` (about 100 kB for the whole network) lists the outages in effect now. Each
``Placemark`` is one incident: its ``id`` is the incident number, ``styleUrl`` ends in
``_planned`` or ``_unplanned``, the HTML ``description`` holds ``Time Off``, ``Est. Time
On``, ``No. of Customers affected``, ``Reason`` and ``Last Updated`` (Sydney local
``DD/MM/YYYY HH:MM:SS``), and a ``MultiGeometry`` holds the outage polygons. Verified on
2026-10-16. The file has no spatial query, so it is only fetched when the radius reaches
Essential Energy's network.
"""

from __future__ import annotations

import contextlib
import html
import re
from typing import TYPE_CHECKING, Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.models import PowerOutageItem

from .base import MALFORMED_ITEM_ERRORS, ProviderUnavailableError
from .power import PowerOutageSource

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

ESSENTIAL_OUTAGES_URL = "https://www.essentialenergy.com.au/Assets/kmz/current.kml"

_KML_NS = re.compile(r"^\{[^}]*\}")
_FIELD_RE = re.compile(r"<span>\s*([^<:]+):\s*</span>\s*([^<]*)", re.IGNORECASE)


def _local(tag: str) -> str:
    return _KML_NS.sub("", tag)


def _children(element: Element, name: str) -> list[Element]:
    return [child for child in element.iter() if _local(child.tag) == name]


def _ring(text: str | None) -> tuple[tuple[float, float], ...]:
    """Parse a KML ``coordinates`` list (``lon,lat[,alt]`` tuples) into (lat, lon) points."""
    points: list[tuple[float, float]] = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            points.append((float(parts[1]), float(parts[0])))
    return tuple(points)


class EssentialEnergyOutageSource(PowerOutageSource):
    """Essential Energy outages."""

    key = "essential_outages"
    distributor = "Essential Energy"
    local_tz = "Australia/Sydney"
    # Regional NSW and the ACT surrounds, with a margin
    service_area = (-37.6, 140.9, -28.1, 153.7)

    async def _async_fetch_outages(self) -> list[PowerOutageItem]:
        label = "Essential Energy outages"
        text = await self.async_fetch_feed_text(ESSENTIAL_OUTAGES_URL, label)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise ProviderUnavailableError(f"{label} returned malformed KML: {err}") from err
        if _local(root.tag) != "kml":
            raise ProviderUnavailableError(f"{label} returned an unexpected document <{root.tag}>")
        outages: list[PowerOutageItem] = []
        for placemark in _children(root, "Placemark"):
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if (item := self._parse(placemark)) is not None:
                    outages.append(item)
        return outages

    def _parse(self, placemark: Element) -> PowerOutageItem | None:
        incident = placemark.get("id") or ""
        if not incident:
            raise ValueError("placemark without an incident id")
        style = next((el.text or "" for el in _children(placemark, "styleUrl")), "")
        planned = style.strip().lower().endswith("_planned")
        description = next((el.text or "" for el in _children(placemark, "description")), "")
        fields: dict[str, Any] = {
            key.strip().lower(): html.unescape(value).strip() for key, value in _FIELD_RE.findall(description)
        }
        start = self.parse_datetime(fields.get("time off"))
        restore = self.parse_datetime(fields.get("est. time on"))
        if not self.in_effect(planned, start, restore):
            return None
        rings = tuple(ring for coords in _children(placemark, "coordinates") if len(ring := _ring(coords.text)) >= 3)
        lat, lon, dist = self.located(rings=rings)
        return PowerOutageItem(
            id=incident,
            distributor=self.distributor,
            planned=planned,
            cause=fields.get("reason") or "Under Investigation",
            customers_affected=int(fields.get("no. of customers affected") or 0),
            start_time=self.time_text(start),
            restore_time=self.time_text(restore),
            latitude=lat,
            longitude=lon,
            distance_km=dist,
        )
