import { describe, expect, it } from "vitest";
import {
  cycloneRefs,
  fetchCycloneGeometry,
  isAllowedGeometryUrl,
  parseCycloneGeometry,
  resetCycloneCache,
  unwrapCoordinates,
} from "../../src/cards/map/gdacs";
import {
  defaultViirsDay,
  describeDomainsUrl,
  fetchSatelliteTimes,
  gibsDate,
  gibsTileUrl,
  gibsTime,
  parseDomainTimes,
  periodMs,
  resetSatelliteCache,
  SATELLITE,
  viirsDate,
} from "../../src/cards/map/gibs";

// DescribeDomains answer recorded on 2026-10-16 (Himawari band 13, a 20-minute gap at 14:40).
const DOMAINS = `<Domains xmlns:ows='http://www.opengis.net/ows/1.1'><SpaceDomain><BoundingBox miny='-20037508.342789' crs='urn:ogc:def:crs:EPSG::3857' maxx='20037508.342789' minx='-20037508.342789' maxy='20037508.342789'/></SpaceDomain><DimensionDomain><ows:Identifier>time</ows:Identifier><Domain>2026-10-15T13:30:00Z/2026-10-15T14:30:00Z/PT10M,2026-10-15T14:50:00Z/2026-10-16T00:50:00Z/PT10M</Domain><Size>2</Size></DimensionDomain></Domains>`;
const at = (iso: string) => Date.parse(iso);

describe("NASA GIBS (#71)", () => {
  it("formats WMTS times and dates", () => {
    expect(gibsTime(at("2026-10-16T01:23:45.678Z"))).toBe("2026-10-16T01:23:00Z");
    expect(gibsDate(at("2026-10-16T23:59:00Z"))).toBe("2026-10-16");
    expect(viirsDate(at("2026-10-16T01:00:00Z"), 0)).toBe("2026-10-16");
    expect(viirsDate(at("2026-10-16T01:00:00Z"), 2)).toBe("2026-10-14");
  });

  it("defaults to yesterday's VIIRS image until today's covers AU/NZ", () => {
    expect(defaultViirsDay(at("2026-10-16T08:59:00Z"))).toBe(1);
    expect(defaultViirsDay(at("2026-10-16T09:00:00Z"))).toBe(0);
    expect(defaultViirsDay(at("2026-10-16T23:00:00Z"))).toBe(0);
  });

  it("builds tile and DescribeDomains URLs with each layer's tile matrix set", () => {
    expect(gibsTileUrl(SATELLITE.himawari_visible, "2026-10-16T00:50:00Z")).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/Himawari_AHI_Band3_Red_Visible_1km/default/2026-10-16T00:50:00Z/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png",
    );
    expect(gibsTileUrl(SATELLITE.himawari_ir, "2026-10-16T00:50:00Z")).toContain(
      "/Himawari_AHI_Band13_Clean_Infrared/default/2026-10-16T00:50:00Z/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
    );
    expect(gibsTileUrl(SATELLITE.viirs_truecolor, "2026-10-15")).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_NOAA21_CorrectedReflectance_TrueColor/default/2026-10-15/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg",
    );
    expect(describeDomainsUrl(SATELLITE.himawari_ir, at("2026-10-15T22:00:00Z"), at("2026-10-16T01:00:30Z"))).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/Himawari_AHI_Band13_Clean_Infrared/default/GoogleMapsCompatible_Level6/all/2026-10-15T22:00:00Z--2026-10-16T01:00:00Z.xml",
    );
  });

  it("parses ISO durations", () => {
    expect(periodMs("PT10M")).toBe(600000);
    expect(periodMs("P1D")).toBe(86400000);
    expect(periodMs("PT1H30M")).toBe(5400000);
    expect(periodMs("P")).toBeUndefined();
    expect(periodMs("PT")).toBeUndefined();
    expect(periodMs("10 minutes")).toBeUndefined();
    expect(periodMs("PT0M")).toBeUndefined();
  });

  it("expands time domains with their gaps", () => {
    const times = parseDomainTimes(DOMAINS);
    expect(times[0]).toBe(at("2026-10-15T13:30:00Z"));
    expect(times.at(-1)).toBe(at("2026-10-16T00:50:00Z"));
    // 7 frames to 14:30, none at 14:40, 61 from 14:50 to 00:50.
    expect(times).toHaveLength(7 + 61);
    expect(times).not.toContain(at("2026-10-15T14:40:00Z"));
    expect(parseDomainTimes("<Domain>2026-10-16/2026-10-16/P1D</Domain>")).toEqual([at("2026-10-16")]);
    expect(parseDomainTimes("<Domain>2026-10-16T00:00:00Z</Domain>")).toEqual([at("2026-10-16T00:00:00Z")]);
    // Unparsable or reversed ranges are skipped, not fatal.
    expect(parseDomainTimes("<Domain>soon/later/PT10M,2026-10-16T01:00:00Z/2026-10-16T00:00:00Z/PT10M</Domain>")).toEqual([]);
    expect(parseDomainTimes("not xml")).toEqual([]);
  });

  it("keeps the latest frames, fetches at most every 10 minutes per layer and surfaces outages", async () => {
    resetSatelliteCache();
    const urls: string[] = [];
    const fetcher = (async (url: string) => {
      urls.push(url);
      return { ok: true, text: async () => DOMAINS } as Response;
    }) as unknown as typeof fetch;
    const now = at("2026-10-16T01:20:00Z");
    const [a, b] = await Promise.all([
      fetchSatelliteTimes(SATELLITE.himawari_ir, now, fetcher),
      fetchSatelliteTimes(SATELLITE.himawari_ir, now, fetcher),
    ]);
    expect(a).toBe(b);
    expect(a).toHaveLength(7);
    expect(a.at(-1)).toBe(at("2026-10-16T00:50:00Z"));
    await fetchSatelliteTimes(SATELLITE.himawari_ir, now + 9 * 60000, fetcher);
    expect(urls).toHaveLength(1);
    await fetchSatelliteTimes(SATELLITE.himawari_visible, now, fetcher);
    expect(urls).toHaveLength(2);
    await fetchSatelliteTimes(SATELLITE.himawari_ir, now + 11 * 60000, fetcher);
    expect(urls).toHaveLength(3);

    resetSatelliteCache();
    const down = (async () => ({ ok: false, status: 503 }) as Response) as typeof fetch;
    await expect(fetchSatelliteTimes(SATELLITE.himawari_ir, now, down)).rejects.toThrow("503");
    const empty = (async () => ({ ok: true, text: async () => "<Domains/>" }) as Response) as typeof fetch;
    await expect(fetchSatelliteTimes(SATELLITE.himawari_ir, now, empty)).rejects.toThrow("no frames");
  });
});

