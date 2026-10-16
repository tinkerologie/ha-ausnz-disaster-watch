/**
 * Satellite imagery from NASA GIBS (#71): Himawari-9 clouds every 10 minutes and the daily
 * VIIRS NOAA-21 true colour image. No key; tiles and the time domain are served with
 * `Access-Control-Allow-Origin: *`. Frame times come from the WMTS DescribeDomains request
 * (a few hundred bytes) instead of the 5.8 MB capabilities document; the list is fetched
 * at most every 10 minutes per layer and shared by every map on the page.
 *
 * Terms: NASA ESDIS data use guidance (no restrictions, acknowledge NASA, no implied
 * endorsement). Himawari data belongs to the Japan Meteorological Agency, so JMA is credited.
 */
export const GIBS_WMTS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";

export type SatelliteLayerId = "himawari_visible" | "himawari_ir" | "viirs_truecolor";
export const SATELLITE_LAYERS = ["none", "himawari_visible", "himawari_ir", "viirs_truecolor"] as const;
export type SatelliteOption = (typeof SATELLITE_LAYERS)[number];

export interface SatelliteLayer {
  id: SatelliteLayerId;
  /** GIBS layer identifier. */
  layer: string;
  /** GoogleMapsCompatible tile matrix set, which caps the native zoom. */
  maxNativeZoom: number;
  format: "png" | "jpg";
  /** `PT10M` loops (Himawari) or one image a day (VIIRS). */
  cadence: "10min" | "daily";
  opacity: number;
  attribution: string;
}

const NASA_LINK =
  '<a href="https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance" target="_blank" rel="noopener noreferrer">NASA GIBS</a>';

export const HIMAWARI_ATTRIBUTION = `Imagery: ${NASA_LINK} / Himawari-9 (JMA)`;
export const VIIRS_ATTRIBUTION = `Imagery: ${NASA_LINK} / VIIRS NOAA-21`;

export const SATELLITE: Record<SatelliteLayerId, SatelliteLayer> = {
  himawari_visible: {
    id: "himawari_visible",
    layer: "Himawari_AHI_Band3_Red_Visible_1km",
    maxNativeZoom: 7,
    format: "png",
    cadence: "10min",
    opacity: 0.6,
    attribution: HIMAWARI_ATTRIBUTION,
  },
  himawari_ir: {
    id: "himawari_ir",
    layer: "Himawari_AHI_Band13_Clean_Infrared",
    maxNativeZoom: 6,
    format: "png",
    cadence: "10min",
    opacity: 0.6,
    attribution: HIMAWARI_ATTRIBUTION,
  },
  viirs_truecolor: {
    id: "viirs_truecolor",
    layer: "VIIRS_NOAA21_CorrectedReflectance_TrueColor",
    maxNativeZoom: 9,
    format: "jpg",
    cadence: "daily",
    opacity: 0.9,
    attribution: VIIRS_ATTRIBUTION,
  },
};

/** Himawari frames animated: about 70 minutes, like the radar. */
export const SATELLITE_FRAMES = 7;
/** How far back the frame list is asked for: GIBS keeps about 9 hours of Himawari frames. */
const LOOKBACK_MS = 3 * 60 * 60 * 1000;
const REFRESH_MS = 10 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
/** Upper bound on expanded frames, whatever the server answers. */
const MAX_EXPANDED = 2000;

function matrixSet(layer: SatelliteLayer): string {
  return `GoogleMapsCompatible_Level${layer.maxNativeZoom}`;
}

/** `2026-10-16T01:20:00Z` (minutes, no milliseconds), the form GIBS uses for 10-minute layers. */
export function gibsTime(ms: number): string {
  return new Date(Math.floor(ms / 60000) * 60000).toISOString().replace(/:\d{2}\.\d{3}Z$/, ":00Z");
}

