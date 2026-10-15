# Changelog

All notable changes to this project will be documented in this file.

The changelog uses date sections in `YYYY.MM.DD` format.

## [Unreleased]

### Fixed

- Feed outages are no longer invisible. A provider that cannot fetch or decode its feed now reports itself unavailable instead of returning "no hazards". The coordinator keeps that feed's last good hazards for up to 30 minutes (so a cancelled warning cannot linger through a long outage), logs once when a feed goes down and once when it recovers, and raises a translated `UpdateFailed` when every hazard feed is down, so entities become unavailable (and setup retries) instead of showing "All Clear". One malformed record now skips only itself, not the rest of its feed. Coordinator data exposes `feeds_ok`/`feeds_failed` (#16).
- Agency timestamps without a time zone are interpreted in the agency's local zone (Brisbane, Sydney, Melbourne, Adelaide, Perth, Hobart, Darwin, Auckland) instead of UTC, so `updated_at` is no longer 8–13 hours off. Zone abbreviations such as `AEDT` are understood, ACT uses the incident's "Updated:" time, and NSW RFS parses `UPDATED` as Sydney time. Unparsable or missing times are now omitted instead of being reported as "now" (#13).
- Hazard IDs are deterministic: NT incidents no longer use list position or a 20-character location prefix (which collided), the BoM fallback no longer uses the per-process `hash()`, and WA items without an ID no longer collapse into one. This stops `geo_location` entity churn after restarts and feed reordering (#7).
- Declare the third-party packages the integration imports (`defusedxml>=0.7.1`, `pydantic>=2.10`) in `manifest.json`, so installs without them no longer fail to load (#17).
- CI, release and PR-governance workflows now target `custom_components/ausnz_disaster_watch/`; release creation and the committed-bundle check work again (#9).
- Manifest documentation, issue tracker and codeowner, README links, HACS repository URL and `hacs.json` name now match `tinkerologie/ha-ausnz-disaster-watch` (#9).
- Hassfest validation gets `contents: read`; with `permissions: {}` it could not check out the private repository and always failed. HACS validation is skipped while the repository is private, because HACS cannot read or install private repositories (#9).
- Lovelace card TypeScript build errors (undeclared sensor variables) and the weather observation entity lookup (#4).

### Changed

- Option changes are applied by reloading the entry (`OptionsFlowWithReload`) and the update listener is removed; Home Assistant 2026.12 breaks integrations that combine an update listener with `async_update_reload_and_abort` (#15).
- The coordinator is stored in typed `entry.runtime_data` instead of `hass.data[DOMAIN]`, receives its config entry explicitly, and initialises its base class before reading config values, so entries without coordinates fall back to the Home Assistant home location instead of raising `AttributeError` (#5, #8).
- Entity names come from translations (`_attr_translation_key`) instead of hard-coded `_attr_name`; names are unchanged. Imports use public Home Assistant modules (#8).
- CI uploads test coverage to Codecov (`codecov.yml`: project coverage may not drop, patch coverage 100%) (#9).
- New `script/check-imports` and CI job verify every module imports in a clean Home Assistant environment with only the declared requirements (#17).
- README entity tables, card type and automation examples (modern `triggers`/`actions` syntax, real entity IDs) updated; AGENTS.md/GEMINI.md/Copilot instructions describe the real package layout and domain (#9).
- Browser regression test steps removed from CI until the card suite rebuild adds Playwright tests (#43).

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