const GEOMETRY_URL = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid=1001338&episodeid=6";

const feature = (Class: string, type: string, coordinates: unknown, extra: Record<string, unknown> = {}) => ({
  type: "Feature",
  properties: { Class, name: "Tropical Cyclone CHAMPI-26", ...extra },
  geometry: { type, coordinates },
});

const GEOMETRY = {
  type: "FeatureCollection",
  features: [
    feature("Point_Centroid", "Point", [156.5, 11.5]),
    feature("Line_Line_0", "LineString", [[150, 10], [152, 12]], { forecast: true }),
    feature("Line_Line_6", "LineString", [[148, 9], [150, 10]], { forecast: false }),
    feature("Poly_Red", "Polygon", [[[150, 10], [151, 10], [151, 11], [150, 10]]]),
    feature("Poly_Green", "Polygon", [[[149, 9], [152, 9], [152, 12], [149, 9]]]),
    feature("Poly_Cones", "Polygon", [[[149, 9], [155, 9], [155, 15], [149, 9]]]),
    feature("Point_Polygon_Point_0", "Polygon", [[[150, 10], [150.1, 10], [150.1, 10.1], [150, 10]]]),
    feature("Poly_Orange", "Point", [150, 10]),
    { type: "Feature", properties: { Class: "Poly_Orange" }, geometry: null },
  ],
};

