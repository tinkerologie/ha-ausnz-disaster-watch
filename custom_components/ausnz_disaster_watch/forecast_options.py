"""Options steps for the opt-in Open-Meteo forecast features (#38, #39, #40)."""

from __future__ import annotations

from datetime import date
import math
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_LOCATION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AI_ENSEMBLE,
    CONF_AI_WEATHERNEXT,
    CONF_GUST_THRESHOLD,
    CONF_HEAT_THRESHOLD,
    CONF_HEAVY_RAIN_THRESHOLD,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RIVER_POINTS,
    CONF_WEATHER_SIGNALS,
    DEFAULT_AI_ENSEMBLE,
    DEFAULT_AI_WEATHERNEXT,
    DEFAULT_GUST_THRESHOLD,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAVY_RAIN_THRESHOLD,
    DEFAULT_RIVER_HORIZON,
    DEFAULT_WEATHER_SIGNALS,
    MAX_GUST_THRESHOLD,
    MAX_HEAT_THRESHOLD,
    MAX_HEAVY_RAIN_THRESHOLD,
    MAX_RIVER_HORIZON,
    MAX_RIVER_POINTS,
    MIN_GUST_THRESHOLD,
    MIN_HEAT_THRESHOLD,
    MIN_HEAVY_RAIN_THRESHOLD,
    RIVER_POINT_BASELINE,
    RIVER_POINT_HORIZON,
    RIVER_POINT_ID,
    RIVER_POINT_NAME,
    RIVER_POINT_THRESHOLD,
)
from .forecast_coordinator import river_points
from .providers.forecast_signals import river_baseline
from .providers.open_meteo import OpenMeteoClient, OpenMeteoError, RiverForecast

CONF_USE_SUGGESTION = "use_suggestion"
CONF_POINT = "point"
BASELINE_YEARS = 20
# Neighbour cells to try when a point is off the 0.05° GloFAS river grid. Open-Meteo suggests
# moving the coordinate by about 0.1°; this probe (one multi-location request) is our own.
PROBE_OFFSETS = [(dy * step, dx * step) for step in (0.05, 0.1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]


def _slider(minimum: float, maximum: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=NumberSelectorMode.SLIDER
        )
    )


def _mean_discharge(forecast: RiverForecast) -> float:
    means = [d.mean for d in forecast.days if d.mean is not None]
    return sum(means) / len(means) if means else 0.0


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance, accurate enough for a few kilometres."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371.0 * math.hypot(x, math.radians(lat2 - lat1))


