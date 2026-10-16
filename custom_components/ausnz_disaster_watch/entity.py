"""Base entity class for Australia and New Zealand Disaster Watch integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOCATION_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import AustralianDisasterWatchCoordinator


class AusNZDisasterWatchEntity(CoordinatorEntity[AustralianDisasterWatchCoordinator]):
    """Base entity for Australia and New Zealand Disaster Watch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AustralianDisasterWatchCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.entity_key = entity_key

        # Credit the upstream publishers as their terms require (#34)
        self._attr_attribution = coordinator.attribution

        # Unique ID for entity
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{entity_key}"

        # Group all entities under a unified device
        self._attr_device_info = entry_device_info(coordinator)


def entry_device_info(coordinator: AustralianDisasterWatchCoordinator) -> DeviceInfo:
    """Return the one service device every entity of an entry belongs to."""
    state = coordinator.state_code
    loc_name = coordinator.combined_config.get(CONF_LOCATION_NAME, "Home")
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        name=f"{DEFAULT_NAME} ({state} - {loc_name})",
        manufacturer="Emergency Services Australia & New Zealand / Local Councils",
        model=f"Disaster Monitor ({state})",
        entry_type=DeviceEntryType.SERVICE,
    )


AustralianDisasterWatchEntity = AusNZDisasterWatchEntity
EmergencyHazardBaseEntity = AusNZDisasterWatchEntity
