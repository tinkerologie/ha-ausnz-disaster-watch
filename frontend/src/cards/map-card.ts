import { css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { deviceName, geoLocationsFor, incidentTitle } from "../ha/entities";
import { formatDateTime, numberAttr, relativeTime, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import { awsPresentation } from "../model/aws";
import { alert, header } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import { assertBoolean, assertNumber, assertPositiveInt, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";
import { LEVEL_LABELS } from "./incidents";
import type { IncidentMap, MapViewOptions, RadarStatus } from "./map/leaflet-map";

export interface MapCardConfig extends BaseCardConfig {
  zoom?: number;
  radar?: boolean;
  radar_opacity?: number;
}

const DEFAULT_RADAR_OPACITY = 0.7;

type MapModule = typeof import("./map/leaflet-map");
let mapModule: Promise<MapModule> | undefined;
const loadMapModule = () => (mapModule ??= import("./map/leaflet-map"));

/** Incidents of the entry on a map, with animated RainViewer radar over HA's basemap (#41). */
export class MapCard extends DisasterCard<MapCardConfig> {
  static override properties = {
    ...DisasterCard.properties,
    _radar: { state: true },
    _loadError: { state: true },
  };

  static override styles = [
    ...DisasterCard.styles,
    css`
      ha-card,
      section.embedded {
        min-height: calc(var(--ha-space-20) * 3.5);
      }
      .map-wrap {
        position: relative;
        flex: 1;
        min-height: calc(var(--ha-space-20) * 2.5);
        margin: var(--ha-space-2) 0 0;
      }
      :host([embedded]) .map-wrap {
        height: calc(var(--ha-space-20) * 4);
        flex: none;
      }
      .map {
        position: absolute;
        inset: 0;
        background-color: var(--ha-color-fill-neutral-quiet-resting);
        font-family: var(--ha-font-family-body);
        z-index: 0;
      }
      .map.dark .basemap {
        filter: invert(0.9) hue-rotate(170deg) brightness(1.5) contrast(1.2) saturate(0.3);
      }
      .map .leaflet-control-attribution {
        background-color: color-mix(in srgb, var(--card-background-color, var(--ha-card-background)) 80%, transparent);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-xs);
      }
      .map .leaflet-control-attribution a {
        color: var(--primary-color);
      }
      .map .leaflet-bar {
        border: var(--ha-border-width-sm) solid var(--divider-color);
        box-shadow: none;
        border-radius: var(--ha-border-radius-md);
        overflow: hidden;
      }
      .map .leaflet-bar a {
        background-color: var(--card-background-color, var(--ha-card-background));
        color: var(--primary-text-color);
        border-bottom-color: var(--divider-color);
      }
      .map .leaflet-tooltip {
        background-color: var(--card-background-color, var(--ha-card-background));
        color: var(--primary-text-color);
        border: var(--ha-border-width-sm) solid var(--divider-color);
        border-radius: var(--ha-border-radius-md);
        box-shadow: none;
        font-family: var(--ha-font-family-body);
        font-size: var(--ha-font-size-s);
      }
      .map .leaflet-tooltip::before {
        display: none;
      }
      .map .radar-frame {
        transition: opacity var(--ha-animation-duration-slow) ease-in-out;
      }
      .map .incident {
        fill-opacity: 0.6;
        stroke-width: 2;
        cursor: pointer;
      }
      .map .incident:focus-visible {
        outline: none;
        stroke-width: 4;
        stroke: var(--primary-text-color);
      }
      .map .tone-red {
        fill: var(--red-color);
        stroke: var(--red-color);
      }
      .map .tone-orange {
        fill: var(--orange-color);
        stroke: var(--orange-color);
      }
      .map .tone-amber {
        fill: var(--amber-color);
        stroke: var(--amber-color);
      }
      .map .tone-blue {
        fill: var(--blue-color);
        stroke: var(--blue-color);
      }
      .map .tone-grey {
        fill: var(--grey-color);
        stroke: var(--grey-color);
      }
      .map .home-zone {
        fill: var(--primary-color);
        fill-opacity: 0.08;
        stroke: var(--primary-color);
        stroke-opacity: 0.6;
        stroke-dasharray: 4 4;
      }
      .map .home-dot {
        fill: var(--primary-color);
        fill-opacity: 1;
        stroke: var(--card-background-color, var(--ha-card-background));
        stroke-width: 2;
      }
      .radar-bar {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2);
        min-height: var(--ha-space-12);
        padding: 0 var(--ha-space-4) 0 var(--ha-space-1);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .radar-bar .time {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .frames {
        display: flex;
        gap: var(--ha-space-1);
      }
      .frames span {
        width: var(--ha-space-2);
        height: var(--ha-space-2);
        border-radius: var(--ha-border-radius-pill);
        background-color: var(--ha-color-fill-neutral-normal-resting);
      }
      .frames span.current {
        background-color: var(--primary-color);
      }
      .notice {
        padding: 0 var(--ha-space-4) var(--ha-space-4);
      }
    `,
  ];

  protected declare _radar: RadarStatus;
  protected declare _loadError: boolean;
  protected readonly titleKey = "map.title" as const;
  protected override readonly usesIncidents = true;

  private _map?: IncidentMap;
  private _container?: HTMLElement;
  private _creating = false;
  private _resizeObserver?: ResizeObserver;
  private _intersectionObserver?: IntersectionObserver;
  private readonly _reducedMotion =
    typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

  constructor() {
    super();
    this._radar = { state: "off" };
    this._loadError = false;
  }

  static override validateConfig(config: MapCardConfig): void {
    super.validateConfig(config);
    const c = config as unknown as Record<string, unknown>;
    assertPositiveInt(c, "zoom", 1, 18);
    assertBoolean(c, "radar");
    assertNumber(c, "radar_opacity", 0.1, 1);
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        { name: "zoom", selector: { number: { min: 1, max: 18, mode: "box" } } },
        { name: "radar", default: true, selector: { boolean: {} } },
        { name: "radar_opacity", selector: { number: { min: 0.1, max: 1, step: 0.05, mode: "slider" } } },
      ],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c),
    };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getGridOptions(): LovelaceGridOptions {
    return { columns: 12, rows: 6, min_columns: 6, min_rows: 4 };
  }

  override getCardSize(): number {
    return 7;
  }

  private readonly trackedHomeId = "zone.home";

  override trackedEntityIds(hass: HomeAssistant): string[] {
    return [...super.trackedEntityIds(hass), this.trackedHomeId];
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.hasUpdated) void this.ensureMap();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.teardown();
  }

  private teardown(): void {
    this._resizeObserver?.disconnect();
    this._intersectionObserver?.disconnect();
    this._resizeObserver = undefined;
    this._intersectionObserver = undefined;
    this._map?.destroy();
    this._map = undefined;
    this._container = undefined;
  }

  protected override updated(changed: PropertyValues<this>): void {
    super.updated(changed);
    if (this._map && this.renderRoot.querySelector(".map") !== this._container) this.teardown();
    if (!this._map) void this.ensureMap();
    else this._map.update(this.viewOptions());
  }

  private viewOptions(): MapViewOptions {
    const hass = this.hass!;
    const incidents = geoLocationsFor(hass, this.entryId).flatMap((s) => {
      const latitude = numberAttr(s.attributes.latitude);
      const longitude = numberAttr(s.attributes.longitude);
      if (latitude === undefined || longitude === undefined) return [];
      const level = awsPresentation(s.attributes.warning_level);
      return [
        {
          id: s.entity_id,
          title: incidentTitle(s),
          levelLabel: t(hass, LEVEL_LABELS[level.level]!),
          tone: level.tone,
          latitude,
          longitude,
          agency: stringAttr(s.attributes.responsible_agency) ?? stringAttr(s.attributes.source),
        },
      ];
    });
    const zone = hass.states[this.trackedHomeId];
    const zoneLat = numberAttr(zone?.attributes.latitude);
    const zoneLon = numberAttr(zone?.attributes.longitude);
    const home =
      zoneLat !== undefined && zoneLon !== undefined
        ? { latitude: zoneLat, longitude: zoneLon, radius: numberAttr(zone?.attributes.radius), label: t(hass, "map.home") }
        : Number.isFinite(hass.config?.latitude) && Number.isFinite(hass.config?.longitude)
          ? { latitude: hass.config.latitude, longitude: hass.config.longitude, label: t(hass, "map.home") }
          : undefined;
    return {
      incidents,
      home,
      darkMode: !!hass.themes?.darkMode,
      zoom: this._config?.zoom,
      radar: this._config?.radar !== false,
      radarOpacity: this._config?.radar_opacity ?? DEFAULT_RADAR_OPACITY,
    };
  }

  private async ensureMap(): Promise<void> {
    if (this._map || this._creating || !this.hass || !this.isConnected) return;
    const container = this.renderRoot.querySelector<HTMLElement>(".map");
    if (!container) return;
    this._creating = true;
    try {
      const module = await loadMapModule();
      const root = this.renderRoot as ShadowRoot;
      if (!root.adoptedStyleSheets.some((s) => (s as CSSStyleSheet & { leaflet?: boolean }).leaflet)) {
        const sheet = new CSSStyleSheet() as CSSStyleSheet & { leaflet?: boolean };
        sheet.replaceSync(module.leafletCss);
        sheet.leaflet = true;
        // Leaflet's base styles first, so the card's token overrides win.
        root.adoptedStyleSheets = [sheet, ...root.adoptedStyleSheets];
      }
      if (!this.isConnected || this._map || !container.isConnected) return;
      this._container = container;
      this._map = new module.IncidentMap(
        container,
        this.hass.connection,
        (status) => (this._radar = status),
        (entityId) => this.moreInfo(entityId),
        this._reducedMotion,
      );
      this._resizeObserver = new ResizeObserver(() => this._map?.invalidateSize());
      this._resizeObserver.observe(container);
      this._intersectionObserver = new IntersectionObserver((entries) =>
        this._map?.setVisible(entries.some((e) => e.isIntersecting)),
      );
      this._intersectionObserver.observe(this);
      this._map.update(this.viewOptions());
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("Disaster Watch map failed to load", err);
      this._loadError = true;
    } finally {
      this._creating = false;
    }
  }

  private togglePlay(): void {
    const playing = !this._radar.playing;
    this._map?.setPlaying(playing);
  }

  private renderRadarBar(hass: HomeAssistant): TemplateResult | typeof nothing {
    const radar = this._radar;
    if (radar.state !== "ok" || radar.frameTime === undefined) return nothing;
    const time = formatDateTime(hass, radar.frameTime, { timeStyle: "short" });
    const ago = relativeTime(hass, radar.frameTime);
    const playing = !!radar.playing;
    return html`<div class="radar-bar">
      <ha-icon-button .label=${t(hass, playing ? "map.pause" : "map.play")} aria-pressed=${playing ? "true" : "false"} @click=${this.togglePlay}>
        <ha-icon .icon=${playing ? "mdi:pause" : "mdi:play"}></ha-icon>
      </ha-icon-button>
      <span class="time" aria-live=${playing ? "off" : "polite"}>${t(hass, "map.radar_at", { time: time ?? "" })}${ago ? ` · ${ago}` : ""}</span>
      <span class="frames" aria-hidden="true">
        ${Array.from({ length: radar.frameCount ?? 0 }, (_, i) => html`<span class=${i === radar.frameIndex ? "current" : ""}></span>`)}
      </span>
    </div>`;
  }

  protected renderBody(hass: HomeAssistant, _config: MapCardConfig): TemplateResult {
    const name = deviceName(hass, this.deviceId) ?? hass.config?.location_name ?? "";
    return html`${header({ title: this.cardTitle(), icon: "mdi:map-marker-radius" })}
      <div class="map-wrap">
        <div class="map" role="region" aria-label=${t(hass, "map.label", { name })}></div>
      </div>
      ${this.renderRadarBar(hass)}
      ${
        this._radar.state === "unavailable"
          ? html`<div class="notice">${alert("info", t(hass, "map.radar_unavailable"))}</div>`
          : nothing
      }
      ${this._loadError ? html`<div class="notice">${alert("error", t(hass, "state.unavailable"))}</div>` : nothing}`;
  }
}
