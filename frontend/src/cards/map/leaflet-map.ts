/**
 * Lazily loaded map chunk: Leaflet, the `map_tiles` basemap and animated RainViewer
 * radar (#41). Loaded by the map card shell with a dynamic `import()`, so dashboards
 * without a map never download Leaflet.
 */
import L from "leaflet";
import leafletCss from "leaflet/dist/leaflet.css?inline";
import type { HassConnection } from "../../types";
import {
  ensureMapTilesToken,
  MAP_TILES_URL,
  OSM_ATTRIBUTION,
  OSM_TILES_URL,
  refreshMapTilesToken,
  subscribeMapTilesToken,
} from "./map-tiles";
import {
  coverageTileUrl,
  fetchRadarFrames,
  RADAR_MAX_NATIVE_ZOOM,
  RAINVIEWER_ATTRIBUTION,
  radarTileUrl,
  type RadarFrames,
} from "./rainviewer";

export { leafletCss };

export interface MapIncident {
  id: string;
  title: string;
  levelLabel: string;
  tone: string;
  latitude: number;
  longitude: number;
  agency?: string;
}

export interface MapHome {
  latitude: number;
  longitude: number;
  radius?: number;
  label: string;
}

export interface MapViewOptions {
  incidents: MapIncident[];
  home?: MapHome;
  darkMode: boolean;
  zoom?: number;
  radar: boolean;
  radarOpacity: number;
}

export interface RadarStatus {
  state: "off" | "loading" | "ok" | "unavailable";
  frameTime?: number;
  frameIndex?: number;
  frameCount?: number;
  playing?: boolean;
}

const FRAME_MS = 500;
const LAST_FRAME_HOLD_MS = 1500;
const RADAR_POLL_MS = 5 * 60 * 1000;
const RADAR_ERROR_LIMIT = 8;
const TOKEN_RETRY_THROTTLE_MS = 30000;

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/** Leaflet map controller owned by one map card. */
export class IncidentMap {
  private readonly map: L.Map;
  private basemap?: L.TileLayer;
  private readonly incidentLayer = L.layerGroup();
  private readonly homeLayer = L.layerGroup();
  private radarLayers: L.TileLayer[] = [];
  private coverageLayer?: L.TileLayer;
  private radarData?: RadarFrames;
  private frameIndex = 0;
  private playing: boolean;
  private visible = true;
  private animTimer?: ReturnType<typeof setTimeout>;
  private pollTimer?: ReturnType<typeof setInterval>;
  private radarErrors = 0;
  private unsubscribeToken?: () => void;
  private fitted = false;
  private lastIncidentKey = "";
  private layerSignature = "";
  private attributionAgencies = new Set<string>();
  private options?: MapViewOptions;
  private destroyed = false;

  constructor(
    private readonly container: HTMLElement,
    private readonly connection: HassConnection,
    private readonly onRadarStatus: (status: RadarStatus) => void,
    private readonly onIncident: (entityId: string) => void,
    reducedMotion: boolean,
  ) {
    this.playing = !reducedMotion;
    this.map = L.map(container, { zoomControl: true, attributionControl: true, minZoom: 2, maxZoom: 18 });
    this.map.attributionControl.setPrefix(false);
    this.incidentLayer.addTo(this.map);
    this.homeLayer.addTo(this.map);
    void this.initBasemap();
  }

  private async initBasemap(): Promise<void> {
    const token = await ensureMapTilesToken(this.connection).catch(() => undefined);
    if (this.destroyed) return;
    const options = { attribution: OSM_ATTRIBUTION, maxZoom: 18, maxNativeZoom: 19, className: "basemap" };
    if (!token) {
      this.basemap = L.tileLayer(OSM_TILES_URL, options).addTo(this.map);
      return;
    }
    const layer = L.tileLayer(MAP_TILES_URL, { ...options, token } as L.TileLayerOptions).addTo(this.map);
    let refused = false;
    let lastRetry = 0;
    layer.on("tileerror", () => {
      refused = true;
      if (Date.now() - lastRetry < TOKEN_RETRY_THROTTLE_MS) return;
      lastRetry = Date.now();
      void refreshMapTilesToken();
    });
    this.unsubscribeToken = subscribeMapTilesToken((newToken) => {
      (layer.options as L.TileLayerOptions & { token?: string }).token = newToken;
      if (refused) {
        refused = false;
        layer.redraw();
      }
    });
    this.basemap = layer;
  }

