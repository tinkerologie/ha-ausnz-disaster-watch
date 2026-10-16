"""Core data models and contracts for Australian Disaster Watch using Pydantic v2."""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Longest call to action written to state attributes
CALL_TO_ACTION_MAX_LENGTH = 255
# Upstream editor fields (ArcGIS ``created_user``/``last_edited_user`` hold email addresses)
_PERSONAL_KEYS = frozenset({"created_user", "last_edited_user", "creator", "editor"})


def _is_personal_key(key: str) -> bool:
    """Return True for raw property keys that may identify a person (never copied to attributes)."""
    lowered = key.lower()
    return lowered in _PERSONAL_KEYS or "email" in lowered


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
        if any(word in val for word in ("storm", "thunder", "rain", "hail", "wind", "severe weather")):
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
    attribution: str | None = Field(
        default=None, description="Data source attribution; the coordinator fills it from the provider (#34)"
    )
    area: tuple[tuple[tuple[float, float], ...], ...] | None = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Simplified warning or incident area: outer rings of (lat, lon) points (#30). "
            "Never written to state attributes or diagnostics."
        ),
    )
    inside_area: bool | None = Field(
        default=None, description="True if the monitored point is inside ``area``; None without an area"
    )
    expires: datetime | None = Field(default=None, description="Timezone-aware UTC time the warning expires")
    call_to_action: str | None = Field(default=None, description="Australian Warning System call to action")

    @field_validator("updated_at", "expires", mode="before")
    @classmethod
    def ensure_utc_datetime(cls, v: Any) -> datetime | None:
        """Normalise a timestamp to an aware UTC datetime; unknown times stay None (#13)."""
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

    @property
    def is_inside_warning(self) -> bool:
        """Return True if the monitored point is inside the area of an Advice or higher warning (#30)."""
        return self.inside_area is True and self.warning_level.severity_rank >= WarningLevel.ADVICE.severity_rank

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
        if self.inside_area is not None:
            attrs["inside_area"] = self.inside_area
        if self.expires is not None:
            attrs["expires"] = self.expires.isoformat()
        if self.call_to_action:
            attrs["call_to_action"] = self.call_to_action[:CALL_TO_ACTION_MAX_LENGTH]

        # Selectively copy small safe primitive properties from raw_properties
        for k, v in self.raw_properties.items():
            if k in attrs or _is_personal_key(k):
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
    include_roadworks: bool = Field(default=False)
    vic_api_key: str | None = Field(default=None)

    @field_validator("vic_api_key", mode="before")
    @classmethod
    def blank_key_is_none(cls, v: Any) -> str | None:
        """Treat a blank or whitespace-only key as no key."""
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    include_planned_outages: bool = Field(default=False)
    extra_outage_feeds: bool = Field(default=False)


class PowerOutageItem(BaseModel):
    """Real-time power outage item from energy network feeds (e.g. Energex, Ergon, Ausgrid)."""

    model_config = ConfigDict(extra="ignore")

    suburb: str = Field(default="", description="Locality or suburb name")
    cause: str = Field(default="Under Investigation", description="Reported cause of outage")
    restore_time: str | None = Field(default=None, description="Estimated time of restoration")
    customers_affected: int = Field(default=0, ge=0, description="Number of customers affected")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    # Distributor feeds (#36); council dashboard items leave id and start_time unset
    id: str | None = Field(default=None, description="Distributor incident ID")
    distributor: str | None = Field(default=None, description="Electricity distributor (e.g. Energex)")
    planned: bool = Field(default=False, description="Planned (maintenance) outage rather than a fault")
    status: str | None = Field(default=None, description="Distributor status text")
    start_time: str | None = Field(default=None, description="When the outage started (ISO 8601)")
    distance_km: float | None = Field(default=None, ge=0, description="Distance from the monitored point")


