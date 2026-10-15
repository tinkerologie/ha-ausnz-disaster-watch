"""Core data models and contracts for Australian Disaster Watch using Pydantic v2."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WarningLevel(StrEnum):
    """Australian Warning System (AWS) warning levels."""

    EMERGENCY_WARNING = "Emergency Warning"  # AWS Level 3 / Red
    WATCH_AND_ACT = "Watch and Act"  # AWS Level 2 / Orange
    ADVICE = "Advice"  # AWS Level 1 / Yellow
    INFORMATION = "Information"  # General incident / Blue
    UNKNOWN = "Unknown"

    @property
    def severity_rank(self) -> int:
        """Return numeric severity rank for comparison (higher is more critical)."""
        ranks = {
            WarningLevel.EMERGENCY_WARNING: 4,
            WarningLevel.WATCH_AND_ACT: 3,
            WarningLevel.ADVICE: 2,
            WarningLevel.INFORMATION: 1,
            WarningLevel.UNKNOWN: 0,
        }
        return ranks.get(self, 0)

    @classmethod
    def from_str(cls, value: str | None) -> WarningLevel:
        """Parse string representation to WarningLevel."""
        if not value:
            return cls.UNKNOWN
        val = value.strip().lower()
        if "emergency" in val:
            return cls.EMERGENCY_WARNING
        if "watch and act" in val or "watch & act" in val:
            return cls.WATCH_AND_ACT
        if "advice" in val:
            return cls.ADVICE
        if "info" in val or "routine" in val or "notification" in val:
            return cls.INFORMATION
        return cls.UNKNOWN


class HazardType(StrEnum):
    """Hazard classifications."""

    BUSHFIRE = "Bushfire"
    GRASS_FIRE = "Grass Fire"
    METROPOLITAN_FIRE = "Structure Fire"
    FLOOD = "Flood"
    SEVERE_STORM = "Severe Storm"
    CYCLONE = "Tropical Cyclone"
    EARTHQUAKE = "Earthquake"
    VOLCANO = "Volcano"
    TSUNAMI = "Tsunami"
    HAZMAT = "Hazmat Incident"
    ROAD_INCIDENT = "Road Hazard / Crash"
    OTHER = "Other"

    @classmethod
    def from_str(cls, value: str | None) -> HazardType:
        """Parse string representation to HazardType."""
        if not value:
            return cls.OTHER
        val = value.strip().lower()
        if "bush" in val or "forest" in val or "scrub" in val:
            return cls.BUSHFIRE
        if "grass" in val:
            return cls.GRASS_FIRE
        if "structure" in val or "building" in val or "house" in val:
            return cls.METROPOLITAN_FIRE
        if "flood" in val or "water level" in val or "inundat" in val:
            return cls.FLOOD
        if "cyclone" in val:
            return cls.CYCLONE
        if "storm" in val or "thunder" in val or "rain" in val or "hail" in val or "wind" in val:
            return cls.SEVERE_STORM
        if "volcan" in val or re.search(r"\bash(fall| fall| cloud| plume)?\b", val):
            return cls.VOLCANO
        if "tsunami" in val:
            return cls.TSUNAMI
        if "earthquake" in val or "tremor" in val:
            return cls.EARTHQUAKE
        if "hazmat" in val or "chemical" in val or "gas" in val:
            return cls.HAZMAT
        if "road" in val or "crash" in val or "traffic" in val or "closure" in val:
            return cls.ROAD_INCIDENT
        if "fire" in val:
            return cls.BUSHFIRE
        return cls.OTHER


class CanonicalHazard(BaseModel):
    """Canonical representation of an emergency hazard incident or warning."""

    model_config = ConfigDict(
        frozen=False,
        arbitrary_types_allowed=True,
        populate_by_name=True,
        extra="ignore",
    )

    id: str = Field(description="Globally unique hazard identifier")
    source: str = Field(description="Source agency or feed identifier")
    title: str = Field(description="Descriptive headline")
    hazard_type: HazardType = Field(description="Normalized hazard classification")
    warning_level: WarningLevel = Field(description="Normalized Australian Warning System level")
    latitude: float = Field(ge=-90.0, le=90.0, description="Centroid latitude in degrees")
    longitude: float = Field(ge=-180.0, le=180.0, description="Centroid longitude in degrees")
    updated_at: datetime | None = Field(
        default=None, description="Timezone-aware UTC timestamp of last update; None when the feed gives no usable time"
    )
    location_name: str = Field(default="", description="Locality, suburb, or region name")
    distance_km: float | None = Field(
        default=None, ge=0.0, description="Haversine distance from center coordinates in km"
    )
    is_hazard_reduction: bool = Field(default=False, description="Flag indicating planned/controlled burn")
    status: str | None = Field(default=None, description="Operational status (e.g. Going, Safe)")
    responsible_agency: str | None = Field(default=None, description="Responsible operational authority")
    web_url: str | None = Field(default=None, description="Direct URL to official emergency alert document")
    raw_properties: dict[str, Any] = Field(
        default_factory=dict, description="Raw upstream properties preserved for inspection"
    )

    @field_validator("updated_at", mode="before")
    @classmethod
    def ensure_utc_datetime(cls, v: Any) -> datetime | None:
        """Normalise updated_at to an aware UTC datetime; unknown times stay None (#13)."""
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v)
            except ValueError:
                return None
        if isinstance(v, datetime):
            return (v if v.tzinfo else v.replace(tzinfo=UTC)).astimezone(UTC)
        return None

    @property
    def is_active_threat(self) -> bool:
        """Return True if hazard is an emergency warning or watch and act."""
        return self.warning_level in (
            WarningLevel.EMERGENCY_WARNING,
            WarningLevel.WATCH_AND_ACT,
        )

    def to_safe_attributes(self) -> dict[str, Any]:
        """Return lean scalar metadata dictionary for Home Assistant state attributes.

        Guarantees that large GeoJSON geometries or heavy nesting are omitted to strictly
        abide by Home Assistant's 16 KB SQLite attribute limit.
        """
        attrs: dict[str, Any] = {
            "source": self.source,
            "title": self.title,
            "hazard_type": self.hazard_type.value,
            "warning_level": self.warning_level.value,
            "location_name": self.location_name,
            "is_hazard_reduction": self.is_hazard_reduction,
            "integration": "ausnz_disaster_watch",
        }
        if self.updated_at is not None:
            attrs["updated_at"] = self.updated_at.isoformat()
        if self.distance_km is not None:
            attrs["distance_km"] = round(self.distance_km, 2)
        if self.status:
            attrs["status"] = self.status
        if self.responsible_agency:
            attrs["responsible_agency"] = self.responsible_agency
        if self.web_url:
            attrs["web_url"] = self.web_url

        # Selectively copy small safe primitive properties from raw_properties
        for k, v in self.raw_properties.items():
            if k in attrs:
                continue
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 120:
                attrs[f"prop_{k}"] = v

        return attrs


