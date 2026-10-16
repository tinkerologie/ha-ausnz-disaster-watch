"""Coordinators for the opt-in Open-Meteo forecast features (#38, #39, #40).

Each feature has its own coordinator and poll interval, separate from the incident
coordinator: a forecast outage never affects hazard data or entry setup, and forecasts,
which change a few times a day, are not fetched every few minutes. Each poll is one request.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AI_ENSEMBLE_INTERVAL,
    AI_WEATHERNEXT_MIN_AGE,
    CONF_AI_ENSEMBLE,
    CONF_AI_WEATHERNEXT,
    CONF_GUST_THRESHOLD,
    CONF_HEAT_THRESHOLD,
    CONF_HEAVY_RAIN_THRESHOLD,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RIVER_POINTS,
    CONF_WEATHER_SIGNALS,
    DEFAULT_GUST_THRESHOLD,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAVY_RAIN_THRESHOLD,
    DEFAULT_RIVER_HORIZON,
    DOMAIN,
    FORECAST_RETRY_INTERVAL,
    MAX_RIVER_HORIZON,
    RIVER_FORECAST_INTERVAL,
    RIVER_POINT_BASELINE,
    RIVER_POINT_HORIZON,
    RIVER_POINT_ID,
    RIVER_POINT_NAME,
    RIVER_POINT_THRESHOLD,
    WEATHER_SIGNALS_INTERVAL,
)
from .providers.forecast_signals import (
    EnsembleOutlook,
    WeatherSignals,
    combine_outlooks,
    model_outlook,
    weather_signals,
)
from .providers.open_meteo import (
    MODEL_AIFS,
    MODEL_WEATHERNEXT,
    EnsembleRun,
    OpenMeteoClient,
    OpenMeteoError,
    RiverForecast,
)

_LOGGER = logging.getLogger(__name__)

# Entity keys per feature, used to remove entities of a feature that was switched off
WEATHER_KEYS = (
    "max_wind_gust_24h",
    "max_apparent_temperature_24h",
    "thunderstorm_potential",
    "calculated_fire_danger_index",
    "damaging_gusts_forecast",
    "extreme_heat_forecast",
)
ENSEMBLE_KEYS = ("heavy_rain_probability_24h", "heavy_rain_probability_72h", "ai_rain_outlook")
RIVER_KEY_PREFIXES = ("river_discharge_", "river_flood_risk_")

# A manual refresh must not re-buy a run that cannot have changed yet
MODEL_MIN_AGE = {MODEL_AIFS: AI_ENSEMBLE_INTERVAL - timedelta(minutes=30), MODEL_WEATHERNEXT: AI_WEATHERNEXT_MIN_AGE}


@dataclass(frozen=True)
class RiverPoint:
    """A user-selected river point from the entry options."""

    point_id: str
    name: str
    latitude: float
    longitude: float
    threshold: float
    baseline: float | None
    horizon_days: int


def river_points(options: Any) -> list[RiverPoint]:
    """Return the valid river points stored in options; malformed entries are skipped."""
    points: list[RiverPoint] = []
    for raw in options if isinstance(options, list) else []:
        try:
            baseline = raw.get(RIVER_POINT_BASELINE)
            points.append(
                RiverPoint(
                    point_id=str(raw[RIVER_POINT_ID]),
                    name=str(raw[RIVER_POINT_NAME]),
                    latitude=float(raw[CONF_LATITUDE]),
                    longitude=float(raw[CONF_LONGITUDE]),
                    threshold=float(raw[RIVER_POINT_THRESHOLD]),
                    baseline=float(baseline) if baseline is not None else None,
                    horizon_days=min(
                        max(int(raw.get(RIVER_POINT_HORIZON, DEFAULT_RIVER_HORIZON)), 1), MAX_RIVER_HORIZON
                    ),
                )
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            _LOGGER.warning("Ignoring malformed river point in options: %s", raw)
    return points


class OpenMeteoCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Shared polling and failure handling for one Open-Meteo feature."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenMeteoClient,
        *,
        feature: str,
        interval: timedelta,
        location: tuple[float, float],
    ) -> None:
        """Initialize the coordinator for one feature at the entry's location."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}_{feature}", update_interval=interval)
        self.client = client
        self.feature = feature
        self.latitude, self.longitude = location
        self.fetched_at: datetime | None = None
        self._interval = interval

    async def _async_update_data(self) -> DataT:
        """Fetch once; on failure retry sooner and make the feature's entities unavailable."""
        try:
            data = await self._async_fetch()
        except OpenMeteoError as err:
            self.update_interval = min(FORECAST_RETRY_INTERVAL, self._interval)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="forecast_unavailable",
                translation_placeholders={"feature": self.feature, "error": str(err)},
            ) from err
        self.update_interval = self._interval
        return data

    @abstractmethod
    async def _async_fetch(self) -> DataT:
        """Fetch and derive this feature's data."""

    @callback
    def set_location(self, latitude: float, longitude: float) -> None:
        """Follow a moved monitoring point (home-mode entries track Home Assistant's location).

        Data for the old point is discarded and a refresh is scheduled.
        """
        if (latitude, longitude) == (self.latitude, self.longitude):
            return
        self.latitude, self.longitude = latitude, longitude
        self._discard_cached()
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), f"{DOMAIN}_{self.feature}_location_changed"
        )

    def _discard_cached(self) -> None:
        """Drop cached upstream data that belongs to the old location."""


