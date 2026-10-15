"""Open-Meteo client for the forecast features (#38, #39, #40).

Open-Meteo serves keyless JSON for weather forecasts, GloFAS river discharge and ensemble
models. The API is one GET per feature, so a small aiohttp client is used instead of a
PyPI dependency (#35). This is not a hazard provider: it is never registered in
``get_providers_for_config`` and its data never becomes a ``CanonicalHazard``.

Terms (https://open-meteo.com/en/terms): the free API is for non-commercial use, under
10,000 calls a day, 5,000 an hour and 600 a minute per IP; data are CC BY 4.0 and need the
attribution "Weather data by Open-Meteo.com". Each fetch is a single attempt: a retry costs
quota, so the coordinators decide when to try again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import logging
import re
from typing import Any

import aiohttp

from .base import ProviderUnavailableError

_LOGGER = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
USER_AGENT = "AusNZDisasterWatch (+https://github.com/tinkerologie/ha-ausnz-disaster-watch)"
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Verified on 2026-10-16 for Brisbane: all filled. `lightning_potential` (all null outside
# Europe/North America) and the `bom_access_global` / `gfs_graphcast025` models are not used.
HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation_probability",
    "wind_speed_10m",
    "wind_gusts_10m",
    "cape",
    "weather_code",
)
DAILY_VARIABLES = ("precipitation_sum", "et0_fao_evapotranspiration")
FORECAST_DAYS = 3
PAST_DAYS = 20  # drought-factor rain and evapotranspiration window

RIVER_VARIABLES = ("river_discharge", "river_discharge_max", "river_discharge_p75")
RIVER_FORECAST_DAYS = 7

MODEL_AIFS = "ecmwf_aifs025_ensemble"
MODEL_WEATHERNEXT = "google_weathernext2_ensemble"
ENSEMBLE_FORECAST_DAYS = 5  # 72 h window plus the 12 h a WeatherNext 2 run is reused

_MEMBER_RE = re.compile(r"^precipitation(?:_member(\d+))?(?:_(\w+))?$")


class OpenMeteoError(ProviderUnavailableError):
    """Open-Meteo could not be reached, refused the request or returned an unusable payload."""


@dataclass(frozen=True)
class WeatherForecast:
    """Hourly and daily forecast for one point (times are UTC)."""

    times: list[datetime]
    hourly: dict[str, list[float | None]]
    days: list[datetime]
    daily: dict[str, list[float | None]]


@dataclass(frozen=True)
class RiverDay:
    """One GloFAS forecast day: ensemble mean, maximum and 75th percentile discharge (m³/s)."""

    day: date
    mean: float | None
    maximum: float | None
    p75: float | None


@dataclass(frozen=True)
class RiverForecast:
    """GloFAS daily discharge for one grid cell."""

    latitude: float
    longitude: float
    days: list[RiverDay] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        """Return True if any day has a discharge value (a point off the river grid has none)."""
        return any(d.mean is not None or d.maximum is not None for d in self.days)


@dataclass(frozen=True)
class EnsembleRun:
    """Hourly precipitation (mm) of every member of one ensemble model."""

    model: str
    times: list[datetime]
    members: list[list[float | None]]


def _number(value: Any) -> float | None:
    """Return a float, or None for null and non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _series(block: dict[str, Any], key: str, length: int) -> list[float | None]:
    """Return a numeric series of ``length`` items; missing or short series are padded with None."""
    raw = block.get(key)
    values = [_number(v) for v in raw] if isinstance(raw, list) else []
    return (values + [None] * length)[:length]


def _times(block: Any, label: str) -> list[datetime]:
    """Return the ``time`` array (unix seconds) of a response block as UTC datetimes."""
    if not isinstance(block, dict) or not isinstance(block.get("time"), list):
        raise OpenMeteoError(f"Open-Meteo {label} response has no time series")
    try:
        return [datetime.fromtimestamp(int(t), UTC) for t in block["time"]]
    except (TypeError, ValueError, OverflowError) as err:
        raise OpenMeteoError(f"Open-Meteo {label} response has invalid times: {err}") from err


def _locations(payload: Any, label: str) -> list[dict[str, Any]]:
    """Return the per-location objects (a multi-location request answers with a list)."""
    items = payload if isinstance(payload, list) else [payload]
    if not items or not all(isinstance(item, dict) for item in items):
        raise OpenMeteoError(f"Open-Meteo {label} returned an unexpected payload")
    return items


def parse_forecast(payload: Any) -> WeatherForecast:
    """Parse a forecast response; nulls stay None so missing data reads as unknown, not zero."""
    item = _locations(payload, "forecast")[0]
    times = _times(item.get("hourly"), "forecast")
    days = _times(item.get("daily"), "forecast")
    return WeatherForecast(
        times=times,
        hourly={key: _series(item["hourly"], key, len(times)) for key in HOURLY_VARIABLES},
        days=days,
        daily={key: _series(item["daily"], key, len(days)) for key in DAILY_VARIABLES},
    )


