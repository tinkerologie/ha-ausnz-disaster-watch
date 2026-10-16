"""The local council area (LGA / territorial authority) of the monitored point (#94).

The boundary is looked up once per location and kept in a Home Assistant Store, so a
restart does not ask again: Australia from the ABS ASGS 2021 local government areas,
New Zealand from the Stats NZ territorial authorities. Both are open (CC BY 4.0) ArcGIS
services that need no key; the boundary is requested generalised (about 100 m), which is
small enough to store and fast enough to test every listed item against.

The area only tags items (``in_council_area``) so the dashboard cards can show what is in
the user's council. It never changes the radius-based entities: a hazard just over the
council border must still count for automations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from custom_components.ausnz_disaster_watch.const import DOMAIN, STATE_NZ
from custom_components.ausnz_disaster_watch.council_registry import COUNCIL_DASHBOARDS
from custom_components.ausnz_disaster_watch.models import CanonicalHazard
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .base import BaseHazardProvider, ProviderUnavailableError
from .cap import LatLon, point_in_polygon
from .sources import DATA_SOURCES, DataSource

_LOGGER = logging.getLogger(__name__)

# About 110 m: a large rural shire is ~75 KB, a city council a few KB
_MAX_OFFSET = 0.001
_QUERY = (
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
    f"&returnGeometry=true&outSR=4326&maxAllowableOffset={_MAX_OFFSET}&geometryPrecision=5&f=json"
)
ABS_LGA_AREA_URL = (
    "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/LGA/MapServer/0/query"
    + _QUERY
    + "&outFields=lga_code_2021,lga_name_2021"
)
STATS_NZ_TA_AREA_URL = (
    "https://services2.arcgis.com/vKb0s8tBIA3bdocZ/ArcGIS/rest/services/Territorial_Authority_2026/FeatureServer/0/query"
    + _QUERY
    + "&outFields=TA2026_V1_00,TA2026_V1_00_NAME"
)

COUNCIL_AREA_STORAGE_VERSION = 1
COUNCIL_AREA_STORAGE_KEY = f"{DOMAIN}.council_area.{{entry_id}}"
# A failed lookup is tried again after this long (the cards fall back to the radius meanwhile)
COUNCIL_AREA_RETRY = timedelta(minutes=30)

type Ring = tuple[LatLon, ...]


@dataclass(frozen=True, slots=True)
class CouncilArea:
    """A council boundary: rings of (lat, lon) points, holes included (even-odd rule)."""

    code: str
    name: str
    rings: tuple[Ring, ...]
    # (min lat, min lon, max lat, max lon), so most points are rejected without a ring test
    bbox: tuple[float, float, float, float] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Compute the bounding box."""
        lats = [lat for ring in self.rings for lat, _ in ring]
        lons = [lon for ring in self.rings for _, lon in ring]
        object.__setattr__(self, "bbox", (min(lats), min(lons), max(lats), max(lons)))

    def contains(self, lat: float | None, lon: float | None) -> bool | None:
        """Return whether a point is inside the council, or None for a point without coordinates."""
        if lat is None or lon is None:
            return None
        south, west, north, east = self.bbox
        if not (south <= lat <= north and west <= lon <= east):
            return False
        return sum(point_in_polygon(lat, lon, ring) for ring in self.rings) % 2 == 1

    def overlaps(self, area: tuple[Ring, ...]) -> bool:
        """Return whether a hazard area and the council overlap.

        Approximate: a vertex of either shape inside the other. Two shapes that only cross
        (no vertex of either inside the other) are rare for real boundaries.
        """
        south, west, north, east = self.bbox
        for ring in area:
            if not ring:
                continue
            if (
                max(lat for lat, _ in ring) < south
                or min(lat for lat, _ in ring) > north
                or max(lon for _, lon in ring) < west
                or min(lon for _, lon in ring) > east
            ):
                continue
            if any(self.contains(lat, lon) for lat, lon in ring):
                return True
            if any(point_in_polygon(lat, lon, ring) for council_ring in self.rings for lat, lon in council_ring):
                return True
        return False

    def tag_hazard(self, hazard: CanonicalHazard) -> bool:
        """Return whether a hazard is in the council: its point, or any part of its area (#94)."""
        return bool(self.contains(hazard.latitude, hazard.longitude)) or bool(
            hazard.area and self.overlaps(hazard.area)
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for the Store."""
        return {"code": self.code, "name": self.name, "rings": [[list(p) for p in ring] for ring in self.rings]}

    @classmethod
    def from_dict(cls, data: Any) -> CouncilArea | None:
        """Return the area a Store held, or None if it is not one."""
        try:
            rings = tuple(tuple((float(lat), float(lon)) for lat, lon in ring) for ring in data["rings"])
            if not rings or not all(len(ring) >= 3 for ring in rings):
                return None
            return cls(code=str(data["code"]), name=str(data["name"]), rings=rings)
        except (KeyError, TypeError, ValueError):
            return None


def _display_name(code: str, name: str, nz: bool) -> str:
    """Return the council's name: the registry's (``City of Moreton Bay``) when it lists the LGA."""
    if not nz:
        for council in COUNCIL_DASHBOARDS.values():
            if council["lga_code"] == code:
                return council["name"]
    return name


def parse_council_area(payload: Any, nz: bool) -> CouncilArea | None:
    """Return the council area from an ArcGIS query answer, or None when no council has the point.

    Raises ``ProviderUnavailableError`` when the answer is not a feature set (an error answer).
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise ProviderUnavailableError("not an ArcGIS feature set")
    for feature in payload["features"]:
        attributes = feature.get("attributes") or {}
        code_field, name_field = ("TA2026_V1_00", "TA2026_V1_00_NAME") if nz else ("lga_code_2021", "lga_name_2021")
        code, name = attributes.get(code_field), attributes.get(name_field)
        rings = (feature.get("geometry") or {}).get("rings") or []
        parsed = tuple(
            tuple((float(lat), float(lon)) for lon, lat in ring)
            for ring in rings
            if isinstance(ring, list) and len(ring) >= 3
        )
        if code and name and parsed:
            return CouncilArea(code=str(code), name=_display_name(str(code), str(name), nz), rings=parsed)
    return None


async def async_remove_stored_council_area(hass: Any, entry_id: str) -> None:
    """Delete the stored council area of a removed entry."""
    await Store(hass, COUNCIL_AREA_STORAGE_VERSION, COUNCIL_AREA_STORAGE_KEY.format(entry_id=entry_id)).async_remove()


class CouncilAreaService(BaseHazardProvider):
    """Resolves the council area of the monitored point; publishes no hazards."""

    provides_hazards = False

    def __init__(self, *args: Any, entry_id: str | None = None, **kwargs: Any) -> None:
        """Initialise; nothing is looked up until the first update."""
        super().__init__(*args, **kwargs)
        self.area: CouncilArea | None = None
        # The location ``area`` belongs to (resolved, possibly to no council)
        self._resolved: tuple[float, float] | None = None
        # After a failed lookup: the point and when to try it again
        self._retry: tuple[tuple[float, float], datetime] | None = None
        self._restored = False
        self._store: Store[dict[str, Any]] | None = (
            Store(self.hass, COUNCIL_AREA_STORAGE_VERSION, COUNCIL_AREA_STORAGE_KEY.format(entry_id=entry_id))
            if entry_id
            else None
        )

    @property
    def state_code(self) -> str:
        """Return the configured jurisdiction."""
        return str(self.config.get("state", "")).upper()

    @property
    def data_sources(self) -> tuple[DataSource, ...]:
        """Return the boundary source for the configured country."""
        return (DATA_SOURCES["stats_nz_ta" if self.state_code == STATE_NZ else "abs_lga"],)

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Publish no hazards."""
        return []

    def _location(self) -> tuple[float, float] | None:
        try:
            return round(float(self.config["latitude"]), 5), round(float(self.config["longitude"]), 5)
        except (KeyError, TypeError, ValueError):
            return None

    async def async_update(self) -> None:
        """Look up the council area when the location changed. Never raises."""
        location = self._location()
        if location is None:
            self.area, self._resolved = None, None
            return
        await self._async_restore(location)
        if self._resolved == location:
            return
        # Whatever area is held belongs to another point: never tag with it
        self.area, self._resolved = None, None
        now = dt_util.utcnow()
        if self._retry is not None and self._retry[0] == location and now < self._retry[1]:
            return
        nz = self.state_code == STATE_NZ
        url = (STATS_NZ_TA_AREA_URL if nz else ABS_LGA_AREA_URL).format(lat=location[0], lon=location[1])
        try:
            payload = await self.async_fetch_feed_json(url, "Stats NZ territorial authority" if nz else "ABS LGA")
            area = parse_council_area(payload, nz)
        except Exception as err:  # noqa: BLE001 - the council area is best effort; cards fall back to the radius
            _LOGGER.debug("Council area lookup failed; trying again later: %s", err)
            self._retry = (location, now + COUNCIL_AREA_RETRY)
            return
        self.area, self._resolved, self._retry = area, location, None
        await self._async_persist(location)

    async def _async_restore(self, location: tuple[float, float]) -> None:
        """Load the stored area once; it is used only if it belongs to this location."""
        if self._restored or self._store is None:
            return
        self._restored = True
        try:
            stored = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 - a damaged store only means one more lookup
            _LOGGER.debug("Ignoring the stored council area: %s", err)
            return
        if not isinstance(stored, dict) or stored.get("location") != list(location):
            return
        if stored.get("area") is None:
            self._resolved = location  # the point is in no council
        elif (area := CouncilArea.from_dict(stored["area"])) is not None:
            self.area, self._resolved = area, location

    async def _async_persist(self, location: tuple[float, float]) -> None:
        if self._store is not None:
            await self._store.async_save(
                {"location": list(location), "area": self.area.to_dict() if self.area else None}
            )
