"""Constants for the Australian Disaster Watch integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from .council_registry import COUNCIL_DASHBOARDS

DOMAIN: Final = "ausnz_disaster_watch"

# Configuration options
CONF_STATE: Final = "state"
CONF_RADIUS: Final = "radius"
CONF_OVERRIDE_EMERGENCY: Final = "override_emergency"
CONF_EXCLUDE_HAZARD_REDUCTION: Final = "exclude_hazard_reduction"
CONF_LOCATION_MODE: Final = "location_mode"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_LOCATION_NAME: Final = "location_name"
CONF_COUNCIL_DASHBOARD_URL: Final = "council_dashboard_url"
# Opt-in Geoscience Australia earthquakes for Australian entries (#23)
CONF_INCLUDE_EARTHQUAKES: Final = "include_earthquakes"
CONF_RIVER_GAUGES: Final = "river_gauges"

# Opt-in national and regional hazard feeds (#37). All default to off.
CONF_ENABLE_TSUNAMI: Final = "enable_tsunami"
CONF_ENABLE_SATELLITE_HOTSPOTS: Final = "enable_satellite_hotspots"
CONF_ENABLE_HEATWAVE: Final = "enable_heatwave"
CONF_ENABLE_UV: Final = "enable_uv"
CONF_ENABLE_AIR_QUALITY: Final = "enable_state_air_quality"
CONF_ENABLE_REGIONAL_ALERTS: Final = "enable_regional_alerts"
NATIONAL_FEED_OPTIONS: Final = (
    CONF_ENABLE_TSUNAMI,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_UV,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_REGIONAL_ALERTS,
)
# Feeds that only cover Australia; they are not offered for New Zealand entries
AU_ONLY_FEED_OPTIONS: Final = (
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_UV,
    CONF_ENABLE_AIR_QUALITY,
)
CONF_INCLUDE_ROADWORKS: Final = "include_roadworks"
CONF_VIC_API_KEY: Final = "vic_api_key"
CONF_INCLUDE_PLANNED_OUTAGES: Final = "include_planned_outages"
CONF_EXTRA_OUTAGE_FEEDS: Final = "extra_outage_feeds"

# Location modes
LOCATION_MODE_HOME: Final = "home"
LOCATION_MODE_CUSTOM: Final = "custom"

# Default values
DEFAULT_NAME: Final = "Australia and New Zealand Disaster Watch"
DEFAULT_RADIUS: Final = 50  # km
MIN_RADIUS: Final = 5  # km
MAX_RADIUS: Final = 300  # km
DEFAULT_OVERRIDE_EMERGENCY: Final = True
DEFAULT_EXCLUDE_HAZARD_REDUCTION: Final = True
DEFAULT_INCLUDE_EARTHQUAKES: Final = False
DEFAULT_INCLUDE_ROADWORKS: Final = False
DEFAULT_INCLUDE_PLANNED_OUTAGES: Final = False
DEFAULT_EXTRA_OUTAGE_FEEDS: Final = False
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes in seconds
THREAT_SCAN_INTERVAL: Final = 60  # 1 minute when active threat detected
# How long a failed feed's last good hazards are kept before they are dropped (#16)
LAST_GOOD_MAX_AGE: Final = timedelta(minutes=30)

# State codes
STATE_QLD: Final = "QLD"
STATE_NSW: Final = "NSW"
STATE_VIC: Final = "VIC"
STATE_WA: Final = "WA"
STATE_SA: Final = "SA"
STATE_TAS: Final = "TAS"
STATE_ACT: Final = "ACT"
STATE_NT: Final = "NT"
STATE_NZ: Final = "NZ"

# IANA time zone each agency publishes local timestamps in (#13)
STATE_TIMEZONES: Final[dict[str, str]] = {
    STATE_QLD: "Australia/Brisbane",
    STATE_NSW: "Australia/Sydney",
    STATE_ACT: "Australia/Sydney",
    STATE_VIC: "Australia/Melbourne",
    STATE_SA: "Australia/Adelaide",
    STATE_WA: "Australia/Perth",
    STATE_TAS: "Australia/Hobart",
    STATE_NT: "Australia/Darwin",
    STATE_NZ: "Pacific/Auckland",
}

SUPPORTED_STATES: Final = [
    STATE_QLD,
    STATE_NSW,
    STATE_VIC,
    STATE_WA,
    STATE_SA,
    STATE_TAS,
    STATE_ACT,
    STATE_NT,
    STATE_NZ,
]

# Preset council disaster dashboards, keyed as before, from the generated registry
# (data/council_dashboards.json, see council_registry.py) (#32). A preset without a URL has no
# Guardian IMS dashboard the integration can read (Brisbane, Sunshine Coast).
PRESET_COUNCIL_DASHBOARDS: Final[dict[str, dict[str, str | float | None]]] = {
    key: {
        "name": council["name"],
        "state": council["state"],
        "url": council["url"],
        "latitude": council["latitude"],
        "longitude": council["longitude"],
    }
    for key, council in COUNCIL_DASHBOARDS.items()
}

# Entity Attributes
ATTR_HAZARD_TYPE: Final = "hazard_type"
ATTR_WARNING_LEVEL: Final = "warning_level"
ATTR_RESPONSIBLE_AGENCY: Final = "responsible_agency"
ATTR_SOURCE: Final = "source"
ATTR_STATUS: Final = "status"
ATTR_LOCATION_NAME: Final = "location_name"
ATTR_DISTANCE: Final = "distance"
ATTR_IS_HAZARD_REDUCTION: Final = "is_hazard_reduction"
ATTR_WEB_URL: Final = "web_url"
ATTR_LAST_UPDATED: Final = "last_updated"
ATTR_INCIDENT_COUNT: Final = "incident_count"
ATTR_HIGHEST_WARNING_LEVEL: Final = "highest_warning_level"
ATTR_NEAREST_INCIDENT_TITLE: Final = "nearest_incident_title"
ATTR_NEAREST_INCIDENT_DISTANCE: Final = "nearest_incident_distance"

# Open-Meteo forecast features (#38, #39, #40). All are opt-in and off for existing entries.
# Model-derived signals: kept apart from agency warnings and never mapped to warning levels.
CONF_WEATHER_SIGNALS: Final = "weather_signals"
CONF_GUST_THRESHOLD: Final = "gust_threshold"
CONF_HEAT_THRESHOLD: Final = "heat_threshold"
CONF_AI_ENSEMBLE: Final = "ai_ensemble"
CONF_AI_WEATHERNEXT: Final = "ai_weathernext"
CONF_HEAVY_RAIN_THRESHOLD: Final = "heavy_rain_threshold"
CONF_RIVER_POINTS: Final = "river_points"

DEFAULT_WEATHER_SIGNALS: Final = False
DEFAULT_GUST_THRESHOLD: Final = 90  # km/h, BoM damaging-wind gust criterion
MIN_GUST_THRESHOLD: Final = 50
MAX_GUST_THRESHOLD: Final = 150
DEFAULT_HEAT_THRESHOLD: Final = 40  # °C apparent temperature
MIN_HEAT_THRESHOLD: Final = 30
MAX_HEAT_THRESHOLD: Final = 50
DEFAULT_AI_ENSEMBLE: Final = False
DEFAULT_AI_WEATHERNEXT: Final = False
DEFAULT_HEAVY_RAIN_THRESHOLD: Final = 50  # mm in 24 h
MIN_HEAVY_RAIN_THRESHOLD: Final = 5
MAX_HEAVY_RAIN_THRESHOLD: Final = 500

# River point keys (stored as a list of dicts in entry options)
RIVER_POINT_ID: Final = "id"
RIVER_POINT_NAME: Final = "name"
RIVER_POINT_THRESHOLD: Final = "threshold"  # m³/s
RIVER_POINT_BASELINE: Final = "baseline"  # m³/s, median annual peak of the GloFAS reanalysis
RIVER_POINT_HORIZON: Final = "horizon_days"
DEFAULT_RIVER_HORIZON: Final = 3
MAX_RIVER_HORIZON: Final = 7
MAX_RIVER_POINTS: Final = 10

# Poll cadence. Forecasts change a few times a day, so they poll far less often than incidents.
WEATHER_SIGNALS_INTERVAL: Final = timedelta(hours=1)
RIVER_FORECAST_INTERVAL: Final = timedelta(hours=6)  # GloFAS updates daily
AI_ENSEMBLE_INTERVAL: Final = timedelta(hours=6)  # AIFS runs every 6 h
AI_WEATHERNEXT_MIN_AGE: Final = timedelta(hours=12)  # WeatherNext 2 runs every 12 h
FORECAST_RETRY_INTERVAL: Final = timedelta(minutes=30)