class WeatherSignalsCoordinator(OpenMeteoCoordinator[WeatherSignals]):
    """Hourly weather hazard signals (#39)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OpenMeteoClient, location: tuple[float, float]
    ) -> None:
        """Initialize with the gust and heat thresholds from options."""
        super().__init__(
            hass, entry, client, feature="weather_signals", interval=WEATHER_SIGNALS_INTERVAL, location=location
        )
        config = {**entry.data, **entry.options}
        self.gust_threshold = float(config.get(CONF_GUST_THRESHOLD, DEFAULT_GUST_THRESHOLD))
        self.heat_threshold = float(config.get(CONF_HEAT_THRESHOLD, DEFAULT_HEAT_THRESHOLD))

    async def _async_fetch(self) -> WeatherSignals:
        forecast = await self.client.async_get_forecast(self.latitude, self.longitude)
        self.fetched_at = dt_util.utcnow()
        return weather_signals(forecast, self.fetched_at)


class RiverForecastCoordinator(OpenMeteoCoordinator[dict[str, RiverForecast]]):
    """Six-hourly GloFAS discharge for every river point in one request (#38)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OpenMeteoClient, points: list[RiverPoint]
    ) -> None:
        """Initialize with the configured river points."""
        super().__init__(
            hass, entry, client, feature="river_forecast", interval=RIVER_FORECAST_INTERVAL, location=(0.0, 0.0)
        )
        self.points = points

    async def _async_fetch(self) -> dict[str, RiverForecast]:
        forecasts = await self.client.async_get_river_forecasts([(p.latitude, p.longitude) for p in self.points])
        self.fetched_at = dt_util.utcnow()
        return {point.point_id: forecast for point, forecast in zip(self.points, forecasts, strict=True)}


