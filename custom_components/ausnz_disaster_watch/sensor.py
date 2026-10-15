"""Sensor platform for Australian Disaster Watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AusNZDisasterWatchConfigEntry
from .coordinator import AustralianDisasterWatchCoordinator
from .entity import AustralianDisasterWatchEntity
from .forecast_entity import forecast_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AusNZDisasterWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Australian Disaster Watch sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
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
    )


class NearestHazardDistanceSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking distance to the closest active emergency hazard."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_translation_key = "nearest_hazard_distance"
    _attr_icon = "mdi:map-marker-distance"

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
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize count sensor."""
        super().__init__(coordinator, "active_hazards_count")

    @property
    def native_value(self) -> int:
        """Return count of active hazards."""
        return len(self.coordinator.active_hazards)


class HighestWarningLevelSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting the highest Australian Warning System level in the perimeter."""

    _attr_translation_key = "highest_warning_level"
    _attr_icon = "mdi:alert-decagram"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize highest warning level sensor."""
        super().__init__(coordinator, "highest_warning_level")

    @property
    def native_value(self) -> str:
        """Return highest warning level string."""
        if not self.coordinator.active_hazards:
            return "All Clear"
        return self.coordinator.highest_warning_level.value

    @property
    def icon(self) -> str:
        """Return dynamic icon based on highest warning level."""
        lvl = self.coordinator.highest_warning_level
        if lvl.value == "Emergency Warning":
            return "mdi:alert-octagon"
        if lvl.value == "Watch and Act":
            return "mdi:alert"
        if lvl.value == "Advice":
            return "mdi:information"
        return "mdi:shield-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes including active emergency news and nearby councils."""
        news = self.coordinator.emergency_news
        councils = self.coordinator.nearby_councils
        return {
            "emergency_news": [n.model_dump(mode="json") for n in news[:20]],
            "nearby_councils": councils[:10],
        }


class NearestHazardTitleSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor displaying the title/headline of the nearest active hazard."""

    _attr_translation_key = "nearest_hazard_title"
    _attr_icon = "mdi:text-box-search"

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
    _attr_icon = "mdi:transmission-tower-off"

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
        return {
            "customers_affected": sum(o.customers_affected for o in outages),
            "outages": [o.model_dump() for o in outages[:25]],
        }


class PowerOutagesCustomersAffectedSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking total customers currently without power."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "customers"
    _attr_translation_key = "power_outages_customers_affected"
    _attr_icon = "mdi:account-alert"

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
    _attr_icon = "mdi:traffic-cone"

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
            "closures": [c.model_dump(mode="json") for c in closures[:25]],
        }


class WeatherWarningsCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor tracking active Bureau of Meteorology weather warnings."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "warnings"
    _attr_translation_key = "weather_warnings_count"
    _attr_icon = "mdi:weather-lightning-rainy"

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
            "warnings": [w.model_dump(mode="json") for w in warnings[:20]],
            "emergency_news": [n.model_dump(mode="json") for n in news[:20]],
            "nearby_councils": councils[:10],
        }


class FireDangerRatingSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting regional Australian Fire Danger Rating System (AFDRS) status."""

    _attr_translation_key = "fire_danger_rating"

    def __init__(self, coordinator: AustralianDisasterWatchCoordinator) -> None:
        """Initialize fire danger rating sensor."""
        super().__init__(coordinator, "fire_danger_rating")

    @property
    def native_value(self) -> str | None:
        """Return current AFDRS rating string."""
        fd = self.coordinator.fire_danger
        return fd.rating if fd else None

    @property
    def icon(self) -> str:
        """Return dynamic icon based on fire danger level."""
        val = str(self.native_value or "").lower()
        if "catastrophic" in val or "extreme" in val:
            return "mdi:fire-alert"
        if "high" in val or "moderate" in val:
            return "mdi:fire"
        return "mdi:shield-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return fire danger rating attributes."""
        fd = self.coordinator.fire_danger
        if not fd:
            return {}
        return {
            "district_name": fd.district_name,
            "district_number": fd.district_number,
            "total_fire_ban": fd.total_fire_ban,
            "day": fd.day,
        }


class AirQualityIndexSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting regional air quality rating and pollutant telemetry."""

    _attr_translation_key = "air_quality_rating"
    _attr_icon = "mdi:air-filter"

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
            "stations": [s.model_dump() for s in stations[:10]],
        }


class PrimaryWeatherObservationSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting local weather station observation."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "primary_weather_observation"
    _attr_icon = "mdi:thermometer"

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
            "stations": [s.model_dump() for s in stations[:10]],
        }


class ReliefFacilitiesCountSensor(AustralianDisasterWatchEntity, SensorEntity):
    """Sensor reporting count of open relief facilities (sandbag stations and evac centres)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "facilities"
    _attr_translation_key = "relief_facilities_count"
    _attr_icon = "mdi:home-heart"

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
            "facilities": [f.model_dump() for f in facilities[:25]],
        }
