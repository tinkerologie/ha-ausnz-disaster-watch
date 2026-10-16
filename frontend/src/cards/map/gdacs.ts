/**
 * GDACS tropical cyclone geometry (#71): the forecast track, wind buffers and uncertainty
 * cone of each current cyclone that the integration's regional alerts sensor lists. The
 * sensor carries each episode's `geometry_url`; the browser fetches it (about 300 kB,
 * `Access-Control-Allow-Origin: *`), so the geometry never enters entity attributes.
 *
 * Only `https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&…` URLs are
 * fetched. GDACS output is automatic and indicative: it does not replace BoM or MetService
 * warnings, which the legend says.
 */
export const GDACS_ORIGIN = "https://www.gdacs.org";
export const GDACS_GEOMETRY_PATH = "/gdacsapi/api/polygons/getgeometry";
export const GDACS_ATTRIBUTION =
  '<a href="https://www.gdacs.org/About/termofuse.aspx" target="_blank" rel="noopener noreferrer">GDACS</a> (EC JRC / UN OCHA)';
/** Cyclones drawn at most (the sensor lists the nearest first). */
export const MAX_CYCLONES = 5;
const REFRESH_MS = 30 * 60 * 1000;
const MAX_FEATURES = 500;

export interface CycloneRef {
  url: string;
  name: string;
}

export type CyclonePart = "buffer-green" | "buffer-orange" | "buffer-red" | "cone" | "track" | "track-forecast";

export interface CycloneShape {
  part: CyclonePart;
  /** GeoJSON geometry: Polygon, MultiPolygon or LineString. */
  geometry: { type: string; coordinates: unknown };
}

export interface CycloneGeometry {
  name: string;
  shapes: CycloneShape[];
}

/** True for an https GDACS tropical cyclone geometry URL, false for anything else. */
export function isAllowedGeometryUrl(url: unknown): url is string {
  if (typeof url !== "string") return false;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return (
    parsed.origin === GDACS_ORIGIN &&
    parsed.username === "" &&
    parsed.password === "" &&
    parsed.pathname === GDACS_GEOMETRY_PATH &&
    parsed.searchParams.get("eventtype") === "TC" &&
    /^\d+$/.test(parsed.searchParams.get("eventid") ?? "") &&
    /^\d+$/.test(parsed.searchParams.get("episodeid") ?? "")
  );
}

/** Cyclones to draw from the regional alerts sensor's `alerts` attribute. */
export function cycloneRefs(alerts: unknown): CycloneRef[] {
  if (!Array.isArray(alerts)) return [];
  const refs: CycloneRef[] = [];
  const seen = new Set<string>();
  for (const alert of alerts) {
    if (!alert || typeof alert !== "object") continue;
    const { geometry_url: url, title } = alert as { geometry_url?: unknown; title?: unknown };
    if (!isAllowedGeometryUrl(url) || seen.has(url)) continue;
    seen.add(url);
    refs.push({ url, name: typeof title === "string" ? title : "" });
    if (refs.length >= MAX_CYCLONES) break;
  }
  return refs;
}

function partOf(cls: unknown, forecast: unknown): CyclonePart | undefined {
  if (typeof cls !== "string") return undefined;
  if (cls === "Poly_Green") return "buffer-green";
  if (cls === "Poly_Orange") return "buffer-orange";
  if (cls === "Poly_Red") return "buffer-red";
  if (cls === "Poly_Cones") return "cone";
  if (cls.startsWith("Line_")) return forecast === true ? "track-forecast" : "track";
  return undefined;
}

const SHAPES: Record<string, readonly string[]> = {
  "buffer-green": ["Polygon", "MultiPolygon"],
  "buffer-orange": ["Polygon", "MultiPolygon"],
  "buffer-red": ["Polygon", "MultiPolygon"],
  cone: ["Polygon", "MultiPolygon"],
  track: ["LineString", "MultiLineString"],
  "track-forecast": ["LineString", "MultiLineString"],
};

/**
 * Longitudes west of -90 moved east by 360: the region crosses the antimeridian (Tonga,
 * Kermadec Islands), and a track from 179 to -179 must not be drawn across the world.
 */
export function unwrapCoordinates(coordinates: unknown): unknown {
  if (!Array.isArray(coordinates)) return coordinates;
  if (typeof coordinates[0] === "number") {
    const [lon, ...rest] = coordinates as number[];
    return [lon! < -90 ? lon! + 360 : lon, ...rest];
  }
  return coordinates.map(unwrapCoordinates);
}

/** Order drawn: wide, pale shapes first, so the track and red buffer stay on top. */
const ORDER: CyclonePart[] = ["cone", "buffer-green", "buffer-orange", "buffer-red", "track", "track-forecast"];

/** Track, buffers and cone from a GDACS geometry FeatureCollection (track points and the centroid are skipped). */
export function parseCycloneGeometry(json: unknown, fallbackName = ""): CycloneGeometry {
  const data = json as { type?: unknown; features?: unknown };
  if (data?.type !== "FeatureCollection" || !Array.isArray(data.features)) throw new Error("GDACS: not GeoJSON");
  const shapes: CycloneShape[] = [];
  let name = fallbackName;
  for (const feature of data.features.slice(0, MAX_FEATURES)) {
    const props = (feature?.properties ?? {}) as Record<string, unknown>;
    const geometry = feature?.geometry as { type?: unknown; coordinates?: unknown } | undefined;
    const part = partOf(props.Class, props.forecast);
    if (!part || typeof geometry?.type !== "string" || !Array.isArray(geometry.coordinates)) continue;
    if (!SHAPES[part]!.includes(geometry.type)) continue;
    if (!name && typeof props.name === "string") name = props.name;
    shapes.push({ part, geometry: { type: geometry.type, coordinates: unwrapCoordinates(geometry.coordinates) } });
  }
  shapes.sort((a, b) => ORDER.indexOf(a.part) - ORDER.indexOf(b.part));
  return { name, shapes };
}

const cache = new Map<string, { at: number; data: CycloneGeometry }>();
const inflight = new Map<string, Promise<CycloneGeometry>>();

/** Geometry of one episode; an allowlisted URL only, cached for 30 minutes and shared by every map. */
export async function fetchCycloneGeometry(
  ref: CycloneRef,
  now: number = Date.now(),
  fetcher: typeof fetch = fetch,
): Promise<CycloneGeometry> {
  if (!isAllowedGeometryUrl(ref.url)) throw new Error("GDACS: URL not allowed");
  const cached = cache.get(ref.url);
  if (cached && now - cached.at < REFRESH_MS) return cached.data;
  let request = inflight.get(ref.url);
  if (!request) {
    request = (async () => {
      try {
        const response = await fetcher(ref.url, { credentials: "omit", referrerPolicy: "no-referrer" });
        if (!response.ok) throw new Error(`GDACS: HTTP ${response.status}`);
        const data = parseCycloneGeometry(await response.json(), ref.name);
        cache.set(ref.url, { at: now, data });
        return data;
      } finally {
        inflight.delete(ref.url);
      }
    })();
    inflight.set(ref.url, request);
  }
  return request;
}

/** Test hook. */
export function resetCycloneCache(): void {
  cache.clear();
  inflight.clear();
}
