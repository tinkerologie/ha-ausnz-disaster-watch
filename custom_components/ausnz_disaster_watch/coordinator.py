"""DataUpdateCoordinator for Australian Disaster Watch."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timedelta
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FIRST_REFRESH_OPTIONAL_TIMEOUT,
    LAST_GOOD_MAX_AGE,
    LOCATION_MODE_HOME,
    OPTIONAL_FEED_TIMEOUT,
    THREAT_SCAN_INTERVAL,
)
from .council_registry import nearest_council, nearest_readable_dashboard, usable_url
from .entity_lifecycle import EntityTracker
from .forecast_coordinator import ForecastCoordinators
from .models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCameraItem,
    DisasterCoordinatorData,
    DisasterWatchConfigModel,
    EmergencyNewsItem,
    FireDangerOutlook,
    FireDangerRating,
    FireSeasonStatus,
    HazardType,
    HeatwaveStatus,
    PowerOutageItem,
    RegionalAlertItem,
    ReliefFacilityItem,
    RoadClosureItem,
    SatelliteHotspots,
    TsunamiStatus,
    UVObservation,
    WarningLevel,
    WeatherStationObservation,
    WeatherWarningItem,
)
from .providers import get_providers_for_config
from .providers.base import BaseHazardProvider, PartialFeedError, ProviderUnavailableError
from .providers.fire_danger import FireDangerService, local_today
from .providers.geometry import area_distance
from .providers.power import PowerOutageSource
from .providers.roads import get_road_providers_for_config, merge_road_items
from .providers.sources import (
    DataSource,
    attribution_for,
    sources_for_feature,
    sources_for_provider,
    sources_for_river_gauges,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .dam_coordinator import DamStorageCoordinator
    from .river_coordinator import RiverGaugeCoordinator

_LOGGER = logging.getLogger(__name__)


class OptionalFeedTimeoutError(ProviderUnavailableError):
    """An optional feed did not answer in time and has no recent result to fall back on (#75)."""


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


# National feed hooks (#37): snapshot field -> (provider hook, expected result type)
NATIONAL_FEED_HOOKS: dict[str, tuple[str, type]] = {
    "tsunami": ("async_fetch_tsunami_status", TsunamiStatus),
    "satellite_hotspots": ("async_fetch_satellite_hotspots", SatelliteHotspots),
    "heatwave": ("async_fetch_heatwave", HeatwaveStatus),
    "uv": ("async_fetch_uv", UVObservation),
    "regional_alerts": ("async_fetch_regional_alerts", list),
}


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
    """Return the URL of the council dashboard for a point in ``state``, or None.

    The council is picked from the generated registry (council_registry.nearest_council, a
    geographic heuristic, not council boundaries). When that council has no dashboard the
    integration can read (Brisbane, Sunshine Coast, or a certificate Home Assistant
    rejects), the nearest readable dashboard within the match distance is used, as before;
    None when there is none. The user can change or clear the URL in the options (#19, #32).
    """
    if latitude is None or longitude is None:
        return None
    match = nearest_council(state, latitude, longitude)
    if match and (url := usable_url(match[1])):
        return url
    return nearest_readable_dashboard(state, latitude, longitude)


def fire_danger_today(outlook: FireDangerOutlook | None) -> FireDangerRating | None:
    """Return today's rating from an outlook, today being the district's local date (#28)."""
    if outlook is None:
        return None
    day = outlook.day(local_today(outlook.time_zone))
    if day is None or day.rating is None:
        return None
    return FireDangerRating(
        district_number=outlook.district_number,
        district_name=outlook.district_name,
        rating=day.rating,
        total_fire_ban=day.total_fire_ban,
        day="Today",
    )


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
        # Distributor outage feeds: health and last good outages, like the hazard feeds (#36)
        self._power_feed_healthy: dict[str, bool] = {}
        self._last_good_outages: dict[str, tuple[datetime, list[PowerOutageItem]]] = {}
        # Opt-in Open-Meteo forecast coordinators, set up by async_setup_entry (#38, #39, #40)
        self.forecasts = ForecastCoordinators()
        # Polls the river gauges chosen in the options flow; None when none are selected (#31)
        self.river_coordinator: RiverGaugeCoordinator | None = None
        # Polls the dam storages chosen in the options flow; None when none are selected
        self.dam_coordinator: DamStorageCoordinator | None = None
        # Unique IDs the sensor platforms created, for the registry cleanup at setup (#92)
        self.entity_tracker = EntityTracker()
        self._road_feed_healthy: dict[str, bool] = {}
        self.road_feeds_failed: list[str] = []
        # Optional (non-hazard) feed calls that outlived their timeout, their last good results,
        # and the feeds whose timeout has been logged (#75)
        # Keyed by (owner, hook): the owner object itself, so a key can never be reused by another owner
        self._optional_tasks: dict[tuple[object, str], asyncio.Task[Any]] = {}
        self._optional_last_good: dict[tuple[object, str], tuple[datetime, Any]] = {}
        self._optional_timed_out: set[tuple[object, str]] = set()
        # The timed-out call each feed has a late-completion callback on
        self._optional_watched: dict[tuple[object, str], asyncio.Task[Any]] = {}
        self._update_config_values()

        session = async_get_clientsession(hass)
        # Providers that measure distance to warning areas need the resolved home location
        provider_config = {
            **self.combined_config,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius": self.radius_km,
        }
        providers = get_providers_for_config(hass, session, provider_config)
        # Distributor outage feeds publish no hazards, so they never count as hazard feeds (#36)
        self.power_sources: list[PowerOutageSource] = [p for p in providers if isinstance(p, PowerOutageSource)]
        self.providers = [p for p in providers if not isinstance(p, PowerOutageSource)]
        # Fire danger outlook / NZ fire season on its own 30-minute schedule (#28)
        self.fire_service = FireDangerService(hass, session, provider_config, entry_id=entry.entry_id)
        # Statewide road feeds (#29), kept apart so they never count towards hazard feed health
        self.road_providers = get_road_providers_for_config(hass, session, provider_config)
        self._update_location()

    def _update_config_values(self) -> None:
        """Update internal parameters from validated entry data and options."""
        # Merge data and options (options take precedence)
        self.combined_config: dict[str, Any] = {
            **self.entry.data,
            **self.entry.options,
        }

        cfg = DisasterWatchConfigModel.from_config(self.combined_config)
        self.state_code: str = cfg.state.upper()
        self.radius_km: float = float(cfg.radius)
        self.override_emergency: bool = cfg.override_emergency
        self.exclude_hazard_reduction: bool = cfg.exclude_hazard_reduction
        self.include_roadworks: bool = cfg.include_roadworks
        self.include_planned_outages: bool = cfg.include_planned_outages
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
            self._last_good_outages.clear()
            # Optional results, and calls still running, belong to the old point: forget them
            # (a running call finishes in the background, but its result is no longer used, #75)
            self._optional_last_good.clear()
            self._optional_tasks.clear()
            self._optional_timed_out.clear()
            self._optional_watched.clear()
        for provider in [*self.providers, *self.road_providers, *self.power_sources, self.fire_service]:
            if isinstance(provider, BaseHazardProvider):
                provider.set_location(self.latitude, self.longitude)
        # Location-based forecasts follow too; river points are user-picked coordinates and stay
        for forecast in (self.forecasts.weather, self.forecasts.ensemble):
            if forecast is not None:
                forecast.set_location(self.latitude, self.longitude)

    async def _async_optional(self, owner: Any, hook: str, *, log_timeout: bool = True) -> Any:
        """Call an optional feed hook with a timeout, so a slow source never holds up a refresh (#75).

        The call runs as an entry background task. If it does not finish in time, the refresh
        uses the feed's last good result (for up to ``LAST_GOOD_MAX_AGE``) or, without one,
        raises ``OptionalFeedTimeoutError`` so the feed reads as unavailable. The call keeps
        running, and the next refresh uses its result instead of starting another call. When a
        feed with no data yet finishes late, a refresh is requested so its entities fill in.
        The first refresh waits less, so entry setup is not held up by optional feeds.
        """
        key = (owner, hook)
        name = f"{type(owner).__name__}.{hook}"
        task = self._optional_tasks.get(key)
        if task is None:
            task = self.config_entry.async_create_background_task(self.hass, getattr(owner, hook)(), f"{DOMAIN} {name}")
            self._optional_tasks[key] = task
        timeout = FIRST_REFRESH_OPTIONAL_TIMEOUT if self.data is None else OPTIONAL_FEED_TIMEOUT
        # asyncio.wait never cancels the call (unlike wait_for, or shield, which would also
        # report a late failure as an unhandled error)
        await asyncio.wait({task}, timeout=timeout)
        if not task.done():
            if log_timeout and key not in self._optional_timed_out:
                _LOGGER.warning("Optional feed %s did not answer within %s s; using its last result", name, timeout)
            self._optional_timed_out.add(key)
            if self._optional_watched.get(key) is not task:
                self._optional_watched[key] = task
                task.add_done_callback(lambda done: self._optional_finished_late(key, done))
            if (cached := self._fresh_optional_result(key)) is not None:
                return cached[1]
            raise OptionalFeedTimeoutError(f"{name} timed out after {timeout} s")
        self._optional_tasks.pop(key, None)
        if task.cancelled():
            raise OptionalFeedTimeoutError(f"{name} was cancelled")
        value = task.result()  # raises the call's own error
        if key in self._optional_timed_out:
            self._optional_timed_out.discard(key)
            if log_timeout:
                _LOGGER.info("Optional feed %s is answering again", name)
        self._optional_last_good[key] = (dt_util.utcnow(), value)
        return value

    @callback
    def _optional_finished_late(self, key: tuple[object, str], task: asyncio.Task[Any]) -> None:
        """Refresh once a timed-out feed without a usable result finishes, so its entities fill in.

        A call that is no longer the feed's current one (for example after a location change)
        is obsolete: its error is still consumed, but it neither clears the current call's
        watcher nor requests a refresh.
        """
        failed = task.cancelled() or task.exception() is not None
        if self._optional_watched.get(key) is not task:
            return
        del self._optional_watched[key]
        if failed or self._fresh_optional_result(key) is not None:
            return
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), f"{DOMAIN} refresh after {type(key[0]).__name__}.{key[1]}"
        )

    def _fresh_optional_result(self, key: tuple[object, str]) -> tuple[datetime, Any] | None:
        """Return the feed's last good result if it is recent enough to stand in for a timed-out call."""
        cached = self._optional_last_good.get(key)
        if cached is not None and dt_util.utcnow() - cached[0] <= LAST_GOOD_MAX_AGE:
            return cached
        return None

    async def _async_fetch_all_hazards(self) -> list[CanonicalHazard]:
        """Fetch all hazards from active providers concurrently, tracking each feed's health (#16).

        A failed provider contributes its last good hazards so a transient outage does not
        look like an all-clear. Health transitions are logged once (warning when a feed goes
        down, info when it recovers). If every provider fails, UpdateFailed makes the entities
        unavailable and, on first refresh, puts the entry into setup retry.
        """
        # Providers of auxiliary data only must not count as healthy hazard feeds
        hazard_providers = [p for p in self.providers if getattr(p, "provides_hazards", True) is not False]
        results = await asyncio.gather(
            *(provider.async_fetch_hazards() for provider in hazard_providers),
            return_exceptions=True,
        )
        all_hazards: list[CanonicalHazard] = []
        feeds_ok: list[str] = []
        feeds_failed: list[str] = []
        for provider, result in zip(hazard_providers, results, strict=True):
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
        if hazard_providers and not feeds_ok:
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
        now = dt_util.utcnow()

        for hazard in all_hazards:
            if self.exclude_hazard_reduction and hazard.is_hazard_reduction:
                continue
            if hazard.expires is not None and hazard.expires <= now:
                continue

            if hazard.area:
                # Distance to the warning area, 0 when the monitored point is inside it (#30)
                dist = area_distance(self.latitude, self.longitude, hazard.area)
                hazard.distance_km = dist
                hazard.inside_area = dist == 0.0
            elif hazard.distance_km is not None:
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
                po = await self._async_optional(provider, "async_fetch_power_outages")
                if isinstance(po, list):
                    # Radius filtering happens with the distributor outages (_process_power_outages)
                    power_outages.extend(item for item in po if isinstance(item, PowerOutageItem))
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating power outages from %s: %s", provider.__class__.__name__, err)

        async def _fetch_roads() -> None:
            await self._async_collect_roads(provider, road_closures)

        async def _fetch_relief() -> None:
            try:
                rf = await self._async_optional(provider, "async_fetch_relief_facilities")
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

    async def _async_collect_statewide_roads(self, provider: Any, road_closures: list[RoadClosureItem]) -> bool:
        """Collect a statewide road feed's items; return False (logged once per outage) if it is down.

        A feed is down when it raises, or when one of its sources has been unavailable for longer
        than the last-good window (its remaining items are still used, but the feed is incomplete).
        """
        key = type(provider).__name__
        try:
            await self._async_collect_roads(provider, road_closures, raise_errors=True)
        except Exception as err:
            if self._road_feed_healthy.get(key, True):
                _LOGGER.warning("Road feed %s is unavailable: %s", key, err)
            if not isinstance(err, ProviderUnavailableError):
                _LOGGER.debug("Unexpected error from road feed %s", key, exc_info=err)
            self._road_feed_healthy[key] = False
            return False
        if failed_sources := getattr(provider, "failed_sources", None):
            if self._road_feed_healthy.get(key, True):
                _LOGGER.warning("Road feed %s is incomplete; unavailable: %s", key, ", ".join(failed_sources))
            self._road_feed_healthy[key] = False
            return False
        if self._road_feed_healthy.get(key) is False:
            _LOGGER.info("Road feed %s is available again", key)
        self._road_feed_healthy[key] = True
        return True

    async def _async_collect_roads(
        self, provider: Any, road_closures: list[RoadClosureItem], raise_errors: bool = False
    ) -> None:
        """Collect a provider's road items within the radius (unlocated council items are kept)."""
        try:
            # Statewide feeds report their own outages (once), so their timeouts are not logged twice
            rc = await self._async_optional(provider, "async_fetch_road_closures", log_timeout=not raise_errors)
            if isinstance(rc, list):
                for item in rc:
                    if isinstance(item, RoadClosureItem) and item.latitude is not None and item.longitude is not None:
                        dist = round(
                            calculate_haversine_distance(self.latitude, self.longitude, item.latitude, item.longitude),
                            2,
                        )
                        item.distance_km = dist
                        if dist <= self.radius_km:
                            road_closures.append(item)
                    elif isinstance(item, RoadClosureItem):
                        road_closures.append(item)
        except Exception as err:
            if raise_errors:
                raise
            _LOGGER.debug("Error updating road closures from %s: %s", provider.__class__.__name__, err)

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
                ww = await self._async_optional(provider, "async_fetch_weather_warnings")
                if isinstance(ww, list):
                    weather_warnings.extend([item for item in ww if isinstance(item, WeatherWarningItem)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating weather warnings from %s: %s", provider.__class__.__name__, err)

        async def _fetch_news() -> None:
            try:
                en = await self._async_optional(provider, "async_fetch_emergency_news")
                if isinstance(en, list):
                    emergency_news.extend([item for item in en if isinstance(item, EmergencyNewsItem)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating emergency news from %s: %s", provider.__class__.__name__, err)

        async def _fetch_stations() -> None:
            try:
                ws = await self._async_optional(provider, "async_fetch_weather_telemetry")
                if isinstance(ws, list):
                    weather_stations.extend([item for item in ws if isinstance(item, WeatherStationObservation)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating weather telemetry from %s: %s", provider.__class__.__name__, err)

        async def _fetch_aq() -> None:
            try:
                aq = await self._async_optional(provider, "async_fetch_air_quality")
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
        cameras_failed: list[str],
    ) -> None:
        """Collect cameras and nearby council links from a provider concurrently.

        A provider whose camera source failed is listed in ``cameras_failed``, so its missing
        cameras are not taken as delisted (#92); a partial failure keeps the cameras it did get.
        """

        def _add(items: list[Any]) -> None:
            cameras.extend([item for item in items if isinstance(item, DisasterCameraItem) and self._near(item)])

        async def _fetch_cam() -> None:
            try:
                cam = await self._async_optional(provider, "async_fetch_cameras")
                if isinstance(cam, list):
                    _add(cam)
            except PartialFeedError as err:
                _LOGGER.debug("Some cameras of %s are unavailable: %s", provider.__class__.__name__, err)
                _add(err.items)
                cameras_failed.append(provider.__class__.__name__)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating cameras from %s: %s", provider.__class__.__name__, err)
                cameras_failed.append(provider.__class__.__name__)

        async def _fetch_councils() -> None:
            try:
                nc = await self._async_optional(provider, "async_fetch_nearby_councils")
                if isinstance(nc, list):
                    nearby_councils.extend([item for item in nc if isinstance(item, dict)])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating nearby councils from %s: %s", provider.__class__.__name__, err)

        await asyncio.gather(_fetch_cam(), _fetch_councils())

    async def _collect_distributor_outages(self, power_outages: list[PowerOutageItem]) -> None:
        """Fetch every distributor feed (#36).

        Like the hazard feeds, a failed feed keeps its last good outages for up to
        LAST_GOOD_MAX_AGE, so a short feed outage does not look like power coming back, and
        health transitions are logged once.
        """
        results = await asyncio.gather(
            # Each distributor logs its own outages, so its timeout is not logged twice (#75)
            *(
                self._async_optional(source, "async_fetch_power_outages", log_timeout=False)
                for source in self.power_sources
            ),
            return_exceptions=True,
        )
        for source, result in zip(self.power_sources, results, strict=True):
            key = type(source).__name__
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result  # e.g. CancelledError
                if self._power_feed_healthy.get(key, True):
                    _LOGGER.warning("Power outage feed %s is unavailable: %s", source.distributor, result)
                else:
                    _LOGGER.debug("Power outage feed %s still unavailable: %s", source.distributor, result)
                self._power_feed_healthy[key] = False
                cached = self._last_good_outages.get(key)
                if cached and dt_util.utcnow() - cached[0] <= LAST_GOOD_MAX_AGE:
                    power_outages.extend(cached[1])
                continue
            if self._power_feed_healthy.get(key) is False:
                _LOGGER.info("Power outage feed %s is available again", source.distributor)
            self._power_feed_healthy[key] = True
            items = [item for item in result if isinstance(item, PowerOutageItem)]
            self._last_good_outages[key] = (dt_util.utcnow(), items)
            power_outages.extend(items)

    def _process_power_outages(self, outages: list[PowerOutageItem]) -> list[PowerOutageItem]:
        """Drop planned and duplicate outages, filter by radius and sort nearest first (#36).

        Council dashboard outages (Energex and Ergon) and distributor feed outages come from
        different networks (Energy Queensland's own feeds are not used: its terms require a
        written agreement), so the two never describe the same outage.
        """
        seen: set[tuple[str | None, str]] = set()
        kept: list[PowerOutageItem] = []
        for item in outages:
            if item.planned and not self.include_planned_outages:
                continue
            if item.id is not None:
                if (item.distributor, item.id) in seen:
                    continue
                seen.add((item.distributor, item.id))
            if item.distance_km is None and item.latitude is not None and item.longitude is not None:
                # A copy: the item may be a feed's cached or last good outage
                item = dataclasses.replace(
                    item,
                    distance_km=round(
                        calculate_haversine_distance(self.latitude, self.longitude, item.latitude, item.longitude),
                        2,
                    ),
                )
            if item.distance_km is not None and item.distance_km > self.radius_km:
                continue
            kept.append(item)
        # Located outages nearest first; outages without a location last
        return sorted(kept, key=lambda o: (o.distance_km is None, o.distance_km or 0.0))

    @property
    def power_outage_sources(self) -> list[dict[str, str]]:
        """Return the distributor and register entry (licence, attribution) of each outage feed."""
        return [source.metadata() for source in self.power_sources]

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
        cameras_failed: list[str] = []
        nearby_councils: list[dict[str, str]] = []

        statewide_roads: list[RoadClosureItem] = []
        coros: list[Any] = [
            asyncio.gather(
                *(self._async_collect_statewide_roads(provider, statewide_roads) for provider in self.road_providers)
            )
        ]
        for provider in self.providers:
            coros.append(self._collect_infrastructure(provider, power_outages, road_closures, relief_facilities))
            coros.append(
                self._collect_environmental(
                    provider, weather_warnings, emergency_news, weather_stations, air_quality_stations
                )
            )
            coros.append(self._collect_cameras_and_councils(provider, cameras, nearby_councils, cameras_failed))

        coros.append(self._collect_distributor_outages(power_outages))

        async def _update_fire_service() -> None:
            try:
                # The service keeps its last outlook, so a slow update only delays the new one
                await self._async_optional(self.fire_service, "async_update")
            except ProviderUnavailableError as err:
                _LOGGER.debug("Fire danger outlook not updated: %s", err)

        # Updated alongside the other feeds, so its timeout overlaps theirs instead of adding to it
        coros.append(_update_fire_service())
        road_results, *_ = await asyncio.gather(*coros)
        self.road_feeds_failed = [
            type(provider).__name__ for provider, ok in zip(self.road_providers, road_results, strict=True) if not ok
        ]

        fire_outlook = self.fire_service.outlook
        fire_danger = fire_danger_today(fire_outlook)

        # Fall back to the providers' own (single-day) sources when there is no outlook for today.
        # They are asked together, so their timeouts overlap; the first provider (in order) with a
        # rating wins, as before.
        if fire_danger is None:

            async def _fallback(provider: Any) -> FireDangerRating | None:
                try:
                    fd = await self._async_optional(provider, "async_fetch_fire_danger")
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Error updating fire danger from %s: %s", provider.__class__.__name__, err)
                    return None
                return fd if isinstance(fd, FireDangerRating) else None

            ratings = await asyncio.gather(*(_fallback(provider) for provider in self.providers))
            fire_danger = next((rating for rating in ratings if rating is not None), None)

        # One entity per camera ID: the first occurrence wins (#19). A council dashboard and a
        # road agency network can list the same camera image under different IDs (#70).
        unique_cameras: list[DisasterCameraItem] = []
        camera_ids: set[str] = set()
        image_urls: set[str] = set()
        for camera in cameras:
            if camera.id not in camera_ids and camera.image_url not in image_urls:
                camera_ids.add(camera.id)
                image_urls.add(camera.image_url)
                unique_cameras.append(camera)

        return {
            "power_outages": self._process_power_outages(power_outages),
            # Statewide feeds first, so their items win over council copies of the same event
            # Nearest first, so capped lists (the sensor shows 25) hold the closest roads; unlocated last
            "road_closures": sorted(
                merge_road_items(statewide_roads, road_closures, self.include_roadworks),
                key=lambda item: (item.distance_km is None, item.distance_km or 0.0),
            ),
            "weather_warnings": _unique_by_title(weather_warnings),
            "emergency_news": emergency_news,
            "fire_danger": fire_danger,
            "fire_outlook": fire_outlook,
            "fire_season": self.fire_service.season,
            "weather_stations": weather_stations,
            "air_quality_stations": self._nearest_first(air_quality_stations),
            "relief_facilities": relief_facilities,
            "cameras": unique_cameras,
            "cameras_failed": cameras_failed,
            "nearby_councils": nearby_councils,
        }

    def _nearest_first(self, stations: list[AirQualityStationData]) -> list[AirQualityStationData]:
        """Set each located station's distance and order stations nearest first (unlocated last)."""
        for station in stations:
            if station.latitude is not None and station.longitude is not None:
                station.distance_km = round(
                    calculate_haversine_distance(self.latitude, self.longitude, station.latitude, station.longitude), 1
                )
        return sorted(stations, key=lambda s: (s.distance_km is None, s.distance_km or 0.0))

    async def _async_fetch_national_feeds(self) -> dict[str, Any]:
        """Collect the opt-in national feeds (#37); each feed fails on its own.

        The first provider that returns a value of the expected type wins; ``None`` means the
        feed is off or undetermined. National data never enters ``hazards``.
        """

        async def fetch(provider: Any, field: str, hook: str, expected: type) -> tuple[str, Any]:
            try:
                value = await self._async_optional(provider, hook)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error updating %s from %s: %s", field, provider.__class__.__name__, err)
                return field, None
            if field == "regional_alerts" and isinstance(value, list):
                value = [item for item in value if isinstance(item, RegionalAlertItem)]
            return field, value if isinstance(value, expected) else None

        results: dict[str, Any] = dict.fromkeys(NATIONAL_FEED_HOOKS)
        gathered = await asyncio.gather(
            *(
                fetch(provider, field, hook, expected)
                for provider in self.providers
                for field, (hook, expected) in NATIONAL_FEED_HOOKS.items()
            )
        )
        for field, value in gathered:
            if results[field] is None and value is not None:
                results[field] = value
        return results

    async def _async_update_data(self) -> DisasterCoordinatorData:
        """Fetch all hazards and telemetry from active providers."""
        self._update_location()
        all_hazards = await self._async_fetch_all_hazards()
        filtered_hazards, has_active_threat = self._filter_and_process_hazards(all_hazards)
        aux, national = await asyncio.gather(self._async_fetch_composite_feeds(), self._async_fetch_national_feeds())

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
            fire_outlook=aux.get("fire_outlook"),
            fire_season=aux.get("fire_season"),
            weather_stations=aux["weather_stations"],
            air_quality_stations=aux["air_quality_stations"],
            relief_facilities=aux["relief_facilities"],
            cameras=aux["cameras"],
            cameras_failed=aux.get("cameras_failed", []),
            nearby_councils=aux["nearby_councils"],
            feeds_ok=self._feeds_ok,
            feeds_failed=self._feeds_failed,
            **national,
        )

    @property
    def data_sources(self) -> list[DataSource]:
        """Return the register entries for every source this entry's providers read (#34)."""
        return list(
            dict.fromkeys(
                source
                for provider in [*self.providers, *self.road_providers, *self.power_sources]
                for source in sources_for_provider(type(provider).__name__)
            )
        )

    @property
    def diagnostic_sources(self) -> list[DataSource]:
        """Return ``data_sources`` plus the sources of enabled opt-in features with their own coordinator.

        Dam storages are polled by their own coordinator and each storage entity credits its
        data owner, so their source is listed here (for diagnostics) but kept out of the
        entry-wide attribution. River gauges likewise: each gauge entity credits its own
        service, and the services of the selected gauges are listed here (#21).
        """
        extra: list[DataSource] = []
        if self.dam_coordinator is not None:
            extra.extend(sources_for_feature("dam_storages"))
            # Operator feeds (WaterNSW, Hydro Tasmania) matched to the selected storages
            for operator in dict.fromkeys(site.operator for site in self.dam_coordinator.sites if site.operator):
                extra.extend(sources_for_feature(operator))
        rivers = (
            sources_for_river_gauges(site.source for site in self.river_coordinator.sites)
            if self.river_coordinator is not None
            else ()
        )
        return list(dict.fromkeys([*self.data_sources, *extra, *rivers]))

    @property
    def attribution(self) -> str | None:
        """Return the combined attribution text for this entry's sources."""
        return attribution_for(self.data_sources)

    @property
    def feed_health(self) -> dict[str, tuple[str, datetime | None]]:
        """Return each hazard feed's status and the time of its last good fetch (#72).

        ``ok``: the last fetch worked. ``stale``: it failed, but its last good hazards (at
        most ``LAST_GOOD_MAX_AGE`` old) still stand in, or the whole update failed and the
        data is the previous update's. ``failed``: it failed and nothing stands in.
        """
        now = dt_util.utcnow()
        health: dict[str, tuple[str, datetime | None]] = {}
        for key in [*self._feeds_ok, *self._feeds_failed]:
            cached = self._last_good_hazards.get(key)
            last = cached[0] if cached else None
            if key in self._feeds_failed:
                status = "stale" if last is not None and now - last <= LAST_GOOD_MAX_AGE else "failed"
            else:
                status = "ok" if self.last_update_success else "stale"
            health[key] = (status, last)
        return health

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
    def inside_warning_hazards(self) -> list[CanonicalHazard]:
        """Return Advice-or-higher hazards whose area contains the monitored point, most severe first.

        The monitored point is the configured location (the Home Assistant home for home-zone
        entries). Hazards published only as a point never count (#30).
        """
        return sorted(
            (h for h in self.active_hazards if h.is_inside_warning),
            key=lambda h: h.warning_level.severity_rank,
            reverse=True,
        )

    @property
    def is_inside_warning_area(self) -> bool:
        """Return True if the monitored point is inside an Advice-or-higher warning area."""
        return any(h.is_inside_warning for h in self.active_hazards)

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
    def fire_outlook(self) -> FireDangerOutlook | None:
        """Return the multi-day fire danger and total fire ban outlook (#28)."""
        return getattr(self.data, "fire_outlook", None) if self.data is not None else None

    @property
    def fire_season(self) -> FireSeasonStatus | None:
        """Return the New Zealand fire season status (#28)."""
        return getattr(self.data, "fire_season", None) if self.data is not None else None

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

    @property
    def tsunami(self) -> TsunamiStatus | None:
        """Return the tsunami status, or None if off or undetermined."""
        return getattr(self.data, "tsunami", None) if self.data is not None else None

    @property
    def tsunami_hazards(self) -> list[CanonicalHazard]:
        """Return retained tsunami hazards (for example official NZ NEMA alerts)."""
        return [h for h in self.active_hazards if h.hazard_type is HazardType.TSUNAMI]

    @property
    def satellite_hotspots(self) -> SatelliteHotspots | None:
        """Return satellite hotspots within the radius, or None if off or undetermined."""
        return getattr(self.data, "satellite_hotspots", None) if self.data is not None else None

    @property
    def heatwave(self) -> HeatwaveStatus | None:
        """Return the heatwave status, or None if off or undetermined."""
        return getattr(self.data, "heatwave", None) if self.data is not None else None

    @property
    def uv(self) -> UVObservation | None:
        """Return the UV observation, or None if off or undetermined."""
        return getattr(self.data, "uv", None) if self.data is not None else None

    @property
    def regional_alerts(self) -> list[RegionalAlertItem] | None:
        """Return regional GDACS alerts, or None if off or undetermined."""
        return getattr(self.data, "regional_alerts", None) if self.data is not None else None


AusNZDisasterWatchCoordinator = AustralianDisasterWatchCoordinator
EmergencyDataCoordinator = AustralianDisasterWatchCoordinator