class RoadEventCategory(StrEnum):
    """What a road event means for someone travelling nearby (#29).

    Planned categories (roadworks, special events) never turn on the "road closure nearby"
    or "flooded road nearby" binary sensors, even when the include-roadworks option lists them.
    """

    FLOODING = "flooding"  # flooded road or crossing, open or closed
    CLOSURE = "closure"  # road closed or impassable (unplanned)
    HAZARD = "hazard"  # unplanned incident or damage on an open road
    ROADWORKS = "roadworks"  # planned roadworks
    SPECIAL_EVENT = "special_event"  # planned special event

    @property
    def is_planned(self) -> bool:
        """Return True for scheduled works and events."""
        return self in (RoadEventCategory.ROADWORKS, RoadEventCategory.SPECIAL_EVENT)

    @classmethod
    def infer(cls, status: str | None, reason: str | None = None) -> RoadEventCategory:
        """Classify an item from its status and reason text (council feeds without a category).

        Precedence is flooding, planned works, closure, then hazard, so a flooded road that
        is also closed reads as flooding.
        """
        status_text = (status or "").lower()
        text = f"{status_text} {(reason or '').lower()}"
        if "flood" in text or "water over" in text:
            return cls.FLOODING
        if "roadwork" in text or re.search(r"\bplanned\b", text):  # not "unplanned"
            return cls.ROADWORKS
        if "special event" in text:
            return cls.SPECIAL_EVENT
        if "closed" in status_text or "closure" in status_text or "impassable" in status_text:
            return cls.CLOSURE
        return cls.HAZARD


class RoadClosureItem(BaseModel):
    """Road hazard, closure, or flooded crossing from Council or TMR/LiveTraffic."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def infer_category(cls, data: Any) -> Any:
        """Derive the category from status and reason when a feed does not set one."""
        if isinstance(data, dict) and data.get("category") is None:
            # One fallback for a missing and a null status, matching the field default
            status = data.get("status") or "Closed"
            data = {**data, "category": RoadEventCategory.infer(str(status), data.get("reason"))}
        return data

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
    category: RoadEventCategory = Field(
        default=RoadEventCategory.CLOSURE, description="Closure, flooding, hazard, roadworks or special event"
    )

    @property
    def is_flooding(self) -> bool:
        """Return True for a flooded road."""
        return self.category == RoadEventCategory.FLOODING

    @property
    def is_planned(self) -> bool:
        """Return True for planned roadworks and special events."""
        return self.category.is_planned


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
    total_fire_ban: bool | None = Field(
        default=None, description="Total Fire Ban in force; None when the feed does not say"
    )
    day: str | None = Field(default=None, description="Forecast day")


class FireDangerDay(BaseModel):
    """One day of a district fire danger forecast, dated in the district's local time (#28)."""

    model_config = ConfigDict(extra="ignore")

    date: dt.date = Field(description="Local calendar day the forecast applies to")
    rating: str | None = Field(
        default=None, description="AFDRS rating (No Rating, Moderate, High, Extreme, Catastrophic)"
    )
    fire_behaviour_index: int | None = Field(default=None, description="AFDRS Fire Behaviour Index")
    total_fire_ban: bool | None = Field(default=None, description="Total fire ban declared; None when not published")


class FireDangerOutlook(BaseModel):
    """Multi-day fire danger forecast and total fire bans for one BoM fire weather district (#28)."""

    model_config = ConfigDict(extra="ignore")

    district_number: str = Field(description="BoM fire weather district AAC (e.g. NSW_FW008)")
    district_name: str = Field(description="Fire weather district name")
    time_zone: str = Field(description="IANA time zone the forecast days are dated in")
    issued_at: datetime | None = Field(default=None, description="Forecast issue time")
    source: str = Field(description="Fire danger forecast source")
    total_fire_ban_source: str | None = Field(default=None, description="Total fire ban source, if any")
    days: list[FireDangerDay] = Field(default_factory=list)

    def day(self, on: dt.date) -> FireDangerDay | None:
        """Return the forecast for a local calendar day, if the forecast covers it."""
        return next((day for day in self.days if day.date == on), None)


class FireSeasonStatus(BaseModel):
    """New Zealand fire season status and Section 52 prohibitions at a location (#28)."""

    model_config = ConfigDict(extra="ignore")

    season: str | None = Field(default=None, description="open, restricted or prohibited")
    zone: str | None = Field(default=None, description="Fire zone name")
    district: str | None = Field(default=None, description="Fire and Emergency NZ district")
    last_updated: datetime | None = Field(default=None)
    section_52: bool | None = Field(default=None, description="A Section 52 prohibition covers the location")
    section_52_comment: str | None = Field(default=None)
    prohibited_activities: list[str] = Field(default_factory=list)


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
    overall_rating: str | None = Field(
        default="Good", description="Overall station air quality rating; None when no reading is available"
    )
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    distance_km: float | None = Field(default=None, ge=0.0)
    observed_at: datetime | None = Field(default=None, description="Time of the reading")
    source: str | None = Field(default=None, description="Agency that published the reading")