class EnsembleOutlookCoordinator(OpenMeteoCoordinator[EnsembleOutlook]):
    """Experimental AI ensemble rain outlook (#40).

    Polls every 6 hours. Each poll requests only the models with a new run due (AIFS every
    6 h, WeatherNext 2 every 12 h), in one request; a model's last run is reused in between.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OpenMeteoClient, location: tuple[float, float]
    ) -> None:
        """Initialize with the model selection and heavy-rain threshold from options."""
        super().__init__(hass, entry, client, feature="ai_ensemble", interval=AI_ENSEMBLE_INTERVAL, location=location)
        config = {**entry.data, **entry.options}
        self.models = [MODEL_AIFS] + ([MODEL_WEATHERNEXT] if config.get(CONF_AI_WEATHERNEXT, False) else [])
        self.threshold = float(config.get(CONF_HEAVY_RAIN_THRESHOLD, DEFAULT_HEAVY_RAIN_THRESHOLD))
        self._runs: dict[str, tuple[datetime, EnsembleRun]] = {}

    def _discard_cached(self) -> None:
        """Runs fetched for the old location must not be reused."""
        self._runs.clear()

    async def _async_fetch(self) -> EnsembleOutlook:
        now = dt_util.utcnow()
        due = [m for m in self.models if m not in self._runs or now - self._runs[m][0] >= MODEL_MIN_AGE[m]]
        if due:
            runs = await self.client.async_get_ensemble(self.latitude, self.longitude, due)
            for model in due:
                if model in runs:
                    self._runs[model] = (now, runs[model])
                else:
                    # A due model without members must not keep serving its previous run
                    _LOGGER.warning("Open-Meteo ensemble returned no members for %s", model)
                    self._runs.pop(model, None)
            self.fetched_at = now
        outlooks = {
            model: model_outlook(run, now, self.threshold, fetched)
            for model, (fetched, run) in self._runs.items()
            if model in self.models
        }
        if not outlooks:
            raise OpenMeteoError("Open-Meteo ensemble returned no members for the requested models")
        return combine_outlooks(outlooks, self.threshold)


@dataclass
class ForecastCoordinators:
    """The forecast coordinators of one entry; None when the feature is off."""

    weather: WeatherSignalsCoordinator | None = None
    river: RiverForecastCoordinator | None = None
    ensemble: EnsembleOutlookCoordinator | None = None

    def __iter__(self) -> Iterator[OpenMeteoCoordinator[Any]]:
        """Iterate over the enabled coordinators."""
        yield from (c for c in (self.weather, self.river, self.ensemble) if c is not None)


async def async_setup_forecasts(
    hass: HomeAssistant, entry: ConfigEntry, location: tuple[float, float]
) -> ForecastCoordinators:
    """Create the enabled forecast coordinators and start their first refresh; nothing is fetched for a disabled one.

    The first refresh runs as an entry task, so a slow or failing Open-Meteo request never
    holds up entry setup (#75); the forecast entities are unavailable until it completes.
    """
    config = {**entry.data, **entry.options}
    client = OpenMeteoClient(async_get_clientsession(hass))
    forecasts = ForecastCoordinators()
    if config.get(CONF_WEATHER_SIGNALS, False):
        forecasts.weather = WeatherSignalsCoordinator(hass, entry, client, location)
    if points := river_points(config.get(CONF_RIVER_POINTS)):
        forecasts.river = RiverForecastCoordinator(hass, entry, client, points)
    if config.get(CONF_AI_ENSEMBLE, False):
        forecasts.ensemble = EnsembleOutlookCoordinator(hass, entry, client, location)
    for coordinator in forecasts:
        entry.async_create_task(hass, coordinator.async_refresh(), f"{coordinator.name} first refresh")
    async_remove_stale_forecast_entities(hass, entry, forecasts)
    return forecasts


@callback
def async_remove_stale_forecast_entities(
    hass: HomeAssistant, entry: ConfigEntry, forecasts: ForecastCoordinators
) -> None:
    """Remove registry entries of forecast features switched off and river points removed."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    point_ids = {p.point_id for p in forecasts.river.points} if forecasts.river else set()
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        key = reg_entry.unique_id.removeprefix(prefix)
        river_point = next((key.removeprefix(p) for p in RIVER_KEY_PREFIXES if key.startswith(p)), None)
        if (
            (key in WEATHER_KEYS and forecasts.weather is None)
            or (key in ENSEMBLE_KEYS and forecasts.ensemble is None)
            or (river_point is not None and river_point not in point_ids)
        ):
            registry.async_remove(reg_entry.entity_id)
