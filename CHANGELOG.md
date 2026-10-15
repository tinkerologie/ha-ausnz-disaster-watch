# Changelog

All notable changes to this project will be documented in this file.

The changelog uses date sections in `YYYY.MM.DD` format.

## [Unreleased]

### Added

- **Australia and New Zealand Disaster Watch Integration**: Complete real-time hazard, disaster, and emergency incident monitoring integration for Home Assistant across Australian jurisdictions and New Zealand.
  - Nationwide Australian and New Zealand coverage:
    - **Queensland (QLD)**: QFD incident feed, BoM telemetry, and local Council Disaster Dashboards (Moreton Bay, Sunshine Coast, Brisbane, Gold Coast, Cairns, Townsville, etc.).
    - **New South Wales (NSW)**: NSW RFS bushfire and NSW SES storm/flood incident feeds.
    - **Victoria (VIC)**: EMV OSOM (VicEmergency) multi-agency emergency incidents.
    - **Western Australia (WA)**: Emergency WA / DFES official warnings, active CAD incidents, and fire danger ratings.
    - **South Australia (SA)**: SA SAFECOM / CFS CAP-AU XML warning and incident feed.
    - **Tasmania (TAS)**: TasALERT multi-agency emergency alert feed.
    - **Northern Territory (NT)**: NT Police, Fire and Emergency Services (PFES) incident map data.
    - **Australian Capital Territory (ACT)**: ACT Emergency Services Agency (ESA) GeoRSS feed.
    - **New Zealand (NZ)**: GeoNet earthquakes REST API, GeoNet volcanic activity alerts, NEMA AlertHub CAP Atom feed, and MetService severe weather warning RSS.
    - **Federal (BoM)**: Bureau of Meteorology national and statewide warning summaries.
  - Australian Warning System (AWS) & CAP normalization across all jurisdictions.
  - Multi-platform sensor suite:
    - `geo_location` entities with dynamic lifecycle synchronization and native Home Assistant map plotting.
    - `binary_sensor` entities for active threats, emergency warnings, road closures, and power outages.
    - `sensor` entities for active hazard count, highest warning level, closest incident distance, nearest incident title, fire danger ratings, air quality, local weather observation, road closures count, power outages count, weather warnings count, and relief facilities.
    - `camera` platform providing live flood camera and traffic webcam snapshot streaming.
  - Custom Lovelace dashboard cards (`ausnz-disaster-card` / `aus-disaster-card`).
  - Professional branding package in `branding/` (`icon.png`, `logo.png`, `icon.svg`).
  - Strict 100% test coverage across all integration files, zero lint warnings/errors, and complete validation with Home Assistant 2026 standards.