describe("GDACS cyclone geometry (#71)", () => {
  it("allows only https GDACS tropical cyclone geometry URLs", () => {
    expect(isAllowedGeometryUrl(GEOMETRY_URL)).toBe(true);
    for (const url of [
      GEOMETRY_URL.replace("https:", "http:"),
      GEOMETRY_URL.replace("www.gdacs.org", "gdacs.org"),
      GEOMETRY_URL.replace("www.gdacs.org", "www.gdacs.org.evil.example"),
      GEOMETRY_URL.replace("www.gdacs.org", "www.gdacs.org:8443"),
      GEOMETRY_URL.replace("https://", "https://user:pw@"),
      GEOMETRY_URL.replace("eventtype=TC", "eventtype=EQ"),
      GEOMETRY_URL.replace("eventid=1001338", "eventid=x"),
      GEOMETRY_URL.replace("&episodeid=6", ""),
      GEOMETRY_URL.replace("getgeometry", "getgeometry/../other"),
      "https://www.gdacs.org/report.aspx?eventtype=TC&eventid=1001338",
      "javascript:alert(1)",
      "not a url",
      42,
      undefined,
    ]) {
      expect(isAllowedGeometryUrl(url), String(url)).toBe(false);
    }
  });

  it("picks allowlisted cyclones from the regional alerts attribute", () => {
    expect(cycloneRefs(undefined)).toEqual([]);
    const alerts = [
      { title: "Cyclone A", geometry_url: GEOMETRY_URL },
      { title: "Duplicate", geometry_url: GEOMETRY_URL },
      { title: "Earthquake", geometry_url: GEOMETRY_URL.replace("TC", "EQ") },
      { title: "Elsewhere", geometry_url: "https://evil.example/geo.json" },
      { title: "No geometry" },
      null,
      "text",
      { geometry_url: GEOMETRY_URL.replace("episodeid=6", "episodeid=7") },
    ];
    expect(cycloneRefs(alerts)).toEqual([
      { url: GEOMETRY_URL, name: "Cyclone A" },
      { url: GEOMETRY_URL.replace("episodeid=6", "episodeid=7"), name: "" },
    ]);
    const many = Array.from({ length: 9 }, (_, i) => ({ geometry_url: GEOMETRY_URL.replace("episodeid=6", `episodeid=${i}`) }));
    expect(cycloneRefs(many)).toHaveLength(5);
  });

  it("keeps the track, wind buffers and cone, widest first", () => {
    const geometry = parseCycloneGeometry(GEOMETRY);
    expect(geometry.name).toBe("Tropical Cyclone CHAMPI-26");
    expect(geometry.shapes.map((s) => s.part)).toEqual(["cone", "buffer-green", "buffer-red", "track", "track-forecast"]);
    expect(parseCycloneGeometry({ type: "FeatureCollection", features: [] }, "Fallback").name).toBe("Fallback");
    expect(() => parseCycloneGeometry({ type: "Feature" })).toThrow();
    expect(() => parseCycloneGeometry(null)).toThrow();
  });

  it("moves longitudes across the antimeridian east", () => {
    expect(unwrapCoordinates([[179, -20], [-179, -21]])).toEqual([[179, -20], [181, -21]]);
    expect(unwrapCoordinates([[[[-175, -30, 5]]]])).toEqual([[[[185, -30, 5]]]]);
    expect(unwrapCoordinates("x")).toBe("x");
  });

  it("fetches allowlisted URLs only, cached for 30 minutes", async () => {
    resetCycloneCache();
    const urls: string[] = [];
    const fetcher = (async (url: string) => {
      urls.push(url);
      return { ok: true, json: async () => GEOMETRY } as Response;
    }) as unknown as typeof fetch;
    const ref = { url: GEOMETRY_URL, name: "Cyclone A" };
    const [a, b] = await Promise.all([fetchCycloneGeometry(ref, 0, fetcher), fetchCycloneGeometry(ref, 0, fetcher)]);
    expect(a).toBe(b);
    await fetchCycloneGeometry(ref, 29 * 60000, fetcher);
    expect(urls).toEqual([GEOMETRY_URL]);
    await fetchCycloneGeometry(ref, 31 * 60000, fetcher);
    expect(urls).toHaveLength(2);
    await expect(fetchCycloneGeometry({ url: "https://evil.example/x", name: "" }, 0, fetcher)).rejects.toThrow("not allowed");
    expect(urls).toHaveLength(2);
    resetCycloneCache();
    const down = (async () => ({ ok: false, status: 500 }) as Response) as typeof fetch;
    await expect(fetchCycloneGeometry(ref, 0, down)).rejects.toThrow("500");
  });
});
