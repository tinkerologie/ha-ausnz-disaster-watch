/**
 * Basemap through Home Assistant core's `map_tiles` raster proxy (HA 2026.10), the same
 * path HA's own Leaflet map uses: a short-lived token from the `map_tiles/access_token`
 * websocket command in the tile URL. Core rotates tokens every 30 minutes and keeps two
 * valid, so the token is refreshed every 20 minutes, on reconnect and after a refused
 * tile. Without a token (older core, proxy not ready) the map falls back to OSM tiles.
 */
import type { HassConnection } from "../../types";

export const MAP_TILES_URL = "/api/map_tiles/raster/{z}/{x}/{y}.png?token={token}";
export const OSM_TILES_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';
const REFRESH_MS = 20 * 60 * 1000;
const RETRY_DELAYS_MS = [0, 400, 1000];

let token: string | undefined;
let acquiring: Promise<string | undefined> | undefined;
let interval: ReturnType<typeof setInterval> | undefined;
let watched: HassConnection | undefined;
let active: HassConnection | undefined;
const listeners = new Set<(token: string) => void>();

async function fetchToken(connection: HassConnection): Promise<void> {
  const result = await connection.sendMessagePromise<{ token: string }>({ type: "map_tiles/access_token" });
  if (result?.token && result.token !== token) {
    token = result.token;
    for (const listener of listeners) listener(token);
  }
}

const onReady = () => {
  if (active) void fetchToken(active).catch(() => undefined);
};

/** Shared token for every map on the page; undefined when the proxy is not available. */
export async function ensureMapTilesToken(connection: HassConnection): Promise<string | undefined> {
  active = connection;
  if (!token) {
    acquiring ??= (async () => {
      for (const delay of RETRY_DELAYS_MS) {
        if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
        try {
          await fetchToken(connection);
          if (token) break;
        } catch {
          // Next attempt.
        }
      }
      return token;
    })().finally(() => {
      acquiring = undefined;
    });
    await acquiring;
  }
  if (token && !interval) {
    interval = setInterval(() => void refreshMapTilesToken(), REFRESH_MS);
  }
  if (token && watched !== connection) {
    watched?.removeEventListener?.("ready", onReady);
    watched = connection;
    connection.addEventListener?.("ready", onReady);
  }
  return token;
}

let refreshing: Promise<void> | undefined;

/** Force a new token (after a refused tile); deduplicated. */
export function refreshMapTilesToken(): Promise<void> {
  if (!active) return Promise.resolve();
  refreshing ??= fetchToken(active)
    .catch(() => undefined)
    .finally(() => {
      refreshing = undefined;
    });
  return refreshing;
}

/** Leaflet bakes the URL template at layer creation, so layers subscribe to new tokens. */
export function subscribeMapTilesToken(listener: (token: string) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test hook. */
export function resetMapTiles(): void {
  token = undefined;
  acquiring = undefined;
  if (interval) clearInterval(interval);
  interval = undefined;
  watched = undefined;
  active = undefined;
  listeners.clear();
}
