"""Camera platform for Australian Disaster Watch.

Provides live snapshots of flood cameras and traffic webcams from council and road networks.
Camera entities follow the coordinator data: cameras that appear are added and cameras that
disappear are removed (their registry entries are kept, so a camera that comes back keeps
its entity ID and customisations) (#19).
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientTimeout

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AusNZDisasterWatchConfigEntry
from .const import DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity
from .models import DisasterCameraItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera entities and keep them in step with the coordinator's cameras."""
    coordinator = entry.runtime_data
    tracked: dict[str, AustralianDisasterWatchCamera] = {}

    @callback
    def _sync_entities() -> None:
        current = {camera.id for camera in coordinator.cameras}
        for camera_id in set(tracked) - current:
            entity = tracked.pop(camera_id)
            if entity.hass is not None:
                hass.async_create_task(entity.async_remove())
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

    _attr_icon = "mdi:cctv"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator, camera_id: str) -> None:
        """Initialize camera entity for the camera with ``camera_id``."""
        Camera.__init__(self)
        AustralianDisasterWatchEntity.__init__(self, coordinator, f"camera_{camera_id}")
        self.camera_id = camera_id
        item = self.camera_item
        self._attr_name = item.name if item else camera_id
        self._last_image: bytes | None = None

    @property
    def camera_item(self) -> DisasterCameraItem | None:
        """Return this camera's current data, or None if the feed no longer lists it."""
        return next((camera for camera in self.coordinator.cameras if camera.id == self.camera_id), None)

    @property
    def available(self) -> bool:
        """Return True while the coordinator is healthy and the camera is still listed."""
        return super().available and self.camera_item is not None

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture only when a valid image has been captured."""
        if self._last_image:
            return super().entity_picture
        return None

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Fetch the latest snapshot from the camera's current image URL."""
        item = self.camera_item
        if item is None:
            return None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(item.image_url, timeout=ClientTimeout(total=10), allow_redirects=True) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    self._last_image = data
                    return data
                _LOGGER.debug("Error fetching camera image %s from %s: HTTP %s", self.name, item.image_url, resp.status)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Network error fetching camera image %s: %s", self.name, err)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return camera location attributes."""
        attrs: dict[str, Any] = {"integration": DOMAIN}
        if (item := self.camera_item) is None:
            return attrs
        attrs["image_url"] = item.image_url
        if item.suburb:
            attrs["suburb"] = item.suburb
        if item.latitude is not None and item.longitude is not None:
            attrs["latitude"] = item.latitude
            attrs["longitude"] = item.longitude
        return attrs


AusNZDisasterWatchCamera = AustralianDisasterWatchCamera
