"""Council disaster dashboards of Queensland and NSW, from the generated registry (#32).

``data/council_dashboards.json`` is written by ``script/update_councils.py`` (run it with
``script/update-councils``): every council whose dashboard is a live Guardian IMS (QIT Plus)
dashboard, from the official Queensland list of council dashboards and the known NSW ones,
located at its ABS Local Government Area centroid with an equal-area radius. Councils on
other platforms (Brisbane's ArcGIS dashboard, Sunshine Coast's Disaster Hub) are listed
without a URL so their location stays selectable. The original eleven presets keep their
keys, names and points.

The file is read once when the module is imported. Home Assistant imports integration
modules in an executor, so the read never runs in the event loop.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Final, TypedDict

_REGISTRY_PATH = Path(__file__).parent / "data" / "council_dashboards.json"

# A home-zone entry gets the nearest council dashboard within this distance of the
# council's point, or within the council's own equal-area radius if that is larger (#19, #32)
COUNCIL_AUTO_MATCH_KM: Final = 40
# Small councils are ranked as if they were at least this big
_MIN_RANK_RADIUS_KM = 10.0


class CouncilDashboard(TypedDict):
    """One council in the registry."""

    name: str
    state: str
    url: str | None  # None: no Guardian IMS dashboard the integration can read
    latitude: float
    longitude: float
    radius_km: float
    platform: str  # "guardian", "brisbane_arcgis" or "sunshine_hub"
    certificate_ok: bool  # False: incomplete TLS chain, Home Assistant cannot connect


def _load() -> dict[str, CouncilDashboard]:
    with _REGISTRY_PATH.open(encoding="utf-8") as file:
        councils: list[dict[str, Any]] = json.load(file)["councils"]
    return {
        council["key"]: CouncilDashboard(
            name=council["name"],
            state=council["state"],
            url=council["url"],
            latitude=float(council["latitude"]),
            longitude=float(council["longitude"]),
            radius_km=float(council["radius_km"]),
            platform=council["platform"],
            certificate_ok=bool(council["certificate_ok"]),
        )
        for council in councils
    }


COUNCIL_DASHBOARDS: Final[dict[str, CouncilDashboard]] = _load()


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * 6371.0088 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def councils_for_state(state: str) -> list[tuple[str, CouncilDashboard]]:
    """Return the councils of a state as (key, council), sorted by name."""
    return sorted(
        ((key, council) for key, council in COUNCIL_DASHBOARDS.items() if council["state"] == state),
        key=lambda item: item[1]["name"],
    )


def nearest_council(state: str, latitude: float, longitude: float) -> tuple[str, CouncilDashboard] | None:
    """Return the council a point most likely belongs to, or None.

    A council qualifies within ``COUNCIL_AUTO_MATCH_KM`` of its point, or within its own
    equal-area radius if that is larger (large rural councils). The qualifying councils are
    ranked by distance relative to their size, so a point in a big council is not given
    the smaller neighbour whose centre happens to be closer. This is a geographic
    heuristic, not a check against council boundaries.
    """
    best: tuple[float, str, CouncilDashboard] | None = None
    for key, council in COUNCIL_DASHBOARDS.items():
        if council["state"] != state:
            continue
        dist = _distance_km(latitude, longitude, council["latitude"], council["longitude"])
        if dist > max(COUNCIL_AUTO_MATCH_KM, council["radius_km"]):
            continue
        score = dist / max(council["radius_km"], _MIN_RANK_RADIUS_KM)
        if best is None or score < best[0]:
            best = (score, key, council)
    return (best[1], best[2]) if best else None


def nearest_readable_dashboard(state: str, latitude: float, longitude: float) -> str | None:
    """Return the closest readable dashboard within ``COUNCIL_AUTO_MATCH_KM`` (plain distance), or None."""
    best: tuple[float, str] | None = None
    for council in COUNCIL_DASHBOARDS.values():
        if council["state"] != state or not (url := usable_url(council)):
            continue
        dist = _distance_km(latitude, longitude, council["latitude"], council["longitude"])
        if dist <= COUNCIL_AUTO_MATCH_KM and (best is None or dist < best[0]):
            best = (dist, url)
    return best[1] if best else None


def usable_url(council: CouncilDashboard) -> str | None:
    """Return the dashboard URL the integration can read, or None."""
    return council["url"] if council["url"] and council["certificate_ok"] else None


def _normalise_url(url: str | None) -> str:
    """Return a URL for comparison: no scheme, no trailing slash, lower case."""
    return re.sub(r"^https?://", "", (url or "").strip().lower()).rstrip("/")


# How many neighbouring council dashboards the card links to.
NEARBY_COUNCIL_LINKS: Final = 6


def nearby_council_links(
    state: str, latitude: float | None, longitude: float | None, exclude_url: str | None = None
) -> list[dict[str, str]]:
    """Return links to the council dashboards nearest a point in ``state``, nearest first (#32).

    The links are shown on the card and never polled, so a dashboard whose certificate Home
    Assistant rejects is still linked (browsers open it). Councils without a dashboard and
    the entry's own dashboard (``exclude_url``) are left out. Without a point, the councils
    are listed by name.
    """
    own = _normalise_url(exclude_url)
    candidates = [
        council
        for council in COUNCIL_DASHBOARDS.values()
        if council["state"] == state and council["url"] and _normalise_url(council["url"]) != own
    ]
    if latitude is None or longitude is None:
        candidates.sort(key=lambda council: council["name"])
    else:
        candidates.sort(key=lambda c: _distance_km(latitude, longitude, c["latitude"], c["longitude"]))
    return [{"name": council["name"], "url": str(council["url"])} for council in candidates[:NEARBY_COUNCIL_LINKS]]
