"""Entities for the opt-in Open-Meteo forecast features (#38, #39, #40).

These are model-derived forecast signals, kept apart from agency warnings: they are plain
sensors and binary sensors (never geo_location hazards), carry ``official: false``, and are
never mapped to warning levels or to the official fire danger rating.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,  # pyright: ignore[reportPrivateImportUsage]
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION_AIFS, ATTRIBUTION_GLOFAS, ATTRIBUTION_OPEN_METEO, ATTRIBUTION_WEATHERNEXT
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import entry_device_info
from .forecast_coordinator import (
    EnsembleOutlookCoordinator,
    OpenMeteoCoordinator,
    RiverForecastCoordinator,
    RiverPoint,
    WeatherSignalsCoordinator,
)
from .providers.forecast_signals import (
    DROUGHT_FACTOR_METHOD,
    THUNDERSTORM_LEVELS,
    EnsembleOutlook,
    Peak,
    WeatherSignals,
    river_horizon,
    river_peak,
    river_trend,
)
from .providers.open_meteo import MODEL_WEATHERNEXT, RiverDay, RiverForecast

FFDI_DISCLAIMER = (
    "Calculated from model forecasts with an experimental drought factor. Not an official fire danger rating."
)
AI_NOTICE = "Experimental AI model output. Not an official warning."


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ForecastEntity[CoordinatorT: OpenMeteoCoordinator[Any]](CoordinatorEntity[CoordinatorT]):
    """Base for forecast entities: shared device, ``{entry_id}_{key}`` unique ID, attribution."""

    _attr_has_entity_name = True

    def __init__(self, main: AustralianDisasterWatchCoordinator, coordinator: CoordinatorT, key: str) -> None:
        """Attach the entity to the entry's device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{main.entry.entry_id}_{key}"
        self._attr_device_info = entry_device_info(main)


# --- Weather hazard signals (#39) ---


@dataclass(frozen=True, kw_only=True)
class WeatherSensorDescription(SensorEntityDescription):
    """A weather signal sensor: how to read its value and attributes from the signals."""

    value_fn: Callable[[WeatherSignals], Any]
    attrs_fn: Callable[[WeatherSignals], dict[str, Any]]


def _peak_value(item: Peak | None) -> float | None:
    return round(item.value, 1) if item else None


WEATHER_SENSORS = (
    WeatherSensorDescription(
        key="max_wind_gust_24h",
        translation_key="max_wind_gust_24h",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda s: _peak_value(s.max_gust),
        attrs_fn=lambda s: {"peak_time": _iso(s.max_gust.time if s.max_gust else None)},
    ),
    WeatherSensorDescription(
        key="max_apparent_temperature_24h",
        translation_key="max_apparent_temperature_24h",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: _peak_value(s.max_apparent_temperature),
        attrs_fn=lambda s: {"peak_time": _iso(s.max_apparent_temperature.time if s.max_apparent_temperature else None)},
    ),
    WeatherSensorDescription(
        key="thunderstorm_potential",
        translation_key="thunderstorm_potential",
        device_class=SensorDeviceClass.ENUM,
        options=list(THUNDERSTORM_LEVELS),
        value_fn=lambda s: s.thunderstorm.level if s.thunderstorm else None,
        attrs_fn=lambda s: (
            {
                "max_cape": s.thunderstorm.max_cape,
                "max_precipitation_probability": s.thunderstorm.max_precipitation_probability,
                "thunderstorm_weather_code": s.thunderstorm.thunderstorm_code,
                "peak_time": _iso(s.thunderstorm.time),
                "method": "heuristic from CAPE, precipitation probability and weather code; not a BoM category",
            }
            if s.thunderstorm
            else {}
        ),
    ),
    WeatherSensorDescription(
        key="calculated_fire_danger_index",
        translation_key="calculated_fire_danger_index",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: round(s.fire_danger.index, 1) if s.fire_danger else None,
        attrs_fn=lambda s: {
            "calculated": True,
            "disclaimer": FFDI_DISCLAIMER,
            "formula": "McArthur Mk5 FFDI (Noble et al. 1980)",
            "drought_factor_method": DROUGHT_FACTOR_METHOD,
            **(
                {
                    "drought_factor": round(s.fire_danger.drought_factor, 1),
                    "deficit_mm": round(s.fire_danger.deficit_mm, 1),
                    "peak_time": _iso(s.fire_danger.time),
                    "temperature": s.fire_danger.temperature,
                    "relative_humidity": s.fire_danger.humidity,
                    "wind_speed": s.fire_danger.wind_speed,
                }
                if s.fire_danger
                else {}
            ),
        },
    ),
)


class WeatherSignalEntity(ForecastEntity[WeatherSignalsCoordinator]):
    """Common attributes of the weather signal entities."""

    _attr_attribution = ATTRIBUTION_OPEN_METEO

    def _common_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "source": "Open-Meteo",
            "model": "best_match",
            "forecast_issued_at": _iso(self.coordinator.fetched_at),
            "window_start": _iso(data.window_start),
            "window_end": _iso(data.window_end),
            "official": False,
        }


