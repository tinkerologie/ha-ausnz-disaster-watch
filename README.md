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
  - **Earthquakes (optional)**: Geoscience Australia earthquakes of magnitude 3 or more from the last 48 hours, within your radius (M6+ Watch and Act, M4.5+ Advice, smaller Information). Turn it on under **Configure > Earthquakes** (Australian entries; New Zealand entries use GeoNet). Earthquake data © Commonwealth of Australia (Geoscience Australia), from [earthquakes.ga.gov.au](https://earthquakes.ga.gov.au/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
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
- **Warning Areas**:
  - Where an agency publishes a warning's area (QFD and QPS warning polygons, SA SES warnings, SA CFS CAP areas, Emergency WA warnings, TasALERT, NSW RFS fire grounds, BoM, NEMA and MetService CAP areas), `distance_km` is the distance to the nearest edge of the area, 0 when the monitored location is inside it, instead of the distance to a single point.
  - `binary_sensor.…_inside_warning_area` and the `inside_warning_area` attribute of the highest warning level sensor tell you when you are inside a warning area. Each hazard has an `inside_area` attribute. Warnings published only as a point never count.
  - Polygons are simplified (about 50 m, at most 400 vertices per hazard) and kept in memory only: they never appear in state attributes or diagnostics. A point in a hole of a polygon counts as inside.
  - Not covered: NSW SES (its only feed, HazardWatch, allows personal non-commercial use only), VicEmergency polygons (EMV terms need written permission), ACT (its polygon feed has burnt areas only).
- **Dynamic Map Pins (`geo_location`)**:
  - Active incidents are displayed directly on the native Home Assistant Map.
  - Dynamic lifecycle: new incidents appear instantly, and cleared incidents are automatically removed without leaving orphaned unavailable entities.
  - Strictly adheres to Home Assistant's 16 KB SQLite attribute limit by storing only centroids and scalar metadata.
- **Dynamic Polling Engine**:
  - Normal update interval: 5 minutes (300 seconds).
  - Threat update interval: Automatically drops to 60 seconds when an active Emergency Warning or Watch and Act is detected in your perimeter.
- **Dashboard card suite**:
  - Eleven cards that register automatically: status, incidents, warnings, fire danger, power outages, roads, conditions, relief, cameras, a map with animated rain radar, and an all-in-one card. See [Dashboard Cards](#dashboard-cards).

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
| `…_inside_warning_area` | `on` when the monitored location is inside the published area of an Advice, Watch and Act or Emergency Warning. Attributes: `warning_count`, `warning_level`, `warning_title`, `call_to_action` of the most severe one | `safety` |
| `…_active_hazards_nearby` | `on` when any active incident is within perimeter | `problem` |
| `…_power_outage_active` | `on` when a power outage is reported nearby | `problem` |
| `…_road_closure_nearby` | `on` when a road closure is reported nearby | `problem` |
| `…_total_fire_ban` | `on` when a total fire ban is declared today for your fire weather district (Australia only; see [Fire danger and total fire bans](#fire-danger-and-total-fire-bans)) | `safety` |

### Sensors (`sensor`)
| Entity (suffix) | Description | Unit |
| ------ | ----------- | ---- |
| `…_nearest_hazard_distance` | Distance to the closest active incident | `km` |
| `…_nearest_hazard_title` | Headline of the nearest incident | — |
| `…_active_hazards_count` | Active incidents in the monitored perimeter | `hazards` |
| `…_highest_warning_level` | Highest AWS level currently active (`Emergency Warning`, `Watch and Act`, `Advice`, `Information`, `All Clear`) | — |
| `…_weather_warnings_count` | Active weather warnings | `warnings` |
| `…_fire_danger_rating` | Today's AFDRS fire danger rating for your fire weather district, with a 4-day `forecast` attribute | — |
| `…_fire_season` | New Zealand only: fire season at your location (`open`, `restricted`, `prohibited`) with Section 52 prohibitions | — |
| `…_power_outages_count` / `…_power_outages_customers_affected` | Power outages and customers affected | `outages` / `customers` |
| `…_road_closures_count` | Road closures nearby | `closures` |
| `…_relief_facilities_count` | Evacuation centres and sandbag stations nearby | `facilities` |
| `…_air_quality` | Air quality rating of the nearest station | — |
| `…_local_weather_observation` | Temperature at the nearest weather station | `°C` |

Entity IDs start with the device name, for example `binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby`.

### Cameras (`camera`)
Flood and traffic camera snapshots near the monitored location, where the jurisdiction provides them.

### Fire danger and total fire bans

Your location is matched to its Bureau of Meteorology fire weather district (bundled, simplified `IDM00007` boundaries, so border towns such as Albury and Wodonga or Queanbeyan and Canberra get their own district). The rating and 4-day outlook come from the Bureau's fire danger forecast for that state. Each forecast day is dated in the district's local time, so the sensor always shows today's rating, including in the evening after the next day's forecast is issued. Fire danger is polled at most every 30 minutes.

`…_fire_danger_rating` attributes: `district_name`, `district_number` (BoM district code such as `NSW_FW008`), `date`, `fire_behaviour_index`, `total_fire_ban`, `forecast` (one entry per day: `date`, `rating`, `fire_behaviour_index`, `total_fire_ban`), `issued_at`, `source` and `total_fire_ban_source`. The state is unchanged: `No Rating`, `Moderate`, `High`, `Extreme` or `Catastrophic`.

Total fire bans come from the agency that declares them:

| District | Total fire ban source |
| -------- | --------------------- |
| NSW | NSW RFS 4-day fire danger feed (falls back to `fdrToban.xml`, today and tomorrow) |
| ACT | ACT ESA fire danger feed (today and tomorrow) |
| VIC | CFA total fire ban and fire danger forecast RSS |
| SA | SA CFS fire danger and total fire ban feed |
| WA | Emergency WA total fire bans, matched to your local government area (ABS boundaries) |
| QLD, NT, TAS | No ban feed is read, so `…_total_fire_ban` is unknown. TasALERT's ban feed needs permission from TasALERT. |

A ban the source does not publish, or a source that cannot be read, is unknown, never `off`.

In New Zealand, `…_fire_season` reports the Fire and Emergency NZ fire season zone at your location. Its `section_52`, `section_52_comment` and `prohibited_activities` attributes show any Section 52 prohibition (for example fireworks) covering the location.

Fire danger forecasts and district boundaries © Bureau of Meteorology. Total fire bans © NSW RFS, ACT ESA, CFA, SA CFS and DFES WA. LGA boundaries © Australian Bureau of Statistics (CC BY 4.0). NZ fire seasons © Fire and Emergency New Zealand.

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
Click **Configure** on the integration card to open the options menu:

- **Monitoring settings**: radius, emergency override, planned burns and council dashboard URL.
- **Forecast signals and AI rain outlook**: the opt-in Open-Meteo features below.
- **Earthquakes** (Australian entries): include Geoscience Australia earthquakes (off by default).
- **Add / edit / remove river points**: river flood forecast points.

Saving any options page reloads the entry; no Home Assistant restart is needed.

---

## Forecast Signals (model-derived, not official)

Three optional features use [Open-Meteo](https://open-meteo.com/) model forecasts. **All are off by default** and fetch nothing until you turn them on. They are separate from agency warnings: they are plain sensors with `official: false`, never `geo_location` hazards, never counted in the hazard sensors, and never mapped to Australian Warning System levels or to the official fire danger rating. **They do not replace BoM, MetService or emergency service warnings.**

Each feature polls on its own schedule with one request per poll; a failed fetch makes only that feature's entities unavailable and is retried after 30 minutes.

### Weather hazard signals (hourly)

From the Open-Meteo Forecast API (best-match model) for the next 24 hours from the current hour:

| Entity | Meaning |
|---|---|
| `sensor.*_max_wind_gust_forecast_24h` | Highest forecast 10 m gust (km/h) |
| `binary_sensor.*_damaging_gusts_forecast` | On when that gust reaches the threshold (default 90 km/h, BoM's damaging wind criterion) |
| `sensor.*_max_apparent_temperature_forecast_24h` | Highest forecast apparent temperature (°C) |
| `binary_sensor.*_extreme_heat_forecast` | On when that temperature reaches the threshold (default 40 °C) |
| `sensor.*_thunderstorm_potential_forecast` | `low` / `moderate` / `high` / `very_high` |
| `sensor.*_calculated_fire_danger_index_not_official` | Calculated McArthur FFDI (not official) |

- **Thunderstorm potential** is a project heuristic, not a BoM category. Each hour is rated from CAPE and precipitation probability together: very high at CAPE ≥ 2500 J/kg and ≥ 40 %, high at ≥ 1000 J/kg and ≥ 30 %, moderate at ≥ 500 J/kg and ≥ 20 %. A model thunderstorm weather code (WMO 95, 96, 99) makes the hour at least high. It ignores wind shear and convective inhibition. Open-Meteo's `lightning_potential` is not used because it is empty for Australia and New Zealand.
- **Calculated fire danger index** uses the McArthur Mk5 FFDI in the Noble et al. (1980) form, `FFDI = 2·exp(−0.450 + 0.987·ln D − 0.0345·RH + 0.0338·T + 0.0234·V)`, with mean 10 m wind (not gusts). The drought factor `D` is **experimental and not validated**: Griffiths (1999) with the soil dryness index replaced by a 20-day proxy (FAO reference evapotranspiration minus effective rain, the part of each rain event above its first 5 mm, clamped to 0–203.2 mm). The past 20 days are archived model values, not gauge observations. It is not an AFDRS rating; the official rating stays in the Fire Danger Rating sensor.
- Attributes: `source`, `model` (`best_match`), `forecast_issued_at` (when the forecast was fetched; Open-Meteo does not report a run time for best match), `window_start`, `window_end`, `peak_time` and the values behind each signal.

### River flood forecast (every 6 hours)

From the Open-Meteo Flood API (GloFAS v4, about 5 km river grid), for up to 10 named points. For each point:

| Entity | Meaning |
|---|---|
| `sensor.*_river_discharge_<name>` | Today's (UTC) ensemble-mean discharge (m³/s); attributes `forecast` (7 days of mean, max and p75), `p75`, `trend` (rising/steady/falling over the horizon, 10 % band) |
| `binary_sensor.*_river_flood_risk_<name>` | On when the ensemble maximum (`river_discharge_max`, the wettest ensemble member) on any day within the horizon (1–7 days, default 3) exceeds the point's threshold |

- When you add a point, the integration checks that it has GloFAS data. A point in a city centre or by a small creek can fall outside the river grid; it then checks 16 neighbouring cells (0.05° and 0.1° away, in one request) and suggests the one with the largest discharge. This neighbour search is the integration's own heuristic.
- The default threshold is the cell's **median annual peak discharge** over the last 20 years of the GloFAS reanalysis (about a 2-year flood; GloFAS's own flood alerts use return-period thresholds like this). It is fetched once when the point is added; you can override it with a local flood level in m³/s. `river_discharge_p75` is the 75th percentile across ensemble members, not a historical percentile.
- All points are fetched in one request. GloFAS updates daily.

### Experimental AI ensemble rain outlook (every 6 hours)

Experimental AI model output from the Open-Meteo Ensemble API: ECMWF AIFS (51 members, new run every 6 hours) and, behind its own toggle (off by default), Google WeatherNext 2 (64 members, every 12 hours). Only models with a new run are requested, together in one request.

| Entity | Meaning |
|---|---|
| `sensor.*_experimental_ai_heavy_rain_probability_24h` | Share of members (%) with a next-24-hour total at or above the threshold (default 50 mm) |
| `sensor.*_experimental_ai_heavy_rain_probability_72h` | Share of members with any rolling 24-hour total in the next 72 hours at or above the threshold |
| `sensor.*_experimental_ai_rain_outlook` | Ensemble-mean rain in the next 24 hours (mm); attributes give each model's probabilities, mean and 90th percentile, and whether the models agree within 20 points |

Models are combined with equal weight, so WeatherNext 2's larger ensemble does not dominate. Every entity carries `experimental: true` and the notice "Experimental AI model output. Not an official warning." Whether Google's experimental real-time data terms carry through to WeatherNext 2 data served by Open-Meteo is **unverified**; that is why it has a separate toggle.

### Data licence and usage limits

Open-Meteo data are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ("Weather data by Open-Meteo.com"); flood data come from GloFAS (Copernicus) and AIFS from ECMWF (CC BY 4.0). Each entity's `attribution` names its sources. Open-Meteo's free API is for **non-commercial use only** and limited to 10,000 calls a day, 5,000 an hour and 600 a minute per IP ([terms](https://open-meteo.com/en/terms)). Large requests count as several calls, and ensemble requests count per member set. With all features on, one entry uses well under 1,000 weighted calls a day; adding a river point costs a one-off history request.

To change the state or location, use **Reconfigure** on the integration entry. Reconfigure also updates the options above, and renames the entry when the state or location changes.

---

## Dashboard Cards

The integration serves and registers its card suite automatically: one Lovelace resource, `/ausnz_disaster_watch/ausnz-disaster-card.js`, with no manual resource setup. All cards appear in the card picker (search for **Disaster Watch**) with a live preview, have a visual editor, size themselves in the sections view and follow your light or dark theme.

| Card | Type | Shows |
|---|---|---|
| Status | `custom:ausnz-disaster-status-card` | Highest Australian Warning System level, hazard count, nearest hazard and active alerts (emergency warning, hazards, power outage, road closure) |
| Incidents | `custom:ausnz-disaster-incidents-card` | Incidents nearest first with category filters (Fire, Flood & storm, Geological, Roads, Other), warning level, distance, last update and the agency's page |
| Warnings | `custom:ausnz-disaster-warnings-card` | Weather warnings and emergency news |
| Fire danger | `custom:ausnz-disaster-fire-danger-card` | Fire danger rating on the four-level AFDRS scale, district, forecast day and total fire ban |
| Power outages | `custom:ausnz-disaster-outages-card` | Outages, customers affected, cause and estimated restore time |
| Roads | `custom:ausnz-disaster-roads-card` | Road closures and hazards with status, advice and distance |
| Conditions | `custom:ausnz-disaster-conditions-card` | Local weather observation (temperature, feels like, humidity, wind, gust, pressure, rain since 9 am) and air quality |
| Relief | `custom:ausnz-disaster-relief-card` | Evacuation centres, places of refuge and sandbag stations, and links to nearby council disaster dashboards |
| Cameras | `custom:ausnz-disaster-cameras-card` | Flood and traffic camera snapshots, refreshed while visible |
| Map | `custom:ausnz-disaster-map-card` | Incidents on a map with your home zone and animated rain radar |
| All-in-one | `custom:ausnz-disaster-card` | A stack of the cards above in one card |

### Options

Every card has these options:

| Option | Default | Description |
|---|---|---|
| `device` | first Disaster Watch entry | The Disaster Watch device (one per configured location). Each card only shows data from this entry, so several locations never mix. |
| `title` | card name | Card heading. |

Card-specific options:

| Card | Option | Default | Description |
|---|---|---|---|
| Incidents | `max_items` | `10` | Rows shown before a **Show all** button. |
| Incidents | `show_planned_burns` | `false` | Show planned (hazard reduction) burns. They only reach the card when the integration option **Exclude hazard reduction burns** is off. |
| Incidents | `categories` | all | Any of `fire`, `flood_storm`, `geological`, `roads`, `other`. |
| Warnings, Power outages, Roads | `max_items` | `8` | Rows shown before a **Show all** button. |
| Cameras | `refresh_interval` | `60` | Seconds between snapshot refreshes (minimum 10). Snapshots only refresh while the card is on screen. |
| Map | `zoom` | fit incidents | Initial zoom level (1 to 18). |
| Map | `radar` | `true` | Animated RainViewer rain radar. |
| Map | `radar_opacity` | `0.7` | Radar layer opacity (0.1 to 1). |
| All-in-one | `cards` | `status`, `incidents`, `warnings`, `fire_danger`, `roads`, `outages` | Sections to stack, in order. Also available: `conditions`, `relief`, `cameras`, `map`. |

### Examples

```yaml
type: custom:ausnz-disaster-status-card
device: 0123456789abcdef0123456789abcdef
```

```yaml
type: custom:ausnz-disaster-incidents-card
device: 0123456789abcdef0123456789abcdef
max_items: 5
categories: [fire, flood_storm]
```

```yaml
type: custom:ausnz-disaster-card
title: Moreton Bay
cards: [status, map, incidents, warnings]
```

To show only this integration's events on Home Assistant's own map card instead:

```yaml
type: map
geo_location_sources:
  - ausnz_disaster_watch
```

Pick the device in the card editor rather than typing the ID. In the **sections** view the cards size themselves (the fire danger card defaults to half width, the map to six rows); you can resize them in the card's **Layout** tab.

### Map and radar

The map uses Home Assistant's own map tile service (OpenStreetMap data) and falls back to OpenStreetMap tiles on older cores. Rain radar comes from the free [RainViewer](https://www.rainviewer.com/) public API, which is free for personal and educational use and requires attribution; the credit is shown on the map. RainViewer's public tiles stop at zoom level 7, so radar is scaled up when you zoom in. The radar list is fetched at most every 10 minutes, the animation pauses when the card is off screen, and it does not autoplay if your device asks for reduced motion.

### Upgrading from the single card

**Breaking change:** the old single card was replaced by the card suite.

- `custom:aus-disaster-card` was removed. Change it to `custom:ausnz-disaster-card` (the all-in-one card) or use the focused cards.
- The all-in-one card's `max_incidents` and `show_map_button` options were removed and are ignored. Use the incidents card's `max_items` and the map card instead.
- The integration removes the old `/ausnz_disaster_watch/aus-disaster-card.js` resource automatically. If you manage Lovelace resources in YAML, delete that resource yourself.

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