def parse_river(payload: Any) -> list[RiverForecast]:
    """Parse a flood response for one or more locations, in request order."""
    forecasts: list[RiverForecast] = []
    for item in _locations(payload, "flood"):
        days = _times(item.get("daily"), "flood")
        daily = item["daily"]
        columns = [_series(daily, key, len(days)) for key in RIVER_VARIABLES]
        forecasts.append(
            RiverForecast(
                latitude=_number(item.get("latitude")) or 0.0,
                longitude=_number(item.get("longitude")) or 0.0,
                days=[
                    RiverDay(day=when.date(), mean=mean, maximum=maximum, p75=p75)
                    for when, mean, maximum, p75 in zip(days, *columns, strict=True)
                ],
            )
        )
    return forecasts


def parse_ensemble(payload: Any, models: Sequence[str]) -> dict[str, EnsembleRun]:
    """Parse an ensemble response into member series per model.

    With one model the columns are ``precipitation`` (control) and ``precipitation_memberNN``;
    with several, each column also ends in ``_<model>``. A model without columns is left out.
    """
    item = _locations(payload, "ensemble")[0]
    times = _times(item.get("hourly"), "ensemble")
    hourly = item["hourly"]
    columns: dict[str, list[str]] = {model: [] for model in models}
    for key in hourly:
        if not (match := _MEMBER_RE.match(key)):
            continue
        model = match.group(2) or (models[0] if len(models) == 1 else None)
        if model in columns:
            columns[model].append(key)
    return {
        model: EnsembleRun(model=model, times=times, members=[_series(hourly, key, len(times)) for key in keys])
        for model, keys in columns.items()
        if keys
    }


class OpenMeteoClient:
    """Fetch Open-Meteo forecast, flood and ensemble data over Home Assistant's shared session."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with an injected aiohttp session."""
        self._session = session

    async def _async_get(self, url: str, params: dict[str, str]) -> Any:
        """GET one Open-Meteo endpoint once and return the decoded JSON."""
        try:
            async with self._session.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
            ) as resp:
                try:
                    payload = await resp.json(content_type=None)
                except ValueError as err:
                    raise OpenMeteoError(f"Open-Meteo returned HTTP {resp.status} with invalid JSON") from err
                if resp.status != 200 or (isinstance(payload, dict) and payload.get("error")):
                    reason = payload.get("reason") if isinstance(payload, dict) else None
                    raise OpenMeteoError(f"Open-Meteo returned HTTP {resp.status}: {reason or 'no reason given'}")
                return payload
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OpenMeteoError(f"Open-Meteo unavailable: {err!r}") from err

    async def async_get_forecast(self, latitude: float, longitude: float) -> WeatherForecast:
        """Fetch 3 forecast days plus 20 past days (for the drought factor) for one point."""
        payload = await self._async_get(
            FORECAST_URL,
            {
                "latitude": f"{latitude:.4f}",
                "longitude": f"{longitude:.4f}",
                "hourly": ",".join(HOURLY_VARIABLES),
                "daily": ",".join(DAILY_VARIABLES),
                "forecast_days": str(FORECAST_DAYS),
                "past_days": str(PAST_DAYS),
                "timezone": "auto",
                "timeformat": "unixtime",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            },
        )
        return parse_forecast(payload)

    async def async_get_river_forecasts(self, points: Sequence[tuple[float, float]]) -> list[RiverForecast]:
        """Fetch 7 days of GloFAS discharge for every point in one multi-location request."""
        payload = await self._async_get(
            FLOOD_URL,
            {
                "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
                "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
                "daily": ",".join(RIVER_VARIABLES),
                "forecast_days": str(RIVER_FORECAST_DAYS),
                "timezone": "GMT",  # keep the model's own dates
                "timeformat": "unixtime",
            },
        )
        forecasts = parse_river(payload)
        if len(forecasts) != len(points):
            raise OpenMeteoError(f"Open-Meteo flood returned {len(forecasts)} locations for {len(points)} points")
        return forecasts

    async def async_get_river_history(
        self, latitude: float, longitude: float, start: date, end: date
    ) -> list[tuple[date, float]]:
        """Fetch the GloFAS reanalysis daily discharge for one cell (used once, when a point is added)."""
        payload = await self._async_get(
            FLOOD_URL,
            {
                "latitude": f"{latitude:.4f}",
                "longitude": f"{longitude:.4f}",
                "daily": "river_discharge",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "timeformat": "unixtime",
            },
        )
        item = _locations(payload, "flood")[0]
        days = _times(item.get("daily"), "flood")
        values = _series(item["daily"], "river_discharge", len(days))
        return [(when.date(), value) for when, value in zip(days, values, strict=True) if value is not None]

    async def async_get_ensemble(
        self, latitude: float, longitude: float, models: Sequence[str]
    ) -> dict[str, EnsembleRun]:
        """Fetch hourly precipitation members of the given ensemble models in one request."""
        payload = await self._async_get(
            ENSEMBLE_URL,
            {
                "latitude": f"{latitude:.4f}",
                "longitude": f"{longitude:.4f}",
                "models": ",".join(models),
                "hourly": "precipitation",
                "forecast_days": str(ENSEMBLE_FORECAST_DAYS),
                "timezone": "GMT",
                "timeformat": "unixtime",
            },
        )
        return parse_ensemble(payload, models)
