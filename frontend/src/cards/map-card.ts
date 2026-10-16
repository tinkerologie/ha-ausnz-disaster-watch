import { css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { KEY } from "../const";
import { deviceName, entityIdFor, geoLocationsFor, incidentTitle } from "../ha/entities";
import { formatDateTime, language, numberAttr, relativeTime, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { awsPresentation } from "../model/aws";
import { alert, header } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import {
  assertBoolean,
  assertChoice,
  assertNumber,
  assertPositiveInt,
  baseSchema,
  computeHelper,
  computeLabel,
  DisasterCard,
  stubConfig,
} from "./base";
import { LEVEL_LABELS } from "./incidents";
// Small, Leaflet-free helpers: the Leaflet chunk still loads lazily.
import { cycloneRefs } from "./map/gdacs";
import { defaultViirsDay, SATELLITE_LAYERS, type SatelliteOption, VIIRS_DAYS, type ViirsDay, viirsDate } from "./map/gibs";
import type { IncidentMap, MapStatus, MapViewOptions } from "./map/leaflet-map";

export interface MapCardConfig extends BaseCardConfig {
  zoom?: number;
  radar?: boolean;
  radar_opacity?: number;
  satellite_layer?: SatelliteOption;
  show_cyclone_tracks?: boolean;
}

const DEFAULT_RADAR_OPACITY = 0.7;
const INITIAL_STATUS: MapStatus = { radar: "off", satellite: "off", cyclones: "off", cycloneCount: 0 };

/** Card state that feeds the map (besides `hass`). */
const MAP_INPUTS = ["_config", "_satelliteHidden", "_cyclonesHidden", "_viirsDay"] as const;

type MapModule = typeof import("./map/leaflet-map");
let mapModule: Promise<MapModule> | undefined;
const loadMapModule = () => (mapModule ??= import("./map/leaflet-map"));

/** Incidents of the entry on a map, with animated RainViewer radar over HA's basemap (#41). */
export class MapCard extends DisasterCard<MapCardConfig> {
  static override properties = {
    ...DisasterCard.properties,
    _status: { state: true },
    _loadError: { state: true },
    _satelliteHidden: { state: true },
    _cyclonesHidden: { state: true },
    _viirsDay: { state: true },
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
      .layers {
        padding: var(--ha-space-2) var(--ha-space-4) 0;
      }
      .legend {
        margin: 0;
        padding: var(--ha-space-1) var(--ha-space-4) var(--ha-space-2);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .map .satellite-frame {
        transition: opacity var(--ha-animation-duration-slow) ease-in-out;
      }
      /* Loud fills at low opacity read on light, dark and satellite backgrounds alike. */
      .map .cyclone {
        stroke-opacity: 0.9;
      }
      .map .cyclone-cone {
        fill: var(--ha-color-fill-neutral-loud-resting);
        fill-opacity: 0.12;
        stroke: var(--ha-color-border-neutral-normal);
        stroke-dasharray: 4 4;
      }
      .map .cyclone-buffer-green {
        fill: var(--ha-color-fill-warning-loud-resting);
        fill-opacity: 0.15;
        stroke: var(--ha-color-border-warning-normal);
      }
      .map .cyclone-buffer-orange {
        fill: var(--ha-color-fill-warning-loud-resting);
        fill-opacity: 0.3;
        stroke: var(--ha-color-border-warning-loud);
      }
      .map .cyclone-buffer-red {
        fill: var(--ha-color-fill-danger-loud-resting);
        fill-opacity: 0.35;
        stroke: var(--ha-color-border-danger-loud);
      }
      .map .cyclone-track,
      .map .cyclone-track-forecast {
        fill: none;
        stroke: var(--ha-color-border-danger-loud);
        stroke-opacity: 1;
      }
      .map .cyclone-track-forecast {
        stroke-dasharray: 6 4;
      }
    `,
  ];

  protected declare _status: MapStatus;
  protected declare _loadError: boolean;
  /** Layer chips: the configured satellite layer and cyclone tracks can be hidden on the map. */
  protected declare _satelliteHidden: boolean;
  protected declare _cyclonesHidden: boolean;
  protected declare _viirsDay: ViirsDay;
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
    this._status = INITIAL_STATUS;
    this._loadError = false;
    this._satelliteHidden = false;
    this._cyclonesHidden = false;
    this._viirsDay = defaultViirsDay(Date.now());
  }

  static override validateConfig(config: MapCardConfig): void {
    super.validateConfig(config);
    const c = config as unknown as Record<string, unknown>;
    assertPositiveInt(c, "zoom", 1, 18);
    assertBoolean(c, "radar");
    assertNumber(c, "radar_opacity", 0.1, 1);
    assertChoice(c, "satellite_layer", SATELLITE_LAYERS);
    assertBoolean(c, "show_cyclone_tracks");
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        { name: "zoom", selector: { number: { min: 1, max: 18, mode: "box" } } },
        { name: "radar", default: true, selector: { boolean: {} } },
        { name: "radar_opacity", selector: { number: { min: 0.1, max: 1, step: 0.05, mode: "slider" } } },
        {
          name: "satellite_layer",
          default: "none",
          selector: {
            select: {
              mode: "dropdown",
              options: SATELLITE_LAYERS.map((value) => ({ value, label: t(undefined, layerLabelKey(value)) })),
            },
          },
        },
        { name: "show_cyclone_tracks", default: false, selector: { boolean: {} } },
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
    const ids = [...super.trackedEntityIds(hass), this.trackedHomeId];
    const alerts = this._config?.show_cyclone_tracks ? this.alertsEntityId(hass) : undefined;
    if (alerts) ids.push(alerts);
    return ids;
  }

  /** The entry's Regional Disaster Alerts sensor, which lists current cyclones and their geometry URL. */
  private alertsEntityId(hass: HomeAssistant): string | undefined {
    return entityIdFor(hass, this.deviceId, KEY.regionalDisasterAlerts);
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
    // Only map inputs: radar frame ticks re-render the card twice a second.
    else if (changed.has("hass") || MAP_INPUTS.some((k) => changed.has(k as keyof MapCard))) {
      this._map.update(this.viewOptions());
    }
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
          agency: stringAttr(s.attributes.responsible_agency) ?? stringAttr(s.attributes.agency),
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
    const satellite = this._config?.satellite_layer ?? "none";
    const alertsId = this._config?.show_cyclone_tracks && !this._cyclonesHidden ? this.alertsEntityId(hass) : undefined;
    return {
      incidents,
      home,
      darkMode: !!hass.themes?.darkMode,
      zoom: this._config?.zoom,
      radar: this._config?.radar !== false,
      radarOpacity: this._config?.radar_opacity ?? DEFAULT_RADAR_OPACITY,
      satellite: this._satelliteHidden ? "none" : satellite,
      viirsDay: this._viirsDay,
      cyclones: alertsId ? cycloneRefs(hass.states[alertsId]?.attributes.alerts) : [],
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
        (status) => (this._status = status),
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
    const playing = !this._status.frame?.playing;
    this._map?.setPlaying(playing);
  }

  private renderRadarBar(hass: HomeAssistant): TemplateResult | typeof nothing {
    const frame = this._status.frame;
    if (!frame) return nothing;
    const time = formatDateTime(hass, frame.time, { timeStyle: "short" });
    const ago = relativeTime(hass, frame.time);
    const playing = frame.playing;
    const radar = frame.source === "radar";
    const label = radar
      ? t(hass, playing ? "map.pause" : "map.play")
      : t(hass, playing ? "map.pause_satellite" : "map.play_satellite");
    const text = t(hass, radar ? "map.radar_at" : "map.satellite_at", { time: time ?? "" });
    return html`<div class="radar-bar">
      <ha-icon-button .label=${label} aria-pressed=${playing ? "true" : "false"} @click=${this.togglePlay}>
        <ha-icon .icon=${playing ? "mdi:pause" : "mdi:play"}></ha-icon>
      </ha-icon-button>
      <span class="time" aria-live=${playing ? "off" : "polite"}>${text}${ago ? ` · ${ago}` : ""}</span>
      <span class="frames" aria-hidden="true">
        ${Array.from({ length: frame.count }, (_, i) => html`<span class=${i === frame.index ? "current" : ""}></span>`)}
      </span>
    </div>`;
  }

  /** Chips to show or hide the configured satellite layer and cyclone tracks, and the VIIRS day. */
  private renderLayerChips(hass: HomeAssistant, config: MapCardConfig): TemplateResult | typeof nothing {
    const satellite = config.satellite_layer ?? "none";
    if (satellite === "none" && !config.show_cyclone_tracks) return nothing;
    const viirs = satellite === "viirs_truecolor" && !this._satelliteHidden;
    // VIIRS images are per UTC day, so the chips show UTC dates.
    const dateFormat = new Intl.DateTimeFormat(language(hass), { day: "numeric", month: "short", timeZone: "UTC" });
    const now = Date.now();
    const dayChip = (day: ViirsDay) => {
      const date = dateFormat.format(Date.parse(viirsDate(now, day)));
      return html`<ha-filter-chip
        no-leading-icon
        .selected=${this._viirsDay === day}
        .label=${date}
        title=${`${t(hass, "map.viirs_days")}: ${date}`}
        @click=${(ev: Event) => {
          ev.preventDefault();
          this._viirsDay = day;
        }}
      ></ha-filter-chip>`;
    };
    return html`<div class="layers">
      <ha-chip-set aria-label=${t(hass, "map.layers")}>
        ${
          satellite !== "none"
            ? html`<ha-filter-chip
                .selected=${!this._satelliteHidden}
                .label=${t(hass, layerLabelKey(satellite))}
                @click=${(ev: Event) => {
                  ev.preventDefault();
                  this._satelliteHidden = !this._satelliteHidden;
                }}
              >
                <ha-icon slot="icon" icon="mdi:satellite-variant"></ha-icon>
              </ha-filter-chip>`
            : nothing
        }
        ${viirs ? VIIRS_DAYS.map(dayChip) : nothing}
        ${
          config.show_cyclone_tracks
            ? html`<ha-filter-chip
                .selected=${!this._cyclonesHidden}
                .label=${t(hass, "map.cyclones")}
                @click=${(ev: Event) => {
                  ev.preventDefault();
                  this._cyclonesHidden = !this._cyclonesHidden;
                }}
              >
                <ha-icon slot="icon" icon="mdi:weather-hurricane"></ha-icon>
              </ha-filter-chip>`
            : nothing
        }
      </ha-chip-set>
    </div>`;
  }

  private renderNotices(hass: HomeAssistant): TemplateResult[] {
    const status = this._status;
    const notice = (key: TranslationKey) => html`<div class="notice">${alert("info", t(hass, key))}</div>`;
    const notices: TemplateResult[] = [];
    if (status.radar === "unavailable") notices.push(notice("map.radar_unavailable"));
    if (status.satellite === "unavailable") notices.push(notice("map.satellite_unavailable"));
    if (status.cyclones === "unavailable") notices.push(notice("map.cyclones_unavailable"));
    return notices;
  }

  protected renderBody(hass: HomeAssistant, config: MapCardConfig): TemplateResult {
    const name = deviceName(hass, this.deviceId) ?? hass.config?.location_name ?? "";
    return html`${header({ title: this.cardTitle(), icon: "mdi:map-marker-radius" })}
      <div class="map-wrap">
        <div class="map" role="region" aria-label=${t(hass, "map.label", { name })}></div>
      </div>
      ${this.renderLayerChips(hass, config)}
      ${this.renderRadarBar(hass)}
      ${
        this._status.cyclones === "ok" && this._status.cycloneCount > 0
          ? html`<p class="legend">${t(hass, "map.cyclone_legend")}</p>`
          : nothing
      }
      ${this.renderNotices(hass)}
      ${this._loadError ? html`<div class="notice">${alert("error", t(hass, "state.unavailable"))}</div>` : nothing}`;
  }
}

function layerLabelKey(layer: SatelliteOption): TranslationKey {
  return layer === "none" ? "editor.satellite_layer.none" : (`map.layer.${layer}` as TranslationKey);
}
