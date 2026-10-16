"""Air quality from state environment agencies (NSW, Queensland, ACT), with station coordinates.

All three feeds need no key and are CC BY 4.0. Each station carries its coordinates, so the
coordinator can order stations by distance. A reading the agency marks as unavailable is
``None`` and never counts as "Good"; a station's overall rating is its worst current
pollutant category, or ``None`` when it has no current reading.

- NSW: Department of Climate Change, Energy, the Environment and Water air quality API.
  ``get_SiteDetails`` (GET) lists sites; ``get_Observations`` (POST) returns hourly averages.
  ``Hour`` is the hour ending, in Sydney local time.
- Queensland: Department of the Environment hourly XML feed; ``-1111`` style values mean
  "not available" even when a rating is attached.
- ACT: ACT Government Socrata dataset ``94a5-zqnn``; ``datetime`` is a floating local time,
  read explicitly as Australia/Sydney. Categories follow the ACT AQI bands.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.models import AirQualityStationData

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError
from .cap import haversine_km

NSW_SITES_URL = "https://data.airquality.nsw.gov.au/api/Data/get_SiteDetails"
NSW_OBSERVATIONS_URL = "https://data.airquality.nsw.gov.au/api/Data/get_Observations"
QLD_AIR_QUALITY_URL = "https://apps.des.qld.gov.au/air-quality/xml/feed.php?category=1&region=ALL"
ACT_AIR_QUALITY_URL = "https://www.data.act.gov.au/resource/94a5-zqnn.json?$order=datetime%20DESC&$limit=50"
NSW_SOURCE = "NSW Department of Climate Change, Energy, the Environment and Water"
QLD_SOURCE = "Queensland Department of the Environment"
ACT_SOURCE = "ACT Government"

# Nearest NSW sites to request observations for (the API answers per site and hour)
NSW_NEAREST_SITES = 3
NSW_PARAMETERS = ("PM2.5", "PM10", "NO2", "O3")

# Worst last; used to pick a station's overall category
_CATEGORY_ORDER = ("very good", "good", "fair", "poor", "very poor", "extremely poor", "hazardous")
# ACT AQI bands (upper bound inclusive, category)
_ACT_AQI_BANDS = ((33, "Very Good"), (66, "Good"), (99, "Fair"), (149, "Poor"), (199, "Very Poor"))


def _rank(category: str) -> int:
    return _CATEGORY_ORDER.index(category.lower()) if category.lower() in _CATEGORY_ORDER else -1


def worst_category(categories: list[str | None]) -> str | None:
    """Return the worst known category, or None if none is known."""
    known = [c for c in categories if c and _rank(c) >= 0]
    return max(known, key=_rank) if known else None


def _title(category: Any) -> str | None:
    return " ".join(str(category).split()).title() if category else None


def _measure(value: float | None, units: str) -> str | None:
    return f"{round(value, 3):g} {units}" if value is not None else None


def nearest_nsw_sites(sites: Any, lat: float, lon: float) -> list[dict[str, Any]]:
    """Return the NSW sites nearest to a point (sites without coordinates are skipped)."""
    if not isinstance(sites, list):
        raise ProviderUnavailableError("NSW air quality site list is not a list")
    located: list[tuple[float, dict[str, Any]]] = []
    for site in sites:
        try:
            located.append((haversine_km(lat, lon, float(site["Latitude"]), float(site["Longitude"])), site))
        except MALFORMED_ITEM_ERRORS:
            continue
    located.sort(key=lambda pair: pair[0])
    return [site for _, site in located[:NSW_NEAREST_SITES]]


def nsw_observation_request(sites: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Return the ``get_Observations`` body from yesterday to tomorrow (time zones may differ) at the sites."""
    return {
        "Parameters": list(NSW_PARAMETERS),
        "Sites": [site["Site_Id"] for site in sites],
        "StartDate": (today - timedelta(days=1)).isoformat(),
        "EndDate": (today + timedelta(days=2)).isoformat(),
        "Categories": ["Averages"],
        "SubCategories": ["Hourly"],
        "Frequency": ["Hourly average"],
    }


def _nsw_time(record: dict[str, Any]) -> datetime | None:
    """Return the end of the record's hour (``Hour`` 1 is 00:00-01:00) in UTC."""
    start = BaseHazardProvider.parse_datetime(f"{record['Date']} 00:00:00", "Australia/Sydney")
    return start + timedelta(hours=int(record["Hour"])) if start else None