/** `2026-10-16`, the UTC day of a daily layer. */
export function gibsDate(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** DescribeDomains request for the layer's time dimension between two instants. */
export function describeDomainsUrl(layer: SatelliteLayer, startMs: number, endMs: number): string {
  return `${GIBS_WMTS}/1.0.0/${layer.layer}/default/${matrixSet(layer)}/all/${gibsTime(startMs)}--${gibsTime(endMs)}.xml`;
}

/** Leaflet tile URL template of one frame (`time` is a `gibsTime` or `gibsDate` string). */
export function gibsTileUrl(layer: SatelliteLayer, time: string): string {
  return `${GIBS_WMTS}/${layer.layer}/default/${time}/${matrixSet(layer)}/{z}/{y}/{x}.${layer.format}`;
}

const PERIOD_RE = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/;

/** ISO 8601 duration (`PT10M`, `P1D`) in milliseconds, or undefined. */
export function periodMs(period: string): number | undefined {
  const match = PERIOD_RE.exec(period.trim());
  if (!match || period.trim() === "P" || period.trim() === "PT") return undefined;
  const [, d, h, m] = match;
  const ms = (Number(d ?? 0) * 24 * 60 + Number(h ?? 0) * 60 + Number(m ?? 0)) * 60000;
  return ms > 0 ? ms : undefined;
}

/**
 * Frame times (ms, ascending) from a DescribeDomains document: the time `<Domain>` is a
 * comma-separated list of `start/end/period` ranges, with gaps between ranges.
 */
export function parseDomainTimes(xml: string): number[] {
  const domains = [...xml.matchAll(/<Domain>([^<]*)<\/Domain>/g)].map((m) => m[1]!);
  const times = new Set<number>();
  for (const domain of domains) {
    for (const range of domain.split(",")) {
      const [startText, endText, period] = range.trim().split("/");
      const start = Date.parse(startText ?? "");
      if (Number.isNaN(start)) continue;
      const end = endText ? Date.parse(endText) : start;
      const step = period ? periodMs(period) : undefined;
      if (Number.isNaN(end) || end < start) continue;
      if (!step) {
        times.add(start);
        continue;
      }
      for (let t = start; t <= end && times.size < MAX_EXPANDED; t += step) times.add(t);
    }
  }
  return [...times].sort((a, b) => a - b);
}

const cache = new Map<SatelliteLayerId, { at: number; times: number[] }>();
const inflight = new Map<SatelliteLayerId, Promise<number[]>>();

/** Latest frame times of a 10-minute layer, shared by every map and refreshed at most every 10 minutes. */
export async function fetchSatelliteTimes(
  layer: SatelliteLayer,
  now: number = Date.now(),
  fetcher: typeof fetch = fetch,
  maxFrames = SATELLITE_FRAMES,
): Promise<number[]> {
  const cached = cache.get(layer.id);
  if (cached && now - cached.at < REFRESH_MS) return cached.times;
  let request = inflight.get(layer.id);
  if (!request) {
    request = (async () => {
      try {
        const response = await fetcher(describeDomainsUrl(layer, now - LOOKBACK_MS, now), {
          credentials: "omit",
          referrerPolicy: "no-referrer",
        });
        if (!response.ok) throw new Error(`GIBS: HTTP ${response.status}`);
        const times = parseDomainTimes(await response.text())
          .filter((t) => t <= now)
          .slice(-maxFrames);
        if (!times.length) throw new Error("GIBS: no frames");
        cache.set(layer.id, { at: now, times });
        return times;
      } finally {
        inflight.delete(layer.id);
      }
    })();
    inflight.set(layer.id, request);
  }
  return request;
}

/** Days offered for the daily VIIRS image: today, yesterday and the day before (UTC). */
export const VIIRS_DAYS = [0, 1, 2] as const;
export type ViirsDay = (typeof VIIRS_DAYS)[number];

/** UTC hour after which the day's VIIRS image covers Australia and New Zealand. */
export const VIIRS_COMPLETE_UTC_HOUR = 9;

/**
 * Default VIIRS day: NOAA-21 crosses AU/NZ around 13:30 local time (about 00:30 to 05:30
 * UTC) and GIBS publishes a few hours later, so before 09:00 UTC today's image is still
 * empty over the region and yesterday's is shown instead.
 */
export function defaultViirsDay(now: number): ViirsDay {
  return new Date(now).getUTCHours() >= VIIRS_COMPLETE_UTC_HOUR ? 0 : 1;
}

/** The UTC date of the VIIRS image `daysAgo` days before `now`. */
export function viirsDate(now: number, daysAgo: number): string {
  return gibsDate(now - daysAgo * DAY_MS);
}

/** Test hook. */
export function resetSatelliteCache(): void {
  cache.clear();
  inflight.clear();
}
