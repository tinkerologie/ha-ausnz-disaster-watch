"""Base entity class for Australian Emergency Hazards integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOCATION_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import EmergencyDataCoordinator


class EmergencyHazardBaseEntity(CoordinatorEntity[EmergencyDataCoordinator]):
    """Base entity for Australian Emergency Hazards."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EmergencyDataCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.entity_key = entity_key
        state = coordinator.state_code
        loc_name = coordinator.combined_config.get(CONF_LOCATION_NAME, "Home")

        # Unique ID for entity
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{entity_key}"

        # Group all entities under a unified device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"{DEFAULT_NAME} ({state} - {loc_name})",
            manufacturer="Emergency Services Australia / Local Councils",
            model=f"Disaster Monitor ({state})",
            entry_type=DeviceEntryType.SERVICE,
        )