def parse_nsw(sites: list[dict[str, Any]], observations: Any) -> list[AirQualityStationData]:
    """Return one station per site with its latest reading of each pollutant."""
    if not isinstance(observations, list):
        raise ProviderUnavailableError("NSW air quality observations are not a list")
    latest: dict[tuple[Any, str], tuple[datetime, dict[str, Any]]] = {}
    for record in observations:
        try:
            if record.get("Value") is None:
                continue
            when = _nsw_time(record)
            key = (record["Site_Id"], record["Parameter"]["ParameterCode"])
            if when is not None and (key not in latest or when > latest[key][0]):
                latest[key] = (when, record)
        except MALFORMED_ITEM_ERRORS:
            continue

    stations: list[AirQualityStationData] = []
    for site in sites:
        readings: dict[str, tuple[str | None, str | None]] = {}
        times: list[datetime] = []
        for code in NSW_PARAMETERS:
            if (entry := latest.get((site["Site_Id"], code))) is None:
                continue
            when, record = entry
            times.append(when)
            readings[code] = (
                _measure(float(record["Value"]), str(record["Parameter"].get("Units") or "")),
                _title(record.get("AirQualityCategory")),
            )
        stations.append(
            AirQualityStationData(
                station_id=f"nsw_{site['Site_Id']}",
                station_name=str(site.get("SiteName") or site["Site_Id"]).title(),
                pm2_5_measurement=readings.get("PM2.5", (None, None))[0],
                pm2_5_rating=readings.get("PM2.5", (None, None))[1],
                pm10_measurement=readings.get("PM10", (None, None))[0],
                pm10_rating=readings.get("PM10", (None, None))[1],
                no2_measurement=readings.get("NO2", (None, None))[0],
                no2_rating=readings.get("NO2", (None, None))[1],
                o3_measurement=readings.get("O3", (None, None))[0],
                o3_rating=readings.get("O3", (None, None))[1],
                overall_rating=worst_category([rating for _, rating in readings.values()]),
                latitude=float(site["Latitude"]),
                longitude=float(site["Longitude"]),
                observed_at=max(times) if times else None,
                source=NSW_SOURCE,
            )
        )
    return stations


_QLD_FIELDS = {
    "particle pm2.5": "pm2_5",
    "particle pm10": "pm10",
    "nitrogen dioxide": "no2",
    "ozone": "o3",
}


def parse_qld(xml_text: str) -> list[AirQualityStationData]:
    """Return Queensland stations from the hourly XML feed."""
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, ValueError) as err:
        raise ProviderUnavailableError(f"Queensland air quality feed returned invalid XML: {err}") from err
    if root.tag != "airdata":
        raise ProviderUnavailableError(f"Queensland air quality feed returned an unexpected document <{root.tag}>")
    stations: list[AirQualityStationData] = []
    for station in root.iter("station"):
        try:
            fields: dict[str, str | None] = {}
            ratings: list[str | None] = []
            for measurement in station.findall("measurement"):
                value = float(measurement.text or "-1")
                if value < 0:
                    continue  # "not available": the attached rating is meaningless
                rating = _title(measurement.get("rating_name"))
                ratings.append(rating)
                if (field := _QLD_FIELDS.get((measurement.get("name") or "").strip().lower())) is not None:
                    unit = "ppm" if field in ("no2", "o3") else "µg/m³"
                    fields[f"{field}_measurement"] = _measure(value, unit)
                    fields[f"{field}_rating"] = rating
            name = (station.get("name") or "").strip()
            hour = station.get("measurementhour")
            observed = BaseHazardProvider.parse_datetime(
                f"{station.get('measurementdate')} {int(hour or 0):02d}:00:00", "Australia/Brisbane"
            )
            stations.append(
                AirQualityStationData(
                    station_id=f"qld_{name.lower().replace(' ', '_')}",
                    station_name=name,
                    overall_rating=worst_category(ratings),
                    latitude=float(station.get("latitude") or ""),
                    longitude=float(station.get("longitude") or ""),
                    observed_at=observed,
                    source=QLD_SOURCE,
                    **fields,  # type: ignore[arg-type]
                )
            )
        except MALFORMED_ITEM_ERRORS:
            continue
    return stations


def act_category(aqi: Any) -> str | None:
    """Return the ACT AQI category for an index value."""
    try:
        value = float(aqi)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return next((name for limit, name in _ACT_AQI_BANDS if value <= limit), "Hazardous")


def _act_value(record: dict[str, Any], field: str) -> float | None:
    try:
        value = float(record[field])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


# ACT pollutant: (reading field, AQI field, units)
_ACT_POLLUTANTS = {
    "pm2_5": ("pm2_5_1_hr", "aqi_pm2_5", "µg/m³"),
    "pm10": ("pm10_1_hr", "aqi_pm10", "µg/m³"),
    "no2": ("no2", "aqi_no2", "ppm"),
    "o3": ("o3_1hr", "aqi_o3_1hr", "ppm"),
}


def parse_act(records: Any) -> list[AirQualityStationData]:
    """Return the latest record of each ACT station (records arrive newest first)."""
    if not isinstance(records, list):
        raise ProviderUnavailableError("ACT air quality dataset is not a list")
    stations: dict[str, AirQualityStationData] = {}
    for record in records:
        try:
            name = str(record["name"]).strip()
            if name in stations:
                continue
            gps = record.get("gps") or {}
            fields: dict[str, str | None] = {}
            for key, (value_field, aqi_field, units) in _ACT_POLLUTANTS.items():
                value = _act_value(record, value_field)
                fields[f"{key}_measurement"] = _measure(value, units)
                # A category without a reading is not reported (it must never read as "Good")
                fields[f"{key}_rating"] = act_category(record.get(aqi_field)) if value is not None else None
            ratings = [rating for key, rating in fields.items() if key.endswith("_rating")]
            stations[name] = AirQualityStationData(
                station_id=f"act_{name.lower().replace(' ', '_')}",
                station_name=name,
                overall_rating=act_category(record.get("aqi_site")) or worst_category(ratings),
                **fields,  # type: ignore[arg-type]
                latitude=float(gps["latitude"]),
                longitude=float(gps["longitude"]),
                observed_at=BaseHazardProvider.parse_datetime(record.get("datetime"), "Australia/Sydney"),
                source=ACT_SOURCE,
            )
        except MALFORMED_ITEM_ERRORS:
            continue
    return list(stations.values())