class ForecastOptionsFlow(OptionsFlowWithReload):
    """Options steps for forecast signals, river points and the AI ensemble outlook."""

    def __init__(self) -> None:
        """Initialize flow state for adding a river point."""
        super().__init__()
        self._pending: dict[str, Any] = {}
        self._suggestion: RiverForecast | None = None
        self._edit_id: str | None = None

    @property
    def _points(self) -> list[dict[str, Any]]:
        points = self.config_entry.options.get(CONF_RIVER_POINTS)
        return list(points) if isinstance(points, list) else []

    def _save(self, updates: dict[str, Any]) -> ConfigFlowResult:
        """Save options without dropping the ones other steps own."""
        return self.async_create_entry(data={**self.config_entry.options, **updates})

    def _client(self) -> OpenMeteoClient:
        return OpenMeteoClient(async_get_clientsession(self.hass))

    async def async_step_forecasts(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Toggle and tune the weather signals and the experimental AI ensemble outlook."""
        if user_input is not None:
            return self._save(user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WEATHER_SIGNALS, default=current.get(CONF_WEATHER_SIGNALS, DEFAULT_WEATHER_SIGNALS)
                ): BooleanSelector(),
                vol.Required(
                    CONF_GUST_THRESHOLD, default=current.get(CONF_GUST_THRESHOLD, DEFAULT_GUST_THRESHOLD)
                ): _slider(MIN_GUST_THRESHOLD, MAX_GUST_THRESHOLD, 5, "km/h"),
                vol.Required(
                    CONF_HEAT_THRESHOLD, default=current.get(CONF_HEAT_THRESHOLD, DEFAULT_HEAT_THRESHOLD)
                ): _slider(MIN_HEAT_THRESHOLD, MAX_HEAT_THRESHOLD, 1, "°C"),
                vol.Required(
                    CONF_AI_ENSEMBLE, default=current.get(CONF_AI_ENSEMBLE, DEFAULT_AI_ENSEMBLE)
                ): BooleanSelector(),
                vol.Required(
                    CONF_AI_WEATHERNEXT, default=current.get(CONF_AI_WEATHERNEXT, DEFAULT_AI_WEATHERNEXT)
                ): BooleanSelector(),
                vol.Required(
                    CONF_HEAVY_RAIN_THRESHOLD,
                    default=current.get(CONF_HEAVY_RAIN_THRESHOLD, DEFAULT_HEAVY_RAIN_THRESHOLD),
                ): _slider(MIN_HEAVY_RAIN_THRESHOLD, MAX_HEAVY_RAIN_THRESHOLD, 5, "mm"),
            }
        )
        return self.async_show_form(step_id="forecasts", data_schema=schema)  # type: ignore[arg-type]

    async def async_step_add_river_point(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a named point on a map; check it is on the river grid or suggest a nearby cell."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        default_location = {
            CONF_LATITUDE: current.get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: current.get(CONF_LONGITUDE, self.hass.config.longitude),
        }
        if len(self._points) >= MAX_RIVER_POINTS:
            return self.async_abort(reason="too_many_river_points")
        if user_input is not None:
            name = str(user_input[RIVER_POINT_NAME]).strip()
            location = user_input[CONF_LOCATION]
            lat, lon = float(location[CONF_LATITUDE]), float(location[CONF_LONGITUDE])
            default_location = {CONF_LATITUDE: lat, CONF_LONGITUDE: lon}
            if not name:
                errors[RIVER_POINT_NAME] = "empty_river_point_name"
            elif any(str(p.get(RIVER_POINT_NAME, "")).lower() == name.lower() for p in self._points):
                errors[RIVER_POINT_NAME] = "duplicate_river_point"
            else:
                self._pending = {RIVER_POINT_NAME: name, CONF_LATITUDE: lat, CONF_LONGITUDE: lon}
                try:
                    (forecast,) = await self._client().async_get_river_forecasts([(lat, lon)])
                    if forecast.has_data:
                        return await self.async_step_river_threshold()
                    candidates = await self._client().async_get_river_forecasts(
                        [(lat + dy, lon + dx) for dy, dx in PROBE_OFFSETS]
                    )
                except OpenMeteoError:
                    errors["base"] = "cannot_connect"
                else:
                    if best := max((c for c in candidates if c.has_data), key=_mean_discharge, default=None):
                        self._suggestion = best
                        return await self.async_step_river_suggestion()
                    errors["base"] = "no_river_cell"
        return self._add_point_form(default_location, errors)

    def _add_point_form(self, location: dict[str, Any], errors: dict[str, str]) -> ConfigFlowResult:
        schema = vol.Schema(
            {
                vol.Required(RIVER_POINT_NAME, default=self._pending.get(RIVER_POINT_NAME, "")): TextSelector(),
                vol.Required(CONF_LOCATION, default=location): LocationSelector(LocationSelectorConfig(radius=False)),
            }
        )
        return self.async_show_form(step_id="add_river_point", data_schema=schema, errors=errors)  # type: ignore[arg-type]

    async def async_step_river_suggestion(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer the nearby river cell with the largest discharge."""
        suggestion = self._suggestion
        assert suggestion is not None
        if user_input is not None:
            if not user_input[CONF_USE_SUGGESTION]:
                location = {CONF_LATITUDE: self._pending[CONF_LATITUDE], CONF_LONGITUDE: self._pending[CONF_LONGITUDE]}
                return self._add_point_form(location, {"base": "no_river_cell"})
            self._pending[CONF_LATITUDE] = suggestion.latitude
            self._pending[CONF_LONGITUDE] = suggestion.longitude
            return await self.async_step_river_threshold()
        distance = _distance_km(
            self._pending[CONF_LATITUDE], self._pending[CONF_LONGITUDE], suggestion.latitude, suggestion.longitude
        )
        return self.async_show_form(
            step_id="river_suggestion",
            data_schema=vol.Schema({vol.Required(CONF_USE_SUGGESTION, default=True): BooleanSelector()}),  # type: ignore[arg-type]
            description_placeholders={
                "latitude": f"{suggestion.latitude:.3f}",
                "longitude": f"{suggestion.longitude:.3f}",
                "distance": f"{distance:.1f}",
                "discharge": f"{_mean_discharge(suggestion):.2f}",
            },
        )

    async def async_step_river_threshold(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Set the flood-risk threshold, defaulting to the point's median annual peak discharge."""
        errors: dict[str, str] = {}
        if user_input is not None:
            threshold = float(user_input[RIVER_POINT_THRESHOLD])
            if threshold <= 0:
                errors[RIVER_POINT_THRESHOLD] = "invalid_threshold"
            else:
                point = {
                    RIVER_POINT_ID: uuid4().hex,
                    **self._pending,
                    RIVER_POINT_THRESHOLD: threshold,
                    RIVER_POINT_HORIZON: int(user_input[RIVER_POINT_HORIZON]),
                }
                return self._save({CONF_RIVER_POINTS: [*self._points, point]})
        if RIVER_POINT_BASELINE not in self._pending:
            this_year = dt_util.utcnow().year
            try:
                history = await self._client().async_get_river_history(
                    self._pending[CONF_LATITUDE],
                    self._pending[CONF_LONGITUDE],
                    date(this_year - BASELINE_YEARS, 1, 1),
                    date(this_year - 1, 12, 31),
                )
            except OpenMeteoError:
                history = []
            self._pending[RIVER_POINT_BASELINE] = river_baseline(history)
        baseline = self._pending[RIVER_POINT_BASELINE]
        threshold_key = (
            vol.Required(RIVER_POINT_THRESHOLD, default=baseline)
            if baseline is not None
            else vol.Required(RIVER_POINT_THRESHOLD)
        )
        schema = vol.Schema(
            {
                threshold_key: NumberSelector(
                    NumberSelectorConfig(min=0, step="any", unit_of_measurement="m³/s", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(RIVER_POINT_HORIZON, default=DEFAULT_RIVER_HORIZON): _slider(1, MAX_RIVER_HORIZON, 1, "d"),
            }
        )
        return self.async_show_form(
            step_id="river_threshold",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
            description_placeholders={
                "name": self._pending[RIVER_POINT_NAME],
                "baseline": f"{baseline:.2f} m³/s" if baseline is not None else "not available",
            },
        )

    def _point_selector(self, multiple: bool) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=p.point_id, label=p.name) for p in river_points(self._points)],
                multiple=multiple,
            )
        )

    async def async_step_edit_river_point(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose a river point to edit."""
        if user_input is not None:
            self._edit_id = user_input[CONF_POINT]
            return await self.async_step_edit_river_point_details()
        schema = vol.Schema({vol.Required(CONF_POINT): self._point_selector(multiple=False)})
        return self.async_show_form(step_id="edit_river_point", data_schema=schema)  # type: ignore[arg-type]

    async def async_step_edit_river_point_details(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change a river point's threshold and horizon; to move it, remove it and add a new one."""
        point = next(p for p in river_points(self._points) if p.point_id == self._edit_id)
        errors: dict[str, str] = {}
        if user_input is not None:
            threshold = float(user_input[RIVER_POINT_THRESHOLD])
            if threshold <= 0:
                errors[RIVER_POINT_THRESHOLD] = "invalid_threshold"
            else:
                updated = [
                    {**p, RIVER_POINT_THRESHOLD: threshold, RIVER_POINT_HORIZON: int(user_input[RIVER_POINT_HORIZON])}
                    if p.get(RIVER_POINT_ID) == point.point_id
                    else p
                    for p in self._points
                ]
                return self._save({CONF_RIVER_POINTS: updated})
        schema = vol.Schema(
            {
                vol.Required(RIVER_POINT_THRESHOLD, default=point.threshold): NumberSelector(
                    NumberSelectorConfig(min=0, step="any", unit_of_measurement="m³/s", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(RIVER_POINT_HORIZON, default=point.horizon_days): _slider(1, MAX_RIVER_HORIZON, 1, "d"),
            }
        )
        baseline = f"{point.baseline:.2f} m³/s" if point.baseline is not None else "not available"
        return self.async_show_form(
            step_id="edit_river_point_details",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
            description_placeholders={"name": point.name, "baseline": baseline},
        )

    async def async_step_remove_river_point(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Remove river points; their entities are removed on the reload."""
        if user_input is not None:
            remove = set(user_input[CONF_POINT])
            return self._save({CONF_RIVER_POINTS: [p for p in self._points if p.get(RIVER_POINT_ID) not in remove]})
        schema = vol.Schema({vol.Required(CONF_POINT): self._point_selector(multiple=True)})
        return self.async_show_form(step_id="remove_river_point", data_schema=schema)  # type: ignore[arg-type]