class SatelliteHotspotItem(BaseModel):
    """A satellite-detected heat source (DEA Hotspots). Informational: not a fire or a warning."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Upstream hotspot identifier")
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    confidence: float | None = Field(default=None, description="Detection confidence (0-100)")
    power: float | None = Field(default=None, description="Fire radiative power in MW, when reported")
    temp_kelvin: float | None = Field(default=None)
    hours_since_hotspot: float | None = Field(default=None, ge=0.0)
    observed_at: datetime | None = Field(default=None)
    satellite: str | None = Field(default=None)
    distance_km: float | None = Field(default=None, ge=0.0)


class SatelliteHotspots(BaseModel):
    """Hotspots within the monitoring radius, plus how the query was limited."""

    model_config = ConfigDict(extra="ignore")

    items: list[SatelliteHotspotItem] = Field(default_factory=list)
    min_confidence: float = Field(description="Hotspots below this confidence were excluded")
    truncated: bool = Field(default=False, description="The upstream query hit its feature limit")


class TsunamiStatus(BaseModel):
    """Tsunami threat for the configured jurisdiction (JATWC for Australia, PTWC guidance for NZ)."""

    model_config = ConfigDict(extra="ignore")

    active: bool = Field(description="A current tsunami watch or warning applies")
    threat_level: str | None = Field(default=None, description="no_threat, watch, marine or land")
    headline: str | None = Field(default=None)
    issued: datetime | None = Field(default=None)
    expires: datetime | None = Field(default=None)
    products: list[str] = Field(default_factory=list, description="Products present in the last check")
    source: str = Field(description="Issuing centre")
    checked_at: datetime | None = Field(default=None)


class HeatwaveArea(BaseModel):
    """One district in a BoM heatwave warning."""

    model_config = ConfigDict(extra="ignore")

    name: str
    severity: str


class HeatwaveStatus(BaseModel):
    """Highest current BoM heatwave warning severity in the configured state."""

    model_config = ConfigDict(extra="ignore")

    severity: str = Field(description="none, low_intensity, severe or extreme")
    areas: list[HeatwaveArea] = Field(default_factory=list)
    headline: str | None = Field(default=None)
    issued: datetime | None = Field(default=None)
    expires: datetime | None = Field(default=None)
    product_id: str = Field(description="BoM product checked")


class UVObservation(BaseModel):
    """Latest ARPANSA UV index at the nearest monitoring station, with the BoM sun protection forecast."""

    model_config = ConfigDict(extra="ignore")

    station_id: str
    station_name: str
    index: float = Field(ge=0.0)
    observed_at: datetime | None = Field(default=None)
    distance_km: float | None = Field(default=None, ge=0.0)
    forecast: str | None = Field(default=None, description="BoM UV alert text for today")
    forecast_max_index: int | None = Field(default=None)


class RegionalAlertItem(BaseModel):
    """GDACS Orange or Red alert in the Australia/New Zealand region (context only, not a local warning)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    event_type: str | None = Field(default=None)
    alert_level: str
    severity: str | None = Field(default=None)
    country: str | None = Field(default=None)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    from_date: datetime | None = Field(default=None)
    to_date: datetime | None = Field(default=None)
    url: str | None = Field(default=None)
    distance_km: float | None = Field(default=None, ge=0.0)
    # GDACS identifiers and the episode geometry the map card draws (#71)
    event_type_code: str | None = Field(default=None, description="GDACS event type code, e.g. 'TC'")
    event_id: int | None = Field(default=None)
    episode_id: int | None = Field(default=None)
    geometry_url: str | None = Field(default=None)


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
    fire_outlook: FireDangerOutlook | None = Field(default=None)
    fire_season: FireSeasonStatus | None = Field(default=None)
    weather_stations: list[WeatherStationObservation] = Field(default_factory=list)
    air_quality_stations: list[AirQualityStationData] = Field(default_factory=list)
    relief_facilities: list[ReliefFacilityItem] = Field(default_factory=list)
    cameras: list[DisasterCameraItem] = Field(default_factory=list)
    nearby_councils: list[dict[str, str]] = Field(default_factory=list)
    feeds_ok: list[str] = Field(default_factory=list, description="Hazard providers that fetched successfully")
    feeds_failed: list[str] = Field(default_factory=list, description="Hazard providers that failed this update")
    # Opt-in national feeds (#37). None means "not enabled or could not be determined"; they
    # never enter ``hazards``, so they do not change counts, warning levels or polling.
    satellite_hotspots: SatelliteHotspots | None = Field(default=None)
    tsunami: TsunamiStatus | None = Field(default=None)
    heatwave: HeatwaveStatus | None = Field(default=None)
    uv: UVObservation | None = Field(default=None)
    regional_alerts: list[RegionalAlertItem] | None = Field(default=None)

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
