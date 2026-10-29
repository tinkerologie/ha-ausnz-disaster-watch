"""Road and flood camera catalogues from state road agencies (#70).

Opt-in per entry (options step "Road and flood cameras"). Each network publishes a keyless
catalogue of cameras with their location and a still-image URL:

- QLDTraffic flood cameras and web cameras (GeoJSON, CC BY 4.0). Coordinates are GDA2020
  (EPSG:7844), which differs from WGS84 by under two metres, so they are used as WGS84.
- NZ Transport Agency Waka Kotahi traffic cameras (JSON). Cameras flagged ``offline`` or
  ``underMaintenance`` are skipped.

Live Traffic NSW cameras are not used: their image host answers non-browser clients with
an HTML placeholder, and getting around that would mean pretending to be a browser. The
data source register records the request to Transport for NSW.

Catalogues change rarely, so each is fetched at most every six hours and its last good copy
is kept for a day. Images are fetched only when a camera entity is viewed (``camera.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
import logging
import re
from typing import Any, ClassVar
from urllib.parse import urlsplit

from custom_components.ausnz_disaster_watch.const import (
    CAMERA_NETWORK_NZTA,
    CAMERA_NETWORK_QLDTRAFFIC_FLOOD,
    CAMERA_NETWORK_QLDTRAFFIC_WEB,
    CONF_CAMERA_MAX,
    CONF_CAMERA_NETWORKS,
    CONF_CAMERA_RADIUS,
    DEFAULT_CAMERA_MAX,
    DEFAULT_CAMERA_RADIUS,
    STATE_NSW,
    STATE_NZ,
    STATE_QLD,
)
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, DisasterCameraItem

from .base import (
    MALFORMED_ITEM_ERRORS,
    BaseHazardProvider,
    FeedCache,
    PartialFeedError,
    ProviderUnavailableError,
    as_float,
)
from .cap import haversine_km
from .sources import DATA_SOURCES, DataSource

_LOGGER = logging.getLogger(__name__)

CATALOGUE_TTL = timedelta(hours=6)
CATALOGUE_MAX_STALE = timedelta(hours=24)

QLDTRAFFIC_FLOOD_CAMERAS_URL = "https://data.qldtraffic.qld.gov.au/floodcameras.geojson"
QLDTRAFFIC_WEB_CAMERAS_URL = "https://data.qldtraffic.qld.gov.au/webcameras.geojson"
NZTA_CAMERAS_URL = "https://trafficnz.info/service/traffic/rest/4/cameras/all"
NZTA_BASE_URL = "https://trafficnz.info"

# GeoJSON CRS names read as WGS84: GDA2020 (QLDTraffic) is within two metres of it
WGS84_COMPATIBLE_CRS = frozenset(
    {
        "EPSG:7844",
        "EPSG:4326",
        "urn:ogc:def:crs:EPSG::7844",
        "urn:ogc:def:crs:EPSG::4326",
        "urn:ogc:def:crs:OGC:1.3:CRS84",
    }
)


@dataclass(frozen=True, slots=True)
class CameraNetwork:
    """One camera catalogue: where it is, how to parse it and whose terms apply."""

    key: str
    url: str
    source_key: str
    parse: Callable[[Any, str], list[DisasterCameraItem]]
    headers: tuple[tuple[str, str], ...] = ()


def _text(value: Any) -> str | None:
    """Return a stripped non-empty string, else None."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    return text or None


def _https_url(value: Any, base: str | None = None) -> str | None:
    """Return an absolute https image URL (relative paths joined to ``base``), else None."""
    url = _text(value)
    if url is None:
        return None
    if url.startswith("/") and not url.startswith("//") and base:
        url = f"{base}{url}"
    return url if url.startswith("https://") else None


def _point(lat: Any, lon: Any) -> tuple[float, float] | None:
    """Return (lat, lon) inside the AU/NZ region (antimeridian included), else None."""
    lat_f, lon_f = as_float(lat), as_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if not (-56.0 <= lat_f <= -8.0 and (100.0 <= lon_f <= 180.0 or -180.0 <= lon_f <= -170.0)):
        return None
    return lat_f, lon_f


