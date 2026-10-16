# Australia and New Zealand Disaster Watch for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](https://github.com/tinkerologie/ha-ausnz-disaster-watch/releases)
[![License](https://img.shields.io/github/license/tinkerologie/ha-ausnz-disaster-watch?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://hacs.xyz)

A comprehensive, real-time emergency disaster and hazard monitoring integration for Home Assistant across Australian jurisdictions.

Directly integrates official emergency feeds—including the **Queensland Fire Department (QFD)**, local council disaster dashboards (such as the **City of Moreton Bay Disaster Dashboard**), **NSW Rural Fire Service (NSW RFS)**, **Emergency Management Victoria (EMV OSOM)**, and **Bureau of Meteorology (BoM)** weather alerts—normalized under the **Australian Warning System (AWS)**.

---

## Key Features

- **Jurisdiction & Local Council Feeds**:
  - **Queensland**: Real-time QFD vegetation fire & emergency warnings feed + direct integration with Local Council Disaster Dashboards (62 Queensland councils on Guardian IMS, from **City of Moreton Bay** and Gold Coast to Toowoomba, Mackay and the RAPAD councils) covering fire incidents, road closures/hazards, power outages, and bulletins. NSW: Hawkesbury, Blue Mountains, Ballina, Byron and Northern Beaches.
  - **New South Wales**: NSW RFS Major Incidents & SES data feeds.
  - **Victoria**: Emergency Management Victoria (EMV OSOM) feed covering fires, floods, storms, and health hazards.
  - **New Zealand**: GeoNet earthquakes (with GeoNet's CAP quake alerts) and volcanic alert levels, NEMA Civil Defence alerts, MetService warnings, and NZTA state highway closures and hazards.
  - **Northern Territory**: Bushfires NT and NT Fire and Rescue Service incidents from the NT Government Fire_Incidents service.
  - **National / Federal**: Bureau of Meteorology (BoM) weather warnings (severe thunderstorms, tropical cyclones, flood warnings).
  - **Earthquakes (optional)**: Geoscience Australia earthquakes of magnitude 3 or more from the last 48 hours, within your radius (M6+ Watch and Act, M4.5+ Advice, smaller Information). Turn it on under **Configure > Earthquakes** (Australian entries; New Zealand entries use GeoNet). Earthquake data © Commonwealth of Australia (Geoscience Australia), from [earthquakes.ga.gov.au](https://earthquakes.ga.gov.au/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **River and Creek Levels** (opt-in): pick nearby water level gauges in Queensland, New South Wales, the ACT and New Zealand and get one sensor per gauge, polled every 15 minutes. See [River and creek level gauges](#river-and-creek-level-gauges).
- **Dam and Weir Storage Levels** (opt-in): pick dams and weirs anywhere in Australia and get percent full (above 100% when a dam holds flood water), volume, level and an "above full supply" binary sensor per storage. See [Dam and weir storage levels](#dam-and-weir-storage-levels).
  - **Roads (NSW, QLD, VIC, SA, WA, NT, TAS)**: road closures, flooded roads and road hazards from each state's official open road feed (see [Road closures and flooded roads](#road-closures-and-flooded-roads)).
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
| `…_road_closure_nearby` | `on` when a road closure, flooded road or road hazard is reported nearby (planned roadworks and events never turn it on) | `problem` |
| `…_flooded_road_nearby` | `on` when a flooded road is reported nearby; attributes `flooded_count` and the `nearest` five flooded roads | `safety` |
| `…_total_fire_ban` | `on` when a total fire ban is declared today for your fire weather district (Australia only; see [Fire danger and total fire bans](#fire-danger-and-total-fire-bans)) | `safety` |
| `…_<gauge name>_above_alert_level` | `on` when a selected river gauge is at or above the alert level you set (see below) | `problem` |

### Sensors (`sensor`)
| Entity (suffix) | Description | Unit |
| ------ | ----------- | ---- |
| `…_nearest_hazard_distance` | Distance to the closest active incident | `km` |
| `…_nearest_hazard_title` | Headline of the nearest incident | — |
| `…_active_hazards_count` | Active incidents in the monitored perimeter | `hazards` |
| `…_highest_warning_level` | Highest AWS level currently active. States: `emergency_warning`, `watch_and_act`, `advice`, `information`, `all_clear` (no incidents); `unknown` when the incidents have no known level. The dashboard shows them translated (Emergency Warning, Watch and Act, …) | — |
| `…_weather_warnings_count` | Active weather warnings | `warnings` |
| `…_fire_danger_rating` | Today's AFDRS fire danger rating for your fire weather district (`no_rating`, `moderate`, `high`, `extreme`, `catastrophic`), with a 4-day `forecast` attribute | — |
| `…_fire_season` | New Zealand only: fire season at your location (`open`, `restricted`, `prohibited`) with Section 52 prohibitions | — |
| `…_power_outages_count` / `…_power_outages_customers_affected` | Power outages and customers affected (see [Power outages](#power-outages)) | `outages` / `customers` |
| `…_road_closures_count` | Road closures, flooded roads and road hazards nearby (plus roadworks when enabled); the `closures` attribute lists the nearest 25 with their `category` | `closures` |
| `…_relief_facilities_count` | Evacuation centres and sandbag stations nearby | `facilities` |
| `…_air_quality` | Air quality rating of the nearest station | — |
| `…_local_weather_observation` | Temperature at the nearest weather station | `°C` |
| `…_<gauge name>_water_level` | Water level at each river gauge you selected (see below) | `m` |

Entity IDs start with the device name, for example `binary_sensor.australia_and_new_zealand_disaster_watch_qld_home_emergency_warning_nearby`.

### River and creek level gauges

Gauge sensors are off until you choose gauges. Open **Configure** on the integration and pick
**River and creek level gauges** from the menu. The form lists up to 10 of the nearest gauges
within the monitoring radius that reported a level in the last 6 hours, with distance and current
level. Finding them can take up to a minute the first time; the site lists are then cached for
24 hours. Tick the gauges you want and submit. Each one becomes a sensor named after the gauge,
for example `sensor.australia_and_new_zealand_disaster_watch_qld_home_brisbane_river_at_savages_crossing_water_level`.

- **State**: water level in metres (`device_class: distance`, `state_class: measurement`) above the gauge's own datum, not above sea level. Readings in mm or cm are converted to metres.
- **Attributes**: `site_id`, `source`, `latitude`, `longitude`, `distance_km` (from your location), `observed_at` (time of the reading, UTC), `trend` (`rising`, `falling` or `steady`, or `null` when there is no reading an hour before the latest one) and `change_1h_m` (the level change behind the trend, compared with the newest reading at least an hour older; changes within 1 cm are `steady`). The sensor's attribution names the data publisher.
- **Availability**: a gauge without a reading in the last 6 hours is unavailable. If a gauge service cannot be reached, its last reading is kept until it is 6 hours old. Gauges stay selected until you untick them; unticked gauges' entities are removed.
- **Alert levels**: after ticking gauges, the next form lets you enter an optional alert level in metres per gauge, on the same datum as its level (for example the minor flood level from your council or the Bureau of Meteorology). Each gauge with a level gets `binary_sensor.…_<gauge name>_above_alert_level` (`device_class: problem`), on while the level is at or above it, with `alert_level_m`, `level_m` and `site_id` attributes. Leave the field blank for no alert sensor; clearing a level removes its sensor. None of the gauge services publishes minor, moderate or major flood levels, so there are no built-in thresholds.

| Region | Source | Licence |
| ------ | ------ | ------- |
| Queensland | [Water Monitoring Information Portal](https://water-monitoring.information.qld.gov.au/) (Kisters Hydstra web service, telemetered stream gauges) | CC BY 4.0, stated in every response |
| New South Wales and ACT | [WaterNSW real-time data](https://realtimedata.waternsw.com.au/) (Kisters Hydstra web service) | Listed as CC BY on data.gov.au/SEED (version 3.0 or 4.0 differs between listings) |
| New Zealand | Regional council Hilltop servers: Greater Wellington, Horizons, Hawke's Bay, Tasman, Northland, West Coast, Taranaki and Marlborough (measurement `Stage`) | Hawke's Bay: CC BY. Others: public, keyless servers; licence not stated |

Queensland and NSW locations search both Kisters services, so gauges across the border are found too.
Data is provisional and unvalidated. Not supported: Environment Canterbury (no sites returned, site
behind a bot wall), Waikato (times out), Bay of Plenty, Otago and Nelson (no public Hilltop server
found), Southland and Gisborne (server errors), Victoria and the other states (no source yet).
Groundwater bores on the Hilltop servers are not offered.

The `…_air_quality` sensor reports the nearest station first. With **State air quality stations** enabled (NSW, QLD and ACT), it uses the state environment agency's stations and adds `distance_km`, `observed_at` and `source` attributes. A station with no current reading has an unknown rating, never "Good".

### Dam and weir storage levels

Storage sensors are off until you choose storages. Open **Configure** on the integration and pick
**Dam and weir storage levels** from the menu. The form lists up to 15 of the nearest storages that
reported in the last 7 days, with distance and percent full. It searches the monitoring radius, but
at least 150 km, because the dams that flood a town are often well upstream (Wivenhoe is 65 km from
Brisbane). The first search can take up to a minute; the storage list is then cached for 24 hours.
Tick the storages you want and submit.

Each storage gets these entities, named after the storage, for example
`sensor.australia_and_new_zealand_disaster_watch_qld_home_wivenhoe_percent_full`:

- `sensor.…_percent_full`: volume as a share of full supply volume, in %. It goes **above 100%** when a dam holds more than its full supply, for example when Wivenhoe or Somerset are using their flood storage compartment.
- `sensor.…_volume`: volume in megalitres (ML).
- `sensor.…_level`: water level in metres, usually above sea level (AHD).
- `binary_sensor.…_above_full_supply`: on while the storage is above 100% of full supply volume, above full supply level, or reported spilling by its operator (WaterNSW spillway discharge in the last daily total, or Hydro Tasmania's "Spilling"). An ungated dam above full supply is spilling; a gated flood-mitigation dam above full supply is holding flood water that it will release.
- **Attributes** (on all four): `site_id`, `latitude`, `longitude`, `distance_km`, `full_supply_volume_ml`, `full_supply_level_m`, `observed_at` (time of the reading, UTC), `percent_full`, `volume_ml`, `level_m`, `change_24h_ml` (volume change since the reading closest to 24 hours earlier, taken 18 to 36 hours before the latest; `null` without one) and `above_full_supply`. The attribution names the data owner.
- **Availability**: storages are polled hourly. A storage without a reading in the last 7 days is unavailable; if Water Data Online cannot be reached, the last readings are kept until they are 7 days old, and operator readings still update them. Storages stay selected until you untick them.

- **Operator feeds (NSW, ACT and Tasmania)**: WaterNSW and Hydro Tasmania publish their own storage data under CC BY. When you pick a storage they operate, it is matched to their feed and the match is stored with it, so the sensors use the fresher data. Storages picked before this feature need the step opened and saved once to be matched.
  - **WaterNSW** (NSW storages, including the Sydney dams, Hume and Blowering): the level comes from the WaterNSW gauge, updated every 15 to 60 minutes, instead of the Bureau's day-old value. Attributes `spillway_24h_ml` and `release_24h_ml` are the spillway discharge and total releases in ML for the last 24 hours to 9 am (`totals_date`), and `spilling` is on when the spillway discharged. Percent full and volume stay the Bureau's, because WaterNSW's own storage tables differ by a few per cent from the Bureau's full supply volume. A gauge is matched only when it is within 30 km and its level and volume agree with the Bureau's.
  - **Hydro Tasmania** (its hydro lakes): `metres_below_full` and `spilling` from Hydro Tasmania's daily lake table, matched by lake name.
  - Each storage's `source` attribute says where its level comes from: `waternsw` for a matched WaterNSW gauge with a newer reading, otherwise `bom`. Hydro Tasmania storages always report `bom`, because Hydro Tasmania publishes no level or volume; its data is in `metres_below_full` and `spilling`. `operator_observed_at` gives the operator's reading time. If an operator feed is down, the Bureau's data is used alone.

| Region | Source | Licence |
| ------ | ------ | ------- |
| All Australian states and territories | [Bureau of Meteorology Water Data Online](https://www.bom.gov.au/waterdata/) (KiWIS web service), with data supplied by Seqwater, WaterNSW, Sunwater, Melbourne Water, Goulburn-Murray Water, SA Water, Water Corporation, Hydro Tasmania, Icon Water, Power and Water and other water agencies | CC BY 3.0 AU per data owner ([owner list](https://www.bom.gov.au/waterdata/wiski-web-public/copyright.htm)). Storages of owners with other terms (Snowy Hydro, Gosford City Council) are not offered |
| New South Wales and ACT | [WaterNSW real-time data](https://realtimedata.waternsw.com.au/) storage gauges (level, daily spillway discharge and releases) | CC BY, as the river gauges |
| Tasmania | [Hydro Tasmania lake levels](https://www.hydro.com.au/water/water-information) (metres from full, "Spilling") | CC BY 3.0 AU |

> **These sensors are not a dam release warning.** Water agencies send their data to the Bureau
> about once a day, so the Bureau's readings are usually **12 to 48 hours old**. WaterNSW levels are
> current to within an hour, but its spill and release figures are daily totals to 9 am, and
> Hydro Tasmania's table is daily. During a flood, a dam can start releasing well before these
> sensors change. **The Bureau's flood warnings, which this integration already reports as
> hazards, remain the release signal.** For releases, also sign up to the dam operator's
> notifications (for example the [Seqwater Dam Release Notification Service](https://www.seqwater.com.au/dam-release-notification-service)).
> Release notices are not read: none is published in a form the integration may reuse. Seqwater
> (all rights reserved), the WaterNSW release notifications via the Early Warning Network (whose
> terms ban automated tools), Sunwater (prior written consent) and the NZ operators Mercury and
> Genesis are listed under permission requests in the data source register. Seqwater, Sunwater
> and Melbourne Water live levels are not licensed for reuse, so their storages use the Bureau's
> data. New Zealand has no openly licensed live source yet.

### Optional national and regional feeds
These feeds are off by default. Turn them on under **Configure** > **National and regional feeds (optional)**. Each one adds its entity when enabled. An entity is unavailable while its source cannot confirm a state, so a failed feed never shows as all clear. None of these feeds add hazards, so they do not change the hazard counts, warning levels, map pins or polling rate.

| Entity (suffix) | Description | States / Unit | Jurisdictions |
| ------ | ----------- | ------------- | ------------- |
| `binary_sensor.…_tsunami_warning` | `on` while a tsunami watch or warning applies, or a tsunami hazard is in range. Attributes: `threat_level` (`no_threat`, `watch`, `marine`, `land`), headline, expiry and the products checked | `safety` | AU: JATWC. NZ: PTWC guidance (official NZ warnings come from NEMA) |
| `sensor.…_satellite_hotspots_nearby` | Satellite heat detections in the last 24 hours within the radius, with confidence of at least 50. Hotspots are not fire warnings | `hotspots` | AU |
| `sensor.…_heatwave_severity` | Highest current BoM heatwave warning in your state, with each district's severity as an attribute | `none`, `low_intensity`, `severe`, `extreme` | AU |
| `sensor.…_uv_index` | UV index at the nearest ARPANSA station, with the BoM sun protection forecast for that station | UV index | AU |
| `sensor.…_regional_disaster_alerts` | Current GDACS Orange and Red alerts around Australia and New Zealand. These alerts are context only and never count as local warnings | `alerts` | AU, NZ |

#### Data sources and licences
| Feed | Source | Licence and conditions |
| ---- | ------ | ---------------------- |
| Tsunami (AU) | Joint Australian Tsunami Warning Centre CAP products `IDY680nn`, BoM anonymous FTP | © Bureau of Meteorology. Personal, non-commercial use |
| Tsunami (NZ) | NOAA Pacific Tsunami Warning Center Atom and CAP feed | US Government work, public domain. Credit NOAA. No endorsement is implied |
| Satellite hotspots | Digital Earth Australia Hotspots (Geoscience Australia) WFS, queried by bounding box | CC BY 4.0. Not for safety-of-life decisions |
| Heatwave, UV forecast | BoM products `IDx21013`/`IDN21014` and `IDZ00107`–`IDZ00113`, BoM anonymous FTP | © Bureau of Meteorology. Personal, non-commercial use |
| UV observations | ARPANSA real-time UV (`uvvalues.xml`) | Attribution "UV observations courtesy of ARPANSA". Developers must notify ARPANSA that the data is used. No retransmission or commercial use without permission |
| Regional alerts | GDACS RSS (European Commission JRC), read with `aio-georss-gdacs` | © European Union. The feed is marked public domain. Indicative only |
| Air quality (NSW) | NSW DCCEEW air quality API | CC BY 4.0 |
| Air quality (QLD) | Queensland Government air quality XML feed | CC BY 4.0 |
| Air quality (ACT) | ACT Government open data, dataset `94a5-zqnn` | CC BY 4.0 |

### Cameras (`camera`)
Flood and traffic camera snapshots near the monitored location: the council dashboard's cameras (QLD and NSW council dashboards), and, when you turn them on under **Road and flood cameras** in the options, road agency cameras:

- **QLDTraffic flood cameras** and **QLDTraffic web cameras** for Queensland entries (and NSW entries near the border), CC BY 4.0.
- **NZ Transport Agency traffic cameras** for New Zealand entries; cameras that are offline or under maintenance are left out.

The options set the **camera radius** (default 25 km, and cameras must also be inside the monitoring radius) and the **maximum number of cameras** (default 12, nearest first), so a city entry does not get hundreds of entities. Camera lists are downloaded at most every six hours; an image is fetched only when you view the camera. A camera's `attribution` names its network and, where the feed says, who supplies the image; its attributes include `direction`, `distance_km` and `network`.

Only real images are shown: if a camera host answers with an error page instead of a picture, the camera keeps its last good image. Live Traffic NSW cameras are not available: their image server refuses requests that do not come from a web browser, and the integration does not pretend to be one.

When a camera entity is within 5 km of an incident, the incident's map pin (`geo_location`) gets a `nearest_camera` attribute (`entity_id`, `name`, `distance_km`), and the incidents card shows a camera button next to the incident.

### Fire danger and total fire bans

Your location is matched to its Bureau of Meteorology fire weather district (bundled, simplified `IDM00007` boundaries, so border towns such as Albury and Wodonga or Queanbeyan and Canberra get their own district). The rating and 4-day outlook come from the Bureau's fire danger forecast for that state. Each forecast day is dated in the district's local time, so the sensor always shows today's rating, including in the evening after the next day's forecast is issued. The last outlook is stored, so today's rating survives a restart; if no earlier forecast is known, today's rating comes from the state agency (NSW RFS, ACT ESA, CFA, SA CFS or Emergency WA) and `source` names it. Fire danger is polled at most every 30 minutes.

`…_fire_danger_rating` attributes: `district_name`, `district_number` (BoM district code such as `NSW_FW008`), `date`, `fire_behaviour_index`, `total_fire_ban`, `forecast` (one entry per day: `date`, `rating`, `fire_behaviour_index`, `total_fire_ban`), `issued_at`, `source` and `total_fire_ban_source`. The state is `no_rating`, `moderate`, `high`, `extreme` or `catastrophic` (shown translated, for example "Extreme"); it is `unknown` when the district has no AFDRS rating. The `rating` of each `forecast` day keeps the display name (`Extreme`).

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
### Power outages

Outages come from the electricity distributors' own outage feeds and, in Queensland and NSW, from the council disaster dashboard (Energex and Ergon outages). Only outages in effect now count: planned work that has not started, and finished or cancelled outages, are left out. Planned outages are excluded unless **Include planned power outages** is on in the **Power outages** options page.

| Distributor | Area | Feed | Terms | Default |
| ----------- | ---- | ---- | ----- | ------- |
| Endeavour Energy | Western Sydney, Blue Mountains, Illawarra | [Open data portal](https://data.endeavourenergy.com.au) (`outagecustomerlive`, `plannedoutagecustomer`), queried within the radius and grouped by incident (no street addresses) | [ODbL 1.0](https://www.opendatacommons.org/licenses/odbl/1.0/) | On |
| Essential Energy | Regional NSW, around the ACT | Outage map KML (`current.kml`) | No terms published | On |
| TasNetworks | Tasmania | Outage map JSON (`GetPowerOutages`) | No reuse terms published | On |
| MainPower | North Canterbury, Kaikōura | Outage map JSON (`/jobs`) | No terms published | On |
| Western Power | South-west WA | Outage map ArcGIS service, queried within the radius | [Personal, non-commercial use only](https://www.westernpower.com.au/terms--conditions/) | Extra feeds |
| Powerco | Taranaki, Whanganui, Manawatū, Wairarapa, Tauranga, Coromandel | Outage map ArcGIS service, queried within the radius | [No public or commercial use](https://www.powerco.co.nz/terms-of-use) | Extra feeds |
| Unison | Hawke's Bay, Taupō, Rotorua | Outage map JSON (about 2.6 MB, fetched at most every 15 minutes) | No terms published | Extra feeds |

Feeds marked "Extra feeds" are used only when **Extra power outage feeds** is on in the **Power outages** options page. Feeds without a radius query are only downloaded when the radius reaches the distributor's network, and no feed is fetched more often than every 5 minutes.

`…_power_outages_count` lists up to 25 outages, nearest first, each with `distributor`, `id`, `planned`, `status`, `start_time`, `restore_time` and `distance_km` (to the outage area's edge where the feed has polygons; 0 when home is inside it). It also has `est_restore`, `nearest_outage_distance_km` and `nearest_outage_distributor` for the nearest outage, and `data_sources` with each feed's distributor, licence and attribution. Endeavour Energy data: "Contains information from Endeavour Energy Open Data, made available under the Open Database Licence (ODbL) v1.0". Outages are only kept in your own Home Assistant; the integration does not publish them.

Not used: Energex and Ergon's own ArcGIS services (Energy Queensland's terms require a written agreement; their outages still come from council dashboards), Ausgrid (counts only, no reuse without permission), SA Power Networks, CitiPower, Powercor, United Energy, Jemena, AusNet, Evoenergy, Horizon Power, Power and Water, Vector (API key), Wellington Electricity, Orion, Aurora Energy and the Waikato network (terms or robots.txt rule out reuse, or no keyless feed).

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Enter repository URL: `https://github.com/tinkerologie/ha-ausnz-disaster-watch`
4. Select Category: **Integration**
5. Click **Add**, then find **Australia and New Zealand Disaster Watch** and click **Download**.
6. **Restart Home Assistant**.

### Removal

1. Go to **Settings** > **Devices & Services**, open **Australia and New Zealand Disaster Watch**, and choose **Delete** from the menu of each entry. Deleting an entry removes its device and entities; deleting the last entry also removes the dashboard card resource.
2. Remove any dashboard cards, automations and scripts that used the integration's entities.
3. To remove the files as well, open **HACS**, find **Australia and New Zealand Disaster Watch**, choose **Remove**, then restart Home Assistant.

---

## Setup & Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Australia and New Zealand Disaster Watch**.
3. **Step 1: Jurisdiction & Monitoring**:
   - **State / Jurisdiction**: Select your state (e.g. `QLD`, `NSW`, `VIC`, etc.).
   - **Location Source**: Choose **Use the Home Assistant home location** or **Specify a custom location**.
   - **Monitoring Radius**: Set perimeter radius (default: `50 km`).
   - **Statewide Emergency Warning Override**: Enabled by default (alerts on Level 3 warnings across state regardless of distance).
   - **Exclude Hazard Reduction**: Enabled by default (filters out planned burns).
4. **Step 2 (if Custom Location selected)**:
   - Select your **council** (every Queensland and NSW council with a Guardian IMS disaster dashboard, sorted by name) or enter custom coordinates and a council dashboard URL. A council marked "no readable dashboard" (Brisbane, Sunshine Coast) only sets the location.
   - A **Use Home Zone** entry in Queensland or NSW gets the dashboard of the council its home location is in (a distance heuristic on each council's centre and size, not council boundaries). If that council has no readable dashboard, the nearest one within 40 km is used. You can change or clear it in the options.
   - Click **Submit**.
5. Before the entry is created, the integration fetches the state's emergency feeds (and, in Australia, the Bureau of Meteorology warnings). If none of them answers, the form shows **None of the emergency feeds for this state answered**; check the internet connection of Home Assistant and submit again. Reconfigure runs the same check.

The council list (and the nearby council links on the card, up to six dashboards nearest you) is generated by `script/update-councils` (a wrapper for `script/update_councils.py`), refreshed by a monthly workflow, from the [Queensland Government list of council disaster dashboards](https://www.qld.gov.au/community/disasters-emergencies/disasters/resources-translations) and ABS Local Government Area data, keeping only dashboards that answer as Guardian IMS (a dashboard listed before is kept when it does not answer during a run, unless the run uses `--prune`). Eight Queensland dashboards (Barcoo, Gympie, Paroo, Redland, Richmond, Scenic Rim, Torres Strait Island and Yarrabah) currently send an incomplete TLS certificate chain. Browsers cope, but Home Assistant cannot connect, so they are listed as "no readable dashboard" until the councils fix them. Brisbane's ArcGIS emergency dashboard and Sunshine Coast's Disaster Hub are not read: their layers carry no licence (Brisbane: "Access to this information is intended to be through the Emergency Dashboard") and the Disaster Hub's robots.txt disallows `/api/`.

### Reconfiguration via Options Flow
Click **Configure** on the integration card to open the options menu:

- **Monitoring settings**: radius, emergency override, planned burns and council dashboard URL.
- **Road closures** (not for ACT or New Zealand): planned roadworks and events, and the optional Victorian road data key; see [Road closures and flooded roads](#road-closures-and-flooded-roads).
- **Power outages** (NSW, ACT, Tasmania, WA and New Zealand): include planned outages and turn on the extra outage feeds; see [Power outages](#power-outages).
- **Forecast signals and AI rain outlook**: the opt-in Open-Meteo features below.
- **Earthquakes** (Australian entries): include Geoscience Australia earthquakes (off by default).
- **National and regional feeds (optional)**: tsunami, satellite hotspots, heatwave, UV, state air quality and GDACS (see [Optional national and regional feeds](#optional-national-and-regional-feeds)).
- **Road and flood cameras (optional)** (Queensland, New South Wales and New Zealand): camera networks, camera radius and maximum number of cameras (see [Cameras](#cameras-camera)).
- **Add / edit / remove river points**: river flood forecast points.
- **River and creek level gauges**: the [river gauge picker](#river-and-creek-level-gauges) and optional alert levels (Queensland, New South Wales, the ACT and New Zealand).
- **Dam and weir storage levels**: the [storage picker](#dam-and-weir-storage-levels) (all Australian states and territories).

Saving any options page reloads the entry; no Home Assistant restart is needed.

To change the state or location, use **Reconfigure** on the integration entry. Reconfigure also updates the options above, and renames the entry when the state or location changes.

---

## Road closures and flooded roads

Each state's official road feed is read every few minutes and filtered to your radius. Every road item has a `category`:

| `category` | Meaning | Turns on `road_closure_nearby` | Turns on `flooded_road_nearby` |
| ---------- | ------- | :---: | :---: |
| `flooding` | Flooded road or crossing, open or closed | yes | yes |
| `closure` | Road closed or impassable | yes | no |
| `hazard` | Unplanned incident or damage on an open road (crashes, debris, landslips, 4WD only) | yes | no |
| `roadworks` | Planned roadworks (listed only with the option on) | no | no |
| `special_event` | Planned special events (listed only with the option on) | no | no |

Breakdowns, traffic signal faults, ferries, congestion and standing heavy-vehicle limits are not listed. Timestamps are converted from the agency's local time zone. A feed whose sources are all down keeps its last good items for up to 30 minutes. After that, or when any one source of a multi-source feed (for example one of the Live Traffic NSW files) has been down for more than 30 minutes, `…_road_closure_nearby` and `…_flooded_road_nearby` become unavailable rather than showing `off`; the remaining sources' items are still listed.

| State | Source | Key | Licence |
| ----- | ------ | --- | ------- |
| NSW | [Live Traffic NSW](https://www.livetraffic.com) hazard feeds (incidents, floods, fires, alpine, council incidents; roadworks and major events with the option) | none | CC BY 4.0, Transport for NSW |
| QLD | [QLDTraffic](https://qldtraffic.qld.gov.au) `events_v2.geojson` (the keyless GeoJSON feed; the documented API needs a key) | none | CC BY 4.0, Department of Transport and Main Roads; council events are attributed to the council that provided them |
| VIC | DTP [Unplanned Disruptions - Road](https://opendata.transport.vic.gov.au/dataset/unplanned-disruptions-road) API v3 | free DTP key | CC BY 4.0, Department of Transport and Planning |
| SA | [Traffic SA](https://www.traffic.sa.gov.au) open data (incidents and closures; roadworks with the option) | none | CC BY, Department for Infrastructure and Transport |
| WA | Main Roads WA WebEOC road incidents and closures (roadworks and events with the option) | none | CC BY 4.0, Commissioner of Main Roads |
| NT | [NT Road Report](https://roadreport.nt.gov.au) obstructions | none | reuse terms not published; attributed to NT Road Report |
| TAS | [TasALERT](https://alert.tas.gov.au) road closures | none | feed access by request (not yet granted), as for the TasALERT hazard feed |

QLD council dashboards (Guardian IMS) still add council road closures. A council copy of an event already in the state feed (same QLDTraffic event ID, or the same road and suburb within 1 km) is listed once, with the state feed's details. ACT has no road feed yet. New Zealand road closures come from NZTA (#24); their categories are read from the event's impact and description, so a flooded NZ road also turns on `…_flooded_road_nearby`.

The **Road closures** options page has:

- **Include planned roadworks and events** (off by default; not shown for ACT, which has no road feed, or New Zealand, whose NZTA feed never lists planned roadworks): lists planned roadworks and special events from the state road feed in `…_road_closures_count`. They never turn on `…_road_closure_nearby` or `…_flooded_road_nearby`.
- **VicRoads (DTP) open data API key** (Victoria only, optional): Victorian road data needs a free key. Register at [opendata.transport.vic.gov.au](https://opendata.transport.vic.gov.au/), subscribe to the *Unplanned Disruptions - Road* API, and paste the key. Leave it empty to skip Victorian road data. The key is stored in the entry options and redacted from diagnostics.

---

## Emergency broadcaster radio

In Australia, ABC Local Radio is the official emergency broadcaster: warnings tell you to "listen to ABC Local Radio", and local stations switch to emergency coverage. In New Zealand, RNZ is a lifeline broadcaster. Radio often keeps working when power or mobile networks are under strain.

Turn it on in **Options > Emergency broadcaster radio**. It is off by default. Choose **Nearest station**, or pick a station yourself: the nearest station is matched by its studio location, which is not always the station that covers your town.

- **Sensor** `sensor.<device>_emergency_broadcaster` (disabled by default; enable it in the entity settings): the station name, with `stream_url`, `media_content_id`, `region`, `network`, `station_page`, `selection` (`nearest` or `chosen`) and `distance_km`. It stays available when the hazard feeds are down.
- **Media browser:** **Media > Australia and New Zealand Disaster Watch** lists the emergency broadcaster of each location. `media-source://ausnz_disaster_watch/emergency_broadcaster/<entry_id>` always plays the location's current station, so automations keep working if you move house or change the station. See [automation example 4](#4-play-the-emergency-broadcaster-on-an-emergency-warning).
- **Stations:** all 52 ABC Local Radio regions and RNZ National, as HTTPS HLS streams. The table is bundled (`data/emergency_broadcasters.json`, built by `script/update-broadcasters` from the public-domain [Radio Browser](https://www.radio-browser.info/) directory and checked against the ABC and RNZ station pages), so nothing is looked up at runtime. Your media player streams directly from the ABC or RNZ for your personal listening; the integration does not proxy or record audio.
- **Not included:** AM/FM frequencies for battery radios (no open machine-readable source yet).

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
| Map | `satellite_layer` | `none` | Satellite imagery under the incidents: `himawari_visible` (daytime clouds, every 10 minutes), `himawari_ir` (clouds day and night, every 10 minutes), `viirs_truecolor` (daily true colour image: smoke, burn scars, flood extent) or `none`. |
| Map | `show_cyclone_tracks` | `false` | Draw the GDACS forecast track, wind areas and uncertainty cone of current cyclones listed by the **Regional Disaster Alerts** sensor. Needs the integration option **Regional disaster alerts (GDACS)**. |
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

Satellite imagery (`satellite_layer`, off by default) comes from [NASA GIBS](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance), which needs no key:

- **Himawari** visible and infrared show clouds and storms where radar has no coverage (inland and offshore). They animate on the same timeline as the radar: each radar frame shows the satellite image taken at or before it. With the radar off, the satellite frames animate on their own. Reduced motion shows the latest frame only. Himawari-9 belongs to the Japan Meteorological Agency, which is credited on the map.
- **VIIRS true colour** is one image a day, useful the day after an event for smoke plumes, burn scars and flood extent. Chips under the map pick today, yesterday or the day before (UTC dates). Before 09:00 UTC today's image does not yet cover Australia and New Zealand, so yesterday's is shown first.

Cyclone tracks (`show_cyclone_tracks`, off by default) are drawn from GDACS for each current tropical cyclone in the **Regional Disaster Alerts** sensor: the observed and forecast track (dashed), the wind areas and the uncertainty cone. The card fetches only GDACS tropical cyclone geometry links. GDACS output is an automatic model estimate, so the map says so: follow BoM and MetService warnings.

Chips under the map hide or show the satellite layer and cyclone tracks. The attribution on the map lists only the layers that are on. Your browser fetches the radar, satellite and cyclone data directly, not Home Assistant; see the [data source register](docs/development/DATA_SOURCES.md#shown-in-the-card-fetched-by-the-browser).

### Upgrading from the single card

**Breaking change:** the old single card was replaced by the card suite.

- `custom:aus-disaster-card` was removed. Change it to `custom:ausnz-disaster-card` (the all-in-one card) or use the focused cards.
- The all-in-one card's `max_incidents` and `show_map_button` options were removed and are ignored. Use the incidents card's `max_items` and the map card instead.
- The integration removes the old `/ausnz_disaster_watch/aus-disaster-card.js` resource automatically. If you manage Lovelace resources in YAML, delete that resource yourself.

---

## Ask your voice assistant

The integration gives Assist, and any LLM conversation agent that uses the Assist API (OpenAI, Anthropic, Google, Ollama and others), three read-only tools. You can then ask questions such as "Is there anything I need to worry about near home?", "What's the fire danger tomorrow?" or "Are any roads closed nearby?".

| Tool | What it answers |
| --- | --- |
| `ausnz_disaster_watch__get_disaster_situation` | The highest warning level, active warnings and incidents nearest first (up to 10), weather warnings, fire danger today and tomorrow with the total fire ban, road closures and power outages |
| `ausnz_disaster_watch__get_fire_danger` | The fire danger rating and total fire ban for `today`, `tomorrow`, `day3` or `day4` (the fire season in New Zealand) |
| `ausnz_disaster_watch__list_hazards` | Warnings and incidents filtered by `category` (fire, flood, storm, earthquake, tsunami, road, power, other), `max_distance_km` and `min_level` (advice, watch_and_act, emergency_warning), up to 20 |

- **Setup:** none. In your conversation agent's options, set **Control Home Assistant** to **Assist**. The tools are offered for a location only when at least one of its entities is exposed to Assist (**Settings > Voice assistants > Expose**), so your exposure choices apply. The MCP Server integration serves the same tools to MCP clients.
- **Several locations:** with more than one location the assistant passes the location's name (the entry title). If it doesn't, the tool lists the locations so the assistant can ask you.
- **Feed health:** every answer says whether each feed is `ok`, `stale` (its last fetch failed and its last good data stands in) or `failed`, with the time of its last good fetch. When a feed is not `ok`, the answer is marked incomplete, and the assistant is told to say so and never to call the situation all clear.
- **What it is not:** the tools only read what the integration already fetched, so they cannot replace official warnings. Follow official advice, and call 000 (Australia) or 111 (New Zealand) in an emergency.

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

### 4. Play the Emergency Broadcaster on an Emergency Warning

Turn on the [emergency broadcaster](#emergency-broadcaster-radio) first. Replace `ENTRY_ID` with the entry's ID (the `media_content_id` attribute of the emergency broadcaster sensor shows the full ID).

```yaml
alias: "Emergency Warning: Play the Emergency Broadcaster"
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

States of the highest warning level and fire danger rating sensors are snake_case (`watch_and_act`, `extreme`); the dashboard and history show them translated.

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

---

## Use cases

- Get a phone notification, flash lights or play the [emergency broadcaster](#emergency-broadcaster-radio) when an Emergency Warning or Watch and Act is issued near home, or when home is inside a warning area.
- Close windows, turn off evaporative coolers or start a pump when a bushfire, flood or storm warning gets close.
- Check the fire danger rating and total fire ban before running a mower, a welder or a fire pit.
- Watch nearby river gauges and dam storages during heavy rain, with an alert level per gauge.
- See road closures and flooded roads before a trip, and power outages that affect the area.
- Keep a holiday house, a relative's home or a workplace under watch with a second entry for that location.
- Ask Assist "are there any warnings near home?" (see [Ask your voice assistant](#ask-your-voice-assistant)).

## Data updates

The integration polls public feeds; nothing is pushed to it.

| Data | Interval |
| ---- | -------- |
| Hazard and warning feeds, council dashboards and road feeds | Every 5 minutes; every minute while an Emergency Warning or Watch and Act is active in the radius |
| Power outages | Every 5 minutes |
| Fire danger ratings and total fire bans | Every 30 minutes |
| River and creek gauges | Every 15 minutes |
| Dam and weir storages | Every hour |
| Weather hazard signals | Every hour |
| River flood forecast and AI rain outlook | Every 6 hours |
| Camera images | When a dashboard or the camera view asks for a frame |

When a feed fails, its last good data stands in for up to 30 minutes, so a short outage does not look like an all-clear; after that its incidents are dropped. A feed going down and coming back is logged once each. When every hazard feed fails, the hazard entities become unavailable until a feed answers again. Download the [diagnostics](#troubleshooting) to see each hazard feed's status and its last successful fetch.

## Known limitations

- Each entry watches one location. Add another entry for each extra location.
- Coverage depends on what each agency publishes. NSW SES, VicEmergency and ACT warning areas are not read (see [Warning Areas](#key-features)), and some council dashboards cannot be read (see [Setup & Configuration](#setup--configuration)).
- Distances are to the published warning area where an agency publishes one, otherwise to a single point, which can be far from the edge of a large fire or flood.
- Hazard attributes (`warning_level`, the emergency warning sensor's `highest_warning_level` attribute) and fire danger `forecast` days keep the English level names (`Watch and Act`, `Extreme`); only the two sensors' states are snake_case.
- Forecast signals and the AI rain outlook are model output, not official warnings.
- Data is only as current as each feed. Always follow the official advice of your emergency services; this integration is not a warning service.

## Troubleshooting

- **"None of the emergency feeds for this state answered" during setup**: Home Assistant could not reach the state's feeds or the Bureau of Meteorology. Check that Home Assistant can reach the internet and try again; an agency's feed may also be down for maintenance.
- **Entities are unavailable**: every hazard feed failed at the last update. The log names each feed that went down. Entities recover by themselves at the next successful update.
- **An incident shown on an agency website is missing**: check the monitoring radius and **Exclude Hazard Reduction** in the options, and that the entry's state is the incident's state. Statewide Emergency Warning Override only widens the radius for Emergency Warnings.
- **Diagnostics**: on the integration entry, open the menu and choose **Download diagnostics**. The file lists each hazard feed's status and last successful fetch. Coordinates, the location name and the council dashboard are redacted, but check the file before sharing it.
- **Debug logging**: choose **Enable debug logging** on the integration entry, reproduce the problem, then **Disable debug logging** to download the log. Or add this to `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.ausnz_disaster_watch: debug
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
| NSW | Live Traffic NSW road hazards (Transport for NSW) | CC BY 4.0 |
| QLD | QLDTraffic road events (Transport and Main Roads) | CC BY 4.0; keyless path not in the API documentation |
| VIC | DTP Unplanned Disruptions - Road (only with your own key) | CC BY 4.0 |
| SA | Traffic SA road incidents and closures | CC BY |
| WA | Main Roads WA road incidents and closures | CC BY 4.0 |
| NT | NT Road Report | No licence published |
| TAS | TasALERT road closures | Feed access by request; not yet granted |
| AU | Bureau of Meteorology warnings via WMO SWIC | Personal, non-commercial use under BoM terms |
| NZ | GeoNet | CC BY 3.0 NZ |
| NZ | NEMA (Civil Defence) alerts | CC BY 4.0 |
| NZ | MetService CAP warnings | CC BY 4.0, CAP Code of Practice |
| NZ | NZ Transport Agency Waka Kotahi road events (`trafficnz.info`) | No licence stated on data.govt.nz; open data, unverified |
| QLD, NSW | QLDTraffic flood and web cameras (opt-in) | CC BY 4.0; images credited to their supplier |
| NZ | NZ Transport Agency traffic cameras (opt-in) | No licence stated on data.govt.nz; unverified |
| QLD | Water Monitoring Information Portal river gauges (opt-in) | CC BY 4.0 |
| NSW, ACT | WaterNSW real-time river gauges (opt-in) | CC BY (data.gov.au lists 3.0 and 4.0) |
| NZ | Regional council Hilltop river gauges (opt-in) | Hawke's Bay CC BY; other councils unverified |
| AU | Bureau of Meteorology Water Data Online dam and weir storages (opt-in) | CC BY 3.0 AU per data owner; other owners excluded |
| NSW, ACT | WaterNSW real-time storage gauges for matched dam storages (opt-in) | CC BY |
| TAS | Hydro Tasmania lake levels for matched dam storages (opt-in) | CC BY 3.0 AU |

GeoNet and NSW RFS feeds are read with the maintained `aio_geojson_geonetnz_quakes`, `aio_geojson_geonetnz_volcano` and `aio_geojson_nsw_rfs_incidents` libraries (Apache-2.0), the same ones Home Assistant core uses.

Several publishers restrict reuse to personal, non-commercial use or require permission. This integration is for personal home automation. Do not use it to republish these feeds or for commercial purposes without checking each publisher's terms.

The full register, with every endpoint, terms evidence, rate limits and the decisions taken for restricted sources, is in [docs/development/DATA_SOURCES.md](docs/development/DATA_SOURCES.md).

---

## Quality Scale & Standards

- **Integration Quality Scale**: Gold. [`quality_scale.yaml`](custom_components/ausnz_disaster_watch/quality_scale.yaml) records each [rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules) as done, exempt (with the reason) or still to do.
- **Type Checking**: Pyright in basic mode.
- **Modern Code Standards**: Linted and formatted with Ruff (`py313`).
- **Comprehensive Test Suite**: Tested with `pytest-homeassistant-custom-component`.
- **Database Safety Guardrail**: All entity attributes are strictly capped to ensure payloads remain well under the 16 KB SQLite threshold.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