class WeatherSignalSensor(WeatherSignalEntity, SensorEntity):
    """A model-derived weather hazard signal for the next 24 hours."""

    entity_description: WeatherSensorDescription

    def __init__(
        self,
        main: AustralianDisasterWatchCoordinator,
        coordinator: WeatherSignalsCoordinator,
        description: WeatherSensorDescription,
    ) -> None:
        """Initialize from a description."""
        super().__init__(main, coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the signal value, or None when the forecast lacks it."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the signal's drivers plus source metadata."""
        return {**self._common_attributes(), **self.entity_description.attrs_fn(self.coordinator.data)}


class WeatherThresholdBinarySensor(WeatherSignalEntity, BinarySensorEntity):
    """On when a 24-hour forecast maximum reaches the configured threshold."""

    def __init__(
        self,
        main: AustralianDisasterWatchCoordinator,
        coordinator: WeatherSignalsCoordinator,
        key: str,
        *,
        device_class: BinarySensorDeviceClass,
        peak_fn: Callable[[WeatherSignals], Peak | None],
        threshold: float,
    ) -> None:
        """Initialize with the peak to compare and its threshold."""
        super().__init__(main, coordinator, key)
        self._attr_translation_key = key
        self._attr_device_class = device_class
        self._peak_fn = peak_fn
        self._threshold = threshold

    @property
    def is_on(self) -> bool | None:
        """Return whether the forecast maximum reaches the threshold; unknown without data."""
        item = self._peak_fn(self.coordinator.data)
        return item.value >= self._threshold if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the threshold and forecast maximum."""
        item = self._peak_fn(self.coordinator.data)
        return {
            **self._common_attributes(),
            "threshold": self._threshold,
            "forecast_maximum": _peak_value(item),
            "peak_time": _iso(item.time if item else None),
        }


# --- River flood forecast (#38) ---


class RiverEntity(ForecastEntity[RiverForecastCoordinator]):
    """Base for one river point's entities."""

    _attr_attribution = ATTRIBUTION_GLOFAS

    def __init__(
        self,
        main: AustralianDisasterWatchCoordinator,
        coordinator: RiverForecastCoordinator,
        point: RiverPoint,
        key: str,
    ) -> None:
        """Initialize for one point; the name comes from the point."""
        super().__init__(main, coordinator, f"{key}_{point.point_id}")
        self.point = point
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"name": point.name}

    @property
    def forecast(self) -> RiverForecast | None:
        """Return this point's forecast from the last poll."""
        return (self.coordinator.data or {}).get(self.point.point_id)

    def _common_attributes(self) -> dict[str, Any]:
        forecast = self.forecast
        return {
            "source": "Open-Meteo Flood API (GloFAS)",
            "forecast_issued_at": _iso(self.coordinator.fetched_at),
            "grid_latitude": forecast.latitude if forecast else None,
            "grid_longitude": forecast.longitude if forecast else None,
            "official": False,
        }


class RiverDischargeSensor(RiverEntity, SensorEntity):
    """Today's GloFAS ensemble-mean river discharge at a point, with the 7-day forecast."""

    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND
    _attr_suggested_display_precision = 2

    def __init__(
        self, main: AustralianDisasterWatchCoordinator, coordinator: RiverForecastCoordinator, point: RiverPoint
    ) -> None:
        """Initialize the discharge sensor."""
        super().__init__(main, coordinator, point, "river_discharge")

    @property
    def native_value(self) -> float | None:
        """Return today's (UTC) mean discharge; None when the point is off the river grid."""
        forecast = self.forecast
        days = river_horizon(forecast.days, dt_util.utcnow().date(), 1) if forecast else []
        return days[0].mean if days else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the daily forecast, today's 75th percentile and the trend."""
        forecast = self.forecast
        days = river_horizon(forecast.days, dt_util.utcnow().date(), 7) if forecast else []
        return {
            **self._common_attributes(),
            "forecast": [{"date": d.day.isoformat(), "mean": d.mean, "max": d.maximum, "p75": d.p75} for d in days],
            "p75": days[0].p75 if days else None,
            "trend": river_trend(days[: self.point.horizon_days]),
        }


