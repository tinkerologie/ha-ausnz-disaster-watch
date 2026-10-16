"""Warning-area geometry: normalise agency polygons into a small, simplified ``area`` (#30).

Agencies publish warning areas as GeoJSON (``[lon, lat]``), ArcGIS GeoJSON output, CAP
``"lat,lon lat,lon"`` strings or CAP circles. Hazards carry them as ``area``: a tuple of outer
rings of ``(lat, lon)`` points. Holes are ignored, so a point in a hole counts as inside; that
errs on the side of warning. Rings are simplified (Douglas-Peucker) and capped in size so that
hazards stay small in memory. ``area`` is never written to state attributes or diagnostics.

Pure Python; no geometry dependency.
"""

from __future__ import annotations

import math
from typing import Any

from .cap import EARTH_RADIUS_KM, CapArea, LatLon, distance_to_polygon_km, interior_point

type Ring = tuple[LatLon, ...]
type Area = tuple[Ring, ...]

# About 50 m: below the accuracy of a warning boundary, and it removes most redundant vertices
AREA_SIMPLIFY_TOLERANCE_DEG = 0.0005
# Upper bound on the vertices kept per hazard (all rings together)
AREA_MAX_VERTICES = 400
# Coordinates are rounded to 5 decimal places (about 1 m)
AREA_COORD_DECIMALS = 5
# Sides of the polygon that stands in for a CAP circle
CIRCLE_SIDES = 24


def _valid(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and not (math.isnan(lat) or math.isnan(lon))


def _ring_from_lonlat(coords: Any) -> Ring | None:
    """Return a ring from a GeoJSON ``[[lon, lat], ...]`` list, or None if it has <3 valid points."""
    if not isinstance(coords, list):
        return None
    points: list[LatLon] = []
    for pair in coords:
        if not isinstance(pair, list | tuple) or len(pair) < 2:
            continue
        try:
            lon, lat = float(pair[0]), float(pair[1])
        except (TypeError, ValueError):
            continue
        if _valid(lat, lon):
            points.append((lat, lon))
    return tuple(points) if len(set(points)) >= 3 else None


def rings_from_geojson(geometry: Any) -> list[Ring]:
    """Return the outer rings of every Polygon in a GeoJSON geometry, Feature or collection.

    Points and lines are ignored; malformed parts are skipped.
    """
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    if kind == "Feature":
        return rings_from_geojson(geometry.get("geometry"))
    if kind == "FeatureCollection":
        features = geometry.get("features")
        return [ring for feat in features for ring in rings_from_geojson(feat)] if isinstance(features, list) else []
    if kind == "GeometryCollection":
        parts = geometry.get("geometries")
        return [ring for part in parts for ring in rings_from_geojson(part)] if isinstance(parts, list) else []
    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or not coords:
        return []
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return []
    return [
        ring
        for polygon in polygons
        if isinstance(polygon, list) and polygon and (ring := _ring_from_lonlat(polygon[0])) is not None
    ]


def ring_from_latlon_text(text: str) -> Ring | None:
    """Parse a ``"lat,lon lat,lon ..."`` polygon (CAP, Emergency WA GeoRSS) or GeoRSS ``"lat lon lat lon ..."``."""
    tokens = text.replace(",", " ").split()
    values: list[float] = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError:
            return None
    if len(values) % 2:
        return None
    points = [(lat, lon) for lat, lon in zip(values[::2], values[1::2], strict=True) if _valid(lat, lon)]
    return tuple(points) if len(set(points)) >= 3 else None


def circle_ring(lat: float, lon: float, radius_km: float) -> Ring:
    """Return a polygon approximating a circle (for CAP ``<circle>``)."""
    d_lat = math.degrees(radius_km / EARTH_RADIUS_KM)
    d_lon = d_lat / max(math.cos(math.radians(lat)), 1e-6)
    return tuple(
        (lat + d_lat * math.sin(2 * math.pi * i / CIRCLE_SIDES), lon + d_lon * math.cos(2 * math.pi * i / CIRCLE_SIDES))
        for i in range(CIRCLE_SIDES)
    )


def rings_from_cap_areas(areas: tuple[CapArea, ...]) -> list[Ring]:
    """Return the polygons of CAP areas, with circles of non-zero radius as polygons.

    A zero-radius circle (SA CFS uses ``"lat,lon 0.0"`` for an incident's point) is a point,
    not an area.
    """
    rings: list[Ring] = [ring for area in areas for ring in area.polygons]
    rings += [circle_ring(lat, lon, radius) for area in areas for lat, lon, radius in area.circles if radius > 0]
    return rings


def _perpendicular(point: LatLon, start: LatLon, end: LatLon) -> float:
    """Distance (degrees) from ``point`` to the segment ``start``-``end``."""
    (py, px), (ay, ax), (by, bx) = point, start, end
    dx, dy = bx - ax, by - ay
    seg = dx * dx + dy * dy
    t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _simplify_ring(ring: Ring, tolerance: float) -> Ring:
    """Douglas-Peucker on an open ring (closing vertex dropped), iterative so huge rings are safe."""
    points = list(ring[:-1] if len(ring) > 3 and ring[0] == ring[-1] else ring)
    if len(points) <= 3:
        return tuple(points)
    # Split at the vertex farthest from the first, so the open ends are not a degenerate segment
    far = max(range(len(points)), key=lambda i: math.dist(points[0], points[i]))
    keep = {0, far, len(points) - 1}
    stack = [(0, far), (far, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        best, index = 0.0, -1
        for i in range(first + 1, last):
            dist = _perpendicular(points[i], points[first], points[last])
            if dist > best:
                best, index = dist, i
        if index >= 0 and best > tolerance:
            keep.add(index)
            stack += [(first, index), (index, last)]
    return tuple(points[i] for i in sorted(keep))


def simplify_area(rings: list[Ring] | tuple[Ring, ...]) -> Area | None:
    """Simplify, round and cap rings for storage on a hazard; None when nothing usable is left.

    The tolerance doubles until all rings together have at most AREA_MAX_VERTICES vertices.
    If many tiny rings still exceed the cap, the largest rings (by vertex extent) are kept.
    """
    tolerance = AREA_SIMPLIFY_TOLERANCE_DEG
    simplified: list[Ring] = []
    for _ in range(12):
        simplified = []
        for ring in rings:
            out = tuple(
                (round(lat, AREA_COORD_DECIMALS), round(lon, AREA_COORD_DECIMALS))
                for lat, lon in _simplify_ring(ring, tolerance)
            )
            if len(set(out)) >= 3:
                simplified.append(out)
        if sum(len(ring) for ring in simplified) <= AREA_MAX_VERTICES:
            break
        tolerance *= 2
    simplified.sort(key=_extent, reverse=True)
    kept: list[Ring] = []
    total = 0
    for ring in simplified:
        if total + len(ring) > AREA_MAX_VERTICES:
            continue
        kept.append(ring)
        total += len(ring)
    return tuple(kept) or None


def _extent(ring: Ring) -> float:
    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    return (max(lats) - min(lats)) * (max(lons) - min(lons))


def area_distance(lat: float, lon: float, area: Area) -> float:
    """Distance in km from a point to the nearest ring of an area; 0 when inside any ring."""
    return min(distance_to_polygon_km(lat, lon, ring) for ring in area)


def area_point(area: Area, lat: float | None = None, lon: float | None = None) -> LatLon:
    """Return a point inside the area: inside the ring nearest the given point, if any."""
    if lat is None or lon is None:
        return interior_point(area[0])
    return interior_point(min(area, key=lambda ring: distance_to_polygon_km(lat, lon, ring)))
