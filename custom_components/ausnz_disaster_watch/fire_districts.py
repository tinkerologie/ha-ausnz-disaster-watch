"""Fire weather district lookup from bundled Bureau of Meteorology district polygons.

Agencies publish fire danger ratings per BoM fire weather district (an AAC code such as
``WA_FW091``) without geometry. The bundled polygons come from the BoM ``IDM00007``
dataset, simplified to about 1 km, so the configured location can be matched to its
district with a point-in-polygon test (#14).
"""

from __future__ import annotations

from functools import cache
from itertools import pairwise
import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent / "data"

# A location within this distance (degrees, about 25 km) of a district boundary still
# resolves to that district. This covers coastal points that fall outside the simplified
# coastline. Anything further away is not in any district.
NEAREST_DISTRICT_MAX_DEG = 0.25

type Ring = list[list[float]]


@cache
def load_fire_districts(name: str) -> dict[str, dict[str, Any]]:
    """Load bundled district polygons as ``{aac: {"name": str, "rings": [[[lon, lat], ...]]}}``.

    This reads a file (once per name), so call it from an executor job, not the event loop.
    The returned mapping is cached and shared by every caller: treat it as read-only.
    """
    with (_DATA_DIR / f"{name}.json").open(encoding="utf-8") as file:
        return json.load(file)["districts"]


def _ring_contains(ring: Ring, lat: float, lon: float) -> bool:
    """Ray-casting test for one ring (ring coordinates are [lon, lat])."""
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segment_distance(lat: float, lon: float, a: list[float], b: list[float]) -> float:
    """Return the planar distance in degrees from a point to the segment a-b."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((lon - x1) * dx + (lat - y1) * dy) / (dx * dx + dy * dy)))
    return float(((lon - x1 - t * dx) ** 2 + (lat - y1 - t * dy) ** 2) ** 0.5)


def find_district(districts: dict[str, dict[str, Any]], lat: float, lon: float) -> str | None:
    """Return the AAC of the district containing the point, else the nearest one within range.

    Rings use the even-odd rule, so holes in a district are honoured.
    """
    for aac, district in districts.items():
        if sum(_ring_contains(ring, lat, lon) for ring in district["rings"]) % 2:
            return aac

    best: tuple[float, str] | None = None
    for aac, district in districts.items():
        for ring in district["rings"]:
            for a, b in pairwise(ring):
                distance = _segment_distance(lat, lon, a, b)
                if distance <= NEAREST_DISTRICT_MAX_DEG and (best is None or distance < best[0]):
                    best = (distance, aac)
    return best[1] if best else None


def resolve_district(name: str, lat: float, lon: float) -> str | None:
    """Return the AAC of the bundled ``name`` district for a point. Blocking: run in an executor."""
    return find_district(load_fire_districts(name), lat, lon)
