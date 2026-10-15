"""DataUpdateCoordinator for Australian Disaster Watch."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LAST_GOOD_MAX_AGE, THREAT_SCAN_INTERVAL
from .models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCameraItem,
    DisasterCoordinatorData,
    DisasterWatchConfigModel,
    EmergencyNewsItem,
    FireDangerRating,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WarningLevel,
    WeatherStationObservation,
    WeatherWarningItem,
)
from .providers import get_providers_for_config
from .providers.base import ProviderUnavailableError

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


def _unique_by_title(warnings: list[WeatherWarningItem]) -> list[WeatherWarningItem]:
    """Drop repeated warnings, keeping order.

    The key includes the affected locations: generic titles such as "Severe Thunderstorm
    Warning" are reused by every state, so title alone would merge different warnings.
    """
    seen: set[tuple[str, str | None]] = set()
    unique: list[WeatherWarningItem] = []
    for warning in warnings:
        key = (warning.title, warning.locations)
        if key not in seen:
            seen.add(key)
            unique.append(warning)
    return unique


class AustralianDisasterWatchCoordinator(DataUpdateCoordinator[DisasterCoordinatorData]):
    """Coordinator to manage polling of emergency hazards with spatial filtering."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator.

        The base class is initialised first so ``self.hass`` exists before the config
        values (which may fall back to the Home Assistant home location) are read.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{str(entry.data.get('state', 'QLD')).upper()}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self._feed_healthy: dict[str, bool] = {}
        self._last_good_hazards: dict[str, tuple[datetime, list[CanonicalHazard]]] = {}
        self._feeds_ok: list[str] = []
        self._feeds_failed: list[str] = []
        self._update_config_values()

        session = async_get_clientsession(hass)
        # Providers that measure distance to warning areas need the resolved home location
        provider_config = {**self.combined_config, "latitude": self.latitude, "longitude": self.longitude}
        self.providers = get_providers_for_config(hass, session, provider_config)

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

    async def _async_fetch_all_hazards(self) -> list[CanonicalHazard]:
        """Fetch all hazards from active providers concurrently, tracking each feed's health (#16).

        A failed provider contributes its last good hazards so a transient outage does not
        look like an all-clear. Health transitions are logged once (warning when a feed goes
        down, info when it recovers). If every provider fails, UpdateFailed makes the entities
        unavailable and, on first refresh, puts the entry into setup retry.
        """
        results = await asyncio.gather(
            *(provider.async_fetch_hazards() for provider in self.providers),
            return_exceptions=True,
        )
        all_hazards: list[CanonicalHazard] = []
        feeds_ok: list[str] = []
        feeds_failed: list[str] = []
        for provider, result in zip(self.providers, results, strict=True):
            key = type(provider).__name__
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result  # e.g. CancelledError
                feeds_failed.append(key)
                if self._feed_healthy.get(key, True):
                    _LOGGER.warning("Hazard feed %s is unavailable: %s", key, result)
                else:
                    _LOGGER.debug("Hazard feed %s still unavailable: %s", key, result)
                if not isinstance(result, ProviderUnavailableError):
                    _LOGGER.debug("Unexpected error from %s", key, exc_info=result)
                self._feed_healthy[key] = False
                # Bridge short outages with the last good data, but never indefinitely: a
                # cancelled warning must not stay active through a long outage.
                if (cached := self._last_good_hazards.get(key)) and dt_util.utcnow() - cached[0] <= LAST_GOOD_MAX_AGE:
                    all_hazards.extend(cached[1])
                continue
            feeds_ok.append(key)
            if self._feed_healthy.get(key) is False:
                _LOGGER.info("Hazard feed %s is available again", key)
            self._feed_healthy[key] = True
            self._last_good_hazards[key] = (dt_util.utcnow(), result)
            all_hazards.extend(result)

        self._feeds_ok = feeds_ok
        self._feeds_failed = feeds_failed
        if self.providers and not feeds_ok:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="feeds_unavailable",
                translation_placeholders={"feeds": ", ".join(feeds_failed)},
            )
        return all_hazards

    def _filter_and_process_hazards(
        self, all_hazards: list[CanonicalHazard]
    ) -> tuple[dict[str, CanonicalHazard], bool]:
        """Filter hazards by radius and active threat status."""
        filtered_hazards: dict[str, CanonicalHazard] = {}
        has_active_threat = False

        for hazard in all_hazards:
            if self.exclude_hazard_reduction and hazard.is_hazard_reduction:
                continue

            if hazard.distance_km is not None:
                # Provider-supplied distance to the warning *area* (0 when home is inside it);
                # the centroid of a large district can be far away even when home is inside (#10)
                dist = hazard.distance_km
            else:
                dist = calculate_haversine_distance(
                    self.latitude,
                    self.longitude,
                    hazard.latitude,
                    hazard.longitude,
                )
                hazard.distance_km = dist

            within_radius = dist <= self.radius_km
            is_emergency_override = self.override_emergency and hazard.warning_level == WarningLevel.EMERGENCY_WARNING

            if within_radius or is_emergency_override:
                filtered_hazards[hazard.id] = hazard
                if hazard.is_active_threat:
                    has_active_threat = True

        return filtered_hazards, has_active_threat

    async def _collect_infrastructure(
        self,
        provider: Any,
        power_outages: list[PowerOutageItem],
        road_closures: list[RoadClosureItem],
        relief_facilities: list[ReliefFacilityItem],
    ) -> None:
        """Collect power outages, road closures, and relief facilities from a provider concurrently."""

        async def _fetch_power() -> None:
            try:
                po = await provider.async_fetch_power_outages()
                if isinstance(po, list):
                    for item in po:
                        if isinstance(item, PowerOutageItem):
                            if item.latitude is not None and item.longitude is not None:
                                dist = round(
                                    calculate_haversine_distance(
                                        self.latitude, self.longitude, item.latitude, item.longitude
                                    ),
                                    2,
                                )
                                if dist <= self.radius_km:
                                    power_outages.append(item)
                            else:
                                power_outages.append(item)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating power outages from %s: %s", provider.__class__.__name__, err)

        async def _fetch_roads() -> None:
            try:
                rc = await provider.async_fetch_road_closures()
                if isinstance(rc, list):
                    for item in rc:
                        if (
                            isinstance(item, RoadClosureItem)
                            and item.latitude is not None
                            and item.longitude is not None
                        ):
                            dist = round(
                                calculate_haversine_distance(
                                    self.latitude, self.longitude, item.latitude, item.longitude
                                ),
                                2,
                            )
                            item.distance_km = dist
                            if dist <= self.radius_km:
                                road_closures.append(item)
                        elif isinstance(item, RoadClosureItem):
                            road_closures.append(item)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating road closures from %s: %s", provider.__class__.__name__, err)

        async def _fetch_relief() -> None:
            try:
                rf = await provider.async_fetch_relief_facilities()
                if isinstance(rf, list):
                    for item in rf:
                        if (
                            isinstance(item, ReliefFacilityItem)
                            and item.latitude is not None
                            and item.longitude is not None
                        ):
                            dist = round(
                                calculate_haversine_distance(
                                    self.latitude, self.longitude, item.latitude, item.longitude
                                ),
                                2,
                            )
                            item.distance_km = dist
                            if dist <= self.radius_km:
                                relief_facilities.append(item)
                        elif isinstance(item, ReliefFacilityItem):
                            relief_facilities.append(item)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating relief facilities from %s: %s", provider.__class__.__name__, err)

        await asyncio.gather(_fetch_power(), _fetch_roads(), _fetch_relief())

    async def _collect_environmental(
        self,
        provider: Any,
        weather_warnings: list[WeatherWarningItem],
        emergency_news: list[EmergencyNewsItem],
        weather_stations: list[WeatherStationObservation],
        air_quality_stations: list[AirQualityStationData],
    ) -> None:
        """Collect weather warnings, news, weather stations, and air quality from a provider concurrently."""

        async def _fetch_warnings() -> None:
            try:
                ww = await provider.async_fetch_weather_warnings()
                if isinstance(ww, list):
                    weather_warnings.extend([item for item in ww if isinstance(item, WeatherWarningItem)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating weather warnings from %s: %s", provider.__class__.__name__, err)

        async def _fetch_news() -> None:
            try:
                en = await provider.async_fetch_emergency_news()
                if isinstance(en, list):
                    emergency_news.extend([item for item in en if isinstance(item, EmergencyNewsItem)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating emergency news from %s: %s", provider.__class__.__name__, err)

        async def _fetch_stations() -> None:
            try:
                ws = await provider.async_fetch_weather_telemetry()
                if isinstance(ws, list):
                    weather_stations.extend([item for item in ws if isinstance(item, WeatherStationObservation)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating weather telemetry from %s: %s", provider.__class__.__name__, err)

        async def _fetch_aq() -> None:
            try:
                aq = await provider.async_fetch_air_quality()
                if isinstance(aq, list):
                    air_quality_stations.extend([item for item in aq if isinstance(item, AirQualityStationData)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating air quality from %s: %s", provider.__class__.__name__, err)

        await asyncio.gather(_fetch_warnings(), _fetch_news(), _fetch_stations(), _fetch_aq())

    async def _collect_cameras_and_councils(
        self,
        provider: Any,
        cameras: list[DisasterCameraItem],
        nearby_councils: list[dict[str, str]],
    ) -> None:
        """Collect cameras and nearby council links from a provider concurrently."""

        async def _fetch_cam() -> None:
            try:
                cam = await provider.async_fetch_cameras()
                if isinstance(cam, list):
                    cameras.extend([item for item in cam if isinstance(item, DisasterCameraItem)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating cameras from %s: %s", provider.__class__.__name__, err)

        async def _fetch_councils() -> None:
            try:
                nc = await provider.async_fetch_nearby_councils()
                if isinstance(nc, list):
                    nearby_councils.extend([item for item in nc if isinstance(item, dict)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating nearby councils from %s: %s", provider.__class__.__name__, err)

        await asyncio.gather(_fetch_cam(), _fetch_councils())

    async def _async_fetch_composite_feeds(self) -> dict[str, Any]:
        """Collect auxiliary telemetry and relief information from providers."""
        power_outages: list[PowerOutageItem] = []
        road_closures: list[RoadClosureItem] = []
        weather_warnings: list[WeatherWarningItem] = []
        emergency_news: list[EmergencyNewsItem] = []
        fire_danger: FireDangerRating | None = None
        weather_stations: list[WeatherStationObservation] = []
        air_quality_stations: list[AirQualityStationData] = []
        relief_facilities: list[ReliefFacilityItem] = []
        cameras: list[DisasterCameraItem] = []
        nearby_councils: list[dict[str, str]] = []

        coros = []
        for provider in self.providers:
            coros.append(self._collect_infrastructure(provider, power_outages, road_closures, relief_facilities))
            coros.append(
                self._collect_environmental(
                    provider, weather_warnings, emergency_news, weather_stations, air_quality_stations
                )
            )
            coros.append(self._collect_cameras_and_councils(provider, cameras, nearby_councils))

        if coros:
            await asyncio.gather(*coros)

        for provider in self.providers:
            if fire_danger is None:
                try:
                    fd = await provider.async_fetch_fire_danger()
                    if isinstance(fd, FireDangerRating):
                        fire_danger = fd
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Error updating fire danger from %s: %s", provider.__class__.__name__, err)

        return {
            "power_outages": power_outages,
            "road_closures": road_closures,
            "weather_warnings": _unique_by_title(weather_warnings),
            "emergency_news": emergency_news,
            "fire_danger": fire_danger,
            "weather_stations": weather_stations,
            "air_quality_stations": air_quality_stations,
            "relief_facilities": relief_facilities,
            "cameras": cameras,
            "nearby_councils": nearby_councils,
        }

    async def _async_update_data(self) -> DisasterCoordinatorData:
        """Fetch all hazards and telemetry from active providers."""
        all_hazards = await self._async_fetch_all_hazards()
        filtered_hazards, has_active_threat = self._filter_and_process_hazards(all_hazards)
        aux = await self._async_fetch_composite_feeds()

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

        return DisasterCoordinatorData(
            hazards=filtered_hazards,
            power_outages=aux["power_outages"],
            road_closures=aux["road_closures"],
            weather_warnings=aux["weather_warnings"],
            emergency_news=aux["emergency_news"],
            fire_danger=aux["fire_danger"],
            weather_stations=aux["weather_stations"],
            air_quality_stations=aux["air_quality_stations"],
            relief_facilities=aux["relief_facilities"],
            cameras=aux["cameras"],
            nearby_councils=aux["nearby_councils"],
            feeds_ok=self._feeds_ok,
            feeds_failed=self._feeds_failed,
        )

    @property
    def active_hazards(self) -> list[CanonicalHazard]:
        """Return list of all active hazards currently in perimeter."""
        if not self.data:
            return []
        if isinstance(self.data, dict):
            return list(self.data.values())
        if hasattr(self.data, "hazards") and self.data.hazards:
            return list(self.data.hazards.values())
        return []

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

    @property
    def power_outages(self) -> list[Any]:
        """Return active power outages."""
        return getattr(self.data, "power_outages", []) if self.data is not None else []

    @property
    def road_closures(self) -> list[Any]:
        """Return active road closures."""
        return getattr(self.data, "road_closures", []) if self.data is not None else []

    @property
    def weather_warnings(self) -> list[Any]:
        """Return active weather warnings."""
        return getattr(self.data, "weather_warnings", []) if self.data is not None else []

    @property
    def emergency_news(self) -> list[Any]:
        """Return active emergency bulletins."""
        return getattr(self.data, "emergency_news", []) if self.data is not None else []

    @property
    def fire_danger(self) -> Any | None:
        """Return current AFDRS fire danger rating."""
        return getattr(self.data, "fire_danger", None) if self.data is not None else None

    @property
    def weather_stations(self) -> list[Any]:
        """Return local weather telemetry stations."""
        return getattr(self.data, "weather_stations", []) if self.data is not None else []

    @property
    def air_quality_stations(self) -> list[Any]:
        """Return air quality stations."""
        return getattr(self.data, "air_quality_stations", []) if self.data is not None else []

    @property
    def relief_facilities(self) -> list[Any]:
        """Return relief facilities."""
        return getattr(self.data, "relief_facilities", []) if self.data is not None else []

    @property
    def cameras(self) -> list[Any]:
        """Return flood and traffic webcams."""
        return getattr(self.data, "cameras", []) if self.data is not None else []

    @property
    def nearby_councils(self) -> list[dict[str, str]]:
        """Return nearby council dashboard links."""
        return getattr(self.data, "nearby_councils", []) if self.data is not None else []


AusNZDisasterWatchCoordinator = AustralianDisasterWatchCoordinator
EmergencyDataCoordinator = AustralianDisasterWatchCoordinator