class DisasterWatchConfigModel(BaseModel):
    """Pydantic model validating configuration entry parameters."""

    model_config = ConfigDict(extra="ignore")

    state: str = Field(default="QLD", pattern=r"^[A-Z]{2,3}$")
    radius: int = Field(default=50, ge=5, le=300)
    override_emergency: bool = Field(default=True)
    exclude_hazard_reduction: bool = Field(default=True)
    location_mode: str = Field(default="home")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_name: str | None = Field(default=None)
    council_dashboard_url: str | None = Field(default=None)


class PowerOutageItem(BaseModel):
    """Real-time power outage item from energy network feeds (e.g. Energex, Ergon, Ausgrid)."""

    model_config = ConfigDict(extra="ignore")

    suburb: str = Field(default="", description="Locality or suburb name")
    cause: str = Field(default="Under Investigation", description="Reported cause of outage")
    restore_time: str | None = Field(default=None, description="Estimated time of restoration")
    customers_affected: int = Field(default=0, ge=0, description="Number of customers affected")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


class RoadClosureItem(BaseModel):
    """Road hazard, closure, or flooded crossing from Council or TMR/LiveTraffic."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique road condition identifier")
    road: str = Field(default="", description="Road or highway name")
    suburb: str = Field(default="", description="Suburb or locality")
    status: str = Field(default="Closed", description="Operational road status (Closed, Hazard, Flooded)")
    reason: str | None = Field(default=None, description="Cause (e.g. Flooded, Debris, Crash)")
    description: str | None = Field(default=None, description="Detailed condition information")
    advice: str | None = Field(default=None, description="Driver advice (e.g. Proceed with caution)")
    source: str = Field(default="Council / TMR", description="Reporting agency")
    updated_at: datetime | None = Field(default=None, description="Timestamp of status update")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    distance_km: float | None = Field(default=None, ge=0.0)


class WeatherWarningItem(BaseModel):
    """Bureau of Meteorology weather warning summary from dashboard feed."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Headline summary of warning")
    link: str | None = Field(default=None, description="Direct URL to BoM warning product")
    locations: str | None = Field(default=None, description="Affected forecast districts and regions")
    pub_date: datetime | None = Field(default=None, description="Publication timestamp")


