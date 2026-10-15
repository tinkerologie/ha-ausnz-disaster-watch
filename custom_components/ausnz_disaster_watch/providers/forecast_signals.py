"""Model-derived forecast signals from Open-Meteo data (#38, #39, #40).

Pure functions, no I/O. Everything here is *calculated* from model forecasts. None of it is
an official warning, and nothing here is mapped to Australian Warning System levels or to
the official AFDRS fire danger rating.

Thunderstorm potential is a project heuristic, not a BoM category: per hour, CAPE and
precipitation probability give a level (very high: CAPE >= 2500 J/kg and >= 40 %; high:
>= 1000 J/kg and >= 30 %; moderate: >= 500 J/kg and >= 20 %), and a model thunderstorm
weather code (WMO 95, 96, 99) raises the hour to at least high. It ignores wind shear and
convective inhibition.

Calculated fire danger is the McArthur Mk5 Forest Fire Danger Index in the Noble et al.
(1980) form, FFDI = 2 exp(-0.450 + 0.987 ln D - 0.0345 RH + 0.0338 T + 0.0234 V), with mean
10 m wind (not gusts). The drought factor D is EXPERIMENTAL and not validated: Griffiths
(1999) with the soil dryness index replaced by a 20-day proxy, the sum of FAO reference
evapotranspiration minus effective rain (each rain event's total above its first 5 mm),
clamped to 0-203.2 mm. The past 20 days are archived model values, not gauge observations.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
import statistics

from .open_meteo import EnsembleRun, RiverDay, WeatherForecast

SIGNAL_WINDOW = timedelta(hours=24)

THUNDERSTORM_LEVELS = ("low", "moderate", "high", "very_high")
# (level index, minimum CAPE J/kg, minimum precipitation probability %), strongest first
THUNDERSTORM_RULES = ((3, 2500.0, 40.0), (2, 1000.0, 30.0), (1, 500.0, 20.0))
THUNDERSTORM_CODES = frozenset({95, 96, 99})

RAIN_DAY_MM = 0.2
EVENT_RAIN_ALLOWANCE_MM = 5.0
MAX_DEFICIT_MM = 203.2
DROUGHT_FACTOR_METHOD = "experimental: Griffiths (1999) with a 20-day evapotranspiration-minus-rain deficit proxy"

ENSEMBLE_AGREEMENT_POINTS = 20.0  # models "agree" when their probabilities are within 20 points
MIN_BASELINE_YEARS = 5
MIN_DAYS_PER_YEAR = 300
RIVER_TREND_TOLERANCE = 0.10


@dataclass(frozen=True)
class Peak:
    """The highest value in the window and the hour it occurs."""

    value: float
    time: datetime


@dataclass(frozen=True)
class Thunderstorm:
    """Thunderstorm potential level and the values that drove it."""

    level: str
    max_cape: float | None
    max_precipitation_probability: float | None
    thunderstorm_code: bool
    time: datetime | None


@dataclass(frozen=True)
class FireDanger:
    """Calculated FFDI peak with its inputs."""

    index: float
    time: datetime
    temperature: float
    humidity: float
    wind_speed: float
    drought_factor: float
    deficit_mm: float


@dataclass(frozen=True)
class WeatherSignals:
    """Signals for the next 24 hours, derived from one forecast."""

    window_start: datetime
    window_end: datetime
    max_gust: Peak | None
    max_apparent_temperature: Peak | None
    thunderstorm: Thunderstorm | None
    fire_danger: FireDanger | None


def window_indices(times: Sequence[datetime], start: datetime, length: timedelta) -> list[int]:
    """Return indices of times in [start, start + length)."""
    end = start + length
    return [i for i, t in enumerate(times) if start <= t < end]


def peak(times: Sequence[datetime], values: Sequence[float | None], indices: Sequence[int]) -> Peak | None:
    """Return the maximum non-null value among ``indices``, or None if all are null."""
    best: Peak | None = None
    for i in indices:
        value = values[i]
        if value is not None and (best is None or value > best.value):
            best = Peak(value, times[i])
    return best


def thunderstorm_level(cape: float | None, probability: float | None, code: float | None) -> int:
    """Return the heuristic level index for one hour."""
    level = 0
    if cape is not None and probability is not None:
        level = next(
            (lvl for lvl, min_cape, min_prob in THUNDERSTORM_RULES if cape >= min_cape and probability >= min_prob), 0
        )
    if code is not None and int(code) in THUNDERSTORM_CODES:
        level = max(level, 2)
    return level


def thunderstorm(forecast: WeatherForecast, indices: Sequence[int]) -> Thunderstorm | None:
    """Return the strongest hourly thunderstorm level in the window."""
    cape, prob, code = (forecast.hourly[k] for k in ("cape", "precipitation_probability", "weather_code"))
    if all(cape[i] is None and prob[i] is None and code[i] is None for i in indices):
        return None
    best_level, best_time = 0, None
    for i in indices:
        level = thunderstorm_level(cape[i], prob[i], code[i])
        if best_time is None or level > best_level:
            best_level, best_time = level, forecast.times[i]
    capes = [v for i in indices if (v := cape[i]) is not None]
    probs = [v for i in indices if (v := prob[i]) is not None]
    return Thunderstorm(
        level=THUNDERSTORM_LEVELS[best_level],
        max_cape=max(capes) if capes else None,
        max_precipitation_probability=max(probs) if probs else None,
        thunderstorm_code=any(code[i] is not None and int(code[i] or 0) in THUNDERSTORM_CODES for i in indices),
        time=best_time,
    )


def ffdi(temperature: float, humidity: float, wind_speed: float, drought_factor: float) -> float:
    """McArthur Mk5 FFDI (Noble et al. 1980); D is clamped to 0-10 and D = 0 gives 0."""
    d = min(max(drought_factor, 0.0), 10.0)
    if d == 0:
        return 0.0
    return 2.0 * math.exp(-0.450 + 0.987 * math.log(d) - 0.0345 * humidity + 0.0338 * temperature + 0.0234 * wind_speed)


def rain_events(rain: Sequence[float | None]) -> list[tuple[float, int]]:
    """Return (event total mm, days since the event's wettest day) for each run of rain days.

    ``rain`` is daily rain, oldest first, ending yesterday (so yesterday is 1 day ago).
    """
    events: list[tuple[float, int]] = []
    total, wettest, wettest_index = 0.0, -1.0, -1
    for i, value in enumerate([*rain, None]):
        if value is not None and value >= RAIN_DAY_MM:
            total += value
            if value > wettest:
                wettest, wettest_index = value, i
            continue
        if wettest_index >= 0:
            events.append((total, len(rain) - wettest_index))
        total, wettest, wettest_index = 0.0, -1.0, -1
    return events


def deficit_proxy(rain: Sequence[float | None], et0: Sequence[float | None]) -> float | None:
    """Return evapotranspiration minus effective rain (mm), clamped to 0-203.2, or None without ET0."""
    evaporation = [v for v in et0 if v is not None]
    if not evaporation:
        return None
    effective = sum(max(total - EVENT_RAIN_ALLOWANCE_MM, 0.0) for total, _ in rain_events(rain))
    return min(max(sum(evaporation) - effective, 0.0), MAX_DEFICIT_MM)


def drought_factor(deficit: float, events: Sequence[tuple[float, int]]) -> float:
    """Griffiths (1999) drought factor from a soil dryness value and recent rain events (0-10)."""
    x = 1.0
    for total, days in events:
        if total > 2.0:
            x = min(x, days**1.3 / (days**1.3 + total - 2.0))
    x_limit = 1.0 / (1.0 + 0.1135 * deficit) if deficit < 20 else 75.0 / (270.525 - 1.267 * deficit)
    x = min(x, x_limit)
    value = 10.5 * (1.0 - math.exp(-(deficit + 30.0) / 40.0)) * (41.0 * x * x + x) / (40.0 * x * x + x + 1.0)
    return min(max(value, 0.0), 10.0)


def fire_danger(forecast: WeatherForecast, indices: Sequence[int], today: datetime) -> FireDanger | None:
    """Return the peak calculated FFDI in the window, using past days for the drought factor."""
    past = [i for i, day in enumerate(forecast.days) if day < today]
    rain = [forecast.daily["precipitation_sum"][i] for i in past]
    deficit = deficit_proxy(rain, [forecast.daily["et0_fao_evapotranspiration"][i] for i in past])
    if deficit is None:
        return None
    d = drought_factor(deficit, rain_events(rain))
    temp, rh, wind = (forecast.hourly[k] for k in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m"))
    best: FireDanger | None = None
    for i in indices:
        t, h, v = temp[i], rh[i], wind[i]
        if t is None or h is None or v is None:
            continue
        index = ffdi(t, h, v, d)
        if best is None or index > best.index:
            best = FireDanger(index, forecast.times[i], t, h, v, d, deficit)
    return best


def weather_signals(forecast: WeatherForecast, now: datetime) -> WeatherSignals:
    """Derive the 24-hour signals, starting at the current hour."""
    start = now.replace(minute=0, second=0, microsecond=0)
    indices = window_indices(forecast.times, start, SIGNAL_WINDOW)
    # Daily times are local midnights; the day containing ``now`` is today
    today = max((d for d in forecast.days if d <= now), default=start)
    return WeatherSignals(
        window_start=start,
        window_end=start + SIGNAL_WINDOW,
        max_gust=peak(forecast.times, forecast.hourly["wind_gusts_10m"], indices),
        max_apparent_temperature=peak(forecast.times, forecast.hourly["apparent_temperature"], indices),
        thunderstorm=thunderstorm(forecast, indices),
        fire_danger=fire_danger(forecast, indices, today),
    )


# --- AI ensemble rain outlook (#40) ---


@dataclass(frozen=True)
class ModelOutlook:
    """Heavy-rain statistics of one ensemble model."""

    model: str
    members: int
    probability_24h: float | None
    probability_72h: float | None
    mean_24h: float | None
    p90_24h: float | None
    mean_72h: float | None
    p90_72h: float | None
    fetched_at: datetime


@dataclass(frozen=True)
class EnsembleOutlook:
    """Models combined with equal weight, so a model with more members does not dominate."""

    models: dict[str, ModelOutlook]
    probability_24h: float | None
    probability_72h: float | None
    mean_24h: float | None
    agreement_24h: bool | None
    agreement_72h: bool | None
    threshold: float


def _p90(values: Sequence[float]) -> float:
    """Return the 90th percentile (inclusive linear interpolation)."""
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=10, method="inclusive")[8]


def _percent(hits: int, total: int) -> float:
    return round(100.0 * hits / total, 1)


def model_outlook(run: EnsembleRun, now: datetime, threshold: float, fetched_at: datetime) -> ModelOutlook:
    """Return heavy-rain probabilities from member totals.

    The 24 h probability is the share of members whose next-24 h total reaches the threshold;
    the 72 h probability is the share with any rolling 24 h total in the next 72 h reaching
    it. Members with a gap in the window are left out.
    """
    start = now.replace(minute=0, second=0, microsecond=0)
    indices = window_indices(run.times, start, timedelta(hours=72))
    totals_24: list[float] = []
    totals_72: list[float] = []
    peaks_24: list[float] = []
    if len(indices) == 72:
        for member in run.members:
            values = [member[i] for i in indices]
            if any(v is None for v in values):
                continue
            hourly = [v or 0.0 for v in values]
            totals_24.append(sum(hourly[:24]))
            totals_72.append(sum(hourly))
            peaks_24.append(max(sum(hourly[k : k + 24]) for k in range(49)))

    def stats(values: list[float]) -> tuple[float | None, float | None]:
        return (round(statistics.fmean(values), 1), round(_p90(values), 1)) if values else (None, None)

    mean_24, p90_24 = stats(totals_24)
    mean_72, p90_72 = stats(totals_72)
    valid = len(totals_24)
    return ModelOutlook(
        model=run.model,
        members=valid,
        probability_24h=_percent(sum(t >= threshold for t in totals_24), valid) if valid else None,
        probability_72h=_percent(sum(t >= threshold for t in peaks_24), valid) if valid else None,
        mean_24h=mean_24,
        p90_24h=p90_24,
        mean_72h=mean_72,
        p90_72h=p90_72,
        fetched_at=fetched_at,
    )


def combine_outlooks(outlooks: dict[str, ModelOutlook], threshold: float) -> EnsembleOutlook:
    """Combine per-model outlooks: equal-weight means and an agreement flag when two models exist."""

    def mean(attr: str) -> float | None:
        values = [v for o in outlooks.values() if (v := getattr(o, attr)) is not None]
        return round(statistics.fmean(values), 1) if values else None

    def agree(attr: str) -> bool | None:
        values = [v for o in outlooks.values() if (v := getattr(o, attr)) is not None]
        return abs(values[0] - values[1]) <= ENSEMBLE_AGREEMENT_POINTS if len(values) == 2 else None

    return EnsembleOutlook(
        models=outlooks,
        probability_24h=mean("probability_24h"),
        probability_72h=mean("probability_72h"),
        mean_24h=mean("mean_24h"),
        agreement_24h=agree("probability_24h"),
        agreement_72h=agree("probability_72h"),
        threshold=threshold,
    )


# --- River discharge (#38) ---


def river_baseline(history: Sequence[tuple[date, float]]) -> float | None:
    """Return the median annual peak discharge (about a 2-year flood) of the reanalysis.

    Only years with at least 300 values count, and at least 5 such years are needed. GloFAS
    uses return-period thresholds such as this one for its own flood alerts.
    """
    by_year: dict[int, list[float]] = {}
    for day, value in history:
        by_year.setdefault(day.year, []).append(value)
    peaks = [max(values) for values in by_year.values() if len(values) >= MIN_DAYS_PER_YEAR]
    if len(peaks) < MIN_BASELINE_YEARS:
        return None
    return round(statistics.median(peaks), 2)


def river_horizon(days: Sequence[RiverDay], today: date, horizon: int) -> list[RiverDay]:
    """Return forecast days from today for ``horizon`` days."""
    return [d for d in days if today <= d.day < today + timedelta(days=horizon)]


def river_peak(days: Sequence[RiverDay]) -> RiverDay | None:
    """Return the day with the highest ensemble-maximum discharge, or None if all are null."""
    usable = [d for d in days if d.maximum is not None]
    return max(usable, key=lambda d: d.maximum or 0.0) if usable else None


def river_trend(days: Sequence[RiverDay]) -> str | None:
    """Return rising, falling or steady from the first to the last ensemble mean (10 % band)."""
    means = [d.mean for d in days if d.mean is not None]
    if len(means) < 2:
        return None
    first, last = means[0], means[-1]
    if last > first * (1 + RIVER_TREND_TOLERANCE):
        return "rising"
    if last < first * (1 - RIVER_TREND_TOLERANCE):
        return "falling"
    return "steady"