class RiverFloodRiskBinarySensor(RiverEntity, BinarySensorEntity):
    """On when the ensemble maximum discharge within the horizon exceeds the point's threshold."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self, main: AustralianDisasterWatchCoordinator, coordinator: RiverForecastCoordinator, point: RiverPoint
    ) -> None:
        """Initialize the flood-risk sensor."""
        super().__init__(main, coordinator, point, "river_flood_risk")

    def _peak(self) -> RiverDay | None:
        forecast = self.forecast
        days = river_horizon(forecast.days, dt_util.utcnow().date(), self.point.horizon_days) if forecast else []
        return river_peak(days)

    @property
    def is_on(self) -> bool | None:
        """Return whether any ensemble member exceeds the threshold; unknown without data."""
        peak_day = self._peak()
        return peak_day.maximum > self.point.threshold if peak_day and peak_day.maximum is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the threshold and the forecast peak."""
        peak_day = self._peak()
        return {
            **self._common_attributes(),
            "threshold": self.point.threshold,
            "baseline_median_annual_peak": self.point.baseline,
            "horizon_days": self.point.horizon_days,
            "basis": "ensemble maximum",
            "peak_date": peak_day.day.isoformat() if peak_day else None,
            "peak_maximum": peak_day.maximum if peak_day else None,
            "peak_p75": peak_day.p75 if peak_day else None,
            "peak_mean": peak_day.mean if peak_day else None,
        }


# --- Experimental AI ensemble rain outlook (#40) ---


@dataclass(frozen=True, kw_only=True)
class EnsembleSensorDescription(SensorEntityDescription):
    """An ensemble outlook sensor: how to read its value."""

    value_fn: Callable[[EnsembleOutlook], float | None]


ENSEMBLE_SENSORS = (
    EnsembleSensorDescription(
        key="heavy_rain_probability_24h",
        translation_key="heavy_rain_probability_24h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda o: o.probability_24h,
    ),
    EnsembleSensorDescription(
        key="heavy_rain_probability_72h",
        translation_key="heavy_rain_probability_72h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda o: o.probability_72h,
    ),
    EnsembleSensorDescription(
        key="ai_rain_outlook",
        translation_key="ai_rain_outlook",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=lambda o: o.mean_24h,
    ),
)


class EnsembleOutlookSensor(ForecastEntity[EnsembleOutlookCoordinator], SensorEntity):
    """Experimental heavy-rain outlook from AI ensemble models."""

    entity_description: EnsembleSensorDescription

    def __init__(
        self,
        main: AustralianDisasterWatchCoordinator,
        coordinator: EnsembleOutlookCoordinator,
        description: EnsembleSensorDescription,
    ) -> None:
        """Initialize from a description; attribution names only the models in use."""
        super().__init__(main, coordinator, description.key)
        self.entity_description = description
        sources = [ATTRIBUTION_OPEN_METEO, ATTRIBUTION_AIFS]
        if MODEL_WEATHERNEXT in coordinator.models:
            sources.append(ATTRIBUTION_WEATHERNEXT)
        self._attr_attribution = "; ".join(sources)

    @property
    def native_value(self) -> float | None:
        """Return the combined value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return labelling plus the per-model breakdown."""
        outlook = self.coordinator.data
        attrs: dict[str, Any] = {
            "experimental": True,
            "official": False,
            "notice": AI_NOTICE,
            "threshold_mm_24h": outlook.threshold,
        }
        if self.entity_description.key == "ai_rain_outlook":
            attrs |= {
                "agreement_24h": outlook.agreement_24h,
                "agreement_72h": outlook.agreement_72h,
                "models": {
                    model: {
                        "members": o.members,
                        "probability_24h": o.probability_24h,
                        "probability_72h": o.probability_72h,
                        "mean_24h": o.mean_24h,
                        "p90_24h": o.p90_24h,
                        "mean_72h": o.mean_72h,
                        "p90_72h": o.p90_72h,
                        "fetched_at": _iso(o.fetched_at),
                    }
                    for model, o in outlook.models.items()
                },
            }
        return attrs


def forecast_sensors(main: AustralianDisasterWatchCoordinator) -> list[SensorEntity]:
    """Return the sensors of the enabled forecast features."""
    forecasts = main.forecasts
    entities: list[SensorEntity] = []
    if weather := forecasts.weather:
        entities += [WeatherSignalSensor(main, weather, d) for d in WEATHER_SENSORS]
    if river := forecasts.river:
        entities += [RiverDischargeSensor(main, river, point) for point in river.points]
    if ensemble := forecasts.ensemble:
        entities += [EnsembleOutlookSensor(main, ensemble, d) for d in ENSEMBLE_SENSORS]
    return entities


def forecast_binary_sensors(main: AustralianDisasterWatchCoordinator) -> list[BinarySensorEntity]:
    """Return the binary sensors of the enabled forecast features."""
    forecasts = main.forecasts
    entities: list[BinarySensorEntity] = []
    if weather := forecasts.weather:
        entities += [
            WeatherThresholdBinarySensor(
                main,
                weather,
                "damaging_gusts_forecast",
                device_class=BinarySensorDeviceClass.SAFETY,
                peak_fn=lambda s: s.max_gust,
                threshold=weather.gust_threshold,
            ),
            WeatherThresholdBinarySensor(
                main,
                weather,
                "extreme_heat_forecast",
                device_class=BinarySensorDeviceClass.HEAT,
                peak_fn=lambda s: s.max_apparent_temperature,
                threshold=weather.heat_threshold,
            ),
        ]
    if river := forecasts.river:
        entities += [RiverFloodRiskBinarySensor(main, river, point) for point in river.points]
    return entities
