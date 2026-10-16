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

from .const import (
    COUNCIL_AUTO_MATCH_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LAST_GOOD_MAX_AGE,
    LOCATION_MODE_HOME,
    PRESET_COUNCIL_DASHBOARDS,
    THREAT_SCAN_INTERVAL,
)
from .forecast_coordinator import ForecastCoordinators
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
from .providers.base import BaseHazardProvider, ProviderUnavailableError
from .providers.sources import DataSource, attribution_for, sources_for_provider

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

    A warning is a repeat only if title, affected locations and link all match: generic
    titles such as "Severe Thunderstorm Warning" are reused by every state, and two current
    alerts with different links are different warnings.
    """
    seen: set[tuple[str, str | None, str | None]] = set()
    unique: list[WeatherWarningItem] = []
    for warning in warnings:
        key = (warning.title, warning.locations, warning.link)
        if key not in seen:
            seen.add(key)
            unique.append(warning)
    return unique


def nearest_council_dashboard(state: str, latitude: float | None, longitude: float | None) -> str | None:
    """Return the URL of the nearest preset council dashboard in ``state`` within the match distance.

    This is a geographic heuristic on each council's representative point, not a check
    against council boundaries; the user can change or clear the URL in the options (#19).
    """
    if latitude is None or longitude is None:
        return None
    best: tuple[float, str] | None = None
    for preset in PRESET_COUNCIL_DASHBOARDS.values():
        url = preset.get("url")
        if preset.get("state") != state or not isinstance(url, str):
            continue
        dist = calculate_haversine_distance(
            latitude, longitude, float(preset["latitude"] or 0), float(preset["longitude"] or 0)
        )
        if dist <= COUNCIL_AUTO_MATCH_KM and (best is None or dist < best[0]):
            best = (dist, url)
    return best[1] if best else None


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
        # Opt-in Open-Meteo forecast coordinators, set up by async_setup_entry (#38, #39, #40)
        self.forecasts = ForecastCoordinators()
        self._update_config_values()

        session = async_get_clientsession(hass)
        # Providers that measure distance to warning areas need the resolved home location
        provider_config = {**self.combined_config, "latitude": self.latitude, "longitude": self.longitude}
        self.providers = get_providers_for_config(hass, session, provider_config)
        self._update_location()

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
        self.location_mode: str = cfg.location_mode
        self._stored_latitude = cfg.latitude
        self._stored_longitude = cfg.longitude
        self._resolve_location()

    def _resolve_location(self) -> None:
        """Set the monitored point.

        Home-mode entries follow the Home Assistant home location, so a corrected home
        location applies at the next refresh; their stored coordinates (from older
        versions) are ignored. Other entries use their stored point (#19).
        """
        home = (self.hass.config.latitude, self.hass.config.longitude)
        stored = (self._stored_latitude, self._stored_longitude)
        candidates = (home, stored) if self.location_mode == LOCATION_MODE_HOME else (stored, home)
        lat, lon = next(
            ((la, lo) for la, lo in candidates if la is not None and lo is not None),
            (-27.2657, 152.9818),
        )
        self.latitude: float = float(lat)
        self.longitude: float = float(lon)

    def _update_location(self) -> None:
        """Resolve the monitored point and hand it to every provider.

        When the point moves, cached last-good hazards are dropped: their distances were
        measured from the old point, so they would be filtered against the wrong location.
        """
        previous = (getattr(self, "latitude", None), getattr(self, "longitude", None))
        self._resolve_location()
        if previous not in {(None, None), (self.latitude, self.longitude)}:
            self._last_good_hazards.clear()
        for provider in self.providers:
            if isinstance(provider, BaseHazardProvider):
                provider.set_location(self.latitude, self.longitude)
        # Location-based forecasts follow too; river points are user-picked coordinates and stay
        for forecast in (self.forecasts.weather, self.forecasts.ensemble):
            if forecast is not None:
                forecast.set_location(self.latitude, self.longitude)

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
            # Hazards carry their own provider's attribution, e.g. for map pins (#34)
            if attribution := attribution_for(sources_for_provider(key)):
                for hazard in result:
                    if hazard.attribution is None:
                        hazard.attribution = attribution
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

    def _near(self, item: DisasterCameraItem) -> bool:
        """Return True if a camera is within the radius or has no location."""
        if item.latitude is None or item.longitude is None:
            return True
        return (
            calculate_haversine_distance(self.latitude, self.longitude, item.latitude, item.longitude) <= self.radius_km
        )

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
                    cameras.extend([item for item in cam if isinstance(item, DisasterCameraItem) and self._near(item)])
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

        # One entity per camera ID: the first occurrence wins (#19)
        unique_cameras: list[DisasterCameraItem] = []
        camera_ids: set[str] = set()
        for camera in cameras:
            if camera.id not in camera_ids:
                camera_ids.add(camera.id)
                unique_cameras.append(camera)

        return {
            "power_outages": power_outages,
            "road_closures": road_closures,
            "weather_warnings": _unique_by_title(weather_warnings),
            "emergency_news": emergency_news,
            "fire_danger": fire_danger,
            "weather_stations": weather_stations,
            "air_quality_stations": air_quality_stations,
            "relief_facilities": relief_facilities,
            "cameras": unique_cameras,
            "nearby_councils": nearby_councils,
        }

    async def _async_update_data(self) -> DisasterCoordinatorData:
        """Fetch all hazards and telemetry from active providers."""
        self._update_location()
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
    def data_sources(self) -> list[DataSource]:
        """Return the register entries for every source this entry's providers read (#34)."""
        return list(
            dict.fromkeys(
                source for provider in self.providers for source in sources_for_provider(type(provider).__name__)
            )
        )

    @property
    def attribution(self) -> str | None:
        """Return the combined attribution text for this entry's sources."""
        return attribution_for(self.data_sources)

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