class EmergencyNewsItem(BaseModel):
    """Emergency bulletin or media release from Local Disaster Management Group."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Bulletin identifier")
    title: str = Field(description="Headline / news title")
    description: str | None = Field(default=None, description="Detailed bulletin content")
    link: str | None = Field(default=None, description="URL to full media release")
    pub_date: datetime | None = Field(default=None, description="Publication timestamp")


class FireDangerRating(BaseModel):
    """Australian Fire Danger Rating System (AFDRS) regional rating."""

    model_config = ConfigDict(extra="ignore")

    district_number: str = Field(default="", description="Bureau / Agency district code")
    district_name: str = Field(default="", description="Human-readable district name")
    rating: str = Field(default="Moderate", description="AFDRS level (Moderate, High, Extreme, Catastrophic)")
    total_fire_ban: bool = Field(default=False, description="Flag indicating Total Fire Ban (TOBAN)")
    day: str | None = Field(default=None, description="Forecast day")


class WeatherStationObservation(BaseModel):
    """Local environmental weather station telemetry."""

    model_config = ConfigDict(extra="ignore")

    station_id: str = Field(description="Unique station identifier")
    station_name: str = Field(description="Station name")
    temperature: float | None = Field(default=None, description="Current dry bulb temperature in Celsius")
    apparent_temperature: float | None = Field(default=None, description="Feels like temperature in Celsius")
    relative_humidity: float | None = Field(default=None, ge=0.0, le=100.0, description="Relative humidity in %")
    pressure_hpa: float | None = Field(default=None, description="Barometric air pressure in hPa")
    wind_direction: float | None = Field(default=None, ge=0.0, le=360.0, description="Wind direction vector degrees")
    wind_speed_avg: float | None = Field(default=None, ge=0.0, description="Average wind speed in km/h")
    wind_speed_max: float | None = Field(default=None, ge=0.0, description="Max wind gust in km/h")
    rain_since_9am: float | None = Field(default=None, ge=0.0, description="Rainfall since 9am in mm")
    solar_radiation: float | None = Field(default=None, description="Solar radiation in W/m2")


class AirQualityStationData(BaseModel):
    """Air quality monitoring station telemetry."""

    model_config = ConfigDict(extra="ignore")

    station_id: str = Field(description="Station identifier")
    station_name: str = Field(description="Station display name")
    pm2_5_measurement: str | None = Field(default=None, description="PM2.5 reading (e.g. '4 µg/m³')")
    pm2_5_rating: str | None = Field(default=None, description="PM2.5 rating (Good, Fair, Poor)")
    pm2_5_running_average: str | None = Field(default=None, description="PM2.5 24hr running average")
    pm10_measurement: str | None = Field(default=None, description="PM10 reading")
    pm10_rating: str | None = Field(default=None, description="PM10 rating")
    pm10_running_average: str | None = Field(default=None, description="PM10 24hr running average")
    no2_measurement: str | None = Field(default=None, description="Nitrogen dioxide reading")
    no2_rating: str | None = Field(default=None, description="Nitrogen dioxide rating")
    o3_measurement: str | None = Field(default=None, description="Ozone reading")
    o3_rating: str | None = Field(default=None, description="Ozone rating")
    overall_rating: str = Field(default="Good", description="Overall station air quality rating")


class ReliefFacilityItem(BaseModel):
    """Disaster relief infrastructure (Sandbag station, Evacuation centre, Place of refuge)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Facility unique ID")
    facility_type: str = Field(description="'sandbag_station', 'evacuation_centre', or 'place_of_refuge'")
    name: str = Field(description="Facility name")
    suburb: str = Field(default="", description="Suburb or locality")
    address: str = Field(default="", description="Full street address")
    status: str = Field(default="Open", description="Operational status (Open, Closed)")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    distance_km: float | None = Field(default=None, ge=0.0)


class DisasterCameraItem(BaseModel):
    """Flood or traffic camera feed."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Camera unique identifier")
    name: str = Field(description="Camera description or road crossing name")
    image_url: str = Field(description="Direct URL to live snapshot JPEG/PNG")
    suburb: str | None = Field(default=None, description="Locality or suburb")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


class DisasterCoordinatorData(BaseModel):
    """Composite data structure returned by AustralianDisasterWatchCoordinator."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    hazards: dict[str, CanonicalHazard] = Field(default_factory=dict)
    power_outages: list[PowerOutageItem] = Field(default_factory=list)
    road_closures: list[RoadClosureItem] = Field(default_factory=list)
    weather_warnings: list[WeatherWarningItem] = Field(default_factory=list)
    emergency_news: list[EmergencyNewsItem] = Field(default_factory=list)
    fire_danger: FireDangerRating | None = Field(default=None)
    weather_stations: list[WeatherStationObservation] = Field(default_factory=list)
    air_quality_stations: list[AirQualityStationData] = Field(default_factory=list)
    relief_facilities: list[ReliefFacilityItem] = Field(default_factory=list)
    cameras: list[DisasterCameraItem] = Field(default_factory=list)
    nearby_councils: list[dict[str, str]] = Field(default_factory=list)
    feeds_ok: list[str] = Field(default_factory=list, description="Hazard providers that fetched successfully")
    feeds_failed: list[str] = Field(default_factory=list, description="Hazard providers that failed this update")

    def __len__(self) -> int:
        """Return count of active hazards."""
        return len(self.hazards)

    def __bool__(self) -> bool:
        """Always evaluate to True when coordinator data is instantiated."""
        return True

    def __getitem__(self, key: str) -> CanonicalHazard:
        """Access hazard by unique ID."""
        return self.hazards[key]

    def __contains__(self, key: object) -> bool:
        """Check if hazard unique ID exists."""
        return key in self.hazards

    def get(self, key: str, default: Any = None) -> Any:
        """Get hazard by unique ID or fallback."""
        return self.hazards.get(key, default)
