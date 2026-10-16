"""UV index: ARPANSA real-time observations plus the BoM sun protection forecast.

ARPANSA conditions of use: acknowledge the source ("UV observations courtesy of ARPANSA")
and notify ARPANSA that an application uses the data. The station table holds city
coordinates for each ARPANSA location (Antarctic stations are left out); they only pick the
nearest of a dozen stations, so city-level precision is enough.

The BoM forecast products ``IDZ00107``-``IDZ00113`` list one ``uv_alert`` text per forecast
location; the product per station was verified against the live FTP files (2026-10-16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.models import UVObservation

from .base import BaseHazardProvider, ProviderUnavailableError
from .cap import haversine_km

ARPANSA_UV_URL = "https://uvdata.arpansa.gov.au/xml/uvvalues.xml"


@dataclass(frozen=True, slots=True)
class UVStation:
    """An ARPANSA monitoring location and the BoM forecast product that covers it."""

    latitude: float
    longitude: float
    forecast_product: str


UV_STATIONS: dict[str, UVStation] = {
    "Adelaide": UVStation(-34.93, 138.60, "IDZ00110"),
    "Alice Springs": UVStation(-23.70, 133.88, "IDZ00108"),
    "Brisbane": UVStation(-27.47, 153.03, "IDZ00109"),
    "Canberra": UVStation(-35.28, 149.13, "IDZ00107"),
    "Darwin": UVStation(-12.46, 130.84, "IDZ00108"),
    "Emerald": UVStation(-23.53, 148.16, "IDZ00109"),
    "Gold Coast": UVStation(-28.02, 153.40, "IDZ00109"),
    "Kingston": UVStation(-42.98, 147.31, "IDZ00111"),
    "Melbourne": UVStation(-37.81, 144.96, "IDZ00112"),
    "Newcastle": UVStation(-32.93, 151.78, "IDZ00107"),
    "Perth": UVStation(-31.95, 115.86, "IDZ00113"),
    "Sydney": UVStation(-33.87, 151.21, "IDZ00107"),
    "Townsville": UVStation(-19.26, 146.82, "IDZ00109"),
}

_MAX_INDEX_RE = re.compile(r"UV Index predicted to reach (\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UVReading:
    """One station's reading from the ARPANSA feed."""

    station: str
    index: float
    observed_at: datetime | None


def _observed_at(value: str) -> datetime | None:
    """Parse ARPANSA ``utcdatetime`` (``2026/10/15 22:21``, UTC)."""
    try:
        return datetime.strptime(value.strip(), "%Y/%m/%d %H:%M").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_arpansa(xml_text: str) -> list[UVReading]:
    """Return the readings of stations whose status is ``ok``."""
    try:
        root = ET.fromstring(xml_text.lstrip("﻿"))
    except (ET.ParseError, ValueError) as err:
        raise ProviderUnavailableError(f"ARPANSA UV feed returned invalid XML: {err}") from err
    if root.tag != "stations":
        raise ProviderUnavailableError(f"ARPANSA UV feed returned an unexpected document <{root.tag}>")
    readings: list[UVReading] = []
    for location in root.findall("location"):
        if (location.findtext("status") or "").strip().lower() != "ok":
            continue
        try:
            index = float(location.findtext("index") or "")
        except ValueError:
            continue
        if index < 0:
            continue
        readings.append(UVReading(location.get("id", ""), index, _observed_at(location.findtext("utcdatetime") or "")))
    return readings


def nearest_reading(readings: list[UVReading], lat: float, lon: float) -> tuple[UVReading, float] | None:
    """Return the reading of the nearest known station and its distance in km."""
    candidates = [
        (reading, haversine_km(lat, lon, station.latitude, station.longitude))
        for reading in readings
        if (station := UV_STATIONS.get(reading.station)) is not None
    ]
    return min(candidates, key=lambda c: c[1]) if candidates else None


def parse_uv_forecast(content: bytes, station: str, now: datetime) -> tuple[str, int | None] | None:
    """Return today's ``uv_alert`` text and forecast maximum index for a station, if listed."""
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError) as err:
        raise ProviderUnavailableError(f"BoM UV forecast is invalid XML: {err}") from err
    for area in root.iter("area"):
        if area.get("description") != station or area.get("type") != "location":
            continue
        for period in area.findall("forecast-period"):
            start = BaseHazardProvider.parse_datetime(period.get("start-time-utc"))
            end = BaseHazardProvider.parse_datetime(period.get("end-time-utc"))
            if start is None or end is None or not start <= now < end:
                continue
            text = " ".join((period.findtext("text[@type='uv_alert']") or "").split())
            if not text:
                return None
            match = _MAX_INDEX_RE.search(text)
            return text, int(match.group(1)) if match else None
    return None


def uv_observation(reading: UVReading, distance_km: float, forecast: tuple[str, int | None] | None) -> UVObservation:
    """Build the UV observation for the nearest station."""
    return UVObservation(
        station_id=reading.station.lower().replace(" ", "_"),
        station_name=reading.station,
        index=reading.index,
        observed_at=reading.observed_at,
        distance_km=round(distance_km, 1),
        forecast=forecast[0] if forecast else None,
        forecast_max_index=forecast[1] if forecast else None,
    )
