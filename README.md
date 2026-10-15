# Australian Disaster Watch for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/ruaandeysel/ha-australian-disaster-watch?style=flat-square)](https://github.com/ruaandeysel/ha-australian-disaster-watch/releases)
[![License](https://img.shields.io/github/license/ruaandeysel/ha-australian-disaster-watch?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz)

A comprehensive, real-time emergency disaster and hazard monitoring integration for Home Assistant across Australian jurisdictions.

Directly integrates official emergency feeds—including the **Queensland Fire Department (QFD)**, local council disaster dashboards (such as the **City of Moreton Bay Disaster Dashboard**), **NSW Rural Fire Service (NSW RFS)**, **Emergency Management Victoria (EMV OSOM)**, and **Bureau of Meteorology (BoM)** weather alerts—normalized under the **Australian Warning System (AWS)**.

---

## Key Features

- **Jurisdiction & Local Council Feeds**:
  - **Queensland**: Real-time QFD vegetation fire & emergency warnings feed + direct integration with Local Council Disaster Dashboards (**City of Moreton Bay**, Sunshine Coast, Gold Coast, Cairns, Townsville, Fraser Coast, etc.) covering fire incidents, road closures/hazards, power outages, and bulletins.
  - **New South Wales**: NSW RFS Major Incidents & SES data feeds.
  - **Victoria**: Emergency Management Victoria (EMV OSOM) feed covering fires, floods, storms, and health hazards.
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
  - Includes a custom Lovelace card (`aus-disaster-card`) that automatically registers with Home Assistant.
  - Features real-time threat banners, nearest distance counters, category filtering (Fires, Weather/Floods, Roads), and quick map navigation.

---

## Entity Overview

### Geolocation Platform (`geo_location`)
Renders interactive pins on the native Home Assistant Map for every active hazard in your perimeter.
- **Centroid Coordinates**: Precise latitude and longitude.
- **Attributes**: Warning level, hazard type, distance in km, responsible agency, status, and direct link to official incident documentation.
- **Dynamic Icons**: `mdi:fire` (Bushfire), `mdi:water-alert` (Flood), `mdi:weather-lightning` (Storm), `mdi:weather-hurricane` (Cyclone), `mdi:car-emergency` (Road Hazard), etc.

### Binary Sensors (`binary_sensor`)
| Entity | Description | Device Class |
| ------ | ----------- | ------------ |
| `binary_sensor.emergency_warning_nearby` | `on` when any Emergency Warning (Level 3) or Watch & Act (Level 2) is active in perimeter | `safety` |
| `binary_sensor.active_hazards_nearby` | `on` when any active incident is within perimeter | `problem` |

### Sensors (`sensor`)
| Entity | Description | Unit |
| ------ | ----------- | ---- |
| `sensor.nearest_hazard_distance` | Physical distance to closest active incident | `km` |
| `sensor.active_hazards_count` | Total active incidents in monitored perimeter | `hazards` |
| `sensor.highest_warning_level` | Highest AWS level currently active (`Emergency Warning`, `Watch and Act`, `Advice`, `All Clear`) | string |
| `sensor.nearest_hazard_title` | Headline of nearest incident | string |

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Enter repository URL: `https://github.com/ruaandeysel/ha-australian-disaster-watch`
4. Select Category: **Integration**
5. Click **Add**, then find **Australian Disaster Watch** and click **Download**.
6. **Restart Home Assistant**.

---

## Setup & Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Australian Disaster Watch**.
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

---

## Lovelace Dashboard Card

The integration automatically serves and registers the custom Lovelace card: `custom:aus-disaster-card`.

```yaml
type: custom:aus-disaster-card
title: Moreton Bay Disaster Watch
max_incidents: 10
show_map_button: true
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
trigger:
  - platform: state
    entity_id: binary_sensor.australian_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby
    to: "on"
action:
  - service: notify.notify
    data:
      title: "🚨 EMERGENCY WARNING ACTIVE"
      message: >-
        {{ state_attr('binary_sensor.australian_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby', 'highest_warning_level') }}:
        {{ state_attr('binary_sensor.australian_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby', 'nearest_incident_title') }}
        is currently {{ state_attr('binary_sensor.australian_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby', 'nearest_incident_distance') }} km away.
      data:
        push:
          sound: "critical"
```

### 2. Flash Red Lights on Emergency Warning
```yaml
alias: "Disaster Alert: Red Light Notification"
trigger:
  - platform: state
    entity_id: binary_sensor.australian_disaster_watch_qld_city_of_moreton_bay_emergency_warning_nearby
    to: "on"
action:
  - service: light.turn_on
    target:
      entity_id: light.living_room
    data:
      color_name: red
      flash: short
```

---

## Quality Scale & Standards

- **Strict Type Checking**: 100% compliant with Pyright type checking.
- **Modern Code Standards**: Linted and formatted with Ruff (`py313`).
- **Comprehensive Test Suite**: Tested with `pytest-homeassistant-custom-component`.
- **Database Safety Guardrail**: All entity attributes are strictly capped to ensure payloads remain well under the 16 KB SQLite threshold.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
