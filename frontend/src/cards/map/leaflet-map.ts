/**
 * Lazily loaded map chunk: Leaflet, the `map_tiles` basemap, animated RainViewer radar
 * (#41), NASA GIBS satellite imagery and GDACS cyclone tracks (#71). Loaded by the map card
 * shell with a dynamic `import()`, so dashboards without a map never download Leaflet.
 *
 * Radar and Himawari share one frame timeline: with radar on, each radar frame shows the
 * latest satellite frame at or before its time; with radar off, the Himawari frames drive
 * the animation themselves. VIIRS true colour is a single daily image.
 */
import L from "leaflet";
import leafletCss from "leaflet/dist/leaflet.css?inline";
import type { HassConnection } from "../../types";
import { INITIAL_STATUS, type MapFrame, type MapStatus } from "./status";
import { type CycloneGeometry, type CycloneRef, fetchCycloneGeometry, GDACS_ATTRIBUTION } from "./gdacs";
import {
  fetchSatelliteTimes,
  gibsTileUrl,
  gibsTime,
  SATELLITE,
  type SatelliteLayer,
  type SatelliteOption,
  type ViirsDay,
  viirsDate,
} from "./gibs";
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
export type { LayerState, MapFrame, MapStatus } from "./status";

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
  /** Satellite layer shown (`none` when off or hidden with the chip). */
  satellite: SatelliteOption;
  /** Days before today of the VIIRS image. */
  viirsDay: ViirsDay;
  /** Cyclones whose GDACS geometry is drawn (empty when off). */
  cyclones: CycloneRef[];
}

const FRAME_MS = 500;
const LAST_FRAME_HOLD_MS = 1500;
const POLL_MS = 5 * 60 * 1000;
const TILE_ERROR_LIMIT = 8;
const TOKEN_RETRY_THROTTLE_MS = 30000;
/** Failed basemap tiles in a row (no tile loaded in between) before falling back to OSM. */
const BASEMAP_ERROR_LIMIT = 6;
/** A satellite frame up to a minute after a radar frame still counts as "at" it. */
const FRAME_MATCH_MS = 60 * 1000;
/** Cyclone shapes sit between the tiles (200) and the incident markers (400). */
const CYCLONE_PANE = "cyclones";
const CYCLONE_PANE_Z = "350";

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

interface SatelliteFrame {
  time: number;
  layer: L.TileLayer;
}

/** Leaflet map controller owned by one map card. */
export class IncidentMap {
  private readonly map: L.Map;
  private basemap?: L.TileLayer;
  private readonly incidentLayer = L.layerGroup();
  private readonly homeLayer = L.layerGroup();
  private readonly cycloneLayer = L.layerGroup();
  private radarLayers: L.TileLayer[] = [];
  private coverageLayer?: L.TileLayer;
  private radarData?: RadarFrames;
  private satelliteFrames: SatelliteFrame[] = [];
  private satelliteLayer?: SatelliteLayer;
  private satelliteKey = "";
  private cycloneData: CycloneGeometry[] = [];
  private frameIndex = 0;
  private frameSource?: MapFrame["source"];
  private playing: boolean;
  private visible = true;
  private animTimer?: ReturnType<typeof setTimeout>;
  private pollTimer?: ReturnType<typeof setInterval>;
  private radarErrors = 0;
  private satelliteErrors = 0;
  private unsubscribeToken?: () => void;
  private fitted = false;
  private lastIncidentKey = "";
  private layerSignature = "";
  private attributionAgencies = new Set<string>();
  private options?: MapViewOptions;
  private status: MapStatus = { ...INITIAL_STATUS };
  private destroyed = false;

