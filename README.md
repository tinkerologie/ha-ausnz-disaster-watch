# Australia and New Zealand Disaster Watch for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](https://github.com/tinkerologie/ha-ausnz-disaster-watch/releases)
[![License](https://img.shields.io/github/license/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz)

A comprehensive, real-time emergency disaster and hazard monitoring integration for Home Assistant across Australian jurisdictions.

Directly integrates official emergency feeds—including the **Queensland Fire Department (QFD)**, local council disaster dashboards (such as the **City of Moreton Bay Disaster Dashboard**), **NSW Rural Fire Service (NSW RFS)**, **Emergency Management Victoria (EMV OSOM)**, and **Bureau of Meteorology (BoM)** weather alerts—normalized under the **Australian Warning System (AWS)**.

---

## Key Features

- **Jurisdiction & Local Council Feeds**:
  - **Queensland**: Real-time QFD vegetation fire & emergency warnings feed + direct integration with Local Council Disaster Dashboards (**City of Moreton Bay**, Sunshine Coast, Gold Coast, Cairns, Townsville, Fraser Coast, etc.) covering fire incidents, road closures/hazards, power outages, and bulletins.
  - **New South Wales**: NSW RFS Major Incidents & SES data feeds.
  - **Victoria**: Emergency Management Victoria (EMV OSOM) feed covering fires, floods, storms, and health hazards.
  - **New Zealand**: GeoNet earthquakes (with GeoNet's CAP quake alerts) and volcanic alert levels, NEMA Civil Defence alerts, MetService warnings, and NZTA state highway closures and hazards.
  - **Northern Territory**: Bushfires NT and NT Fire and Rescue Service incidents from the NT Government Fire_Incidents service.
  - **National / Federal**: Bureau of Meteorology (BoM) weather warnings (severe thunderstorms, tropical cyclones, flood warnings).
- **Australian Warning System (AWS) Normalization**:
  - 🚨 **Emergency Warning** (Level 3 - Red)
  - ⚠️ **Watch and Act** (Level 2 - Orange)
  - ℹ️ **Advice** (Level 1 - Yellow)
  - 🛡️ **Information / All Clear** (Level 0 - Blue / Green)
- **Spatial Radius & Location Filtering**:
  - Set monitoring center to your **Home Zone** or specify a **Custom Location** (with one-click presets for councils like Moreton Bay).
  - Configurable proximity radius slider (5 km to 300 km).
  - **Statewide Emergency Warning Override**: Automatically bypasses radius filters if any Level 3 Emergency Warning is active anywhere across your state.
  - **Exclude Hazard Reduction**: Drop planned/controlled burns to prevent false alarms.
- **Dynamic Map Pins (`geo_location`)**:
  - Active incidents are displayed directly on the native Home Assistant Map.
  - Dynamic lifecycle: new incidents appear instantly, and cleared incidents are automatically removed without leaving orphaned unavailable entities.
  - Strictly adheres to Home Assistant's 16 KB SQLite attribute limit by storing only centroids and scalar metadata.
- **Dynamic Polling Engine**:
  - Normal update interval: 5 minutes (300 seconds).
  - Threat update interval: Automatically drops to 60 seconds when an active Emergency Warning or Watch and Act is detected in your perimeter.
- **Bundled Lovelace Dashboard Card**:
  - Includes a custom Lovelace card (`ausnz-disaster-card`) that automatically registers with Home Assistant.
  - Features real-time threat banners, nearest distance counters, category filtering (Fires, Weather/Floods, Roads), and quick map navigation.

---

## Entity Overview

### Geolocation Platform (`geo_location`)
Renders interactive pins on the native Home Assistant Map for every active hazard in your perimeter.
- **Centroid Coordinates**: Precise latitude and longitude.
- **Attributes**: Warning level, hazard type, distance in km, issuing agency (`agency`), responsible agency, status, and direct link to official incident documentation.
- **Source**: Every event has `source: ausnz_disaster_watch`, whichever agency issued it, so one `geo_location` trigger or map card covers the whole integration. Filter on the `agency` attribute to pick out one agency.
- **Entity IDs**: `geo_location.ausnz_disaster_watch_<hazard_id>`, built from the agency's incident ID (not the headline), so the ID stays short and stable while the event lasts. The headline is the entity name. Each event is removed, including its entity registry entry, when the incident ends.
- **Dynamic Icons**: `mdi:fire` (Bushfire), `mdi:water-alert` (Flood), `mdi:weather-lightning` (Storm), `mdi:weather-hurricane` (Cyclone), `mdi:car-emergency` (Road Hazard), etc.

### Binary Sensors (`binary_sensor`)
| Entity (suffix) | Description | Device Class |
| ------ | ----------- | ------------ |
| `…_emergency_warning_nearby` | `on` when any Emergency Warning (Level 3) or Watch and Act (Level 2) is active in perimeter | `safety` |
| `…_active_hazards_nearby` | `on` when any active incident is within perimeter | `problem` |
| `…_power_outage_active` | `on` when a power outage is reported nearby | `problem` |
| `…_road_closure_nearby` | `on` when a road closure is reported nearby | `problem` |

### Sensors (`sensor`)
| Entity (suffix) | Description | Unit |
| ------ | ----------- | ---- |
| `…_nearest_hazard_distance` | Distance to the closest active incident | `km` |
| `…_nearest_hazard_title` | Headline of the nearest incident | — |
| `…_active_hazards_count` | Active incidents in the monitored perimeter | `hazards` |
| `…_highest_warning_level` | Highest AWS level currently active (`Emergency Warning`, `Watch and Act`, `Advice`, `Information`, `All Clear`) | — |
| `…_weather_warnings_count` | Active weather warnings | `warnings` |
| `…_fire_danger_rating` | Fire danger rating for the district | — |
| `…_power_outages_count` / `…_power_outages_customers_affected` | Power outages and customers affected | `outages` / `customers` |
| `…_road_closures_count` | Road closures nearby | `closures` |
| `…_relief_facilities_count` | Evacuation centres and sandbag stations nearby | `facilities` |
| `…_air_quality` | Air quality rating of the nearest station | — |
| `…_local_weather_observation` | Temperature at the nearest weather station | `°C` |

Entity IDs start with the device name, for example `binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby`.

### Cameras (`camera`)
Flood and traffic camera snapshots near the monitored location, where the jurisdiction provides them.

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Enter repository URL: `https://github.com/tinkerologie/ha-ausnz-disaster-watch`
4. Select Category: **Integration**
5. Click **Add**, then find **Australia and New Zealand Disaster Watch** and click **Download**.
6. **Restart Home Assistant**.

---

## Setup & Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Australia and New Zealand Disaster Watch**.
3. **Step 1: Jurisdiction & Monitoring**:
   - **State / Jurisdiction**: Select your state (e.g. `QLD`, `NSW`, `VIC`, etc.).
   - **Location Source**: Choose **Use Home Zone** or **Specify Custom Location**.
   - **Monitoring Radius**: Set perimeter radius (default: `50 km`).
   - **Statewide Emergency Warning Override**: Enabled by default (alerts on Level 3 warnings across state regardless of distance).
   - **Exclude Hazard Reduction**: Enabled by default (filters out planned burns).
4. **Step 2 (if Custom Location selected)**:
   - Select a **Preset Council Dashboard** (e.g. *City of Moreton Bay*, *Sunshine Coast*, *Gold Coast*, etc.) or enter custom coordinates and council dashboard URL.
   - Click **Submit**.

### Reconfiguration via Options Flow
You can adjust the radius, toggle overrides, or change council dashboard URLs anytime by clicking **Configure** on the integration card without needing to restart Home Assistant.

To change the state or location, use **Reconfigure** on the integration entry. Reconfigure also updates the options above, and renames the entry when the state or location changes.

---

## Lovelace Dashboard Card

The integration automatically serves and registers the custom Lovelace card: `custom:ausnz-disaster-card` (the older `custom:aus-disaster-card` name still works for now).

```yaml
type: custom:ausnz-disaster-card
title: Moreton Bay Disaster Watch
max_incidents: 10
show_map_button: true
```

To show only this integration's events on the native map card:

```yaml
type: map
geo_location_sources:
  - ausnz_disaster_watch
```

### Card Features:
- **Australian Warning System Status Banner**: Color-coded alert banner (Red for Emergency Warning with pulsing animation, Orange for Watch and Act, Yellow for Advice, Green for All Clear).
- **Metric Cards**: Quick view of nearest hazard distance and active incidents count.
- **Category Filter**: Filter live incidents by *All*, *Fires*, *Weather / Flood*, or *Roads*.
- **Direct Link**: Click any incident to open the official agency warning advisory or map.
- **View on Map Button**: One-click navigation to Home Assistant's native Map view.

---

## Automation Examples

### 1. High Priority Alert on Nearby Emergency Warning
```yaml
alias: "Emergency Warning: Alert Household"
triggers:
  - trigger: state
    entity_id: binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby
    to: "on"
actions:
  - action: notify.notify
    data:
      title: "🚨 EMERGENCY WARNING ACTIVE"
      message: >-
        {{ state_attr('binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby', 'highest_warning_level') }}:
        {{ state_attr('binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby', 'nearest_incident_title') }}
        is currently {{ state_attr('binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby', 'nearest_incident_distance') }} km away.
      data:
        push:
          sound: "critical"
```

### 2. Flash Red Lights on Emergency Warning
```yaml
alias: "Disaster Alert: Red Light Notification"
triggers:
  - trigger: state
    entity_id: binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.living_room
    data:
      color_name: red
      flash: short
```

### 3. Any Incident Entering a Zone

```yaml
alias: "Disaster Watch: Incident Near Home"
triggers:
  - trigger: geo_location
    source: ausnz_disaster_watch
    zone: zone.home
    event: enter
actions:
  - action: notify.notify
    data:
      title: "Incident near home"
      message: >-
        {{ trigger.to_state.name }}
        ({{ trigger.to_state.attributes.agency }})
```

---

## Data sources & licences

The integration reads public feeds published by emergency services, weather agencies and local councils. Every entity has an `attribution` attribute that credits the sources behind it, and map pins credit the feed the incident came from. Diagnostics list each source with its owner, licence and terms link.

| Region | Source | Terms |
| ------ | ------ | ----- |
| QLD | Queensland Fire Department | CC BY 4.0 |
| QLD, NSW | Council disaster dashboards (Guardian IMS) | Council terms; vary by council |
| NSW | NSW Rural Fire Service | CC BY 4.0 |
| VIC | VicEmergency (Emergency Management Victoria) | Prior written permission required; permission not yet obtained |
| WA | Emergency WA (DFES) | CC BY-ND 4.0; JSON API not a designated feed |
| SA | SA CFS / SES CAP-AU feed | Catalogued CFS feeds are CC BY-NC-ND 4.0 |
| ACT | ACT Emergency Services Agency | No licence published |
| TAS | TasALERT | Feed access by request; not yet granted |
| NT | NT Government Fire_Incidents service (Bushfires NT, NTFRS) | No licence published |
| AU | Bureau of Meteorology warnings via WMO SWIC | Personal, non-commercial use under BoM terms |
| NZ | GeoNet | CC BY 3.0 NZ |
| NZ | NEMA (Civil Defence) alerts | CC BY 4.0 |
| NZ | MetService CAP warnings | CC BY 4.0, CAP Code of Practice |
| NZ | NZ Transport Agency Waka Kotahi road events (`trafficnz.info`) | No licence stated on data.govt.nz; open data, unverified |

GeoNet and NSW RFS feeds are read with the maintained `aio_geojson_geonetnz_quakes`, `aio_geojson_geonetnz_volcano` and `aio_geojson_nsw_rfs_incidents` libraries (Apache-2.0), the same ones Home Assistant core uses.

Several publishers restrict reuse to personal, non-commercial use or require permission. This integration is for personal home automation. Do not use it to republish these feeds or for commercial purposes without checking each publisher's terms.

The full register, with every endpoint, terms evidence, rate limits and the decisions taken for restricted sources, is in [docs/development/DATA_SOURCES.md](docs/development/DATA_SOURCES.md).

---

## Quality Scale & Standards

- **Strict Type Checking**: 100% compliant with Pyright type checking.
- **Modern Code Standards**: Linted and formatted with Ruff (`py313`).
- **Comprehensive Test Suite**: Tested with `pytest-homeassistant-custom-component`.
- **Database Safety Guardrail**: All entity attributes are strictly capped to ensure payloads remain well under the 16 KB SQLite threshold.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
