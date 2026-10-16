"""Camera platform for Australian Disaster Watch.

Provides live snapshots of flood cameras and traffic webcams from council and road networks.
Camera entities follow the coordinator data: cameras that appear are added and cameras that
disappear are removed with their registry entries (#19, #92), as are registry entries left by
cameras that went while Home Assistant was stopped or whose ID changed. A camera is taken as
gone only after a refresh that heard from every camera source; while one is down, its cameras
stay, unavailable. A camera that comes back is re-created, with the same entity ID: it is
derived from the camera's name.

A fetched frame is kept only if its bytes are an image (JPEG, PNG, GIF or WebP magic
bytes), whatever the Content-Type says: some hosts label JPEGs ``binary/octet-stream`` and
others answer a missing image with an HTML page and status 200. Anything else is never
cached as the snapshot; the last good frame is returned instead (#70).
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponse, ClientTimeout

from homeassistant.components.camera import Camera
from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AusNZDisasterWatchConfigEntry
from .const import DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity, camera_unique_id
from .entity_lifecycle import async_remove_registry_entries, cameras_complete
from .models import DisasterCameraItem
from .providers.sources import DATA_SOURCES

_LOGGER = logging.getLogger(__name__)

# Entities only read coordinator data; the coordinator does all fetching
PARALLEL_UPDATES = 0

# Largest frame accepted; QLDTraffic's "resized" flood camera frames are about 0.8 MB
MAX_FRAME_BYTES = 8 * 1024 * 1024


def image_content_type(data: bytes) -> str | None:
    """Return the image MIME type from the leading magic bytes, or None if ``data`` is not an image."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def _async_read_image(resp: ClientResponse) -> tuple[bytes, str] | None:
    """Return the body and its image type, or None if it is not an image or exceeds MAX_FRAME_BYTES."""
    length = resp.headers.get("Content-Length", "")
    if length.isdigit() and int(length) > MAX_FRAME_BYTES:
        return None
    body = bytearray()
    async for chunk in resp.content.iter_chunked(64 * 1024):
        body += chunk
        if len(body) > MAX_FRAME_BYTES:
            return None
    data = bytes(body)
    content_type = image_content_type(data)
    return (data, content_type) if content_type is not None else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera entities and keep them in step with the coordinator's cameras."""
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    tracked: dict[str, AustralianDisasterWatchCamera] = {}
    removing: set[str] = set()
    registry_cleaned = False

    async def _async_remove(camera_id: str, entity: AustralianDisasterWatchCamera) -> None:
        # Keep the ID tracked until the old entity is gone: re-adding a camera whose old
        # entity still exists would be rejected as a unique-ID collision.
        try:
            if entity.entity_id and registry.async_get(entity.entity_id) is not None:
                registry.async_remove(entity.entity_id)
            await entity.async_remove(force_remove=True)
        finally:
            tracked.pop(camera_id, None)
            removing.discard(camera_id)
            _sync_entities()

    @callback
    def _sync_entities() -> None:
        nonlocal registry_cleaned
        current = {camera.id for camera in coordinator.cameras}
        complete = cameras_complete(coordinator)
        if complete and not registry_cleaned:
            # Once per setup, after the first complete refresh: entries of cameras that went
            # while Home Assistant was stopped, or whose ID changed, would otherwise come back
            # as "unavailable" entities.
            registry_cleaned = True
            keep = {camera_unique_id(entry.entry_id, camera_id) for camera_id in current | set(tracked)}
            async_remove_registry_entries(hass, entry.entry_id, (CAMERA_DOMAIN,), keep)
        gone = set(tracked) - current - removing if complete else set()
        for camera_id in gone:
            entity = tracked[camera_id]
            if entity.hass is None:
                tracked.pop(camera_id)
                continue
            removing.add(camera_id)
            hass.async_create_task(_async_remove(camera_id, entity))
        new_entities = [
            AustralianDisasterWatchCamera(coordinator, camera_id) for camera_id in current if camera_id not in tracked
        ]
        for entity in new_entities:
            tracked[entity.camera_id] = entity
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class AustralianDisasterWatchCamera(Camera, AustralianDisasterWatchEntity):
    """Camera entity rendering live disaster and flood webcam snapshots."""

    _attr_translation_key = "disaster_camera"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator, camera_id: str) -> None:
        """Initialize camera entity for the camera with ``camera_id``."""
        Camera.__init__(self)
        AustralianDisasterWatchEntity.__init__(self, coordinator, f"camera_{camera_id}")
        self.camera_id = camera_id
        item = self.camera_item
        self._attr_name = item.name if item else camera_id
        self._last_image: bytes | None = None
        self._last_content_type = self.content_type

    @property
    def camera_item(self) -> DisasterCameraItem | None:
        """Return this camera's current data, or None if the feed no longer lists it."""
        return next((camera for camera in self.coordinator.cameras if camera.id == self.camera_id), None)

    @property
    def available(self) -> bool:
        """Return True while the coordinator is healthy and the camera is still listed."""
        return super().available and self.camera_item is not None

    @property
    def attribution(self) -> str | None:
        """Credit the camera's network and image owner; council dashboard cameras credit the entry's sources."""
        item = self.camera_item
        source = DATA_SOURCES.get(item.source_key) if item and item.source_key else None
        if item is None or source is None:
            return super().attribution
        return f"{source.attribution}. Image: {item.owner}" if item.owner else source.attribution

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture only when a valid image has been captured."""
        if self._last_image:
            return super().entity_picture
        return None

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Fetch the latest snapshot; keep it only if it is an image, else return the last good frame."""
        item = self.camera_item
        if item is None:
            return None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(item.image_url, timeout=ClientTimeout(total=10), allow_redirects=True) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Error fetching camera image %s from %s: HTTP %s", self.name, item.image_url, resp.status
                    )
                elif (frame := await _async_read_image(resp)) is not None:
                    data, content_type = frame
                    self._last_image = data
                    self._last_content_type = self.content_type = content_type
                    return data
                else:
                    # An HTML "image unavailable" page (HTTP 200) or an oversized body: never cache it
                    _LOGGER.debug(
                        "Camera image %s from %s is not an image (Content-Type %s)",
                        self.name,
                        item.image_url,
                        resp.headers.get("Content-Type"),
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Network error fetching camera image %s: %s", self.name, err)
        # Keep showing the last good frame rather than a broken image
        if self._last_image is not None:
            self.content_type = self._last_content_type
        return self._last_image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return camera location attributes."""
        attrs: dict[str, Any] = {"integration": DOMAIN}
        if (item := self.camera_item) is None:
            return attrs
        attrs["image_url"] = item.image_url
        if item.suburb:
            attrs["suburb"] = item.suburb
        for key in ("description", "direction", "owner", "distance_km"):
            if (value := getattr(item, key)) is not None:
                attrs[key] = value
        if item.source_key:
            attrs["network"] = item.source_key
        if item.latitude is not None and item.longitude is not None:
            attrs["latitude"] = item.latitude
            attrs["longitude"] = item.longitude
        if item.in_council_area is not None:
            attrs["in_council_area"] = item.in_council_area
        return attrs


AusNZDisasterWatchCamera = AustralianDisasterWatchCamera