  update(options: MapViewOptions): void {
    const previous = this.options;
    this.options = options;
    this.container.classList.toggle("dark", options.darkMode);
    const key = options.incidents.map((i) => i.id).join("|");
    // Give the map a view first: Leaflet only creates marker elements on a loaded map.
    if (!this.fitted || previous?.zoom !== options.zoom || (!previous?.incidents.length && key !== this.lastIncidentKey)) {
      this.fitView(options);
    }
    this.lastIncidentKey = key;
    // Rebuild markers only when they change, so focus and open tooltips survive updates.
    const signature = JSON.stringify([options.home, options.incidents]);
    if (signature !== this.layerSignature) {
      this.layerSignature = signature;
      this.renderHome(options.home);
      this.renderIncidents(options.incidents);
    }

    if (options.radar !== previous?.radar) {
      if (options.radar) void this.loadRadar();
      else this.clearRadar(true);
    } else if (options.radarOpacity !== previous?.radarOpacity) {
      this.showFrame(this.frameIndex);
    }
  }

  private fitView(options: MapViewOptions): void {
    const home = options.home;
    if (options.zoom !== undefined && home) {
      this.map.setView([home.latitude, home.longitude], options.zoom);
    } else {
      const points: L.LatLngExpression[] = options.incidents.map((i) => [i.latitude, i.longitude]);
      if (home) points.push([home.latitude, home.longitude]);
      if (points.length > 1) {
        this.map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 12 });
      } else if (points.length === 1) {
        this.map.setView(points[0]!, 10);
      } else {
        this.map.setView([-25.5, 145], 4);
      }
    }
    this.fitted = true;
  }

  private renderHome(home: MapHome | undefined): void {
    this.homeLayer.clearLayers();
    if (!home) return;
    if (home.radius) {
      L.circle([home.latitude, home.longitude], {
        radius: home.radius,
        className: "home-zone",
        interactive: false,
      }).addTo(this.homeLayer);
    }
    L.circleMarker([home.latitude, home.longitude], { radius: 6, className: "home-dot", interactive: false })
      .bindTooltip(this.tooltip(home.label))
      .addTo(this.homeLayer);
  }

  private tooltip(...lines: string[]): HTMLElement {
    const el = document.createElement("div");
    lines.forEach((line, i) => {
      const span = document.createElement(i === 0 ? "strong" : "span");
      span.textContent = line;
      el.append(span);
      if (i < lines.length - 1) el.append(document.createElement("br"));
    });
    return el;
  }

  private renderIncidents(incidents: MapIncident[]): void {
    this.incidentLayer.clearLayers();
    const agencies = new Set<string>();
    for (const incident of incidents) {
      if (incident.agency) agencies.add(incident.agency);
      const marker = L.circleMarker([incident.latitude, incident.longitude], {
        radius: 8,
        weight: 2,
        className: `incident tone-${incident.tone}`,
      })
        .bindTooltip(this.tooltip(incident.title, incident.levelLabel))
        .on("click", () => this.onIncident(incident.id))
        .addTo(this.incidentLayer);
      const el = marker.getElement();
      if (el) {
        el.setAttribute("role", "button");
        el.setAttribute("tabindex", "0");
        el.setAttribute("aria-label", `${incident.title}, ${incident.levelLabel}`);
        el.addEventListener("keydown", (ev) => {
          const key = (ev as KeyboardEvent).key;
          if (key === "Enter" || key === " ") {
            ev.preventDefault();
            this.onIncident(incident.id);
          }
        });
      }
    }
    // Credit the agencies whose incidents are on the map.
    for (const agency of this.attributionAgencies) {
      if (!agencies.has(agency)) this.map.attributionControl.removeAttribution(escapeHtml(agency));
    }
    for (const agency of agencies) {
      if (!this.attributionAgencies.has(agency)) this.map.attributionControl.addAttribution(escapeHtml(agency));
    }
    this.attributionAgencies = agencies;
  }

  /* ---------- Radar ---------- */

  private async loadRadar(): Promise<void> {
    if (!this.visible || this.destroyed) return;
    // Keep polling whatever happens below, so an outage or unchanged list retries later.
    this.pollTimer ??= setInterval(() => void this.loadRadar(), RADAR_POLL_MS);
    // A refresh keeps the current frames (and the radar bar) on screen until new ones arrive.
    if (!this.radarLayers.length) this.onRadarStatus({ state: "loading" });
    let data: RadarFrames;
    try {
      data = await fetchRadarFrames();
    } catch {
      if (!this.destroyed) this.radarUnavailable();
      return;
    }
    if (this.destroyed || !this.options?.radar) return;
    if (this.radarData?.generated === data.generated && this.radarLayers.length) {
      // Unchanged list: restore the current frame's status, playing or paused (reduced motion).
      this.showFrame(this.frameIndex);
      this.schedule();
      return;
    }
    this.clearRadar(false);
    this.radarData = data;
    this.radarErrors = 0;
    this.coverageLayer = L.tileLayer(coverageTileUrl(data.host), {
      opacity: 0.25,
      maxNativeZoom: RADAR_MAX_NATIVE_ZOOM,
      maxZoom: 18,
      className: "radar-coverage",
      zIndex: 2,
    }).addTo(this.map);
    this.radarLayers = data.frames.map((frame, i) => {
      const layer = L.tileLayer(radarTileUrl(data.host, frame), {
        opacity: 0,
        maxNativeZoom: RADAR_MAX_NATIVE_ZOOM,
        maxZoom: 18,
        tileSize: 256,
        className: "radar-frame",
        zIndex: 3 + i,
        attribution: RAINVIEWER_ATTRIBUTION,
      });
      layer.on("tileerror", () => {
        this.radarErrors += 1;
        if (this.radarErrors >= RADAR_ERROR_LIMIT) this.radarUnavailable();
      });
      return layer.addTo(this.map);
    });
    this.frameIndex = this.radarLayers.length - 1;
    this.showFrame(this.frameIndex);
    this.schedule();
  }

  private radarUnavailable(): void {
    this.clearRadar(false);
    this.onRadarStatus({ state: "unavailable" });
  }

  private clearRadar(off: boolean): void {
    if (this.animTimer) clearTimeout(this.animTimer);
    this.animTimer = undefined;
    if (off && this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    }
    for (const layer of this.radarLayers) layer.remove();
    this.coverageLayer?.remove();
    this.coverageLayer = undefined;
    this.radarLayers = [];
    this.radarData = undefined;
    if (off) this.onRadarStatus({ state: "off" });
  }

  private showFrame(index: number): void {
    const opacity = this.options?.radarOpacity ?? 0.7;
    this.radarLayers.forEach((layer, i) => layer.setOpacity(i === index ? opacity : 0));
    const frame = this.radarData?.frames[index];
    if (frame) {
      this.onRadarStatus({
        state: "ok",
        frameTime: frame.time * 1000,
        frameIndex: index,
        frameCount: this.radarLayers.length,
        playing: this.playing,
      });
    }
  }

  private schedule(): void {
    if (this.animTimer) clearTimeout(this.animTimer);
    this.animTimer = undefined;
    if (!this.playing || !this.visible || this.radarLayers.length < 2) return;
    const last = this.frameIndex === this.radarLayers.length - 1;
    this.animTimer = setTimeout(
      () => {
        this.frameIndex = (this.frameIndex + 1) % this.radarLayers.length;
        this.showFrame(this.frameIndex);
        this.schedule();
      },
      last ? LAST_FRAME_HOLD_MS : FRAME_MS,
    );
  }

  setPlaying(playing: boolean): void {
    this.playing = playing;
    if (!playing && this.radarLayers.length) {
      this.frameIndex = this.radarLayers.length - 1;
    }
    this.showFrame(this.frameIndex);
    this.schedule();
  }

  /** Pause animation and polling while off screen. */
  setVisible(visible: boolean): void {
    if (visible === this.visible) return;
    this.visible = visible;
    if (!visible) {
      if (this.animTimer) clearTimeout(this.animTimer);
      this.animTimer = undefined;
      if (this.pollTimer) clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    } else if (this.options?.radar) {
      void this.loadRadar();
    }
  }

  invalidateSize(): void {
    this.map.invalidateSize();
  }

  destroy(): void {
    this.destroyed = true;
    this.clearRadar(false);
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = undefined;
    this.unsubscribeToken?.();
    this.basemap?.remove();
    this.map.remove();
  }
}
