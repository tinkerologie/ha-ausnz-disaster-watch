/**
 * RainViewer public radar (#41): free for personal use with attribution, no API key.
 * Since 2026 the public API serves past frames only, up to zoom 7, in the Universal Blue
 * scheme. Requests stay well under the 100 per IP per minute limit: the frame list is
 * fetched at most every 10 minutes and shared by all maps, frames are capped, and tiles
 * are cached by the browser (`max-age=172800`).
 */
export const RAINVIEWER_API = "https://api.rainviewer.com/public/weather-maps.json";
export const RAINVIEWER_ATTRIBUTION =
  'Weather data by <a href="https://www.rainviewer.com/" target="_blank" rel="noopener noreferrer">RainViewer</a>';
export const RADAR_MAX_NATIVE_ZOOM = 7;
/** Frames animated (about 70 minutes at 10-minute cadence). */
export const RADAR_FRAMES = 7;
const REFRESH_MS = 10 * 60 * 1000;

export interface RadarFrame {
  time: number;
  path: string;
}

export interface RadarFrames {
  host: string;
  frames: RadarFrame[];
  generated: number;
}

let cache: { at: number; data: RadarFrames } | undefined;
let inflight: Promise<RadarFrames> | undefined;

export function parseRadarFrames(json: unknown, maxFrames = RADAR_FRAMES): RadarFrames {
  const data = json as { host?: unknown; generated?: unknown; radar?: { past?: unknown } };
  if (typeof data?.host !== "string" || !data.host.startsWith("https://")) throw new Error("RainViewer: no host");
  const past = Array.isArray(data.radar?.past) ? data.radar.past : [];
  const frames = past
    .filter(
      (f): f is RadarFrame =>
        !!f && typeof f.time === "number" && typeof f.path === "string" && f.path.startsWith("/"),
    )
    .sort((a, b) => a.time - b.time)
    .slice(-maxFrames);
  if (!frames.length) throw new Error("RainViewer: no frames");
  return { host: data.host, frames, generated: typeof data.generated === "number" ? data.generated : 0 };
}

/** Frame list, shared by every map and refreshed at most every 10 minutes. */
export async function fetchRadarFrames(now: number = Date.now(), fetcher: typeof fetch = fetch): Promise<RadarFrames> {
  if (cache && now - cache.at < REFRESH_MS) return cache.data;
  inflight ??= (async () => {
    try {
      const response = await fetcher(RAINVIEWER_API, { credentials: "omit", referrerPolicy: "no-referrer" });
      if (!response.ok) throw new Error(`RainViewer: HTTP ${response.status}`);
      const data = parseRadarFrames(await response.json());
      cache = { at: now, data };
      return data;
    } finally {
      inflight = undefined;
    }
  })();
  return inflight;
}

/** Tile URL template of a frame: 256 px tiles, Universal Blue (2), smoothed, with snow. */
export function radarTileUrl(host: string, frame: RadarFrame): string {
  return `${host}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`;
}

/** Coverage mask: shows where radar data exists, so "no rain" and "no radar" differ. */
export function coverageTileUrl(host: string): string {
  return `${host}/v2/coverage/0/256/{z}/{x}/{y}/0/0_0.png`;
}

/** Test hook. */
export function resetRadarCache(): void {
  cache = undefined;
  inflight = undefined;
}
