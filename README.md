<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/dark_logo@2x.png">
    <img alt="Disaster Watch for Australia and New Zealand" src="branding/logo@2x.png" width="480">
  </picture>
</p>

# Australia and New Zealand Disaster Watch for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](https://github.com/tinkerologie/ha-ausnz-disaster-watch/releases)
[![License](https://img.shields.io/github/license/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz)

Emergency warnings, incidents, fire danger, road closures, power outages, rivers and dams from official Australian and New Zealand feeds, normalised to the Australian Warning System and shown as Home Assistant entities, map pins and dashboard cards.

> [!IMPORTANT]
> **This is not an official warning service.** It polls public feeds every few minutes, a feed can be late or down, and coverage depends on what each agency publishes. Always follow the advice of your emergency services and check the official sources: in Australia your state's emergency service ([QLD](https://www.fire.qld.gov.au/Current-Incidents), [NSW](https://www.rfs.nsw.gov.au/fire-information/fires-near-me), [VIC](https://emergency.vic.gov.au), [SA](https://www.ses.sa.gov.au/warnings), [WA](https://www.emergency.wa.gov.au), [TAS](https://alert.tas.gov.au/), [ACT](https://esa.act.gov.au), [NT](https://securent.nt.gov.au/alerts)) and the [Bureau of Meteorology](https://www.bom.gov.au/australia/warnings); in New Zealand [Civil Defence](https://www.civildefence.govt.nz) and [MetService](https://www.metservice.com/warnings/home). In an emergency call **000** (Australia) or **111** (New Zealand).

## Contents

- [Features at a glance](#features-at-a-glance)
  - [Coverage](#coverage)
- [Installation](#installation)
- [Setup & configuration](#setup--configuration)
- [Entities](#entities)
- [Dashboard cards](#dashboard-cards)
- [Voice assistants](#voice-assistants)
- [Automation examples](#automation-examples)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Data sources & licences](#data-sources--licences)
- [Development](#development)
- [Quality scale](#quality-scale)
- [License](#license)

## Features at a glance

**Warnings and incidents**

- Official state and territory emergency feeds, Bureau of Meteorology (BoM) warnings in Australia, and GeoNet, NEMA (Civil Defence) and MetService in New Zealand (see [Coverage](#coverage)).
- 62 Queensland and 5 NSW council disaster dashboards (Guardian IMS): local incidents, road closures, power outages, relief centres, weather observations and cameras.
- Every warning mapped to the Australian Warning System: **Emergency Warning** (level 3, red), **Watch and Act** (level 2, orange), **Advice** (level 1, yellow), **Information** (level 0).
- A radius around your home zone or a fixed location (5 to 300 km), with an optional statewide (or New Zealand-wide) Emergency Warning override and planned burns left out by default.
- Warning areas: where an agency publishes a polygon, distances are to its edge and a binary sensor tells you when you are inside it.
- One map pin (`geo_location`) per incident, added and removed as the feeds change.
- Opt-in Geoscience Australia earthquakes for Australian entries.

**Fire, roads and power**

- Today's AFDRS fire danger rating with a 4-day outlook for your BoM fire weather district, and total fire bans where the agency publishes them. Fire season and Section 52 prohibitions in New Zealand.
- Road closures, flooded roads and road hazards from each state's official road feed and NZTA.
- Power outages from electricity distributors and council dashboards, with customers affected and estimated restore time.

**Water**

- Opt-in river and creek level gauges (QLD, NSW, ACT, NZ) with your own alert level per gauge.
- Opt-in dam and weir storage levels anywhere in Australia: percent full, volume, level and an "above full supply" sensor.

**Optional extras**

- Road and flood cameras (QLDTraffic, NZTA) as camera entities.
- National and regional feeds: tsunami warnings, satellite hotspots, heatwave severity, UV index, state air quality stations and GDACS regional disaster alerts.
- Model-derived forecast signals from Open-Meteo: damaging gusts, extreme heat, thunderstorm potential, a calculated fire danger index, river flood forecasts and an experimental AI heavy rain outlook. Never mixed with official warnings.
- The local emergency broadcaster (ABC Local Radio, RNZ) as a sensor and a media source.

**Dashboards and voice**

- Eleven Lovelace cards, registered automatically: status, incidents, warnings, fire danger, power outages, roads, conditions, relief, cameras, a map with animated rain radar, and an all-in-one card.
- Read-only tools for Assist and LLM conversation agents ("Is there anything I need to worry about near home?").

### Coverage

What an entry for each jurisdiction reads. Items in *italics* are opt-in; see [Options menu](#options-menu).

| Jurisdiction | Hazards and warnings | Fire danger and bans | Roads | Power | Rivers | Dams | Cameras | Extras |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QLD | Queensland Fire Department incidents and warning areas, QPS warning areas, council dashboards, BoM | BoM rating; no ban feed | QLDTraffic, council dashboards | Council dashboards (Energex, Ergon) | *WMIP, WaterNSW* | *BoM Water Data Online* | Council dashboards, *QLDTraffic* | Relief centres, *state air quality* |
| NSW | NSW RFS (with fire grounds), council dashboards, BoM | BoM rating, NSW RFS bans | Live Traffic NSW | Endeavour Energy, Essential Energy | *WaterNSW, WMIP* | *Water Data Online, WaterNSW* | Council dashboards, *QLDTraffic (near the border)* | Relief centres, *state air quality* |
| ACT | ACT ESA incidents, BoM | BoM rating, ACT ESA bans | None | Essential Energy | *WaterNSW* | *Water Data Online, WaterNSW* | None | *State air quality* |
| VIC | VicEmergency, BoM | BoM rating, CFA bans | *DTP (free key)* | None | None | *Water Data Online* | None | |
| SA | SA CFS and SES CAP feed, SA SES warning areas, BoM | BoM rating, SA CFS bans | Traffic SA | None | None | *Water Data Online* | None | |
| WA | Emergency WA warnings and incidents, BoM | BoM rating, Emergency WA bans (by local government area) | Main Roads WA | *Western Power* | None | *Water Data Online* | None | |
| TAS | TasALERT, BoM | BoM rating; no ban feed | TasALERT | TasNetworks | None | *Water Data Online, Hydro Tasmania* | None | |
| NT | Bushfires NT and NT Fire and Rescue Service, BoM | BoM rating; no ban feed | NT Road Report | None | None | *Water Data Online* | None | |
| NZ | GeoNet earthquakes and volcanoes, NEMA (Civil Defence), MetService | Fire and Emergency NZ fire season, Section 52 | NZTA | MainPower, *Powerco, Unison* | *8 regional councils* | None | *NZTA* | *Tsunami (PTWC), GDACS* |

Every Australian entry can also turn on *Geoscience Australia earthquakes*, *tsunami warnings (JATWC)*, *satellite hotspots*, *heatwave*, *UV index* and *GDACS regional alerts*. Every entry can turn on the *forecast signals* and the *emergency broadcaster*.

## Installation

Requires Home Assistant 2026.10.0 or newer.

### HACS (recommended)

1. Open **HACS** in Home Assistant.
2. Open the menu in the top right corner and choose **Custom repositories**.
3. Enter the repository URL `https://github.com/tinkerologie/ha-ausnz-disaster-watch` and select the category **Integration**.
4. Choose **Add**, then find **Australia and New Zealand Disaster Watch** and choose **Download**.
5. Restart Home Assistant.

### Manual

1. Download the source of the [latest release](https://github.com/tinkerologie/ha-ausnz-disaster-watch/releases).
2. Copy `custom_components/ausnz_disaster_watch` into the `custom_components` folder of your Home Assistant configuration directory.
3. Restart Home Assistant.

### Removal

1. Go to **Settings** > **Devices & services**, open **Australia and New Zealand Disaster Watch**, and choose **Delete** from the menu of each entry. Deleting an entry removes its device and entities; deleting the last entry also removes the dashboard card resource.
2. Remove any dashboard cards, automations and scripts that used the integration's entities.
3. To remove the files as well, open **HACS**, find **Australia and New Zealand Disaster Watch**, choose **Remove**, then restart Home Assistant (or delete `custom_components/ausnz_disaster_watch` after a manual install).

## Setup & configuration

### Initial setup

1. Go to **Settings** > **Devices & services** > **Add integration** and search for **Australia and New Zealand Disaster Watch**.
2. Fill in the first form:

   | Field | Default | Description |
   | --- | --- | --- |
   | State / Jurisdiction | Guessed from your home location | QLD, NSW, VIC, WA, SA, TAS, ACT, NT or NZ: whose feeds are read. Pick the one the monitored location is in. |
   | Location Source | Home location | **Use the Home Assistant home location** or **Specify a custom location (council or coordinates)**. See [Location](#location-home-zone-or-fixed). |
   | Monitoring Radius | 50 km | 5 to 300 km. Incidents, warnings, outages and road closures within it are reported. |
   | Statewide / National Emergency Warning Override | On | Also report every Emergency Warning anywhere in the state (or New Zealand), whatever its distance. |
   | Exclude Hazard Reduction / Planned Burns | On | Leave out planned and hazard reduction burns, so they do not raise alerts. |

3. With a custom location, the second form asks for the location: pick a council from the list (every Queensland and NSW council with a Guardian IMS disaster dashboard, sorted by name; Queensland entries start on City of Moreton Bay) or choose **Manual coordinates / custom URL** and enter a name, latitude, longitude and optionally a council dashboard URL. A council marked "no readable dashboard" only sets the location.
4. Before the entry is created, the integration fetches the state's emergency feeds (and, in Australia, the BoM warnings). If none of them answers, the form shows **None of the emergency feeds for this state answered**; check Home Assistant's internet connection and submit again. Reconfigure runs the same check.

Each entry watches one location and has one service device that holds all its entities. Add another entry for each extra location, for example a holiday house or a relative's home.

### Location: home zone or fixed

- **Home location**: the entry follows the Home Assistant home location. Its coordinates are not copied into the entry; every refresh uses the current home location. In Queensland and NSW the entry gets the disaster dashboard of the council its home location is in (a distance heuristic on each council's centre and size, not council boundaries). If that council has no readable dashboard, the nearest one within 40 km is used. You can change or clear it in **Monitoring settings**.
- **Fixed location**: a council preset or your own coordinates. The location does not move with the home zone.

### Council disaster dashboards

Council dashboards add local incidents, road closures, power outages, relief centres (evacuation centres, places of refuge, sandbag stations), weather observations, air quality and cameras.

- The council list (and the nearby council links the Relief card shows with `show_nearby_councils`) is generated by `script/update-councils` (a wrapper for `script/update_councils.py`) and refreshed by a monthly workflow, from the [Queensland Government list of council disaster dashboards](https://www.qld.gov.au/community/disasters-emergencies/disasters/resources-translations) and ABS Local Government Area data. It keeps only dashboards that answer as Guardian IMS; a dashboard listed before is kept when it does not answer during a run, unless the run uses `--prune`.
- NSW dashboards: Ballina, Blue Mountains, Byron, Hawkesbury and Northern Beaches.
- Eight Queensland dashboards (Barcoo, Gympie, Paroo, Redland, Richmond, Scenic Rim, Torres Strait Island and Yarrabah) send an incomplete TLS certificate chain. Browsers cope, but Home Assistant cannot connect, so they are listed as "no readable dashboard" until the councils fix them.
- Brisbane's ArcGIS emergency dashboard and Sunshine Coast's Disaster Hub are not read: their layers carry no licence (Brisbane: "Access to this information is intended to be through the Emergency Dashboard") and the Disaster Hub's robots.txt disallows `/api/`.

### Reconfigure

To change the state, location source, coordinates, name or council dashboard, choose **Reconfigure** on the integration entry. Reconfigure also sets the radius, override and planned burns options, and renames the entry when the state or location changes. Changing the coordinates of a home-location entry makes it a fixed location.

### Options menu

Choose **Configure** on the integration entry. The menu shows only the steps that apply to the entry's jurisdiction, in this order:

| Step | What it does | Default | Offered for |
| --- | --- | --- | --- |
| Monitoring settings | Radius, Emergency Warning override, exclude planned burns, council dashboard URL | 50 km, on, on, set at setup | All |
| Road closures | **Include planned roadworks and events**; the optional **VicRoads (DTP) open data API key** (Victoria). See [Roads](#road-closures-and-flooded-roads). | Off; no key | All but ACT and NZ |
| Power outages | **Include planned power outages**; **Extra power outage feeds** where an opt-in feed exists (WA, NZ). See [Power outages](#power-outages). | Off, off | NSW, ACT, TAS, WA, NZ |
| Forecast signals and AI rain outlook | Weather hazard signals with gust and heat thresholds, the AI rain outlook with its heavy rain threshold, and Google WeatherNext 2. See [Forecast signals](#forecast-signals-model-derived-not-official). | All off; 90 km/h, 40 °C, 50 mm | All |
| Earthquakes (Geoscience Australia) | Include Geoscience Australia earthquakes. See [Earthquakes](#earthquakes). | Off | Australian entries |
| National and regional feeds (optional) | Tsunami, satellite hotspots, heatwave, UV index, state air quality and GDACS. See [National and regional feeds](#national-and-regional-feeds). | All off | All (NZ: tsunami and GDACS; air quality: NSW, QLD, ACT) |
| Road and flood cameras (optional) | Camera networks, camera radius and maximum number of cameras. See [Cameras](#cameras). | No network; 25 km; 12 | QLD, NSW, NZ |
| Emergency broadcaster radio | Off, nearest station or a chosen station. See [Emergency broadcaster radio](#emergency-broadcaster-radio). | Off | All |
| Add a river flood forecast point | A named point for the GloFAS river flood forecast. See [River flood forecast](#river-flood-forecast). | None | All |
| Edit a river point, Remove river points | Change a point's threshold and horizon, or remove points | | Once a point exists |
| River and creek level gauges | Pick gauges, then set an optional alert level per gauge. See [River gauges](#river-and-creek-level-gauges). | None | QLD, NSW, ACT, NZ |
| Dam and weir storage levels | Pick storages. See [Dam and weir storages](#dam-and-weir-storage-levels). | None | Australian entries |

Saving any options step reloads the entry; no Home Assistant restart is needed.

## Entities

Entity IDs start with the device name, for example `binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby`. The tables below use `…` for that prefix. Every entity has an `attribution` attribute that names its sources.

### Hazards on the map (`geo_location`)

One map pin for every active hazard in your radius, shown on Home Assistant's own map.

- **Entity IDs**: `geo_location.ausnz_disaster_watch_<hazard_id>`, built from the agency's incident ID (not the headline), so the ID stays short and stable while the event lasts. The headline is the entity name.
- **Source**: every pin has `source: ausnz_disaster_watch`, whichever agency issued it, so one `geo_location` trigger or map card covers the whole integration. Filter on the `agency` attribute to pick out one agency.
- **Attributes**: `agency`, `responsible_agency`, `title`, `hazard_type`, `warning_level`, `location_name`, `distance_km`, `status`, `updated_at`, `expires`, `call_to_action`, `web_url` (the agency's page), `is_hazard_reduction`, `inside_area`, `in_council_area`, and `nearest_camera` (`entity_id`, `name`, `distance_km`) when a camera entity is within 5 km.
- **Icons** follow the hazard type: `mdi:fire` (bushfire), `mdi:grass` (grass fire), `mdi:water-alert` (flood), `mdi:weather-lightning` (storm), `mdi:weather-hurricane` (cyclone), `mdi:pulse` (earthquake), `mdi:volcano`, `mdi:tsunami`, `mdi:biohazard` (hazmat), `mdi:car-emergency` (road incident) and others.
- Pins hold only the centroid and scalar metadata, so attributes stay well under Home Assistant's 16 KB database limit. A pin is removed, with its entity registry entry, when the incident ends.

### Core binary sensors

| Entity | `on` when | Device class |
| --- | --- | --- |
| `binary_sensor.…_emergency_warning_nearby` | An Emergency Warning or Watch and Act is active in the radius. Attributes: `highest_warning_level`, `incident_count`, `nearest_incident_title`, `nearest_incident_distance` | `safety` |
| `binary_sensor.…_inside_warning_area` | The monitored location is inside the published area of an Advice, Watch and Act or Emergency Warning. Attributes: `warning_count`, and `warning_level`, `warning_title` and `call_to_action` of the most severe one | `safety` |
| `binary_sensor.…_active_hazards_nearby` | Any active incident is in the radius | `problem` |
| `binary_sensor.…_power_outage_active` | A power outage is reported nearby | `problem` |
| `binary_sensor.…_road_closure_nearby` | A road closure, flooded road or road hazard is reported nearby (planned roadworks and events never turn it on) | `problem` |
| `binary_sensor.…_flooded_road_nearby` | A flooded road is reported nearby. Attributes: `flooded_count` and the `nearest` five flooded roads | `safety` |
| `binary_sensor.…_total_fire_ban` | A total fire ban is declared today for your fire weather district (Australian entries only) | `safety` |

### Core sensors

| Entity | Description | Unit |
| --- | --- | --- |
| `sensor.…_highest_warning_level` | Highest Australian Warning System level in the radius (see [Warning levels](#warning-levels-and-enum-states)) | |
| `sensor.…_active_hazards_count` | Active incidents in the radius | `hazards` |
| `sensor.…_nearest_hazard_distance` | Distance to the closest active incident | `km` |
| `sensor.…_nearest_hazard_title` | Headline of the nearest incident | |
| `sensor.…_weather_warnings_count` | Active weather warnings (BoM, MetService and council dashboards) | `warnings` |
| `sensor.…_fire_danger_rating` | Today's AFDRS fire danger rating with a 4-day `forecast` attribute (see [Fire danger](#fire-danger-and-total-fire-bans)) | |
| `sensor.…_fire_season` | New Zealand entries only: fire season at your location | |
| `sensor.…_power_outages_count` | Power outages nearby (see [Power outages](#power-outages)) | `outages` |
| `sensor.…_power_outages_customers_affected` | Customers affected by those outages | `customers` |
| `sensor.…_road_closures_count` | Road closures, flooded roads and road hazards nearby, plus roadworks when enabled (see [Roads](#road-closures-and-flooded-roads)) | `closures` |
| `sensor.…_relief_facilities_count` | Evacuation centres and sandbag stations nearby (council dashboards) | `facilities` |
| `sensor.…_air_quality` | Air quality rating of the nearest station | |
| `sensor.…_local_weather_observation` | Temperature at the nearest weather station (council dashboards) | `°C` |

The air quality sensor reports the nearest station first. With **State air quality stations** turned on (NSW, QLD and ACT), it uses the state environment agency's stations and adds `distance_km`, `observed_at` and `source` attributes. A station with no current reading has an unknown rating, never "Good".

### Warning levels and ENUM states

The enum sensors have snake_case states, which automations use; the dashboard and history show them translated (for example "Watch and Act", "Extreme").

| Sensor | States |
| --- | --- |
| `…_highest_warning_level` | `emergency_warning`, `watch_and_act`, `advice`, `information`, `all_clear` (no incidents); `unknown` when the incidents have no known level |
| `…_fire_danger_rating` | `no_rating`, `moderate`, `high`, `extreme`, `catastrophic`; `unknown` when the district has no AFDRS rating |
| `…_fire_season` | `open`, `restricted`, `prohibited` |
| `…_heatwave_severity` | `none`, `low_intensity`, `severe`, `extreme` |
| `…_thunderstorm_potential_forecast` | `low`, `moderate`, `high`, `very_high` |

Hazard attributes (`warning_level`, the `highest_warning_level` attribute of `…_emergency_warning_nearby`) and the fire danger `forecast` days keep the English names (`Watch and Act`, `Extreme`).

### Warning areas

- Where an agency publishes a warning's area (QFD and QPS warning polygons, SA SES warnings, SA CFS CAP areas, Emergency WA warnings, TasALERT, NSW RFS fire grounds, BoM, NEMA and MetService CAP areas), `distance_km` is the distance to the nearest edge of the area, 0 when the monitored location is inside it, instead of the distance to a single point.
- `binary_sensor.…_inside_warning_area` and the `inside_warning_area` attribute of the highest warning level sensor tell you when you are inside a warning area. Each hazard has an `inside_area` attribute. Warnings published only as a point never count.
- Polygons are simplified (about 50 m, at most 400 vertices per hazard) and kept in memory only: they never appear in state attributes or diagnostics. A point in a hole of a polygon counts as inside.
- Not covered: NSW SES (its only feed, HazardWatch, allows personal non-commercial use only), VicEmergency polygons (EMV terms need written permission), ACT (its polygon feed has burnt areas only).

### Fire danger and total fire bans

**What it is**: today's AFDRS rating and a 4-day outlook for your BoM fire weather district, and the total fire ban declared by the state agency. New Zealand entries get the fire season instead.

**Enable**: always on (Australian entries: rating and ban; New Zealand entries: fire season).

| Entity | Description |
| --- | --- |
| `sensor.…_fire_danger_rating` | Today's rating: `no_rating`, `moderate`, `high`, `extreme`, `catastrophic` |
| `binary_sensor.…_total_fire_ban` | `on` when a total fire ban is declared today for your district (Australia) |
| `sensor.…_fire_season` | `open`, `restricted` or `prohibited` (New Zealand) |

**Attributes** of `…_fire_danger_rating`: `district_name`, `district_number` (BoM district code such as `NSW_FW008`), `date`, `fire_behaviour_index`, `total_fire_ban`, `forecast` (one entry per day: `date`, `rating`, `fire_behaviour_index`, `total_fire_ban`; `rating` keeps the display name such as `Extreme`), `issued_at`, `source` and `total_fire_ban_source`. `…_fire_season` has `section_52`, `section_52_comment` and `prohibited_activities` for any Section 52 prohibition (for example fireworks) covering the location.

**Updates**: at most every 30 minutes.

**How the district and rating are found**: your location is matched to its BoM fire weather district (bundled, simplified `IDM00007` boundaries, so border towns such as Albury and Wodonga or Queanbeyan and Canberra get their own district). The rating and outlook come from the BoM fire danger forecast for that state. Each forecast day is dated in the district's local time, so the sensor shows today's rating, also in the evening after the next day's forecast is issued. The last outlook is stored, so today's rating survives a restart; if no earlier forecast is known, today's rating comes from the state agency (NSW RFS, ACT ESA, CFA, SA CFS or Emergency WA) and `source` names it.

Total fire bans come from the agency that declares them:

| District | Total fire ban source |
| --- | --- |
| NSW | NSW RFS 4-day fire danger feed (falls back to `fdrToban.xml`, today and tomorrow) |
| ACT | ACT ESA fire danger feed (today and tomorrow) |
| VIC | CFA total fire ban and fire danger forecast RSS |
| SA | SA CFS fire danger and total fire ban feed |
| WA | Emergency WA total fire bans, matched to your local government area (ABS boundaries) |
| QLD, NT, TAS | No ban feed is read, so `…_total_fire_ban` is unknown. TasALERT's ban feed needs permission from TasALERT. |

**Notes**: a ban the source does not publish, or a source that cannot be read, is unknown, never `off`. Fire danger forecasts and district boundaries © Bureau of Meteorology; total fire bans © NSW RFS, ACT ESA, CFA, SA CFS and DFES WA; LGA boundaries © Australian Bureau of Statistics (CC BY 4.0); NZ fire seasons © Fire and Emergency New Zealand.

### Road closures and flooded roads

**What it is**: road closures, flooded roads and road hazards from each state's official open road feed, filtered to your radius.

**Enable**: on for every state with a road feed. The **Road closures** options step has:

- **Include planned roadworks and events** (off by default; not shown for ACT, which has no road feed, or New Zealand, whose NZTA feed never lists planned roadworks): lists planned roadworks and special events in `…_road_closures_count`. They never turn on `…_road_closure_nearby` or `…_flooded_road_nearby`.
- **VicRoads (DTP) open data API key** (Victoria only, optional): Victorian road data needs a free key. Register at [opendata.transport.vic.gov.au](https://opendata.transport.vic.gov.au/), subscribe to the *Unplanned Disruptions - Road* API, and paste the key. Leave it empty to skip Victorian road data. The key is stored in the entry options and redacted from diagnostics.

| Entity | Description |
| --- | --- |
| `sensor.…_road_closures_count` | Road items nearby; the `closures` attribute lists the nearest 25 with their `category` |
| `binary_sensor.…_road_closure_nearby` | `on` for a nearby `flooding`, `closure` or `hazard` item |
| `binary_sensor.…_flooded_road_nearby` | `on` for a nearby `flooding` item |

Every road item has a `category`:

| `category` | Meaning | Turns on `road_closure_nearby` | Turns on `flooded_road_nearby` |
| --- | --- | :---: | :---: |
| `flooding` | Flooded road or crossing, open or closed | yes | yes |
| `closure` | Road closed or impassable | yes | no |
| `hazard` | Unplanned incident or damage on an open road (crashes, debris, landslips, 4WD only) | yes | no |
| `roadworks` | Planned roadworks (listed only with the option on) | no | no |
| `special_event` | Planned special events (listed only with the option on) | no | no |

| State | Source | Key | Licence |
| --- | --- | --- | --- |
| NSW | [Live Traffic NSW](https://www.livetraffic.com) hazard feeds (incidents, floods, fires, alpine, council incidents; roadworks and major events with the option) | None | CC BY 4.0, Transport for NSW |
| QLD | [QLDTraffic](https://qldtraffic.qld.gov.au) `events_v2.geojson` (the keyless GeoJSON feed; the documented API needs a key) | None | CC BY 4.0, Department of Transport and Main Roads; council events are attributed to the council that provided them |
| VIC | DTP [Unplanned Disruptions - Road](https://opendata.transport.vic.gov.au/dataset/unplanned-disruptions-road) API v3 | Free DTP key | CC BY 4.0, Department of Transport and Planning |
| SA | [Traffic SA](https://www.traffic.sa.gov.au) open data (incidents and closures; roadworks with the option) | None | CC BY, Department for Infrastructure and Transport |
| WA | Main Roads WA WebEOC road incidents and closures (roadworks and events with the option) | None | CC BY 4.0, Commissioner of Main Roads |
| NT | [NT Road Report](https://roadreport.nt.gov.au) obstructions | None | Reuse terms not published; attributed to NT Road Report |
| TAS | [TasALERT](https://alert.tas.gov.au) road closures | None | Feed access by request (not yet granted), as for the TasALERT hazard feed |
| NZ | NZ Transport Agency Waka Kotahi road events | None | No licence stated on data.govt.nz |

**Updates**: with each hazard refresh, at most every 4 minutes.

**Notes**:

- Breakdowns, traffic signal faults, ferries, congestion and standing heavy-vehicle limits are not listed. Timestamps are converted from the agency's local time zone.
- A feed whose sources are all down keeps its last good items for up to 30 minutes. After that, or when any one source of a multi-source feed (for example one of the Live Traffic NSW files) has been down for more than 30 minutes, `…_road_closure_nearby` and `…_flooded_road_nearby` become unavailable rather than showing `off`; the remaining sources' items are still listed.
- QLD council dashboards still add council road closures. A council copy of an event already in the state feed (same QLDTraffic event ID, or the same road and suburb within 1 km) is listed once, with the state feed's details.
- ACT has no road feed yet. New Zealand categories are read from each NZTA event's impact and description, so a flooded NZ road also turns on `…_flooded_road_nearby`.

### Power outages

**What it is**: outages from the electricity distributors' own outage feeds and, in Queensland and NSW, from the council disaster dashboard (Energex and Ergon outages). Only outages in effect now count: planned work that has not started, and finished or cancelled outages, are left out.

**Enable**: the default feeds are on. In the **Power outages** options step, **Include planned power outages** adds planned outages that are in effect, and **Extra power outage feeds** turns on the feeds marked "Extra feeds" below.

| Distributor | Area | Feed | Terms | Default |
| --- | --- | --- | --- | --- |
| Endeavour Energy | Western Sydney, Blue Mountains, Illawarra | [Open data portal](https://data.endeavourenergy.com.au) (`outagecustomerlive`, `plannedoutagecustomer`), queried within the radius and grouped by incident (no street addresses) | [ODbL 1.0](https://www.opendatacommons.org/licenses/odbl/1.0/) | On |
| Essential Energy | Regional NSW, around the ACT | Outage map KML (`current.kml`) | No terms published | On |
| TasNetworks | Tasmania | Outage map JSON (`GetPowerOutages`) | No reuse terms published | On |
| MainPower | North Canterbury, Kaikōura | Outage map JSON (`/jobs`) | No terms published | On |
| Western Power | South-west WA | Outage map ArcGIS service, queried within the radius | [Personal, non-commercial use only](https://www.westernpower.com.au/terms--conditions/) | Extra feeds |
| Powerco | Taranaki, Whanganui, Manawatū, Wairarapa, Tauranga, Coromandel | Outage map ArcGIS service, queried within the radius | [No public or commercial use](https://www.powerco.co.nz/terms-of-use) | Extra feeds |
| Unison | Hawke's Bay, Taupō, Rotorua | Outage map JSON (about 2.6 MB) | No terms published | Extra feeds |

| Entity | Description |
| --- | --- |
| `sensor.…_power_outages_count` | Outages nearby |
| `sensor.…_power_outages_customers_affected` | Customers affected |
| `binary_sensor.…_power_outage_active` | `on` when an outage is reported nearby |

**Attributes** of `…_power_outages_count`: up to 25 outages, nearest first, each with `distributor`, `id`, `planned`, `status`, `start_time`, `restore_time` and `distance_km` (to the outage area's edge where the feed has polygons; 0 when home is inside it); `est_restore`, `nearest_outage_distance_km` and `nearest_outage_distributor` for the nearest outage; and `data_sources` with each feed's distributor, licence and attribution.

**Updates**: no feed is fetched more often than every 5 minutes (Unison every 15), also while threat polling runs every minute. Feeds without a radius query are only downloaded when the radius reaches the distributor's network.

**Notes**:

- Western Australia's only distributor feed is Western Power, so WA entries get distributor outages only with **Extra power outage feeds** on.
- Endeavour Energy data: "Contains information from Endeavour Energy Open Data, made available under the Open Database Licence (ODbL) v1.0". Outages are only kept in your own Home Assistant; the integration does not publish them.
- Not used: Energex and Ergon's own ArcGIS services (Energy Queensland's terms require a written agreement; their outages still come from council dashboards), Ausgrid (counts only, no reuse without permission), SA Power Networks, CitiPower, Powercor, United Energy, Jemena, AusNet, Evoenergy, Horizon Power, Power and Water, Vector (API key), Wellington Electricity, Orion, Aurora Energy and the Waikato network (terms or robots.txt rule out reuse, or no keyless feed).

### Earthquakes

**What it is**: Geoscience Australia earthquakes of magnitude 3 or more from the last 48 hours, within your radius, as hazards and map pins. Magnitude 6 or more is Watch and Act, 4.5 or more Advice, smaller Information.

**Enable**: **Configure** > **Earthquakes (Geoscience Australia)**; off by default. Australian entries only: New Zealand entries always get GeoNet earthquakes (with GeoNet's CAP quake alerts) and volcanic alert levels.

**Notes**: earthquake data © Commonwealth of Australia (Geoscience Australia), from [earthquakes.ga.gov.au](https://earthquakes.ga.gov.au/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

### Cameras

**What it is**: flood and traffic camera snapshots near the monitored location as `camera` entities. The council dashboard's cameras (QLD and NSW council dashboards) are always included; road agency cameras are opt-in:

- **QLDTraffic flood cameras** and **QLDTraffic web cameras** for Queensland entries (and NSW entries near the border).
- **NZ Transport Agency traffic cameras** for New Zealand entries; cameras that are offline or under maintenance are left out.

**Enable**: **Configure** > **Road and flood cameras (optional)**. Pick the networks (none by default), the **camera radius** (default 25 km; cameras must also be inside the monitoring radius) and the **maximum number of cameras** (default 12, up to 50, nearest first), so a city entry does not get hundreds of entities.

**Attributes**: `direction`, `distance_km` and `network`. A camera's `attribution` names its network and, where the feed says, who supplies the image.

**Updates**: camera lists are downloaded at most every 6 hours; an image is fetched only when you view the camera.

**Notes**:

- Only real images are shown: if a camera host answers with an error page instead of a picture, the camera keeps its last good image.
- When a camera is within 5 km of an incident, the incident's map pin gets a `nearest_camera` attribute and the Incidents card shows a camera button next to the incident.
- Live Traffic NSW cameras are not available: their image server refuses requests that do not come from a web browser, and the integration does not pretend to be one.

### River and creek level gauges

**What it is**: one water level sensor per river or creek gauge you pick, with an optional alert level.

**Enable**: **Configure** > **River and creek level gauges** (QLD, NSW, ACT and NZ). The form lists up to 10 of the nearest gauges within the monitoring radius that reported a level in the last 6 hours, with distance and current level. Finding them can take up to a minute the first time; the site lists are then cached for 24 hours. Tick the gauges you want and submit. The next form takes an optional alert level in metres per gauge, on the same datum as its level (for example the minor flood level from your council or the BoM). Leave it blank for no alert sensor.

| Entity | Description |
| --- | --- |
| `sensor.…_<gauge name>_water_level` | Water level in metres (`device_class: distance`, `state_class: measurement`) above the gauge's own datum, not above sea level. Readings in mm or cm are converted to metres. Example: `sensor.australia_and_new_zealand_disaster_watch_qld_home_brisbane_river_at_savages_crossing_water_level` |
| `binary_sensor.…_<gauge name>_above_alert_level` | `on` while the level is at or above the alert level you set (`device_class: problem`). Attributes: `alert_level_m`, `level_m`, `site_id` |

**Attributes** of the level sensor: `site_id`, `source`, `latitude`, `longitude`, `distance_km` (from your location), `observed_at` (time of the reading, UTC), `trend` (`rising`, `falling` or `steady`, or `null` when there is no reading an hour before the latest one) and `change_1h_m` (the level change behind the trend, compared with the newest reading at least an hour older; changes within 1 cm are `steady`).

**Updates**: every 15 minutes.

**Notes**:

- A gauge without a reading in the last 6 hours is unavailable. If a gauge service cannot be reached, its last reading is kept until it is 6 hours old.
- Gauges stay selected until you untick them; unticked gauges' entities are removed, and clearing an alert level removes its sensor.
- None of the gauge services publishes minor, moderate or major flood levels, so there are no built-in thresholds. Data is provisional and unvalidated.
- Queensland and NSW locations search both Kisters services, so gauges across the border are found too.

| Region | Source | Licence |
| --- | --- | --- |
| Queensland | [Water Monitoring Information Portal](https://water-monitoring.information.qld.gov.au/) (Kisters Hydstra web service, telemetered stream gauges) | CC BY 4.0, stated in every response |
| New South Wales and ACT | [WaterNSW real-time data](https://realtimedata.waternsw.com.au/) (Kisters Hydstra web service) | Listed as CC BY on data.gov.au/SEED (version 3.0 or 4.0 differs between listings) |
| New Zealand | Regional council Hilltop servers: Greater Wellington, Horizons, Hawke's Bay, Tasman, Northland, West Coast, Taranaki and Marlborough (measurement `Stage`) | Hawke's Bay: CC BY. Others: public, keyless servers; licence not stated |

Not supported: Environment Canterbury (no sites returned, site behind a bot wall), Waikato (times out), Bay of Plenty, Otago and Nelson (no public Hilltop server found), Southland and Gisborne (server errors), Victoria and the other states (no source yet). Groundwater bores on the Hilltop servers are not offered.

### Dam and weir storage levels

**What it is**: percent full, volume and level of the dams and weirs you pick, anywhere in Australia, and whether each is above full supply.

**Enable**: **Configure** > **Dam and weir storage levels** (Australian entries). The form lists up to 15 of the nearest storages that reported in the last 7 days, with distance and percent full. It searches the monitoring radius, but at least 150 km, because the dams that flood a town are often well upstream (Wivenhoe is 65 km from Brisbane). The first search can take up to 90 seconds; the storage list is then cached for 24 hours. Tick the storages you want and submit.

| Entity | Description |
| --- | --- |
| `sensor.…_<storage>_percent_full` | Volume as a share of full supply volume, in %. It goes **above 100%** when a dam holds more than its full supply, for example when Wivenhoe or Somerset are using their flood storage compartment. Example: `sensor.australia_and_new_zealand_disaster_watch_qld_home_wivenhoe_percent_full` |
| `sensor.…_<storage>_volume` | Volume in megalitres (ML) |
| `sensor.…_<storage>_level` | Water level in metres, usually above sea level (AHD) |
| `binary_sensor.…_<storage>_above_full_supply` | `on` while the storage is above 100% of full supply volume, above full supply level, or reported spilling by its operator (WaterNSW spillway discharge in the last daily total, or Hydro Tasmania's "Spilling"). An ungated dam above full supply is spilling; a gated flood-mitigation dam above full supply is holding flood water that it will release. |

**Attributes** (on all four): `site_id`, `latitude`, `longitude`, `distance_km`, `full_supply_volume_ml`, `full_supply_level_m`, `observed_at` (time of the reading, UTC), `percent_full`, `volume_ml`, `level_m`, `change_24h_ml` (volume change since the reading closest to 24 hours earlier, taken 18 to 36 hours before the latest; `null` without one), `above_full_supply`, `source` and, for operator-matched storages, the operator attributes below.

**Updates**: every hour. A storage without a reading in the last 7 days is unavailable; if Water Data Online cannot be reached, the last readings are kept until they are 7 days old, and operator readings still update them. Storages stay selected until you untick them.

**Operator feeds (NSW, ACT and Tasmania)**: WaterNSW and Hydro Tasmania publish their own storage data under CC BY. When you pick a storage they operate, it is matched to their feed and the match is stored with it, so the sensors use the fresher data. Storages picked before this feature need the step opened and saved once to be matched.

- **WaterNSW** (NSW storages, including the Sydney dams, Hume and Blowering): the level comes from the WaterNSW gauge, updated every 15 to 60 minutes, instead of the BoM's day-old value. `spillway_24h_ml` and `release_24h_ml` are the spillway discharge and total releases in ML for the last 24 hours to 9 am (`totals_date`), and `spilling` is on when the spillway discharged. Percent full and volume stay the BoM's, because WaterNSW's own storage tables differ by a few per cent from the BoM's full supply volume. A gauge is matched only when it is within 30 km and its level and volume agree with the BoM's.
- **Hydro Tasmania** (its hydro lakes): `metres_below_full` and `spilling` from Hydro Tasmania's daily lake table, matched by lake name.
- `source` says where a storage's level comes from: `waternsw` for a matched WaterNSW gauge with a newer reading, otherwise `bom`. Hydro Tasmania storages always report `bom`, because Hydro Tasmania publishes no level or volume. `operator_observed_at` gives the operator's reading time. If an operator feed is down, the BoM's data is used alone.

| Region | Source | Licence |
| --- | --- | --- |
| All Australian states and territories | [BoM Water Data Online](https://www.bom.gov.au/waterdata/) (KiWIS web service), with data supplied by Seqwater, WaterNSW, Sunwater, Melbourne Water, Goulburn-Murray Water, SA Water, Water Corporation, Hydro Tasmania, Icon Water, Power and Water and other water agencies | CC BY 3.0 AU per data owner ([owner list](https://www.bom.gov.au/waterdata/wiski-web-public/copyright.htm)). Storages of owners with other terms (Snowy Hydro, Gosford City Council) are not offered |
| New South Wales and ACT | [WaterNSW real-time data](https://realtimedata.waternsw.com.au/) storage gauges (level, daily spillway discharge and releases) | CC BY, as the river gauges |
| Tasmania | [Hydro Tasmania lake levels](https://www.hydro.com.au/water/water-information) (metres from full, "Spilling") | CC BY 3.0 AU |

> [!WARNING]
> **These sensors are not a dam release warning.** Water agencies send their data to the BoM about once a day, so the BoM's readings are usually **12 to 48 hours old**. WaterNSW levels are current to within an hour, but its spill and release figures are daily totals to 9 am, and Hydro Tasmania's table is daily. During a flood, a dam can start releasing well before these sensors change. **The BoM's flood warnings, which this integration already reports as hazards, remain the release signal.** For releases, also sign up to the dam operator's notifications (for example the [Seqwater Dam Release Notification Service](https://www.seqwater.com.au/dam-release-notification-service)).
>
> Release notices are not read: none is published in a form the integration may reuse. Seqwater (all rights reserved), the WaterNSW release notifications via the Early Warning Network (whose terms ban automated tools), Sunwater (prior written consent) and the NZ operators Mercury and Genesis are listed under permission requests in the data source register. Seqwater, Sunwater and Melbourne Water live levels are not licensed for reuse, so their storages use the BoM's data. New Zealand has no openly licensed live source yet.

### National and regional feeds

**What it is**: optional national and regional context feeds. None of them add hazards, so they do not change the hazard counts, warning levels, map pins or polling rate.

**Enable**: **Configure** > **National and regional feeds (optional)**; each feed is off by default and adds its entity when turned on. New Zealand entries are offered tsunami warnings and GDACS only; state air quality is offered for NSW, QLD and ACT.

| Entity | Description | States / unit | Jurisdictions |
| --- | --- | --- | --- |
| `binary_sensor.…_tsunami_warning` | `on` while a tsunami watch or warning applies, or a tsunami hazard is in range. Attributes: `threat_level` (`no_threat`, `watch`, `marine`, `land`), headline, expiry and the products checked | `safety` | AU: JATWC. NZ: PTWC guidance (official NZ warnings come from NEMA) |
| `sensor.…_satellite_hotspots_nearby` | Satellite heat detections in the last 24 hours within the radius, with confidence of at least 50. Hotspots are not fire warnings | `hotspots` | AU |
| `sensor.…_heatwave_severity` | Highest current BoM heatwave warning in your state, with each district's severity as an attribute | `none`, `low_intensity`, `severe`, `extreme` | AU |
| `sensor.…_uv_index` | UV index at the nearest ARPANSA station, with the BoM sun protection forecast for that station | UV index | AU |
| `sensor.…_regional_disaster_alerts` | Current GDACS Orange and Red alerts around Australia and New Zealand. Context only; they never count as local warnings | `alerts` | AU, NZ |
| `sensor.…_air_quality` (state stations) | Uses the state environment agency's stations; see [Core sensors](#core-sensors) | | NSW, QLD, ACT |

**Notes**: an entity is unavailable while its source cannot confirm a state, so a failed feed never shows as all clear. Sources: JATWC tsunami CAP products (`IDY680nn`), BoM heatwave (`IDx21013`, ACT `IDN21014`) and UV forecast (`IDZ00107`–`IDZ00113`) products from the BoM anonymous FTP; the NOAA PTWC Atom and CAP feed; the Digital Earth Australia Hotspots WFS (Geoscience Australia), queried by bounding box; ARPANSA real-time UV (`uvvalues.xml`); GDACS RSS (read with `aio-georss-gdacs`); the NSW DCCEEW air quality API, the Queensland Government air quality XML feed and ACT Government open data (dataset `94a5-zqnn`). Licences and conditions are in [Data sources & licences](#data-sources--licences); notably the BoM tsunami, heatwave and UV products and ARPANSA UV observations are for personal, non-commercial use, and ARPANSA asks to be credited ("UV observations courtesy of ARPANSA") and to be told that the data is used.

### Forecast signals (model-derived, not official)

Three optional features use [Open-Meteo](https://open-meteo.com/) model forecasts. **All are off by default** and fetch nothing until you turn them on under **Configure** > **Forecast signals and AI rain outlook** (river points have their own menu steps). They are separate from agency warnings: they are plain sensors with `official: false`, never `geo_location` hazards, never counted in the hazard sensors, and never mapped to Australian Warning System levels or to the official fire danger rating. **They do not replace BoM, MetService or emergency service warnings.**

Each feature polls on its own schedule with one request per poll; a failed fetch makes only that feature's entities unavailable and is retried after 30 minutes.

#### Weather hazard signals

**Enable**: **Weather hazard signals**, with the **Damaging gust threshold** (default 90 km/h, BoM's damaging wind criterion; 50 to 150) and **Extreme heat threshold** (default 40 °C apparent temperature; 30 to 50). **Updates**: every hour, from the Open-Meteo Forecast API (best-match model) for the next 24 hours from the current hour.

| Entity | Meaning |
| --- | --- |
| `sensor.…_max_wind_gust_forecast_24h` | Highest forecast 10 m gust (km/h) |
| `binary_sensor.…_damaging_gusts_forecast` | `on` when that gust reaches the gust threshold |
| `sensor.…_max_apparent_temperature_forecast_24h` | Highest forecast apparent temperature (°C) |
| `binary_sensor.…_extreme_heat_forecast` | `on` when that temperature reaches the heat threshold |
| `sensor.…_thunderstorm_potential_forecast` | `low`, `moderate`, `high` or `very_high` |
| `sensor.…_calculated_fire_danger_index_not_official` | Calculated McArthur FFDI (not official) |

- **Thunderstorm potential** is a project heuristic, not a BoM category. Each hour is rated from CAPE and precipitation probability together: very high at CAPE ≥ 2500 J/kg and ≥ 40 %, high at ≥ 1000 J/kg and ≥ 30 %, moderate at ≥ 500 J/kg and ≥ 20 %. A model thunderstorm weather code (WMO 95, 96, 99) makes the hour at least high. It ignores wind shear and convective inhibition. Open-Meteo's `lightning_potential` is not used because it is empty for Australia and New Zealand.
- **Calculated fire danger index** uses the McArthur Mk5 FFDI in the Noble et al. (1980) form, `FFDI = 2·exp(−0.450 + 0.987·ln D − 0.0345·RH + 0.0338·T + 0.0234·V)`, with mean 10 m wind (not gusts). The drought factor `D` is **experimental and not validated**: Griffiths (1999) with the soil dryness index replaced by a 20-day proxy (FAO reference evapotranspiration minus effective rain, the part of each rain event above its first 5 mm, clamped to 0–203.2 mm). The past 20 days are archived model values, not gauge observations. It is not an AFDRS rating; the official rating stays in the fire danger rating sensor.
- **Attributes**: `source`, `model` (`best_match`), `forecast_issued_at` (when the forecast was fetched; Open-Meteo does not report a run time for best match), `window_start`, `window_end`, `peak_time` and the values behind each signal.

#### River flood forecast

**Enable**: **Configure** > **Add a river flood forecast point** (up to 10 named points); **Edit a river point** and **Remove river points** appear once a point exists. **Updates**: every 6 hours, from the Open-Meteo Flood API (GloFAS v4, about 5 km river grid). All points are fetched in one request; GloFAS updates daily.

| Entity | Meaning |
| --- | --- |
| `sensor.…_river_discharge_<name>` | Today's (UTC) ensemble-mean discharge (m³/s). Attributes: `forecast` (7 days of mean, max and p75), `p75`, `trend` (rising, steady or falling over the horizon, 10 % band) |
| `binary_sensor.…_river_flood_risk_<name>` | `on` when the ensemble maximum (`river_discharge_max`, the wettest ensemble member) on any day within the horizon (1 to 7 days, default 3) exceeds the point's threshold |

- When you add a point, the integration checks that it has GloFAS data. A point in a city centre or by a small creek can fall outside the river grid; it then checks 16 neighbouring cells (0.05° and 0.1° away, in one request) and suggests the one with the largest discharge. This neighbour search is the integration's own heuristic.
- The default threshold is the cell's **median annual peak discharge** over the last 20 years of the GloFAS reanalysis (about a 2-year flood; GloFAS's own flood alerts use return-period thresholds like this). It is fetched once when the point is added; you can override it with a local flood level in m³/s. `river_discharge_p75` is the 75th percentile across ensemble members, not a historical percentile.

#### Experimental AI ensemble rain outlook

**Enable**: **Experimental AI ensemble rain outlook (ECMWF AIFS)**, with the **Heavy rain threshold** (default 50 mm in 24 hours; 5 to 500) and, behind its own toggle (off by default), **Also use Google WeatherNext 2**. **Updates**: every 6 hours. ECMWF AIFS has 51 members and a new run every 6 hours; WeatherNext 2 has 64 members and a new run every 12 hours. Only models with a new run are requested, together in one request.

| Entity | Meaning |
| --- | --- |
| `sensor.…_experimental_ai_heavy_rain_probability_24h` | Share of members (%) with a next-24-hour total at or above the threshold |
| `sensor.…_experimental_ai_heavy_rain_probability_72h` | Share of members with any rolling 24-hour total in the next 72 hours at or above the threshold |
| `sensor.…_experimental_ai_rain_outlook` | Ensemble-mean rain in the next 24 hours (mm); attributes give each model's probabilities, mean and 90th percentile, and whether the models agree within 20 points |

Models are combined with equal weight, so WeatherNext 2's larger ensemble does not dominate. Every entity carries `experimental: true` and the notice "Experimental AI model output. Not an official warning." Whether Google's experimental real-time data terms carry through to WeatherNext 2 data served by Open-Meteo is **unverified**; that is why it has a separate toggle.

#### Open-Meteo licence and usage limits

Open-Meteo data are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ("Weather data by Open-Meteo.com"); flood data come from GloFAS (Copernicus) and AIFS from ECMWF (CC BY 4.0). Each entity's `attribution` names its sources. Open-Meteo's free API is for **non-commercial use only** and limited to 10,000 calls a day, 5,000 an hour and 600 a minute per IP ([terms](https://open-meteo.com/en/terms)). Large requests count as several calls, and ensemble requests count per member set. With all features on, one entry uses well under 1,000 weighted calls a day; adding a river point costs a one-off history request.

### Emergency broadcaster radio

**What it is**: in Australia, ABC Local Radio is the official emergency broadcaster: warnings tell you to "listen to ABC Local Radio", and local stations switch to emergency coverage. In New Zealand, RNZ is a lifeline broadcaster. Radio often keeps working when power or mobile networks are under strain.

**Enable**: **Configure** > **Emergency broadcaster radio**; off by default. Choose **Nearest station**, or pick a station yourself: the nearest station is matched by its studio location, which is not always the station that covers your town.

| Entity | Description |
| --- | --- |
| `sensor.…_emergency_broadcaster` | The station name. Disabled by default: enable it in the entity settings. It stays available when the hazard feeds are down |

**Attributes**: `stream_url`, `media_content_id`, `region`, `network`, `station_page`, `selection` (`nearest` or `chosen`) and `distance_km`.

**Media browser**: **Media** > **Australia and New Zealand Disaster Watch** lists the emergency broadcaster of each location. `media-source://ausnz_disaster_watch/emergency_broadcaster/<entry_id>` always plays the location's current station, so automations keep working if you move house or change the station. See [automation example 4](#4-play-the-emergency-broadcaster-on-an-emergency-warning).

**Notes**:

- Stations: all 52 ABC Local Radio regions and RNZ National, as HTTPS HLS streams. The table is bundled (`data/emergency_broadcasters.json`, built by `script/update-broadcasters` from the public-domain [Radio Browser](https://www.radio-browser.info/) directory and checked against the ABC and RNZ station pages), so nothing is looked up at runtime.
- Your media player streams directly from the ABC or RNZ for your personal listening; the integration does not proxy or record audio.
- Not included: AM/FM frequencies for battery radios (no open machine-readable source yet).

## Dashboard cards

The integration serves and registers its card suite automatically: one Lovelace resource, `/ausnz_disaster_watch/ausnz-disaster-card.js`, with no manual resource setup. All cards appear in the card picker (search for **Disaster Watch**) with a live preview, have a visual editor, size themselves in the sections view and follow your light or dark theme.

| Card | Type | Shows |
| --- | --- | --- |
| Status | `custom:ausnz-disaster-status-card` | Highest Australian Warning System level, hazard count, nearest hazard and active alerts (emergency warning, hazards, power outage, road closure) |
| Incidents | `custom:ausnz-disaster-incidents-card` | Incidents nearest first with category filters (Fire, Flood & storm, Geological, Roads, Other), warning level, distance, last update and the agency's page |
| Warnings | `custom:ausnz-disaster-warnings-card` | Weather warnings and emergency news |
| Fire danger | `custom:ausnz-disaster-fire-danger-card` | Fire danger rating on the four-level AFDRS scale, district, forecast day and total fire ban |
| Power outages | `custom:ausnz-disaster-outages-card` | Outages, customers affected, cause and estimated restore time |
| Roads | `custom:ausnz-disaster-roads-card` | Road closures and hazards with status, advice and distance |
| Conditions | `custom:ausnz-disaster-conditions-card` | Local weather observation (temperature, feels like, humidity, wind, gust, pressure, rain since 9 am) and air quality |
| Relief | `custom:ausnz-disaster-relief-card` | Evacuation centres, places of refuge and sandbag stations, and a link to your council's disaster dashboard (optionally the neighbouring councils' too) |
| Cameras | `custom:ausnz-disaster-cameras-card` | Flood and traffic camera snapshots, refreshed while visible |
| Map | `custom:ausnz-disaster-map-card` | Incidents on a map with your home zone and animated rain radar |
| All-in-one | `custom:ausnz-disaster-card` | A stack of the cards above in one card |

### Common options

Every card has these options:

| Option | Default | Description |
| --- | --- | --- |
| `device` | First Disaster Watch entry | The Disaster Watch device (one per configured location). Each card only shows data from this entry, so several locations never mix. Pick it in the card editor rather than typing the ID. |
| `title` | Card name | Card heading. |

### Your council or the whole radius

The integration looks up the boundary of the council your location is in (Australia: the ABS local government area; New Zealand: the Stats NZ territorial authority), once per location, and marks every listed item with a location as inside or outside it. Cards with an `area` option use that to show only your council:

| Card | `area` default | Why |
| --- | --- | --- |
| Relief, Roads, Power outages, Cameras | `council` | Local services: your council's evacuation centres, roads, outages and cameras. |
| Incidents, Map, Status | `radius` | A fire or flood just over the council border can still reach you, so hazards default to everything within the integration's radius. Switch to `council` if you only want your council's. |

- `council` shows the council's name under the card title. Items without a location are always shown.
- While the boundary is unknown (the lookup has not answered yet, or your location is outside every council), `council` shows everything within the radius with a short note.
- Only the cards change. Every sensor, binary sensor and count used by automations stays radius-based, so a hazard just over the border still turns on **Emergency Warning Nearby**. The Status card's alert chips are those binary sensors, so they stay radius-based in `council` mode too.
- The Warnings card has no `area` option: BoM and MetService weather warnings carry no location the integration could test against the boundary (warnings with an area become incidents, which the Incidents card can filter).
- The boundary is generalised to about 100 m and ABS local government areas approximate the gazetted boundaries, so an item within about 100 m of the border can land on either side.
- In `council` mode the lists show the council's items among the nearest 25 items the sensors list; the counts are the council's own (`council_area_count` attributes).

### Card options

| Card | Option | Default | Description |
| --- | --- | --- | --- |
| Relief, Roads, Power outages, Cameras | `area` | `council` | `council` or `radius`; see [Your council or the whole radius](#your-council-or-the-whole-radius). |
| Incidents, Map, Status | `area` | `radius` | `council` or `radius`; see [Your council or the whole radius](#your-council-or-the-whole-radius). |
| Incidents | `max_items` | `10` | Rows shown before a **Show all** button. |
| Incidents | `show_planned_burns` | `false` | Show planned (hazard reduction) burns. They only reach the card when the integration option **Exclude Hazard Reduction / Planned Burns** is off. |
| Incidents | `categories` | All | Any of `fire`, `flood_storm`, `geological`, `roads`, `other`. |
| Warnings, Power outages, Roads | `max_items` | `8` | Rows shown before a **Show all** button. |
| Cameras | `refresh_interval` | `60` | Seconds between snapshot refreshes (minimum 10). Snapshots only refresh while the card is on screen. |
| Map | `zoom` | Fit incidents | Initial zoom level (1 to 18). |
| Map | `radar` | `true` | Animated RainViewer rain radar. |
| Map | `radar_opacity` | `0.7` | Radar layer opacity (0.1 to 1). |
| Map | `satellite_layer` | `none` | Satellite imagery under the incidents: `himawari_visible` (daytime clouds, every 10 minutes), `himawari_ir` (clouds day and night, every 10 minutes), `viirs_truecolor` (daily true colour image: smoke, burn scars, flood extent) or `none`. |
| Map | `show_cyclone_tracks` | `false` | Draw the GDACS forecast track, wind areas and uncertainty cone of current cyclones listed by the Regional Disaster Alerts sensor. Needs the integration option **Regional disaster alerts (GDACS)**. |
| Relief | `show_nearby_councils` | `false` | Also link to the disaster dashboards of up to six neighbouring councils, below **Council dashboard**. Off, the card links only to the council dashboard the entry reads: your council's, or the nearest readable one when your council has none that Home Assistant can read (none when the entry has no council dashboard). |
| All-in-one | `cards` | `status`, `incidents`, `warnings`, `fire_danger`, `roads`, `outages` | Sections to stack, in order. Also available: `conditions`, `relief`, `cameras`, `map`. |
| All-in-one | `show_nearby_councils` | `false` | Passed to the relief section (see Relief above). |

In the **sections** view the cards size themselves (the fire danger card defaults to half width, the map to six rows); you can resize them in the card's **Layout** tab.

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

### Map, radar and satellite layers

- **Base map**: Home Assistant's own map tile service (OpenStreetMap data), falling back to OpenStreetMap tiles on older cores.
- **Rain radar** comes from the free [RainViewer](https://www.rainviewer.com/) public API, which is free for personal and educational use and requires attribution; the credit is shown on the map. RainViewer's public tiles stop at zoom level 7, so radar is scaled up when you zoom in. The radar list is fetched at most every 10 minutes, the animation pauses when the card is off screen, and it does not autoplay if your device asks for reduced motion.
- **Satellite imagery** (`satellite_layer`, off by default) comes from [NASA GIBS](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance), which needs no key:
  - **Himawari** visible and infrared show clouds and storms where radar has no coverage (inland and offshore). They animate on the same timeline as the radar: each radar frame shows the satellite image taken at or before it. With the radar off, the satellite frames animate on their own. Reduced motion shows the latest frame only. Himawari-9 belongs to the Japan Meteorological Agency, which is credited on the map.
  - **VIIRS true colour** is one image a day, useful the day after an event for smoke plumes, burn scars and flood extent. Chips under the map pick today, yesterday or the day before (UTC dates). Before 09:00 UTC today's image does not yet cover Australia and New Zealand, so yesterday's is shown first.
- **Cyclone tracks** (`show_cyclone_tracks`, off by default) are drawn from GDACS for each current tropical cyclone in the Regional Disaster Alerts sensor: the observed and forecast track (dashed), the wind areas and the uncertainty cone. The card fetches only GDACS tropical cyclone geometry links. GDACS output is an automatic model estimate, so the map says so: follow BoM and MetService warnings.

Chips under the map hide or show the satellite layer and cyclone tracks. The attribution on the map lists only the layers that are on. Your browser fetches the radar, satellite and cyclone data directly, not Home Assistant; see the [data source register](docs/development/DATA_SOURCES.md#shown-in-the-card-fetched-by-the-browser).

### Upgrading from the single card

**Breaking change:** the old single card was replaced by the card suite.

- `custom:aus-disaster-card` was removed. Change it to `custom:ausnz-disaster-card` (the all-in-one card) or use the focused cards.
- The all-in-one card's `max_incidents` and `show_map_button` options were removed and are ignored. Use the Incidents card's `max_items` and the Map card instead.
- The integration removes the old `/ausnz_disaster_watch/aus-disaster-card.js` resource automatically. If you manage Lovelace resources in YAML, delete that resource yourself.

## Voice assistants

The integration gives Assist, and any LLM conversation agent that uses the Assist API (OpenAI, Anthropic, Google, Ollama and others), three read-only tools. You can then ask questions such as "Is there anything I need to worry about near home?", "What's the fire danger tomorrow?" or "Are any roads closed nearby?".

| Tool | What it answers |
| --- | --- |
| `ausnz_disaster_watch__get_disaster_situation` | The highest warning level, active warnings and incidents nearest first (up to 10), weather warnings, fire danger today and tomorrow with the total fire ban, road closures and power outages |
| `ausnz_disaster_watch__get_fire_danger` | The fire danger rating and total fire ban for `today`, `tomorrow`, `day3` or `day4` (the fire season in New Zealand) |
| `ausnz_disaster_watch__list_hazards` | Warnings and incidents filtered by `category` (fire, flood, storm, earthquake, tsunami, road, power, other), `max_distance_km` and `min_level` (advice, watch_and_act, emergency_warning), up to 20 |

- **Setup:** none. In your conversation agent's options, set **Control Home Assistant** to **Assist**. The tools are offered for a location only when at least one of its entities is exposed to Assist (**Settings** > **Voice assistants** > **Expose**), so your exposure choices apply. The MCP Server integration serves the same tools to MCP clients.
- **Several locations:** with more than one location the assistant passes the location's name (the entry title). If it doesn't, the tool lists the locations so the assistant can ask you.
- **Feed health:** every answer says whether each feed is `ok`, `stale` (its last fetch failed and its last good data stands in) or `failed`, with the time of its last good fetch. When a feed is not `ok`, the answer is marked incomplete, and the assistant is told to say so and never to call the situation all clear.
- **What it is not:** the tools only read what the integration already fetched, so they cannot replace official warnings. Follow official advice, and call 000 (Australia) or 111 (New Zealand) in an emergency.

## Automation examples

The examples use an entry called "QLD Home"; replace the entity IDs with your own. Some ideas:

- Get a phone notification, flash lights or play the [emergency broadcaster](#emergency-broadcaster-radio) when an Emergency Warning or Watch and Act is issued near home, or when home is inside a warning area.
- Close windows, turn off evaporative coolers or start a pump when a bushfire, flood or storm warning gets close.
- Check the fire danger rating and total fire ban before running a mower, a welder or a fire pit.
- Watch nearby river gauges and dam storages during heavy rain, with an alert level per gauge.
- See road closures and flooded roads before a trip, and power outages that affect the area.
- Ask Assist "are there any warnings near home?" (see [Voice assistants](#voice-assistants)).

### 1. Alert the household on a nearby Emergency Warning

```yaml
alias: "Emergency Warning: alert household"
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

### 2. Flash red lights on an Emergency Warning

```yaml
alias: "Emergency Warning: red lights"
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

### 3. Any incident entering a zone

```yaml
alias: "Disaster Watch: incident near home"
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

### 4. Play the emergency broadcaster on an Emergency Warning

Turn on the [emergency broadcaster](#emergency-broadcaster-radio) first. Replace `ENTRY_ID` with the entry's ID (the `media_content_id` attribute of the emergency broadcaster sensor shows the full ID).

```yaml
alias: "Emergency Warning: play the emergency broadcaster"
triggers:
  - trigger: state
    entity_id: binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby
    to: "on"
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: "Emergency warning nearby. Playing ABC emergency radio. Follow official advice."
  # Let the announcement finish (at most 30 seconds) before the radio starts on the same player
  - delay: "00:00:02"
  - wait_template: "{{ not is_state('media_player.kitchen', 'playing') }}"
    timeout: "00:00:30"
    continue_on_timeout: true
  - action: media_player.play_media
    target:
      entity_id: media_player.kitchen
    data:
      media:
        media_content_id: media-source://ausnz_disaster_watch/emergency_broadcaster/ENTRY_ID
        media_content_type: music
```

As a blueprint (save as `blueprints/automation/ausnz_disaster_watch/emergency_broadcaster.yaml`; enable the emergency broadcaster sensor first, it is disabled by default):

```yaml
blueprint:
  name: Play the emergency broadcaster on a nearby warning
  description: Announce a nearby Emergency Warning or Watch and Act, then play the local ABC Local Radio (RNZ in New Zealand) station.
  domain: automation
  input:
    warning_sensor:
      name: Emergency warning nearby sensor
      selector:
        entity:
          filter:
            integration: ausnz_disaster_watch
            domain: binary_sensor
    broadcaster_sensor:
      name: Emergency broadcaster sensor
      selector:
        entity:
          filter:
            integration: ausnz_disaster_watch
            domain: sensor
    speaker:
      name: Media player
      selector:
        entity:
          filter:
            domain: media_player
    tts_engine:
      name: Text-to-speech engine
      selector:
        entity:
          filter:
            domain: tts
triggers:
  - trigger: state
    entity_id: !input warning_sensor
    to: "on"
variables:
  broadcaster_sensor: !input broadcaster_sensor
  speaker: !input speaker
actions:
  - action: tts.speak
    target:
      entity_id: !input tts_engine
    data:
      media_player_entity_id: !input speaker
      message: "Emergency warning nearby. Playing {{ states(broadcaster_sensor) }}. Follow official advice."
  # Let the announcement finish (at most 30 seconds) before the radio starts on the same player
  - delay: "00:00:02"
  - wait_template: "{{ not is_state(speaker, 'playing') }}"
    timeout: "00:00:30"
    continue_on_timeout: true
  - action: media_player.play_media
    target:
      entity_id: !input speaker
    data:
      media:
        media_content_id: "{{ state_attr(broadcaster_sensor, 'media_content_id') }}"
        media_content_type: music
```

### 5. Fire danger rating of Extreme or higher

The states of the highest warning level and fire danger rating sensors are snake_case (`watch_and_act`, `extreme`); see [Warning levels and ENUM states](#warning-levels-and-enum-states).

```yaml
alias: "Fire danger: extreme or catastrophic"
triggers:
  - trigger: state
    entity_id: sensor.australia_and_new_zealand_disaster_watch_qld_home_fire_danger_rating
    to:
      - extreme
      - catastrophic
actions:
  - action: notify.notify
    data:
      title: "Fire danger"
      message: >-
        Fire danger is {{ states('sensor.australia_and_new_zealand_disaster_watch_qld_home_fire_danger_rating') }}
        in {{ state_attr('sensor.australia_and_new_zealand_disaster_watch_qld_home_fire_danger_rating', 'district_name') }}.
```

### 6. Dam above full supply

Notify when Somerset holds flood water or Wivenhoe goes over 100%:

```yaml
alias: "Dams: above full supply"
triggers:
  - trigger: state
    entity_id: binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_somerset_above_full_supply
    to: "on"
  - trigger: numeric_state
    entity_id: sensor.australia_and_new_zealand_disaster_watch_qld_home_wivenhoe_percent_full
    above: 100
actions:
  - action: notify.notify
    data:
      title: "Dam above full supply"
      message: >-
        {{ trigger.to_state.name }}: {{ trigger.to_state.state }}
        (reading of {{ trigger.to_state.attributes.observed_at }}).
        Check the dam operator's release notices and the Bureau's flood warnings.
```

## How it works

### Data updates

The integration polls public feeds; nothing is pushed to it.

| Data | Interval |
| --- | --- |
| Hazard and warning feeds and council dashboards | Every 5 minutes; every minute while an Emergency Warning or Watch and Act is active in the radius |
| Road feeds | With each hazard refresh, at most every 4 minutes |
| Power outages | At most every 5 minutes (Unison every 15) |
| Fire danger ratings and total fire bans | At most every 30 minutes |
| State air quality stations | Every 30 minutes |
| River and creek gauges | Every 15 minutes |
| Dam and weir storages | Every hour |
| Weather hazard signals | Every hour |
| River flood forecast and AI rain outlook | Every 6 hours |
| Camera lists | At most every 6 hours |
| Camera images | When a dashboard or the camera view asks for a frame |

### Feed outages

- When a feed fails, its last good data stands in for up to 30 minutes, so a short outage does not look like an all-clear; after that its incidents are dropped. A feed going down and coming back is logged once each.
- When every hazard feed fails, the hazard entities become unavailable until a feed answers again.
- Optional feeds (state air quality, the national feeds, road feeds, power outages, cameras, the fire danger outlook and the rest) never hold up entry setup or a refresh: a slow call is cut short and its last result is used.
- Download the [diagnostics](#troubleshooting) to see each hazard feed's status and its last successful fetch.

### Entity lifecycle

Entities never linger as `unavailable` after the thing they describe has gone:

- **Incidents and cameras** come and go with the feeds. An ended incident or a camera that leaves the feed (delisted, out of the radius or past the maximum) is removed with its entity registry entry, including ones that went while Home Assistant was stopped; a camera that comes back is re-created with the same entity ID. Nothing is removed while the feed it came from is down: its cameras are kept, unavailable.
- **Option-dependent entities** (river gauges, dam storages, forecast features, national feeds, tsunami warnings, the emergency broadcaster) are created only while turned on or selected, and are removed when you turn them off or deselect them. The fire season sensor exists only for New Zealand entries and the total fire ban sensor only for Australian ones; reconfiguring between them swaps the two.
- **At every setup**, after the first refresh that hears from every hazard feed, registry entries of the entry that the current configuration no longer creates (for example from an older release) are removed, and so are devices of the entry left without entities.

Customisations (name, icon, area) of a removed entity are lost with it.

### Council area

Once per location, the integration looks up the council the location is in: the ABS local government area in Australia and the Stats NZ territorial authority in New Zealand. Listed items with a location get `in_council_area`, so the cards can show only your council (see [Your council or the whole radius](#your-council-or-the-whole-radius)). Sensor states, counts and binary sensors stay radius-based. Council boundaries © Australian Bureau of Statistics (CC BY 4.0) and Stats NZ (CC BY 4.0).

## Troubleshooting

- **"None of the emergency feeds for this state answered" during setup**: Home Assistant could not reach the state's feeds or the BoM. Check that Home Assistant can reach the internet and try again; an agency's feed may also be down for maintenance.
- **Entities are unavailable**: every hazard feed failed at the last update. The log names each feed that went down. Entities recover by themselves at the next successful update.
- **An incident shown on an agency website is missing**: check the monitoring radius and **Exclude Hazard Reduction / Planned Burns** in the options, and that the entry's state is the incident's state. The Emergency Warning override only widens the radius for Emergency Warnings.
- **No Victorian road closures**: Victorian road data needs your own free DTP key; see [Roads](#road-closures-and-flooded-roads).
- **The river gauge or dam storage list is empty**: the search covers gauges that reported in the last 6 hours (storages: 7 days) within the radius (storages: at least 150 km). Widen the radius, or try again later if a gauge service is down.
- **Diagnostics**: on the integration entry, open the menu and choose **Download diagnostics**. The file lists each hazard feed's status and last successful fetch. Coordinates, the location name and the council dashboard are redacted, but check the file before sharing it.
- **Debug logging**: choose **Enable debug logging** on the integration entry, reproduce the problem, then **Disable debug logging** to download the log. Or add this to `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.ausnz_disaster_watch: debug
  ```

## Known limitations

- Each entry watches one location. Add another entry for each extra location.
- Coverage depends on what each agency publishes. NSW SES and VicEmergency warning areas and ACT warning polygons are not read (see [Warning areas](#warning-areas)), NSW SES warnings are not read at all, and some council dashboards cannot be read (see [Council disaster dashboards](#council-disaster-dashboards)).
- Distances are to the published warning area where an agency publishes one, otherwise to a single point, which can be far from the edge of a large fire or flood.
- Hazard attributes and fire danger `forecast` days keep the English level names; only the enum sensors' states are snake_case.
- Forecast signals and the AI rain outlook are model output, not official warnings. Dam and river sensors are not release or flood warnings.
- Data is only as current as each feed. Always follow the official advice of your emergency services; this integration is not a warning service.

## Data sources & licences

The integration reads public feeds published by emergency services, weather agencies, water agencies, electricity distributors and local councils. Every entity has an `attribution` attribute that credits the sources behind it, map pins credit the feed the incident came from, and diagnostics list each source with its owner, licence and terms link. The per-feature tables above (roads, power outages, river gauges, dam storages) give those sources' licences.

| Region | Source | Licence / terms |
| --- | --- | --- |
| AU | Bureau of Meteorology warnings via WMO SWIC | BoM: personal, non-commercial use; WMO SWIC: free reuse crediting the issuing service |
| AU | BoM fire danger forecasts and fire weather districts | BoM copyright: personal, non-commercial use |
| QLD | Queensland Fire Department incidents | CC BY 4.0 |
| QLD | QFD and QPS warning areas (ArcGIS) | No licence published |
| QLD, NSW | Council disaster dashboards (Guardian IMS) | Per council; for example Moreton Bay CC BY 4.0 excluding third-party content, Hawkesbury non-commercial |
| NSW | NSW Rural Fire Service incidents, fire danger and total fire bans | CC BY 4.0 |
| VIC | VicEmergency (Emergency Management Victoria) | All rights reserved; prior written permission required, not yet obtained |
| VIC | CFA total fire bans | CC BY 4.0 |
| WA | Emergency WA (DFES) designated RSS feeds | CC BY-ND 4.0; no monitoring or copying except the designated feeds |
| SA | SA CFS / SES CAP-AU feed and CFS fire danger | No terms for these files; neighbouring CFS feeds are CC BY-NC-ND 4.0 |
| SA | SA SES warning areas | ArcGIS item licence "Public Use"; no licence terms published |
| ACT | ACT Emergency Services Agency | No licence published |
| TAS | TasALERT (hazards and road closures) | Feed access by permission, not yet granted; state content non-commercial |
| NT | NT Government Fire_Incidents service (Bushfires NT, NTFRS) | No licence published |
| AU | Geoscience Australia earthquakes (opt-in) | CC BY 4.0 |
| AU | ABS local government areas (fire bans in WA, council area) | CC BY 4.0 |
| NZ | GeoNet | CC BY 3.0 NZ |
| NZ | NEMA (Civil Defence) alerts | CC BY 4.0 |
| NZ | MetService CAP warnings | CC BY 4.0, subject to the CAP Code of Practice |
| NZ | NZ Transport Agency Waka Kotahi road events and cameras | No licence stated on data.govt.nz |
| NZ | Fire and Emergency NZ fire seasons | No licence published |
| NZ | Stats NZ territorial authorities (council area) | CC BY 4.0 |
| QLD, NSW | QLDTraffic flood and web cameras (opt-in) | CC BY 4.0; images credited to their supplier |
| AU | National feeds (opt-in): BoM tsunami, heatwave and UV forecast | BoM: personal, non-commercial use |
| NZ | NOAA Pacific Tsunami Warning Center (opt-in) | US Government work, public domain; no endorsement implied |
| AU | Digital Earth Australia satellite hotspots (opt-in) | CC BY 4.0; not for safety-of-life decisions |
| AU | ARPANSA UV observations (opt-in) | Credit "UV observations courtesy of ARPANSA"; no retransmission or commercial use without permission |
| AU, NZ | GDACS (European Commission JRC) (opt-in) | © European Union; feed marked public domain; indicative only |
| NSW, QLD, ACT | State air quality stations (opt-in) | CC BY 4.0 |
| All | Open-Meteo, GloFAS, ECMWF AIFS (opt-in) | CC BY 4.0; free API non-commercial only. WeatherNext 2: not verified |
| Card | RainViewer, NASA GIBS, OpenStreetMap, GDACS (fetched by your browser) | See the register |

GeoNet, NSW RFS and GDACS feeds are read with the maintained `aio_geojson_geonetnz_quakes`, `aio_geojson_geonetnz_volcano`, `aio_geojson_nsw_rfs_incidents` and `aio_georss_gdacs` libraries, the same ones Home Assistant core uses.

Several publishers restrict reuse to personal, non-commercial use or require permission. This integration is for personal home automation. Do not use it to republish these feeds or for commercial purposes without checking each publisher's terms.

The full register, with every endpoint, terms evidence, rate limits and the decisions taken for restricted sources, is in [docs/development/DATA_SOURCES.md](docs/development/DATA_SOURCES.md).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow (issue first, branch, pull request template) and [AGENTS.md](AGENTS.md) for the architecture and code rules.

### Scripts

| Script | What it does |
| --- | --- |
| `script/setup/bootstrap` | Install or update the development dependencies |
| `script/develop` | Start Home Assistant in development mode with the integration loaded |
| `script/check` | Type checking (Pyright), lint (Ruff), spelling (codespell) and the dashboard card checks |
| `script/test` | Run the pytest suite (`pytest-homeassistant-custom-component`) |
| `script/lint` | Format and fix lint findings with Ruff |
| `script/hassfest` | Run Home Assistant's hassfest validation |
| `script/check-imports` | Check the integration's declared requirements in a clean environment |
| `script/update-councils` | Regenerate the council disaster dashboard registry (`data/council_dashboards.json`) |
| `script/update-broadcasters` | Regenerate the emergency broadcaster table (`data/emergency_broadcasters.json`) |
| `script/brand` | Render the brand images (see [Brand images](#brand-images)) |
| `script/help` | List all scripts |

### Frontend

The dashboard card source is TypeScript (Lit) in `frontend/`. `npm run build` there writes the bundle to `custom_components/ausnz_disaster_watch/frontend/`; `npm test` runs the unit tests and `npm run test:browser` the Playwright tests.

### Continuous integration

GitHub Actions run lint, tests, the declared requirements check, the frontend build and tests, hassfest and HACS validation. CI jobs run on the runner set by the `RUNNER_LABELS` repository variable, a JSON label list such as `["self-hosted","unraid"]`; without it they fall back to `ubuntu-latest`.

### Brand images

`branding/icon.svg`, `branding/logo.svg` and `branding/dark_logo.svg` are the masters. Run `script/brand` after editing them: it renders the PNGs (icon 256/512 px, logos 128/256 px high, plus dark-mode logos) into `branding/` and copies them to `custom_components/ausnz_disaster_watch/brand/`, where Home Assistant loads a custom integration's icon and logo from. `tests/test_brand.py` fails if the two folders drift apart.

## Quality scale

- **Integration Quality Scale**: Gold. [`quality_scale.yaml`](custom_components/ausnz_disaster_watch/quality_scale.yaml) records each [rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules) as done, exempt (with the reason) or still to do.
- **Type checking**: Pyright in basic mode.
- **Code style**: linted and formatted with Ruff (`py313`).
- **Tests**: `pytest-homeassistant-custom-component`.
- **Database safety**: entity attributes are capped to stay well under Home Assistant's 16 KB attribute limit.

## License

This project is licensed under the Apache 2.0 License; see the [LICENSE](LICENSE) file for details.
