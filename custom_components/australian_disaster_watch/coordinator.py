"""DataUpdateCoordinator for Australian Disaster Watch."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, THREAT_SCAN_INTERVAL
from .models import CanonicalHazard, DisasterWatchConfigModel, WarningLevel
from .providers import get_providers_for_config

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def calculate_haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two points in kilometres."""
    # Earth radius in kilometres
    r = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class AustralianDisasterWatchCoordinator(DataUpdateCoordinator[dict[str, CanonicalHazard]]):
    """Coordinator to manage polling of emergency hazards with spatial filtering."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self._update_config_values()

        session = async_get_clientsession(hass)
        self.providers = get_providers_for_config(hass, session, self.combined_config)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.state_code}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _update_config_values(self) -> None:
        """Update internal parameters from entry data and options using Pydantic."""
        # Merge data and options (options take precedence)
        self.combined_config: dict[str, Any] = {
            **self.entry.data,
            **self.entry.options,
        }

        # Validate using Pydantic v2 model
        cfg = DisasterWatchConfigModel.model_validate(self.combined_config)
        self.state_code: str = cfg.state.upper()
        self.radius_km: float = float(cfg.radius)
        self.override_emergency: bool = cfg.override_emergency
        self.exclude_hazard_reduction: bool = cfg.exclude_hazard_reduction

        # Latitude and Longitude (fallback to HA default home location)
        self.latitude: float = float(cfg.latitude or self.hass.config.latitude or -27.2657)
        self.longitude: float = float(cfg.longitude or self.hass.config.longitude or 152.9818)

    def update_options(self) -> None:
        """Handle options update without full integration reload."""
        self._update_config_values()
        session = async_get_clientsession(self.hass)
        self.providers = get_providers_for_config(self.hass, session, self.combined_config)

    async def _async_update_data(self) -> dict[str, CanonicalHazard]:
        """Fetch all hazards from active providers and filter by location and radius."""
        all_hazards: list[CanonicalHazard] = []

        for provider in self.providers:
            try:
                hazards = await provider.async_fetch_hazards()
                all_hazards.extend(hazards)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Error fetching data from provider %s: %s",
                    provider.__class__.__name__,
                    err,
                )

        filtered_hazards: dict[str, CanonicalHazard] = {}
        has_active_threat = False

        for hazard in all_hazards:
            # Drop hazard reduction burns if configured
            if self.exclude_hazard_reduction and hazard.is_hazard_reduction:
                continue

            # Calculate Haversine distance
            dist = calculate_haversine_distance(
                self.latitude,
                self.longitude,
                hazard.latitude,
                hazard.longitude,
            )
            hazard.distance_km = dist

            # Check if within radius OR statewide emergency warning override applies
            within_radius = dist <= self.radius_km
            is_emergency_override = self.override_emergency and hazard.warning_level == WarningLevel.EMERGENCY_WARNING

            if within_radius or is_emergency_override:
                filtered_hazards[hazard.id] = hazard
                if hazard.is_active_threat:
                    has_active_threat = True

        # Dynamic Polling Interval Adjustment
        if has_active_threat:
            if self.update_interval != timedelta(seconds=THREAT_SCAN_INTERVAL):
                _LOGGER.info(
                    "Active emergency warning or threat detected nearby; increasing poll frequency to %ss",
                    THREAT_SCAN_INTERVAL,
                )
                self.update_interval = timedelta(seconds=THREAT_SCAN_INTERVAL)
        elif self.update_interval != timedelta(seconds=DEFAULT_SCAN_INTERVAL):
            _LOGGER.debug(
                "No active threats nearby; setting poll frequency to standard %ss",
                DEFAULT_SCAN_INTERVAL,
            )
            self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        return filtered_hazards

    @property
    def active_hazards(self) -> list[CanonicalHazard]:
        """Return list of all active hazards currently in perimeter."""
        if not self.data:
            return []
        return list(self.data.values())

    @property
    def nearest_hazard(self) -> CanonicalHazard | None:
        """Return the closest hazard to configured location."""
        hazards = self.active_hazards
        if not hazards:
            return None
        return min(
            hazards,
            key=lambda h: h.distance_km if h.distance_km is not None else float("inf"),
        )

    @property
    def highest_warning_level(self) -> WarningLevel:
        """Return the highest warning level currently active in perimeter."""
        hazards = self.active_hazards
        if not hazards:
            return WarningLevel.INFORMATION
        return max(
            (h.warning_level for h in hazards),
            key=lambda lvl: lvl.severity_rank,
            default=WarningLevel.INFORMATION,
        )

    @property
    def has_emergency_warning_nearby(self) -> bool:
        """Return True if any Emergency Warning or Watch and Act is active nearby."""
        return any(h.is_active_threat for h in self.active_hazards)


EmergencyDataCoordinator = AustralianDisasterWatchCoordinator
