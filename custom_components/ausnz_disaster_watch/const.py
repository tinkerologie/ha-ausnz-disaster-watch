"""Constants for the Australian Disaster Watch integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

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

# Preset Council Disaster Dashboards (Guardian IMS). A preset without a URL has no JSON
# dashboard the integration can read.
PRESET_COUNCIL_DASHBOARDS: Final[dict[str, dict[str, str | float | None]]] = {
    "moreton_bay": {
        "name": "City of Moreton Bay",
        "state": STATE_QLD,
        "url": "https://disaster.moretonbay.qld.gov.au",
        "latitude": -27.2657,
        "longitude": 152.9818,
    },
    "sunshine_coast": {
        "name": "Sunshine Coast",
        "state": STATE_QLD,
        # Disaster Hub (disasterhub.sunshinecoast.qld.gov.au) is not a Guardian IMS dashboard
        "url": None,
        "latitude": -26.6500,
        "longitude": 153.0667,
    },
    "noosa": {
        "name": "Noosa Shire",
        "state": STATE_QLD,
        "url": "https://disaster.noosa.qld.gov.au",
        "latitude": -26.3986,
        "longitude": 153.0442,
    },
    "gold_coast": {
        "name": "City of Gold Coast",
        "state": STATE_QLD,
        "url": "https://dashboard.goldcoast.qld.gov.au",
        "latitude": -28.0167,
        "longitude": 153.4000,
    },
    "cairns": {
        "name": "Cairns Regional",
        "state": STATE_QLD,
        "url": "https://disaster.cairns.qld.gov.au",
        "latitude": -16.9186,
        "longitude": 145.7781,
    },
    "townsville": {
        "name": "Townsville City",
        "state": STATE_QLD,
        "url": "https://disaster.townsville.qld.gov.au",
        "latitude": -19.2590,
        "longitude": 146.8169,
    },
    "fraser_coast": {
        "name": "Fraser Coast",
        "state": STATE_QLD,
        "url": "https://disaster.frasercoast.qld.gov.au",
        "latitude": -25.5398,
        "longitude": 152.7032,
    },
    "bundaberg": {
        "name": "Bundaberg Regional",
        "state": STATE_QLD,
        "url": "https://disaster.bundaberg.qld.gov.au",
        "latitude": -24.8661,
        "longitude": 152.3489,
    },
    "redland": {
        "name": "Redland City",
        "state": STATE_QLD,
        "url": "https://dashboard.redland.qld.gov.au",
        "latitude": -27.5306,
        "longitude": 153.2500,
    },
    "ipswich": {
        "name": "Ipswich City",
        "state": STATE_QLD,
        "url": "https://disaster.ipswich.qld.gov.au",
        "latitude": -27.6167,
        "longitude": 152.7667,
    },
    "logan": {
        "name": "Logan City",
        "state": STATE_QLD,
        "url": "https://disaster.logan.qld.gov.au",
        "latitude": -27.6972,
        "longitude": 153.1111,
    },
}

# A home-zone entry gets the nearest preset council dashboard within this distance (#19)
COUNCIL_AUTO_MATCH_KM: Final = 40

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
