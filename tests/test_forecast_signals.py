"""Tests for the model-derived forecast signal calculations (#38, #39, #40)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
import math
from pathlib import Path

import pytest

from custom_components.ausnz_disaster_watch.providers import forecast_signals as fs
from custom_components.ausnz_disaster_watch.providers.open_meteo import (
    MODEL_AIFS,
    MODEL_WEATHERNEXT,
    EnsembleRun,
    RiverDay,
    WeatherForecast,
    parse_ensemble,
    parse_forecast,
)

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"
# The captured Brisbane samples were fetched at about this time
FIXTURE_NOW = datetime(2026, 10, 15, 22, 30, tzinfo=UTC)
T0 = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _forecast(hours: int = 24, **hourly: list[float | None]) -> WeatherForecast:
    """Build a forecast starting at T0 with constant defaults and the given overrides."""
    defaults: dict[str, float | None] = {
        "temperature_2m": 25.0,
        "relative_humidity_2m": 50.0,
        "apparent_temperature": 25.0,
        "precipitation_probability": 0.0,
        "wind_speed_10m": 10.0,
        "wind_gusts_10m": 20.0,
        "cape": 0.0,
        "weather_code": 0.0,
    }
    series = {key: hourly.get(key, [value] * hours) for key, value in defaults.items()}
    days = [T0 - timedelta(days=d) for d in (3, 2, 1, 0)]
    return WeatherForecast(
        times=[T0 + timedelta(hours=h) for h in range(hours)],
        hourly=series,
        days=days,
        daily={"precipitation_sum": [0.0, 0.0, 0.0, 0.0], "et0_fao_evapotranspiration": [5.0, 5.0, 5.0, 5.0]},
    )


# --- McArthur FFDI ---


def test_ffdi_reference_value() -> None:
    """Noble et al. (1980) equation, recomputed for T 30 °C, RH 20 %, V 25 km/h, D 8.

    No primary numerical example from the 1980 paper was accessible, so this value is a
    recomputation of the published equation (24.6), not an independent benchmark.
    """
    assert fs.ffdi(30, 20, 25, 8) == pytest.approx(24.6, abs=0.05)
    # Same equation, extreme conditions (T 45 °C, RH 5 %, V 60 km/h, D 10)
    expected = 2 * math.exp(-0.450 + 0.987 * math.log(10) - 0.0345 * 5 + 0.0338 * 45 + 0.0234 * 60)
    assert fs.ffdi(45, 5, 60, 10) == pytest.approx(expected)
    assert fs.ffdi(45, 5, 60, 10) > 100  # catastrophic territory on the Mk5 scale


def test_ffdi_properties() -> None:
    """D = 0 gives 0, D is clamped to 10, and FFDI rises with T, V and D and falls with RH."""
    assert fs.ffdi(40, 10, 40, 0) == 0
    assert fs.ffdi(40, 10, 40, -3) == 0
    assert fs.ffdi(30, 20, 25, 15) == fs.ffdi(30, 20, 25, 10)
    base = fs.ffdi(30, 20, 25, 8)
    assert fs.ffdi(31, 20, 25, 8) > base
    assert fs.ffdi(30, 21, 25, 8) < base
    assert fs.ffdi(30, 20, 26, 8) > base
    assert fs.ffdi(30, 20, 25, 9) > base


# --- Drought factor (experimental) ---


def test_rain_events() -> None:
    """Consecutive rain days form one event; age counts from its wettest day (yesterday = 1)."""
    assert fs.rain_events([0.0, 0.1, None]) == []
    # Event of 3 + 10 mm, wettest 3 days ago; event of 1 mm yesterday
    assert fs.rain_events([0.0, 3.0, 10.0, 0.0, 1.0]) == [(13.0, 3), (1.0, 1)]


def test_deficit_proxy() -> None:
    """ET0 minus rain above the first 5 mm of each event, clamped to 0-203.2 mm."""
    assert fs.deficit_proxy([0.0, 0.0], [None, None]) is None
    assert fs.deficit_proxy([0.0, 8.0], [4.0, 4.0]) == pytest.approx(5.0)
    assert fs.deficit_proxy([60.0], [4.0]) == 0.0
    assert fs.deficit_proxy([0.0] * 20, [12.0] * 20) == fs.MAX_DEFICIT_MM


def test_drought_factor_branches() -> None:
    """Griffiths (1999): no rain, small rain, recent heavy rain and the dryness limit."""
    no_rain = fs.drought_factor(0.0, [])
    assert no_rain == pytest.approx(10.5 * (1 - math.exp(-30 / 40)))
    # Events of 2 mm or less do not lower the factor
    assert fs.drought_factor(0.0, [(2.0, 1)]) == no_rain
    # Heavy rain yesterday lowers it sharply; older rain less so
    recent = fs.drought_factor(100.0, [(50.0, 1)])
    older = fs.drought_factor(100.0, [(50.0, 15)])
    assert recent < older < fs.drought_factor(100.0, [])
    # The dryness limit caps x when the soil is moist (deficit < 20) and when moderately dry

    def griffiths(deficit: float, x: float) -> float:
        return 10.5 * (1 - math.exp(-(deficit + 30) / 40)) * (41 * x * x + x) / (40 * x * x + x + 1)

    assert fs.drought_factor(10.0, []) == pytest.approx(griffiths(10.0, 1 / (1 + 0.1135 * 10)))
    assert fs.drought_factor(30.0, []) == pytest.approx(griffiths(30.0, 75 / (270.525 - 1.267 * 30)))
    # Very dry and no rain reaches the cap of 10
    assert fs.drought_factor(fs.MAX_DEFICIT_MM, []) == 10.0


# --- Thunderstorm heuristic ---


@pytest.mark.parametrize(
    ("cape", "probability", "code", "level"),
    [
        (2500.0, 40.0, 0.0, 3),
        (2499.0, 40.0, 0.0, 2),
        (1000.0, 30.0, 0.0, 2),
        (1000.0, 29.0, 0.0, 1),
        (500.0, 20.0, 0.0, 1),
        (499.0, 100.0, 0.0, 0),
        (3000.0, 10.0, 0.0, 0),
        (None, 50.0, 0.0, 0),
        (0.0, 0.0, 95.0, 2),
        (2600.0, 50.0, 99.0, 3),
        (None, None, None, 0),
    ],
)
def test_thunderstorm_level(cape: float | None, probability: float | None, code: float | None, level: int) -> None:
    """Thresholds apply to coincident hours; a thunderstorm weather code means at least high."""
    assert fs.thunderstorm_level(cape, probability, code) == level


def test_thunderstorm_window() -> None:
    """The window reports its strongest hour and drivers; an all-null window is unknown."""
    cape = [0.0] * 24
    prob = [0.0] * 24
    cape[5], prob[5] = 1200.0, 35.0
    signal = fs.thunderstorm(_forecast(cape=cape, precipitation_probability=prob), range(24))
    assert signal is not None
    assert signal.level == "high"
    assert signal.time == T0 + timedelta(hours=5)
    assert signal.max_cape == 1200.0
    assert signal.max_precipitation_probability == 35.0
    assert signal.thunderstorm_code is False

    nulls: list[float | None] = [None] * 24
    assert (
        fs.thunderstorm(_forecast(cape=nulls, precipitation_probability=nulls, weather_code=nulls), range(24)) is None
    )

    codes: list[float | None] = [None] * 24
    codes[3] = 96.0
    signal = fs.thunderstorm(_forecast(cape=nulls, precipitation_probability=nulls, weather_code=codes), range(24))
    assert signal is not None
    assert signal.level == "high"
    assert signal.thunderstorm_code is True
    assert signal.max_cape is None
    assert signal.max_precipitation_probability is None


# --- Weather signals end to end ---


def test_window_and_peak() -> None:
    """The window is [start, start + length) and peak skips nulls."""
    forecast = _forecast(hours=30, wind_gusts_10m=[None] * 10 + [50.0] + [90.0] * 19)
    indices = fs.window_indices(forecast.times, T0 + timedelta(hours=2), timedelta(hours=24))
    assert indices == list(range(2, 26))
    peak = fs.peak(forecast.times, forecast.hourly["wind_gusts_10m"], indices)
    assert peak == fs.Peak(90.0, T0 + timedelta(hours=11))
    assert fs.peak(forecast.times, forecast.hourly["wind_gusts_10m"], range(2, 10)) is None


def test_weather_signals_brisbane_fixture() -> None:
    """Captured Brisbane forecast (sample of 2026-10-15) gives plausible, fully populated signals."""
    forecast = parse_forecast(_load("forecast_brisbane.json"))
    signals = fs.weather_signals(forecast, FIXTURE_NOW)
    assert signals.window_start == datetime(2026, 10, 15, 22, tzinfo=UTC)
    assert signals.window_end == datetime(2026, 10, 16, 22, tzinfo=UTC)
    assert signals.max_gust is not None
    assert 0 < signals.max_gust.value < 90
    assert signals.max_apparent_temperature is not None
    assert signals.thunderstorm is not None
    assert signals.thunderstorm.level in fs.THUNDERSTORM_LEVELS
    assert signals.fire_danger is not None
    assert 0 < signals.fire_danger.drought_factor <= 10
    assert 0 < signals.fire_danger.index < 12  # "moderate" spring conditions
    assert signals.fire_danger.time >= signals.window_start


def test_fire_danger_needs_evapotranspiration_and_complete_hours() -> None:
    """Without ET0 the drought factor is unknown, and hours with a missing input are skipped."""
    forecast = _forecast()
    forecast.daily["et0_fao_evapotranspiration"][:] = [None] * 4
    assert fs.fire_danger(forecast, range(24), T0) is None

    temps: list[float | None] = [None] * 24
    temps[7] = 35.0
    danger = fs.fire_danger(_forecast(temperature_2m=temps), range(24), T0)
    assert danger is not None
    assert danger.time == T0 + timedelta(hours=7)
    assert danger.deficit_mm == 15.0  # three past days of 5 mm ET0


def test_weather_signals_without_daily_data() -> None:
    """A forecast without daily rows has no fire danger but still has the hourly signals."""
    forecast = _forecast()
    empty = WeatherForecast(
        forecast.times, forecast.hourly, [], {"precipitation_sum": [], "et0_fao_evapotranspiration": []}
    )
    signals = fs.weather_signals(empty, T0)
    assert signals.fire_danger is None
    assert signals.max_gust == fs.Peak(20.0, T0)


# --- AI ensemble outlook ---


def _run(members: list[list[float | None]], model: str = MODEL_AIFS) -> EnsembleRun:
    return EnsembleRun(model=model, times=[T0 + timedelta(hours=h) for h in range(len(members[0]))], members=members)


def test_model_outlook_probabilities() -> None:
    """24 h uses the next-24 h total; 72 h counts any rolling 24 h total reaching the threshold."""
    dry = [0.0] * 72
    wet_today = [3.0] * 24 + [0.0] * 48  # 72 mm in the first 24 h
    wet_later = [0.0] * 30 + [2.5] * 24 + [0.0] * 18  # 60 mm, starting 30 h out
    gap = [None] + [0.0] * 71  # excluded
    outlook = fs.model_outlook(_run([dry, wet_today, wet_later, gap]), T0, 50.0, T0)
    assert outlook.members == 3
    assert outlook.probability_24h == pytest.approx(33.3)
    assert outlook.probability_72h == pytest.approx(66.7)
    assert outlook.mean_24h == pytest.approx(24.0)
    assert outlook.mean_72h == pytest.approx(44.0)
    assert outlook.p90_24h is not None
    assert outlook.p90_24h > outlook.mean_24h
    assert outlook.p90_72h is not None


def test_model_outlook_insufficient_coverage() -> None:
    """A run that does not cover 72 h, or has no complete member, has unknown values."""
    short = fs.model_outlook(_run([[0.0] * 48]), T0, 50.0, T0)
    assert short.members == 0
    assert short.probability_24h is None
    assert short.probability_72h is None
    assert short.mean_24h is None
    assert short.p90_24h is None

    single = fs.model_outlook(_run([[1.0] * 72]), T0, 50.0, T0)
    assert single.p90_24h == 24.0  # one member: its own total


def test_combine_outlooks() -> None:
    """Models are averaged with equal weight; agreement needs two models."""
    aifs = fs.model_outlook(_run([[3.0] * 72, [0.0] * 72]), T0, 50.0, T0)
    wn2 = fs.model_outlook(_run([[0.0] * 72] * 4, MODEL_WEATHERNEXT), T0, 50.0, T0)
    combined = fs.combine_outlooks({MODEL_AIFS: aifs, MODEL_WEATHERNEXT: wn2}, 50.0)
    assert combined.probability_24h == 25.0
    assert combined.agreement_24h is False
    assert combined.agreement_72h is False
    assert combined.mean_24h == pytest.approx(18.0)
    assert combined.threshold == 50.0

    only = fs.combine_outlooks({MODEL_AIFS: aifs}, 50.0)
    assert only.probability_24h == aifs.probability_24h
    assert only.agreement_24h is None

    empty = fs.combine_outlooks({MODEL_AIFS: fs.model_outlook(_run([[0.0] * 10]), T0, 50.0, T0)}, 50.0)
    assert empty.probability_24h is None


def test_ensemble_brisbane_fixture() -> None:
    """Captured AIFS (51 members) and WeatherNext 2 (64 members) samples give valid outlooks."""
    runs = parse_ensemble(_load("ensemble_brisbane.json"), [MODEL_AIFS, MODEL_WEATHERNEXT])
    assert len(runs[MODEL_AIFS].members) == 51
    assert len(runs[MODEL_WEATHERNEXT].members) == 64
    outlooks = {m: fs.model_outlook(run, FIXTURE_NOW, 10.0, FIXTURE_NOW) for m, run in runs.items()}
    assert outlooks[MODEL_AIFS].members == 51
    assert outlooks[MODEL_WEATHERNEXT].members == 64
    combined = fs.combine_outlooks(outlooks, 10.0)
    assert combined.probability_72h is not None
    assert 0 <= combined.probability_72h <= 100


# --- River ---


def _days(*values: tuple[float | None, float | None]) -> list[RiverDay]:
    return [
        RiverDay(day=date(2026, 10, 15) + timedelta(days=i), mean=mean, maximum=maximum, p75=mean)
        for i, (mean, maximum) in enumerate(values)
    ]


def test_river_baseline() -> None:
    """Median annual peak over years with >= 300 values; fewer than 5 years is unknown."""
    history = [
        (date(year, 1, 1) + timedelta(days=d), float(year - 2000 + d % 3))
        for year in range(2001, 2007)
        for d in range(365)
    ]
    history += [(date(2007, 1, 1), 1000.0)]  # an incomplete year is ignored
    assert fs.river_baseline(history) == pytest.approx(5.5)
    assert fs.river_baseline(history[: 365 * 4]) is None


def test_river_horizon_peak_trend() -> None:
    """Horizon slicing, the ensemble-maximum peak, and the 10 % trend band."""
    days = _days((10.0, 12.0), (11.0, 30.0), (12.0, 15.0), (20.0, None))
    assert [d.day for d in fs.river_horizon(days, date(2026, 10, 16), 2)] == [date(2026, 10, 16), date(2026, 10, 17)]
    assert fs.river_peak(days) == days[1]
    assert fs.river_peak(_days((None, None))) is None
    assert fs.river_trend(days) == "rising"
    assert fs.river_trend(_days((10.0, 1.0), (8.0, 1.0))) == "falling"
    assert fs.river_trend(_days((10.0, 1.0), (10.5, 1.0))) == "steady"
    assert fs.river_trend(_days((10.0, 1.0), (None, 1.0))) is None
