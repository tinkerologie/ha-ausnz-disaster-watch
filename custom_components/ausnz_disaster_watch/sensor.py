"""Sensor platform for Australian Disaster Watch."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UV_INDEX, Platform, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AusNZDisasterWatchConfigEntry
from .broadcaster_sensor import async_setup_broadcaster_sensor
from .const import (
    AU_ONLY_FEED_OPTIONS,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_REGIONAL_ALERTS,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_UV,
    STATE_NZ,
)
from .coordinator import AustralianDisasterWatchCoordinator
from .dam_sensor import async_setup_dam_sensors
from .entity import AustralianDisasterWatchEntity
from .entity_lifecycle import tracks_entities
from .forecast_entity import forecast_sensors
from .models import WarningLevel, to_dict, to_json_dict
from .providers.fire_danger import NZ_SEASONS, local_today
from .providers.heatwave import HEATWAVE_SEVERITIES
from .providers.sources import attribution_for, national_feed_attribution
from .river_sensor import async_setup_river_sensors

# Entities only read coordinator data; the coordinator does all fetching
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Attribute lists are capped to keep state attributes small
MAX_LISTED_ITEMS = 20

# Highest warning level states (#21): one per known level, plus all_clear without hazards.
# WarningLevel.UNKNOWN has none: the sensor is then unknown.
ALL_CLEAR = "all_clear"
WARNING_LEVEL_OPTIONS: dict[WarningLevel, str] = {
    WarningLevel.INFORMATION: "information",
    WarningLevel.ADVICE: "advice",
    WarningLevel.WATCH_AND_ACT: "watch_and_act",
    WarningLevel.EMERGENCY_WARNING: "emergency_warning",
}
WARNING_LEVEL_OPTIONS_WITH_CLEAR = (ALL_CLEAR, *WARNING_LEVEL_OPTIONS.values())

# AFDRS ratings as fire danger rating states (#21), lowest first
FIRE_DANGER_OPTIONS = ("no_rating", "moderate", "high", "extreme", "catastrophic")


def fire_danger_option(rating: str | None) -> str | None:
    """Return the state for an AFDRS display name (``No Rating`` -> ``no_rating``), or None if it is not one."""
    if not rating:
        return None
    option = re.sub(r"[\s-]+", "_", rating.strip().lower())
    if option in FIRE_DANGER_OPTIONS:
        return option
    _LOGGER.debug("Fire danger rating %r is not an AFDRS rating", rating)
    return None


def national_feed_enabled(coordinator: AustralianDisasterWatchCoordinator, option: str) -> bool:
    """Return True if an opt-in national feed is enabled (AU-only feeds never for New Zealand)."""
    if option in AU_ONLY_FEED_OPTIONS and coordinator.state_code == STATE_NZ:
        return False
    return bool(coordinator.combined_config.get(option, False))


@tracks_entities(Platform.SENSOR)
async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch sensors."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NearestHazardDistanceSensor(coordinator),
        ActiveHazardsCountSensor(coordinator),
        HighestWarningLevelSensor(coordinator),
        NearestHazardTitleSensor(coordinator),
        PowerOutagesCountSensor(coordinator),
        PowerOutagesCustomersAffectedSensor(coordinator),
        RoadClosuresCountSensor(coordinator),
        WeatherWarningsCountSensor(coordinator),
        FireDangerRatingSensor(coordinator),
        AirQualityIndexSensor(coordinator),
        PrimaryWeatherObservationSensor(coordinator),
        ReliefFacilitiesCountSensor(coordinator),
        *forecast_sensors(coordinator),
    ]
    if coordinator.state_code == STATE_NZ:
        entities.append(FireSeasonSensor(coordinator))
    # Opt-in national feeds (#37): entities exist only while their feed is enabled
    if national_feed_enabled(coordinator, CONF_ENABLE_SATELLITE_HOTSPOTS):
        entities.append(SatelliteHotspotsSensor(coordinator))
    if national_feed_enabled(coordinator, CONF_ENABLE_HEATWAVE):
        entities.append(HeatwaveSeveritySensor(coordinator))
    if national_feed_enabled(coordinator, CONF_ENABLE_UV):
        entities.append(UVIndexSensor(coordinator))
    if national_feed_enabled(coordinator, CONF_ENABLE_REGIONAL_ALERTS):
        entities.append(RegionalDisasterAlertsSensor(coordinator))
    async_add_entities(entities)
    async_setup_river_sensors(hass, entry, async_add_entities)
    await async_setup_broadcaster_sensor(hass, entry, async_add_entities)
    async_setup_dam_sensors(hass, entry, async_add_entities)


class NearestHazardDistanceSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking distance to the closest active emergency hazard."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_translation_key = "nearest_hazard_distance"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize distance sensor."""
        super().__init__(coordinator, "nearest_hazard_distance")

    @property
    def native_value(self) -> float | None:
        """Return distance in km to closest hazard."""
        nearest = self.coordinator.nearest_hazard
        if nearest and nearest.distance_km is not None:
            return round(nearest.distance_km, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes describing the nearest hazard."""
        nearest = self.coordinator.nearest_hazard
        if not nearest:
            return {}
        return {
            "title": nearest.title,
            "hazard_type": nearest.hazard_type.value,
            "warning_level": nearest.warning_level.value,
            "location_name": nearest.location_name,
            "responsible_agency": nearest.responsible_agency,
            "web_url": nearest.web_url,
        }


class ActiveHazardsCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking total count of active hazards within perimeter."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "hazards"
    _attr_translation_key = "active_hazards_count"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize count sensor."""
        super().__init__(coordinator, "active_hazards_count")

    @property
    def native_value(self) -> int:
        """Return count of active hazards."""
        return len(self.coordinator.active_hazards)


class HighestWarningLevelSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting the highest Australian Warning System level in the perimeter."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(WARNING_LEVEL_OPTIONS_WITH_CLEAR)
    _attr_translation_key = "highest_warning_level"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize highest warning level sensor."""
        super().__init__(coordinator, "highest_warning_level")

    @property
    def native_value(self) -> str | None:
        """Return ``all_clear`` without hazards, else the highest level; None (unknown) when it is unknown."""
        if not self.coordinator.active_hazards:
            return ALL_CLEAR
        return WARNING_LEVEL_OPTIONS.get(self.coordinator.highest_warning_level)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes including active emergency news and nearby councils."""
        news = self.coordinator.emergency_news
        councils = self.coordinator.nearby_councils
        inside = self.coordinator.inside_warning_hazards
        return {
            "inside_warning_area": bool(inside),
            "inside_warning_level": inside[0].warning_level.value if inside else None,
            "emergency_news": [to_json_dict(n) for n in news[:20]],
            "nearby_councils": councils[:10],
        }


class NearestHazardTitleSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor displaying the title/headline of the nearest active hazard."""

    _attr_translation_key = "nearest_hazard_title"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize nearest hazard title sensor."""
        super().__init__(coordinator, "nearest_hazard_title")

    @property
    def native_value(self) -> str:
        """Return headline of nearest hazard or 'None'."""
        nearest = self.coordinator.nearest_hazard
        if nearest:
            return nearest.title[:255]
        return "None"


class PowerOutagesCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking total count of active power outages."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "outages"
    _attr_translation_key = "power_outages_count"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize power outages count sensor."""
        super().__init__(coordinator, "power_outages_count")

    @property
    def native_value(self) -> int:
        """Return count of active power outages."""
        return len(self.coordinator.power_outages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return power outage list attributes."""
        outages = self.coordinator.power_outages
        # Outages are sorted nearest first (#36)
        nearest = outages[0] if outages else None
        return {
            "customers_affected": sum(o.customers_affected for o in outages),
            "outages": [to_dict(o) for o in outages[:25]],
            "est_restore": nearest.restore_time if nearest else None,
            "nearest_outage_distance_km": nearest.distance_km if nearest else None,
            "nearest_outage_distributor": nearest.distributor if nearest else None,
            "data_sources": self.coordinator.power_outage_sources,
        }


class PowerOutagesCustomersAffectedSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking total customers currently without power."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "customers"
    _attr_translation_key = "power_outages_customers_affected"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize customers affected sensor."""
        super().__init__(coordinator, "power_outages_customers_affected")

    @property
    def native_value(self) -> int:
        """Return total affected customers."""
        return sum(o.customers_affected for o in self.coordinator.power_outages)


class RoadClosuresCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking total active road closures and hazards."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "closures"
    _attr_translation_key = "road_closures_count"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize road closures count sensor."""
        super().__init__(coordinator, "road_closures_count")

    @property
    def native_value(self) -> int:
        """Return total active road closures."""
        return len(self.coordinator.road_closures)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return list of active road closures."""
        closures = self.coordinator.road_closures
        return {
            "closures": [to_json_dict(c) for c in closures[:25]],
        }


class WeatherWarningsCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking active Bureau of Meteorology weather warnings."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "warnings"
    _attr_translation_key = "weather_warnings_count"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize weather warnings count sensor."""
        super().__init__(coordinator, "weather_warnings_count")

    @property
    def native_value(self) -> int:
        """Return count of active weather warnings."""
        return len(self.coordinator.weather_warnings)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return list of weather warnings, emergency news, and nearby councils."""
        warnings = self.coordinator.weather_warnings
        news = self.coordinator.emergency_news
        councils = self.coordinator.nearby_councils
        return {
            "warnings": [to_json_dict(w) for w in warnings[:20]],
            "emergency_news": [to_json_dict(n) for n in news[:20]],
            "nearby_councils": councils[:10],
        }


class FireDangerRatingSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting regional Australian Fire Danger Rating System (AFDRS) status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(FIRE_DANGER_OPTIONS)
    _attr_translation_key = "fire_danger_rating"

    @property
    def attribution(self) -> str | None:
        """Credit the fire danger and total fire ban sources for this district (#28, #34)."""
        return attribution_for(self.coordinator.fire_service.data_sources) or super().attribution

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize fire danger rating sensor."""
        super().__init__(coordinator, "fire_danger_rating")

    @property
    def native_value(self) -> str | None:
        """Return the AFDRS rating as an option (``extreme``); None when there is none or it is not AFDRS."""
        fd = self.coordinator.fire_danger
        return fire_danger_option(fd.rating) if fd else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return fire danger rating attributes."""
        fd = self.coordinator.fire_danger
        outlook = self.coordinator.fire_outlook
        if fd:
            attrs: dict[str, Any] = {
                "district_name": fd.district_name,
                "district_number": fd.district_number,
                "total_fire_ban": fd.total_fire_ban,
                "day": fd.day,
            }
        elif outlook is not None:
            # No rating for today: still show the district and the coming days (#89)
            attrs = {
                "district_name": outlook.district_name,
                "district_number": outlook.district_number,
                "total_fire_ban": None,
                "day": None,
            }
        else:
            return {}
        if outlook is not None and outlook.district_number == attrs["district_number"]:
            today = local_today(outlook.time_zone)
            current = outlook.day(today)
            attrs["date"] = today.isoformat()
            attrs["fire_behaviour_index"] = current.fire_behaviour_index if current else None
            attrs["forecast"] = [to_json_dict(day) for day in outlook.days if day.date >= today]
            attrs["issued_at"] = outlook.issued_at.isoformat() if outlook.issued_at else None
            # Today's rating may come from the state agency when BoM's issue starts tomorrow (#89)
            attrs["source"] = (current.source if current else None) or outlook.source
            attrs["total_fire_ban_source"] = outlook.total_fire_ban_source
        return attrs


class FireSeasonSensor(AustralianDisasterWatchEntity, SensorEntity):
    """New Zealand fire season (open, restricted or prohibited) at the configured location (#28)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(NZ_SEASONS)
    _attr_translation_key = "fire_season"

    @property
    def attribution(self) -> str | None:
        """Credit Fire and Emergency New Zealand (#34)."""
        return attribution_for(self.coordinator.fire_service.data_sources) or super().attribution

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize fire season sensor."""
        super().__init__(coordinator, "fire_season")

    @property
    def native_value(self) -> str | None:
        """Return the fire season status."""
        season = self.coordinator.fire_season
        return season.season if season else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the fire zone and any Section 52 prohibition."""
        season = self.coordinator.fire_season
        if season is None:
            return {}
        return {
            "zone": season.zone,
            "district": season.district,
            "last_updated": season.last_updated.isoformat() if season.last_updated else None,
            "section_52": season.section_52,
            "section_52_comment": season.section_52_comment,
            "prohibited_activities": season.prohibited_activities,
        }


class AirQualityIndexSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting regional air quality rating and pollutant telemetry."""

    _attr_translation_key = "air_quality_rating"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize air quality sensor."""
        super().__init__(coordinator, "air_quality_rating")

    @property
    def native_value(self) -> str | None:
        """Return overall rating of closest air quality station."""
        stations = self.coordinator.air_quality_stations
        if stations:
            return stations[0].overall_rating
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return station pollutant readings."""
        stations = self.coordinator.air_quality_stations
        if not stations:
            return {}
        first = stations[0]
        return {
            "station_name": first.station_name,
            "pm2_5": first.pm2_5_measurement,
            "pm10": first.pm10_measurement,
            "no2": first.no2_measurement,
            "o3": first.o3_measurement,
            "distance_km": first.distance_km,
            "observed_at": first.observed_at.isoformat() if first.observed_at else None,
            "source": first.source,
            "stations": [to_json_dict(s) for s in stations[:10]],
        }


class PrimaryWeatherObservationSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting local weather station observation."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "primary_weather_observation"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize weather observation sensor."""
        super().__init__(coordinator, "primary_weather_observation")

    @property
    def native_value(self) -> float | None:
        """Return temperature from primary weather station."""
        stations = self.coordinator.weather_stations
        if stations and stations[0].temperature is not None:
            return round(stations[0].temperature, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return weather observation telemetry attributes."""
        stations = self.coordinator.weather_stations
        if not stations:
            return {}
        first = stations[0]
        return {
            "station_name": first.station_name,
            "apparent_temperature": first.apparent_temperature,
            "relative_humidity": first.relative_humidity,
            "pressure_hpa": first.pressure_hpa,
            "wind_speed_avg_kph": first.wind_speed_avg,
            "wind_speed_max_kph": first.wind_speed_max,
            "wind_direction_deg": first.wind_direction,
            "solar_radiation_wm2": first.solar_radiation,
            "stations": [to_dict(s) for s in stations[:10]],
        }


class ReliefFacilitiesCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting count of open relief facilities (sandbag stations and evac centres)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "facilities"
    _attr_translation_key = "relief_facilities_count"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize relief facilities count sensor."""
        super().__init__(coordinator, "relief_facilities_count")

    @property
    def native_value(self) -> int:
        """Return count of open relief facilities."""
        return len(self.coordinator.relief_facilities)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return facilities list."""
        facilities = self.coordinator.relief_facilities
        return {
            "facilities": [to_dict(f) for f in facilities[:25]],
        }


class SatelliteHotspotsSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Count of satellite hotspots within the radius (informational: hotspots are not warnings)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "hotspots"
    _attr_translation_key = "satellite_hotspots_nearby"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize satellite hotspots sensor."""
        super().__init__(coordinator, "satellite_hotspots_nearby")
        # Credit only the sources behind this feed (#34)
        self._attr_attribution = national_feed_attribution(CONF_ENABLE_SATELLITE_HOTSPOTS)

    @property
    def available(self) -> bool:
        """Return False while the feed is undetermined."""
        return super().available and self.coordinator.satellite_hotspots is not None

    @property
    def native_value(self) -> int | None:
        """Return the number of hotspots within the radius."""
        hotspots = self.coordinator.satellite_hotspots
        return len(hotspots.items) if hotspots is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return nearest distance, confidence and the nearest hotspots."""
        hotspots = self.coordinator.satellite_hotspots
        if hotspots is None:
            return {}
        items = hotspots.items
        confidences = [i.confidence for i in items if i.confidence is not None]
        return {
            "nearest_distance_km": items[0].distance_km if items else None,
            "max_confidence": max(confidences, default=None),
            "min_confidence_filter": hotspots.min_confidence,
            "truncated": hotspots.truncated,
            "hotspots": [to_json_dict(i) for i in items[:MAX_LISTED_ITEMS]],
        }


class HeatwaveSeveritySensor(AustralianDisasterWatchEntity, SensorEntity):
    """Highest current BoM heatwave warning severity in the configured state."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(HEATWAVE_SEVERITIES)
    _attr_translation_key = "heatwave_severity"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize heatwave severity sensor."""
        super().__init__(coordinator, "heatwave_severity")
        # Credit only the sources behind this feed (#34)
        self._attr_attribution = national_feed_attribution(CONF_ENABLE_HEATWAVE)

    @property
    def available(self) -> bool:
        """Return False while the feed is undetermined."""
        return super().available and self.coordinator.heatwave is not None

    @property
    def native_value(self) -> str | None:
        """Return none, low_intensity, severe or extreme."""
        heatwave = self.coordinator.heatwave
        return heatwave.severity if heatwave is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the warning headline, expiry and each district's severity."""
        heatwave = self.coordinator.heatwave
        if heatwave is None:
            return {}
        return {
            "headline": heatwave.headline,
            "issued": heatwave.issued.isoformat() if heatwave.issued else None,
            "expires": heatwave.expires.isoformat() if heatwave.expires else None,
            "areas": [to_dict(area) for area in heatwave.areas],
            "product_id": heatwave.product_id,
        }


class UVIndexSensor(AustralianDisasterWatchEntity, SensorEntity):
    """UV index at the nearest ARPANSA monitoring station."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UV_INDEX
    _attr_translation_key = "uv_index"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize UV index sensor."""
        super().__init__(coordinator, "uv_index")
        # Credit only the sources behind this feed (#34)
        self._attr_attribution = national_feed_attribution(CONF_ENABLE_UV)

    @property
    def available(self) -> bool:
        """Return False while the feed is undetermined."""
        return super().available and self.coordinator.uv is not None

    @property
    def native_value(self) -> float | None:
        """Return the latest UV index."""
        uv = self.coordinator.uv
        return uv.index if uv is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the station, observation time and BoM sun protection forecast."""
        uv = self.coordinator.uv
        if uv is None:
            return {}
        return {
            "station_name": uv.station_name,
            "distance_km": uv.distance_km,
            "observed_at": uv.observed_at.isoformat() if uv.observed_at else None,
            "forecast": uv.forecast,
            "forecast_max_index": uv.forecast_max_index,
        }


class RegionalDisasterAlertsSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Count of current GDACS Orange/Red alerts in the region (context, not local warnings)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "alerts"
    _attr_translation_key = "regional_disaster_alerts"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize regional alerts sensor."""
        super().__init__(coordinator, "regional_disaster_alerts")
        # Credit only the sources behind this feed (#34)
        self._attr_attribution = national_feed_attribution(CONF_ENABLE_REGIONAL_ALERTS)

    @property
    def available(self) -> bool:
        """Return False while the feed is undetermined."""
        return super().available and self.coordinator.regional_alerts is not None

    @property
    def native_value(self) -> int | None:
        """Return the number of regional alerts."""
        alerts = self.coordinator.regional_alerts
        return len(alerts) if alerts is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the alerts, nearest first."""
        alerts = self.coordinator.regional_alerts
        if alerts is None:
            return {}
        return {"alerts": [to_json_dict(a) for a in alerts[:MAX_LISTED_ITEMS]]}