  constructor(
    private readonly container: HTMLElement,
    private readonly connection: HassConnection,
    private readonly onStatus: (status: MapStatus) => void,
    private readonly onIncident: (entityId: string) => void,
    reducedMotion: boolean,
  ) {
    this.playing = !reducedMotion;
    this.map = L.map(container, { zoomControl: true, attributionControl: true, minZoom: 2, maxZoom: 18 });
    this.map.attributionControl.setPrefix(false);
    this.map.createPane(CYCLONE_PANE).style.zIndex = CYCLONE_PANE_Z;
    this.cycloneLayer.addTo(this.map);
    this.incidentLayer.addTo(this.map);
    this.homeLayer.addTo(this.map);
    void this.initBasemap();
  }

  private setStatus(change: Partial<MapStatus>): void {
    this.status = { ...this.status, ...change };
    this.onStatus(this.status);
  }

  private async initBasemap(): Promise<void> {
    const token = await ensureMapTilesToken(this.connection).catch(() => undefined);
    if (this.destroyed) return;
    if (!token) {
      this.useOsmBasemap();
      return;
    }
    const layer = L.tileLayer(MAP_TILES_URL, { ...this.basemapOptions(), token } as L.TileLayerOptions).addTo(this.map);
    let refused = false;
    let lastRetry = 0;
    let errors = 0;
    // Set when a refresh brought no new token: the next failed tile means the proxy is down.
    let refreshDidNotHelp = false;
    const fallBack = () => {
      if (this.destroyed || this.basemap !== layer) return;
      this.unsubscribeToken?.();
      this.unsubscribeToken = undefined;
      layer.remove();
      this.useOsmBasemap();
    };
    layer.on("tileload", () => {
      errors = 0;
      refreshDidNotHelp = false;
    });
    layer.on("tileerror", () => {
      refused = true;
      errors += 1;
      // Tiles keep failing although a token was (re)tried: the proxy itself is down.
      if (refreshDidNotHelp || errors >= BASEMAP_ERROR_LIMIT) return fallBack();
      if (Date.now() - lastRetry < TOKEN_RETRY_THROTTLE_MS) return;
      lastRetry = Date.now();
      void refreshMapTilesToken().then(() => {
        // No new token arrived (refresh failed or the token was fine). A single transient
        // error is not enough to give up: wait for a further failed tile.
        if (refused) refreshDidNotHelp = true;
      });
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

  private basemapOptions(): L.TileLayerOptions {
    return { attribution: OSM_ATTRIBUTION, maxZoom: 18, maxNativeZoom: 19, className: "basemap" };
  }

  private useOsmBasemap(): void {
    this.basemap = L.tileLayer(OSM_TILES_URL, this.basemapOptions()).addTo(this.map);
  }

  update(options: MapViewOptions): void {
    const previous = this.options;
    this.options = options;
    this.container.classList.toggle("dark", options.darkMode);
    const key = options.incidents.map((i) => i.id).join("|");
    // Give the map a view first: Leaflet only creates marker elements on a loaded map.
    const changed = key !== this.lastIncidentKey;
    if (
      !this.fitted ||
      previous?.zoom !== options.zoom ||
      (changed && !previous?.incidents.length) ||
      // A replacement set entirely outside the view: reframe; otherwise keep the user's view.
      (changed && options.incidents.length > 0 && !this.anyInView(options.incidents))
    ) {
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
      else this.radarOff();
    } else if (options.radarOpacity !== previous?.radarOpacity) {
      this.showFrame(this.frameIndex);
    }
    if (options.satellite !== previous?.satellite || options.viirsDay !== previous?.viirsDay) {
      void this.loadSatellite();
    }
    if (cycloneKey(options.cyclones) !== cycloneKey(previous?.cyclones ?? [])) {
      void this.loadCyclones();
    }
    this.stopPollingIfIdle();
  }

  private anyInView(incidents: MapIncident[]): boolean {
    const bounds = this.map.getBounds();
    return incidents.some((i) => bounds.contains([i.latitude, i.longitude]));
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

  /* ---------- Polling ---------- */

  private ensurePolling(): void {
    // Keep polling whatever a load does, so an outage or unchanged list retries later.
    this.pollTimer ??= setInterval(() => this.refreshLayers(), POLL_MS);
  }

  private stopPollingIfIdle(): void {
    const o = this.options;
    const animated = o?.satellite && o.satellite !== "none" && SATELLITE[o.satellite].cadence === "10min";
    if (o?.radar || animated || o?.cyclones.length) return;
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = undefined;
  }

  private refreshLayers(): void {
    const o = this.options;
    if (o?.radar) void this.loadRadar();
    if (o?.satellite && o.satellite !== "none") void this.loadSatellite();
    if (o?.cyclones.length) void this.loadCyclones();
  }

  /* ---------- Radar ---------- */

  private async loadRadar(): Promise<void> {
    if (!this.visible || this.destroyed) return;
    this.ensurePolling();
    // A refresh keeps the current frames (and the radar bar) on screen until new ones arrive.
    if (!this.radarLayers.length) this.setStatus({ radar: "loading" });
    let data: RadarFrames;
    try {
      data = await fetchRadarFrames();
    } catch {
      if (!this.destroyed && this.options?.radar) this.radarUnavailable();
      return;
    }
    if (this.destroyed || !this.options?.radar) return;
    if (this.radarData?.generated === data.generated && this.radarLayers.length) {
      // Unchanged list: restore the current frame's status, playing or paused (reduced motion).
      this.showFrame(this.frameIndex);
      this.schedule();
      return;
    }
    this.clearRadarLayers();
    this.radarData = data;
    this.radarErrors = 0;
    this.coverageLayer = L.tileLayer(coverageTileUrl(data.host), {
      opacity: 0.25,
      maxNativeZoom: RADAR_MAX_NATIVE_ZOOM,
      maxZoom: 18,
      className: "radar-coverage",
      zIndex: 3,
    }).addTo(this.map);
    this.radarLayers = data.frames.map((frame, i) => {
      const layer = L.tileLayer(radarTileUrl(data.host, frame), {
        opacity: 0,
        maxNativeZoom: RADAR_MAX_NATIVE_ZOOM,
        maxZoom: 18,
        tileSize: 256,
        className: "radar-frame",
        zIndex: 4 + i,
        attribution: RAINVIEWER_ATTRIBUTION,
      });
      // Only consecutive failures hide the radar: a loaded tile resets the count.
      layer.on("tileload", () => (this.radarErrors = 0));
      layer.on("tileerror", () => {
        this.radarErrors += 1;
        if (this.radarErrors >= TILE_ERROR_LIMIT) this.radarUnavailable();
      });
      return layer.addTo(this.map);
    });
    this.setStatus({ radar: "ok" });
    this.frameSource = "radar";
    this.frameIndex = this.radarLayers.length - 1;
    this.showFrame(this.frameIndex);
    this.schedule();
  }

  private radarUnavailable(): void {
    this.clearRadarLayers();
    this.setStatus({ radar: "unavailable" });
    this.restartTimeline();
  }

  private radarOff(): void {
    this.clearRadarLayers();
    this.setStatus({ radar: "off" });
    this.restartTimeline();
  }

  private clearRadarLayers(): void {
    for (const layer of this.radarLayers) layer.remove();
    this.coverageLayer?.remove();
    this.coverageLayer = undefined;
    this.radarLayers = [];
    this.radarData = undefined;
  }

  /* ---------- Satellite ---------- */

  private async loadSatellite(): Promise<void> {
    const option = this.options?.satellite ?? "none";
    if (option === "none") {
      if (this.satelliteFrames.length || this.status.satellite !== "off") {
        this.clearSatellite();
        this.setStatus({ satellite: "off" });
        this.restartTimeline();
      }
      return;
    }
    if (!this.visible || this.destroyed) return;
    const layer = SATELLITE[option];
    let times: number[];
    let stamps: string[];
    if (layer.cadence === "daily") {
      const date = viirsDate(Date.now(), this.options!.viirsDay);
      times = [Date.parse(date)];
      stamps = [date];
    } else {
      this.ensurePolling();
      if (!this.satelliteFrames.length) this.setStatus({ satellite: "loading" });
      try {
        times = await fetchSatelliteTimes(layer);
      } catch {
        if (!this.destroyed && this.options?.satellite === option) {
          this.clearSatellite();
          this.setStatus({ satellite: "unavailable" });
          this.restartTimeline();
        }
        return;
      }
      if (this.destroyed || this.options?.satellite !== option) return;
      stamps = times.map(gibsTime);
    }
    const key = `${option}|${stamps.join(",")}`;
    if (key === this.satelliteKey && this.satelliteFrames.length) {
      // Unchanged frames (a poll, or back on screen): resume the animation where it was.
      this.restartTimeline();
      return;
    }
    this.clearSatellite();
    this.satelliteKey = key;
    this.satelliteLayer = layer;
    this.satelliteErrors = 0;
    this.satelliteFrames = stamps.map((stamp, i) => {
      const tiles = L.tileLayer(gibsTileUrl(layer, stamp), {
        opacity: 0,
        maxNativeZoom: layer.maxNativeZoom,
        maxZoom: 18,
        tileSize: 256,
        className: "satellite-frame",
        zIndex: 2,
        attribution: layer.attribution,
      });
      tiles.on("tileload", () => (this.satelliteErrors = 0));
      tiles.on("tileerror", () => {
        this.satelliteErrors += 1;
        if (this.satelliteErrors >= TILE_ERROR_LIMIT) {
          this.clearSatellite();
          this.setStatus({ satellite: "unavailable" });
          this.restartTimeline();
        }
      });
      return { time: times[i]!, layer: tiles.addTo(this.map) };
    });
    this.setStatus({ satellite: "ok" });
    this.restartTimeline();
  }

  private clearSatellite(): void {
    for (const frame of this.satelliteFrames) frame.layer.remove();
    this.satelliteFrames = [];
    this.satelliteLayer = undefined;
    this.satelliteKey = "";
  }

  private satelliteAnimates(): boolean {
    return this.satelliteLayer?.cadence === "10min" && this.satelliteFrames.length > 0;
  }

  /** Show the latest satellite frame at or before `time` (the latest frame when undefined). */
  private showSatelliteAt(time: number | undefined): void {
    const layer = this.satelliteLayer;
    if (!layer || !this.satelliteFrames.length) return;
    let pick = this.satelliteFrames.length - 1;
    if (time !== undefined && layer.cadence === "10min") {
      pick = 0;
      this.satelliteFrames.forEach((frame, i) => {
        if (frame.time <= time + FRAME_MATCH_MS) pick = i;
      });
    }
    this.satelliteFrames.forEach((frame, i) => frame.layer.setOpacity(i === pick ? layer.opacity : 0));
  }

  /* ---------- Cyclones ---------- */

  private async loadCyclones(): Promise<void> {
    const refs = this.options?.cyclones ?? [];
    const key = cycloneKey(refs);
    if (!refs.length) {
      this.clearCyclones();
      this.setStatus({ cyclones: "off", cycloneCount: 0 });
      return;
    }
    if (!this.visible || this.destroyed) return;
    this.ensurePolling();
    if (!this.cycloneData.length) this.setStatus({ cyclones: "loading" });
    const results = await Promise.allSettled(refs.map((ref) => fetchCycloneGeometry(ref)));
    if (this.destroyed || cycloneKey(this.options?.cyclones ?? []) !== key) return;
    const data = results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []));
    if (!data.length) {
      this.clearCyclones();
      this.setStatus({ cyclones: "unavailable", cycloneCount: 0 });
      return;
    }
    // The geometry cache returns the same objects until it refreshes: nothing to redraw.
    if (data.length === this.cycloneData.length && data.every((d, i) => d === this.cycloneData[i])) {
      this.setStatus({ cyclones: "ok", cycloneCount: data.length });
      return;
    }
    this.clearCyclones();
    this.cycloneData = data;
    for (const cyclone of data) {
      for (const shape of cyclone.shapes) {
        const track = shape.part === "track" || shape.part === "track-forecast";
        const layer = L.geoJSON({ type: "Feature", properties: {}, geometry: shape.geometry } as GeoJSON.Feature, {
          pane: CYCLONE_PANE,
          attribution: GDACS_ATTRIBUTION,
          interactive: track,
          style: () => ({ className: `cyclone cyclone-${shape.part}`, weight: track ? 3 : 1, interactive: track }),
        });
        if (track && cyclone.name) layer.bindTooltip(this.tooltip(cyclone.name), { sticky: true });
        layer.addTo(this.cycloneLayer);
      }
    }
    this.setStatus({ cyclones: "ok", cycloneCount: data.length });
  }

  private clearCyclones(): void {
    this.cycloneLayer.clearLayers();
    this.cycloneData = [];
  }

  /* ---------- Timeline ---------- */

  /** Frame times (ms) of the timeline: radar frames, else Himawari frames. */
  private timeline(): { source: MapFrame["source"]; times: number[] } | undefined {
    if (this.radarLayers.length && this.radarData) {
      return { source: "radar", times: this.radarData.frames.map((f) => f.time * 1000) };
    }
    if (this.satelliteAnimates()) return { source: "satellite", times: this.satelliteFrames.map((f) => f.time) };
    return undefined;
  }

  /** After a layer appears or goes: keep the frame if the source is unchanged, else start at the latest. */
  private restartTimeline(): void {
    const timeline = this.timeline();
    if (!timeline) {
      if (this.animTimer) clearTimeout(this.animTimer);
      this.animTimer = undefined;
      this.frameSource = undefined;
      this.showSatelliteAt(undefined);
      if (this.status.frame) this.setStatus({ frame: undefined });
      return;
    }
    if (timeline.source !== this.frameSource || this.frameIndex >= timeline.times.length) {
      this.frameIndex = timeline.times.length - 1;
    }
    this.frameSource = timeline.source;
    this.showFrame(this.frameIndex);
    this.schedule();
  }

  private showFrame(index: number): void {
    const opacity = this.options?.radarOpacity ?? 0.7;
    this.radarLayers.forEach((layer, i) => layer.setOpacity(i === index ? opacity : 0));
    const timeline = this.timeline();
    const time = timeline?.times[index];
    this.showSatelliteAt(time);
    if (timeline && time !== undefined) {
      this.setStatus({
        frame: { source: timeline.source, time, index, count: timeline.times.length, playing: this.playing },
      });
    }
  }

  private schedule(): void {
    if (this.animTimer) clearTimeout(this.animTimer);
    this.animTimer = undefined;
    const count = this.timeline()?.times.length ?? 0;
    if (!this.playing || !this.visible || count < 2) return;
    const last = this.frameIndex === count - 1;
    this.animTimer = setTimeout(
      () => {
        this.frameIndex = (this.frameIndex + 1) % count;
        this.showFrame(this.frameIndex);
        this.schedule();
      },
      last ? LAST_FRAME_HOLD_MS : FRAME_MS,
    );
  }

  setPlaying(playing: boolean): void {
    this.playing = playing;
    const count = this.timeline()?.times.length ?? 0;
    if (!playing && count) this.frameIndex = count - 1;
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
    } else {
      this.refreshLayers();
    }
  }

  invalidateSize(): void {
    this.map.invalidateSize();
  }

  destroy(): void {
    this.destroyed = true;
    if (this.animTimer) clearTimeout(this.animTimer);
    this.animTimer = undefined;
    this.clearRadarLayers();
    this.clearSatellite();
    this.clearCyclones();
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = undefined;
    this.unsubscribeToken?.();
    this.basemap?.remove();
    this.map.remove();
  }
}

function cycloneKey(refs: CycloneRef[]): string {
  return refs.map((r) => r.url).join("|");
}
