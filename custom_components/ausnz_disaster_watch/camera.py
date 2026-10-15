"""Camera platform for Australian Disaster Watch.

Provides live snapshots of flood cameras and traffic webcams from council and road networks.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientTimeout

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity
from .models import DisasterCameraItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch camera entities."""
    coordinator: AustralianDisasterWatchCoordinator = hass.data[DOMAIN][entry.entry_id]

    cameras = coordinator.cameras
    if cameras:
        async_add_entities([AustralianDisasterWatchCamera(coordinator, cam) for cam in cameras])


class AustralianDisasterWatchCamera(Camera, AustralianDisasterWatchEntity):
    """Camera entity rendering live disaster and flood webcam snapshots."""

    def __init__(
        self,
        coordinator: AustralianDisasterWatchCoordinator,
        camera_item: DisasterCameraItem,
    ) -> None:
        """Initialize camera entity."""
        Camera.__init__(self)
        AustralianDisasterWatchEntity.__init__(self, coordinator, f"camera_{camera_item.id}")
        self._camera_id = camera_item.id
        self._image_url = camera_item.image_url
        self._attr_name = camera_item.name
        self._suburb = camera_item.suburb
        self._latitude = camera_item.latitude
        self._longitude = camera_item.longitude
        self._attr_icon = "mdi:cctv"

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Fetch latest snapshot image from upstream webcam URL."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self._image_url, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.debug(
                    "Error fetching camera image %s from %s: HTTP %s",
                    self.name,
                    self._image_url,
                    resp.status,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Network error fetching camera image %s: %s", self.name, err)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return camera location attributes."""
        attrs: dict[str, Any] = {
            "image_url": self._image_url,
        }
        if self._suburb:
            attrs["suburb"] = self._suburb
        if self._latitude is not None and self._longitude is not None:
            attrs["latitude"] = self._latitude
            attrs["longitude"] = self._longitude
        return attrs


AusNZDisasterWatchCamera = AustralianDisasterWatchCamera
