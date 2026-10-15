"""CAP 1.2 (Common Alerting Protocol) parsing and pure-Python area geometry.

Agencies publish warnings as CAP documents whose affected area is a union of polygons and
circles in ``lat,lon`` order. Distances here are "distance to the area": 0 when the point is
inside any shape, otherwise the distance to the nearest edge. No geometry dependency is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
import math
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

from .base import BaseHazardProvider

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
EARTH_RADIUS_KM = 6371.0088

type LatLon = tuple[float, float]


@dataclass(slots=True, frozen=True)
class CapArea:
    """One ``<area>`` block: description, shapes and geocodes."""

    description: str
    polygons: tuple[tuple[LatLon, ...], ...]
    circles: tuple[tuple[float, float, float], ...]  # (lat, lon, radius_km)
    geocodes: tuple[tuple[str, str], ...]  # (valueName, value), e.g. ("AMOC-AreaCode", "QLD_PW008")


@dataclass(slots=True, frozen=True)
class CapAlert:
    """The fields of a CAP 1.2 alert that hazard providers use."""

    identifier: str
    sent: datetime | None
    status: str
    msg_type: str
    references: tuple[str, ...]  # identifiers of the messages this one updates or cancels
    event: str
    headline: str
    severity: str
    urgency: str
    onset: datetime | None
    expires: datetime | None
    web: str
    areas: tuple[CapArea, ...]

    @property
    def has_geometry(self) -> bool:
        """Return True if any area has a polygon or circle."""
        return any(area.polygons or area.circles for area in self.areas)

    @property
    def area_description(self) -> str:
        """Return the affected area descriptions joined for display."""
        return "; ".join(area.description for area in self.areas if area.description)


def _text(element: Element | None, path: str) -> str:
    if element is None:
        return ""
    return (element.findtext(path, "", CAP_NS) or "").strip()


def _parse_polygon(text: str) -> tuple[LatLon, ...] | None:
    """Parse ``"lat,lon lat,lon ..."``; malformed tokens are skipped, <3 points is no polygon."""
    points: list[LatLon] = []
    for token in text.split():
        try:
            lat_s, lon_s = token.split(",", 1)
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            continue
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            points.append((lat, lon))
    return tuple(points) if len(points) >= 3 else None


def _parse_circle(text: str) -> tuple[float, float, float] | None:
    """Parse ``"lat,lon radius_km"``."""
    try:
        centre, radius_s = text.split()
        lat_s, lon_s = centre.split(",", 1)
        lat, lon, radius = float(lat_s), float(lon_s), float(radius_s)
    except ValueError:
        return None
    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and radius >= 0:
        return (lat, lon, radius)
    return None


def parse_cap(xml_text: str) -> CapAlert | None:
    """Parse a CAP 1.2 document; return None for malformed XML or a document without ``<alert>``."""
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, ValueError):
        return None
    alert = root if root.tag == f"{{{CAP_NS['cap']}}}alert" else root.find(".//cap:alert", CAP_NS)
    if alert is None:
        return None

    infos = alert.findall("cap:info", CAP_NS)
    info = next(
        (i for i in infos if _text(i, "cap:language").lower().startswith("en")),
        infos[0] if infos else None,
    )

    areas: list[CapArea] = []
    if info is not None:
        for area in info.findall("cap:area", CAP_NS):
            polygons = tuple(
                polygon
                for el in area.findall("cap:polygon", CAP_NS)
                if (polygon := _parse_polygon(el.text or "")) is not None
            )
            circles = tuple(
                circle
                for el in area.findall("cap:circle", CAP_NS)
                if (circle := _parse_circle(el.text or "")) is not None
            )
            geocodes = tuple(
                (_text(code, "cap:valueName"), _text(code, "cap:value")) for code in area.findall("cap:geocode", CAP_NS)
            )
            areas.append(CapArea(_text(area, "cap:areaDesc"), polygons, circles, geocodes))

    # references: whitespace-separated "sender,identifier,sent" triples
    references = tuple(
        parts[1] for ref in _text(alert, "cap:references").split() if len(parts := ref.split(",")) >= 2 and parts[1]
    )
    parse = BaseHazardProvider.parse_datetime
    return CapAlert(
        identifier=_text(alert, "cap:identifier"),
        sent=parse(_text(alert, "cap:sent")),
        status=_text(alert, "cap:status"),
        msg_type=_text(alert, "cap:msgType"),
        references=references,
        event=_text(info, "cap:event"),
        headline=_text(info, "cap:headline"),
        severity=_text(info, "cap:severity"),
        urgency=_text(info, "cap:urgency"),
        onset=parse(_text(info, "cap:onset")),
        expires=parse(_text(info, "cap:expires")),
        web=_text(info, "cap:web"),
        areas=tuple(areas),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def point_in_polygon(lat: float, lon: float, ring: tuple[LatLon, ...]) -> bool:
    """Ray-casting containment test (longitude as x, latitude as y)."""
    inside = False
    for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:] + ring[:1], strict=True):
        if (lat1 > lat) != (lat2 > lat) and lon < (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1:
            inside = not inside
    return inside


def distance_to_polygon_km(lat: float, lon: float, ring: tuple[LatLon, ...]) -> float:
    """Return 0 inside the polygon, else the distance to its nearest edge.

    Vertices are projected onto a local equirectangular plane centred on the point, which is
    accurate at the tens-to-hundreds of kilometres that radius filtering cares about.
    """
    if point_in_polygon(lat, lon, ring):
        return 0.0
    k_lat = math.pi * EARTH_RADIUS_KM / 180.0
    k_lon = k_lat * math.cos(math.radians(lat))
    xy = [((v_lon - lon) * k_lon, (v_lat - lat) * k_lat) for v_lat, v_lon in ring]
    best = math.inf
    for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1], strict=True):
        dx, dy = x2 - x1, y2 - y1
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / seg))
        best = min(best, math.hypot(x1 + t * dx, y1 + t * dy))
    return best


def area_distance_km(lat: float, lon: float, areas: tuple[CapArea, ...]) -> float | None:
    """Distance from a point to the union of all shapes (0 if inside any), or None without shapes."""
    distances = [distance_to_polygon_km(lat, lon, ring) for area in areas for ring in area.polygons]
    distances += [
        max(0.0, haversine_km(lat, lon, c_lat, c_lon) - radius)
        for area in areas
        for c_lat, c_lon, radius in area.circles
    ]
    return min(distances) if distances else None


def _centroid(ring: tuple[LatLon, ...]) -> LatLon:
    points = ring[:-1] if len(ring) > 3 and ring[0] == ring[-1] else ring
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _interior_point(ring: tuple[LatLon, ...]) -> LatLon:
    """Return a point inside the polygon.

    That is the vertex mean if it is inside, else the middle of the widest horizontal span
    through the polygon (the vertex mean of a concave ring can lie outside it).
    """
    mean = _centroid(ring)
    if point_in_polygon(mean[0], mean[1], ring):
        return mean
    lats = sorted({p[0] for p in ring})
    best: tuple[float, LatLon] | None = None
    for y in [(a + b) / 2 for a, b in pairwise(lats)]:
        xs = sorted(
            lon1 + (y - lat1) * (lon2 - lon1) / (lat2 - lat1)
            for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:] + ring[:1], strict=True)
            if (lat1 > y) != (lat2 > y)
        )
        for left, right in zip(xs[::2], xs[1::2], strict=False):
            if best is None or right - left > best[0]:
                best = (right - left, (y, (left + right) / 2))
    return best[1] if best is not None else mean


def representative_point(
    areas: tuple[CapArea, ...], lat: float | None = None, lon: float | None = None
) -> LatLon | None:
    """Return a map location for the alert: a point inside the shape nearest the point, if given."""
    candidates: list[tuple[float, LatLon]] = []
    for area in areas:
        for ring in area.polygons:
            dist = distance_to_polygon_km(lat, lon, ring) if lat is not None and lon is not None else 0.0
            candidates.append((dist, _interior_point(ring)))
        for c_lat, c_lon, radius in area.circles:
            dist = (
                max(0.0, haversine_km(lat, lon, c_lat, c_lon) - radius) if lat is not None and lon is not None else 0.0
            )
            candidates.append((dist, (c_lat, c_lon)))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None
