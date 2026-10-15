# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read [`AGENTS.md`](AGENTS.md) for the mandatory contribution workflow (issue first, CodeRabbit plan, `feat/<issue>-…` / `fix/<issue>-…` branches, `CHANGELOG.md` `[Unreleased]` entry, draft PRs), the breaking-change policy and HA coding conventions. Per-file-type rules live in `.github/instructions/*.instructions.md` (check the `applyTo` glob for the file you are editing).

Where AGENTS.md or the `.github/instructions/` files (template-derived) conflict with the code, trust the code. The integration uses flat modules plus a `providers/` package and registers no service actions.

## Identifiers

- **Domain:** `ausnz_disaster_watch` (repo: `tinkerologie/ha-ausnz-disaster-watch`)
- **Title:** Australia and New Zealand Disaster Watch
- **Code:** `custom_components/ausnz_disaster_watch/`
- **Class names:** a mix of `AustralianDisasterWatch*` and `AusNZDisasterWatch*`. Module-level aliases keep both working (`AusNZDisasterWatchCoordinator`, `AustralianDisasterWatchEntity`, `EmergencyDataCoordinator`, `EmergencyHazardBaseEntity`). Don't remove the aliases without updating every importer.

## Commands

Always use the `script/` wrappers rather than raw `pytest` / `hass` / `pip`. They activate the venv at `~/.local/ha-venv` or `.local/ha-venv` and run `script/clean --minimal` so an installed copy of the package doesn't shadow `custom_components/`.

```bash
script/setup/bootstrap            # first-time environment setup
script/check                      # pyright + ruff check + codespell (+ hassfest if .local/ha-core exists)
script/lint                       # ruff auto-fix + format
script/test                       # all tests
script/test tests/test_coordinator.py              # one file
script/test tests/test_coordinator.py -k radius    # one test by keyword
script/test --cov                 # coverage, terminal report
script/hassfest                   # validate manifest/translations against HA core
script/check-imports              # clean venv: import every module with only manifest requirements
./script/develop                  # run HA with config/ (port 8123, debug logging)
```

pytest runs with `filterwarnings = error`, so any new warning fails the suite.

Lovelace card (TypeScript + Lit, in `frontend/`):

```bash
cd frontend && npm ci && npm run typecheck && npm run lint:modern && npm test && npm run build && npm run test:browser
```

`npm run build` writes `custom_components/ausnz_disaster_watch/frontend/ausnz-disaster-card.js` and the lazily loaded map chunk (the folder is emptied first). The built bundle is committed, so rebuild and commit it whenever `frontend/src/` changes. `script/check` also runs `lint:modern` and `lint:drift`.

Every dashboard card must be modern and polished, follow Home Assistant's current UI/UX patterns, and use no deprecated features (issues #33, #41, #42):
- Render inside `ha-card`, styled only with HA design tokens (`--ha-space-*`, `--ha-font-*`, `--ha-border-radius-*`, semantic `--ha-color-{fill,on,border}-*`).
- Never use `--paper-*` variables, hex or rgb colours, emoji icons, or `mwc-*`/`paper-*`/`ha-chip` elements.
- Use native HA components (`ha-icon-button`, `ha-assist-chip`/`ha-filter-chip`, `ha-alert`, `ha-md-list-item`) instead of clickable `div`/`span`. Only use elements that are defined on every dashboard; `frontend/src/ha/preload.ts` lists the verified set (`ha-md-list` is not in it, so lists use a `role="list"` container).
- Provide `getGridOptions`, `getConfigForm` and a `window.customCards` entry with `preview: true`.
- Format values with `hass.formatEntityState` and `hass.locale`.
- Before using a token or element, confirm it still exists in the installed frontend (`npm run lint:drift` checks this automatically against `hass_frontend/frontend_latest/`).

## Architecture

Data flows **providers → coordinator → entities**. Entities never fetch data themselves.

- **`providers/`**: one `BaseHazardProvider` subclass per jurisdiction (`qld`, `nsw`, `vic`, `wa`, `sa`, `tas`, `nt`, `act`, `nz`), plus `bom` (Bureau of Meteorology). `providers/__init__.py:get_providers_for_config` chooses the providers from the configured `state`. It adds BoM for every Australian state but not for NZ.
  - The only abstract method is `async_fetch_hazards()`. The other `async_fetch_*` methods (power outages, road closures, weather warnings, news, fire danger, weather telemetry, air quality, relief facilities, cameras, nearby councils) return empty values by default, and a provider overrides only the feeds its jurisdiction offers.
  - Use `_async_request` for HTTP. It retries 429/5xx responses with exponential backoff.
  - Every provider normalises its feed into the Pydantic v2 models in `models.py`, mainly `CanonicalHazard` with a `WarningLevel` from the Australian Warning System.
- **`coordinator.py`**: calls all providers concurrently with `asyncio.gather`. A provider that fails is logged and returns nothing; it never fails the whole update.
  - Applies spatial filtering using a haversine distance from the configured location (home zone or a custom lat/lon). An Emergency Warning anywhere in the state passes the radius filter when `override_emergency` is on, and planned burns are dropped when `exclude_hazard_reduction` is on.
  - Returns a `DisasterCoordinatorData`. The polling interval switches between 300 s and 60 s (`THREAT_SCAN_INTERVAL`) depending on whether there is an active threat nearby.
  - Config is read from `entry.data` merged with `entry.options` (options win) and validated with `DisasterWatchConfigModel`. An options change calls `update_options()` and refreshes in place; it does not reload the config entry.
- **Entities** (`sensor`, `binary_sensor`, `geo_location`, `camera`):
  - Entities inherit `AusNZDisasterWatchEntity`, which sets the unique ID to `{entry_id}_{entity_key}` and puts every entity on one service device per entry. The exception is `geo_location.py`, which subclasses `CoordinatorEntity` directly and adds and removes map pins as hazards come and go.
  - Keep state attributes well under HA's 16 KB recorder limit. Store centroids and scalar fields, never full geometry.
- **`config_flow.py`**: a multi-step flow covering state, location mode, then a custom location or one of the preset council dashboards in `const.PRESET_COUNCIL_DASHBOARDS`, plus an options flow. `infer_state_from_coordinates` guesses the state from coordinates.
- **`frontend.py`**: `async_setup_entry` serves the built card suite at `/ausnz_disaster_watch/` and registers `ausnz-disaster-card.js` as the integration's only Lovelace resource, with a content-hash cache buster. It deletes the legacy `aus-disaster-card.js` resource and duplicates, and `async_remove_entry` removes the resource when the last entry is deleted. If `http` or `frontend` are not loaded yet, it defers registration until HA has started.
- **`frontend/`** (Lit + Vite, built into `custom_components/ausnz_disaster_watch/frontend/`, committed): ten focused cards plus the all-in-one `custom:ausnz-disaster-card`. Cards resolve entities through `hass.entities` (platform, device, translation key) and geolocation incidents by their `entry_id` attribute, never by entity-ID suffix. The map card loads Leaflet as a lazy chunk. `npm run lint:modern` and `npm run lint:drift` enforce HA design tokens and native components (#42); `npm test` and `npm run test:browser` cover the cards.

## Tests

`tests/` has one file per module. `tests/conftest.py` provides `CanonicalHazard` fixtures for each warning level (emergency, watch-and-act, advice, hazard reduction, distant emergency) and a `MockConfigEntry`. AGENTS.md says not to add or change tests unless asked.