def _feature_point(geometry: Any) -> tuple[float, float] | None:
    """Return (lat, lon) of a GeoJSON Point in WGS84 or GDA2020, else None."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None
    crs = geometry.get("crs")
    if crs is not None:
        name = crs.get("properties", {}).get("name") if isinstance(crs, dict) else None
        if name not in WGS84_COMPATIBLE_CRS:
            return None
    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    return _point(coords[1], coords[0])


# Image file names that identify one camera: an ID-like stem (a UUID, or 16+ characters
# mixing letters and digits), never a generic name such as "latest.jpg" or "image.jpg"
_IMAGE_ID = re.compile(r"(?=.*\d)(?=.*[a-z])[a-z0-9_-]{16,}")
# About 10 m: two copies of one camera sit within this of each other
_SAME_PLACE_DECIMALS = 4
# Details the kept copy of a camera takes from a dropped copy when it has none: what a road
# network adds to a council dashboard copy, and the location a copy without geometry lacks
_FILLABLE_DETAILS = (
    "source_key",
    "direction",
    "owner",
    "description",
    "suburb",
    "distance_km",
    "latitude",
    "longitude",
    "in_council_area",
)


def _image_key(url: str) -> str | None:
    """Return the image file name when it identifies one camera, else None."""
    try:
        path = urlsplit(url).path
    except ValueError:  # e.g. an unclosed IPv6 bracket in the host
        return None
    name = path.rsplit("/", 1)[-1].lower()
    stem = name.rsplit(".", 1)[0]
    return name if _IMAGE_ID.fullmatch(stem) else None


def _name_key(name: str) -> str:
    """Return the name folded for comparison: case, dashes, slashes and spacing ignored."""
    return " ".join(re.sub(r"[^\w]+", " ", name.casefold()).split())


def _place_key(camera: DisasterCameraItem) -> tuple[float, float, str] | None:
    """Return (lat, lon, name) rounded to about 10 m, or None without a location."""
    if camera.latitude is None or camera.longitude is None:
        return None
    return (
        round(camera.latitude, _SAME_PLACE_DECIMALS),
        round(camera.longitude, _SAME_PLACE_DECIMALS),
        _name_key(camera.name),
    )


def _resolve_alias(aliases: dict[str, str], camera_id: str) -> str:
    """Return the ID ``camera_id`` was last merged into, following chains; itself on a cycle."""
    seen = {camera_id}
    current = camera_id
    while (target := aliases.get(current)) is not None:
        if target in seen:
            return camera_id
        seen.add(target)
        current = target
    return current


def merge_cameras(cameras: list[DisasterCameraItem], aliases: dict[str, str] | None = None) -> list[DisasterCameraItem]:
    """Return one camera per physical camera, in a stable order.

    Sources answer concurrently, so cameras arrive in any order. They are ordered first:
    council dashboard cameras, then road network cameras, each by ID. That way the same copy
    of a camera is kept on every refresh and its entity never changes. Two cameras are the
    same when they share an ID, the image file (a council dashboard often serves a copy of
    the road agency's image from its own host), or the place and name. The kept copy takes
    the details it lacks (network, direction, owner and so on) from the dropped one.

    ``aliases`` remembers, across refreshes, the ID each dropped copy was merged into. While
    the kept copy's source is down, the other copy takes that ID, so the camera keeps its
    entity instead of gaining a second one.
    """
    if aliases is None:
        aliases = {}
    present = {camera.id for camera in cameras}
    renamed: list[DisasterCameraItem] = []
    for camera in cameras:
        target = _resolve_alias(aliases, camera.id)
        renamed.append(replace(camera, id=target) if target != camera.id and target not in present else camera)
    cameras = renamed
    ordered = sorted(cameras, key=lambda camera: (camera.source_key is not None, camera.id))
    kept: list[DisasterCameraItem] = []
    index: dict[tuple[str, Any], int] = {}
    for camera in ordered:
        keys: list[tuple[str, Any]] = [("id", camera.id), ("image", camera.image_url)]
        if (image := _image_key(camera.image_url)) is not None:
            keys.append(("file", image))
        if (place := _place_key(camera)) is not None:
            keys.append(("place", place))
        match = next((index[key] for key in keys if key in index), None)
        if match is None:
            match = len(kept)
            kept.append(camera)
        else:
            current = kept[match]
            if camera.id != current.id:
                aliases[camera.id] = current.id
                # Earlier copies merged into this one now point at the kept ID too
                for alias, target in list(aliases.items()):
                    if target == camera.id:
                        aliases[alias] = current.id
            details = {
                name: getattr(camera, name)
                for name in _FILLABLE_DETAILS
                if getattr(current, name) is None and getattr(camera, name) is not None
            }
            if details:
                kept[match] = replace(current, **details)
        for key in keys:
            index.setdefault(key, match)
    return kept


def parse_qldtraffic(payload: Any, network: str) -> list[DisasterCameraItem]:
    """Parse a QLDTraffic camera GeoJSON (flood or web cameras)."""
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ProviderUnavailableError(f"{network} returned an unexpected payload")
    features = BaseHazardProvider.require_list(payload, "features", network)
    cameras: list[DisasterCameraItem] = []
    for feature in features:
        try:
            props = feature.get("properties") or {}
            point = _feature_point(feature.get("geometry"))
            image_url = _https_url(props.get("image_url"))
            camera_id = _text(props.get("id"))
            if point is None or image_url is None or camera_id is None:
                continue
            name = _text(props.get("description")) or _text(props.get("locality")) or f"Camera {camera_id}"
            cameras.append(
                DisasterCameraItem(
                    id=f"{network}_{camera_id}",
                    name=name,
                    image_url=image_url,
                    suburb=_text(props.get("locality")),
                    latitude=point[0],
                    longitude=point[1],
                    source_key="qldtraffic_cameras",
                    direction=_text(props.get("direction")),
                    owner=_text(props.get("image_sourced_from")),
                )
            )
        except MALFORMED_ITEM_ERRORS:
            continue
    return cameras


def parse_nzta(payload: Any, network: str) -> list[DisasterCameraItem]:
    """Parse the NZTA camera list, skipping offline cameras and cameras under maintenance."""
    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, dict):
        raise ProviderUnavailableError(f"{network} returned an unexpected payload")
    entries = response.get("camera")
    # The service returns a single camera as an object rather than a list
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        raise ProviderUnavailableError(f"{network} returned an unexpected payload ('camera' is not a list)")
    cameras: list[DisasterCameraItem] = []
    for entry in entries:
        try:
            if entry.get("offline") is not False or entry.get("underMaintenance") is True:
                continue
            point = _point(entry.get("latitude"), entry.get("longitude"))
            image_url = _https_url(entry.get("imageUrl"), NZTA_BASE_URL)
            camera_id = _text(entry.get("id"))
            if point is None or image_url is None or camera_id is None:
                continue
            region = entry.get("region")
            cameras.append(
                DisasterCameraItem(
                    id=f"{network}_{camera_id}",
                    name=_text(entry.get("name")) or f"Camera {camera_id}",
                    image_url=image_url,
                    suburb=_text(region.get("name")) if isinstance(region, dict) else None,
                    latitude=point[0],
                    longitude=point[1],
                    source_key="nzta_cameras",
                    direction=_text(entry.get("direction")),
                    description=_text(entry.get("description")),
                )
            )
        except MALFORMED_ITEM_ERRORS:
            continue
    return cameras


CAMERA_NETWORKS: dict[str, CameraNetwork] = {
    CAMERA_NETWORK_QLDTRAFFIC_FLOOD: CameraNetwork(
        CAMERA_NETWORK_QLDTRAFFIC_FLOOD, QLDTRAFFIC_FLOOD_CAMERAS_URL, "qldtraffic_cameras", parse_qldtraffic
    ),
    CAMERA_NETWORK_QLDTRAFFIC_WEB: CameraNetwork(
        CAMERA_NETWORK_QLDTRAFFIC_WEB, QLDTRAFFIC_WEB_CAMERAS_URL, "qldtraffic_cameras", parse_qldtraffic
    ),
    CAMERA_NETWORK_NZTA: CameraNetwork(
        CAMERA_NETWORK_NZTA, NZTA_CAMERAS_URL, "nzta_cameras", parse_nzta, (("Accept", "application/json"),)
    ),
}

# Networks offered per jurisdiction: QLDTraffic also lists cameras on the NSW side of the border
CAMERA_NETWORKS_BY_STATE: dict[str, tuple[str, ...]] = {
    STATE_QLD: (CAMERA_NETWORK_QLDTRAFFIC_FLOOD, CAMERA_NETWORK_QLDTRAFFIC_WEB),
    STATE_NSW: (CAMERA_NETWORK_QLDTRAFFIC_FLOOD, CAMERA_NETWORK_QLDTRAFFIC_WEB),
    STATE_NZ: (CAMERA_NETWORK_NZTA,),
}


def camera_networks_for_state(state: str) -> tuple[str, ...]:
    """Return the camera networks offered for a jurisdiction (none where no open catalogue exists)."""
    return CAMERA_NETWORKS_BY_STATE.get(state.upper(), ())


def enabled_networks(config: dict[str, Any]) -> list[str]:
    """Return the configured networks that apply to the entry's jurisdiction, in catalogue order."""
    chosen = config.get(CONF_CAMERA_NETWORKS) or []
    offered = camera_networks_for_state(str(config.get("state", STATE_QLD)))
    return [network for network in offered if isinstance(chosen, list) and network in chosen]


class CameraCatalogueProvider(BaseHazardProvider):
    """Cameras from the opted-in networks near the entry: within the camera radius, nearest first, capped."""

    provides_hazards: ClassVar[bool] = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise one catalogue cache per enabled network."""
        super().__init__(*args, **kwargs)
        self.networks = [CAMERA_NETWORKS[key] for key in enabled_networks(self.config)]
        self._caches: dict[str, FeedCache[list[DisasterCameraItem]]] = {
            network.key: FeedCache(f"{network.key} camera catalogue", CATALOGUE_TTL, CATALOGUE_MAX_STALE)
            for network in self.networks
        }

    @property
    def state_code(self) -> str:
        """Return the entry's jurisdiction."""
        return str(self.config.get("state", STATE_QLD)).upper()

    @property
    def data_sources(self) -> tuple[DataSource, ...]:
        """Return the register entries of the enabled networks only."""
        keys = dict.fromkeys(network.source_key for network in self.networks)
        return tuple(DATA_SOURCES[key] for key in keys)

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Return no hazards: cameras are auxiliary data."""
        return []

    async def _async_fetch_catalogue(self, network: CameraNetwork) -> list[DisasterCameraItem]:
        payload = await self.async_fetch_feed_json(network.url, network.key, headers=dict(network.headers) or None)
        return network.parse(payload, network.key)

    async def async_fetch_cameras(self) -> list[DisasterCameraItem]:
        """Return the nearest cameras of every enabled network.

        A network without a catalogue (failed, and no recent copy) adds none and makes the call
        raise ``PartialFeedError`` with the other networks' cameras, so its cameras are not
        taken as delisted (#92).
        """
        lat, lon = as_float(self.config.get("latitude")), as_float(self.config.get("longitude"))
        if lat is None or lon is None:
            return []
        radius = as_float(self.config.get(CONF_CAMERA_RADIUS)) or DEFAULT_CAMERA_RADIUS
        cap = int(as_float(self.config.get(CONF_CAMERA_MAX)) or DEFAULT_CAMERA_MAX)
        nearby: list[DisasterCameraItem] = []
        failed: list[str] = []
        for network in self.networks:
            catalogue = await self._caches[network.key].async_get(lambda n=network: self._async_fetch_catalogue(n))
            if catalogue is None:
                failed.append(network.key)
                continue
            for camera in catalogue:
                # The parsers only keep located cameras
                distance = haversine_km(lat, lon, float(camera.latitude or 0.0), float(camera.longitude or 0.0))
                if distance <= radius:
                    nearby.append(replace(camera, distance_km=round(distance, 1)))
        nearby.sort(key=lambda camera: camera.distance_km or 0.0)
        if failed:
            raise PartialFeedError(f"camera catalogue unavailable: {', '.join(failed)}", nearby[:cap])
        return nearby[:cap]
