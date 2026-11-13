import { css, html, nothing, type PropertyValues, type TemplateResult } from "lit";

import { alert, empty, header } from "../components/render";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatDateTime, formatNumber, isUnavailable, numberAttr, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import type { HomeAssistant, LovelaceConfigForm } from "../types";
import { baseSchema, computeHelper, computeLabel } from "./base";
import { MapCard } from "./map-card";
import { cycloneRefs } from "./map/gdacs";
import type { MapViewOptions } from "./map/leaflet-map";

function cycloneRows(hass: HomeAssistant, device: string | undefined): Record<string, unknown>[] {
  const state = stateFor(hass, device, KEY.cycloneTracker);
  const rows: unknown = state?.attributes.cyclones;
  if (!state || isUnavailable(state) || !Array.isArray(rows)) return [];
  return rows.filter(
    (row): row is Record<string, unknown> =>
      !!row && typeof row === "object" && typeof row.id === "string" && typeof row.title === "string",
  );
}

/** A focused view of one selected cyclone and its latest GDACS track. */
export class CycloneTrackerCard extends MapCard {
  static override properties = { ...MapCard.properties, _selected: { state: true } };

  static override styles = [
    ...MapCard.styles,
    css`
      .details {
        display: grid;
        gap: var(--ha-space-2);
        padding: 0 var(--ha-space-4) var(--ha-space-3);
      }
      .details select {
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: var(--ha-space-1);
        color: var(--primary-text-color);
        font: inherit;
        padding: var(--ha-space-2);
      }
      .details p {
        margin: 0;
      }
      .links {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-3);
      }
    `,
  ];

  protected override readonly titleKey = "card.cyclones.name" as const;
  protected override readonly usesIncidents = false;
  private declare _selected?: string;

  protected override entityKeys() {
    return [KEY.cycloneTracker];
  }

  static override getConfigForm(): LovelaceConfigForm {
    return { schema: baseSchema(), computeLabel, computeHelper, assertConfig: (config) => this.validateConfig(config) };
  }

  protected override mapInputsChanged(changed: PropertyValues<this>): boolean {
    return super.mapInputsChanged(changed) || changed.has("_selected" as keyof CycloneTrackerCard);
  }

  private selection(rows: Record<string, unknown>[]): Record<string, unknown> | undefined {
    return rows.find((row) => row.id === this._selected) ?? rows[0];
  }

  protected override viewOptions(): MapViewOptions {
    const hass = this.hass!;
    const selected = this.selection(cycloneRows(hass, this.deviceId));
    const latitude = numberAttr(selected?.latitude);
    const longitude = numberAttr(selected?.longitude);
    const cycloneFocus =
      typeof selected?.id === "string" && latitude !== undefined && longitude !== undefined
        ? { id: selected.id, latitude, longitude, name: String(selected.title) }
        : undefined;
    return {
      incidents: [],
      darkMode: !!hass.themes?.darkMode,
      radar: false,
      radarOpacity: 0,
      satellite: "none",
      viirsDay: 0,
      cyclones: selected ? cycloneRefs([selected]) : [],
      cycloneFocus,
    };
  }

  protected override renderBody(hass: HomeAssistant): TemplateResult {
    const state = stateFor(hass, this.deviceId, KEY.cycloneTracker);
    const title = header({ title: this.cardTitle(), icon: "mdi:weather-hurricane" });
    if (!state) return html`${title}${empty("mdi:weather-hurricane", t(hass, "cyclones.disabled"))}`;
    if (isUnavailable(state)) return html`${title}${alert("info", t(hass, "state.unavailable"))}`;

    const rows = cycloneRows(hass, this.deviceId);
    const selected = this.selection(rows);
    const stale = state.attributes.stale === true;
    const status = stale ? alert("info", t(hass, "cyclones.stale")) : nothing;
    if (!selected) {
      return html`${title}${status}${stale ? nothing : empty("mdi:weather-hurricane", t(hass, "cyclones.empty"))}`;
    }

    const updated = formatDateTime(hass, selected.updated_at ?? selected.from_date);
    const distance = numberAttr(selected.distance_km);
    const details = stringAttr(selected.severity);
    const id = numberAttr(selected.event_id);
    const report = id !== undefined && Number.isSafeInteger(id) && id > 0
      ? `https://www.gdacs.org/report.aspx?eventtype=TC&eventid=${id}`
      : undefined;
    const official = state.attributes.jurisdiction === "NZ"
      ? "https://www.metservice.com/warnings/tropical-cyclone-activity"
      : "https://www.bom.gov.au/weather-and-climate/severe-weather-and-warnings/tropical-cyclone";
    const geometryAvailable = cycloneRefs([selected]).length > 0;
    return html`${title}
      <div class="details">
        ${status}
        ${rows.length > 1 ? html`
          <label>
            ${t(hass, "cyclones.select")}
            <select .value=${String(selected.id)} @change=${(event: Event) => {
              this._selected = (event.target as HTMLSelectElement).value;
            }}>
              ${rows.map((row) => html`<option value=${String(row.id)} ?selected=${row.id === selected.id}>${row.title}</option>`)}
            </select>
          </label>
        ` : html`<p><strong>${selected.title}</strong></p>`}
        ${details ? html`<p>${details}</p>` : nothing}
        ${updated ? html`<p>${t(hass, "cyclones.updated")}: ${updated}</p>` : nothing}
        ${distance === undefined ? nothing : html`<p>${t(hass, "cyclones.distance", { distance: formatNumber(hass, distance) })}</p>`}
        <p class="links">
          ${report ? html`<a href=${report} target="_blank" rel="noopener noreferrer">${t(hass, "cyclones.report")}</a>` : nothing}
          <a href=${official} target="_blank" rel="noopener noreferrer">${t(hass, "cyclones.official")}</a>
        </p>
      </div>
      <div class="map-wrap"><div class="map" role="region" aria-label=${String(selected.title)}></div></div>
      ${!geometryAvailable || this._status.cyclones === "unavailable" || this._loadError
        ? html`<div class="notice">${alert("info", t(hass, "map.cyclones_unavailable"))}</div>`
        : nothing}
      ${this._status.cyclones === "ok" ? html`<p class="legend">${t(hass, "cyclones.observed")} · ${t(hass, "cyclones.forecast")} · ${t(hass, "cyclones.cone")}</p>` : nothing}
      <p class="legend">${t(hass, "map.cyclone_legend")}</p>`;
  }
}
