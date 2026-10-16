/**
 * Browser tests for the card suite (#43): the committed bundle, loaded the way Home
 * Assistant loads it, against a fixture captured from a live HA 2026.10 instance with
 * two config entries (QLD and NZ). External tiles and RainViewer are mocked.
 */
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const fixture = JSON.parse(readFileSync(new URL("./fixtures/hass.json", import.meta.url), "utf8"));
const QLD = "device-qld";
const NZ = "device-nz";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const RAINVIEWER = {
  version: "2.0",
  generated: 1792101030,
  host: "https://tilecache.rainviewer.com",
  radar: {
    past: Array.from({ length: 13 }, (_, i) => ({ time: 1792093800 + i * 600, path: `/v2/radar/frame${i}` })),
    nowcast: [],
  },
};

const CARDS: { tag: string; text: string; config?: Record<string, unknown> }[] = [
  { tag: "ausnz-disaster-status-card", text: "Watch and Act" },
  { tag: "ausnz-disaster-incidents-card", text: "Road Weather Alert for Brisbane" },
  { tag: "ausnz-disaster-warnings-card", text: "Warnings (1)" },
  { tag: "ausnz-disaster-fire-danger-card", text: "Moderate" },
  { tag: "ausnz-disaster-outages-card", text: "KURWONGBAH" },
  { tag: "ausnz-disaster-roads-card", text: "Dugandan Road, BUNYA" },
  { tag: "ausnz-disaster-conditions-card", text: "Station: Burpengary" },
  { tag: "ausnz-disaster-relief-card", text: "City of Moreton Bay" },
  { tag: "ausnz-disaster-cameras-card", text: "Goodna - Ipswich Mwy East" },
  { tag: "ausnz-disaster-map-card", text: "Radar" },
  { tag: "ausnz-disaster-card", text: "Watch and Act" },
];

async function setup(page: Page, { dark = false, reducedMotion = false } = {}) {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  const external: string[] = [];
  await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    external.push(route.request().url());
    return route.abort();
  });
  await page.route("https://api.rainviewer.com/**", (route) => route.fulfill({ json: RAINVIEWER }));
  await page.route("https://tilecache.rainviewer.com/**", (route) => route.fulfill({ body: PNG, contentType: "image/png" }));
  await page.route("**/api/map_tiles/**", (route) => route.fulfill({ body: PNG, contentType: "image/png" }));
  await page.route("**/api/camera_proxy/**", (route) => route.fulfill({ body: PNG, contentType: "image/png" }));
  await page.emulateMedia({ colorScheme: dark ? "dark" : "light", reducedMotion: reducedMotion ? "reduce" : "no-preference" });
  await page.goto("/");
  await page.evaluate(
    async ({ dark, fixture }) => {
      if (dark) document.documentElement.dataset.theme = "dark";
      (window as unknown as { fixture: unknown }).fixture = fixture;
      // Served by tests/browser/server.mjs, as Home Assistant serves it.
      const bundle = "/ausnz_disaster_watch/ausnz-disaster-card.js";
      await import(/* @vite-ignore */ bundle);
    },
    { dark, fixture },
  );
  return { errors, external };
}

async function mount(page: Page, tag: string, config: Record<string, unknown>, opts: { dark?: boolean; states?: object } = {}) {
  await page.evaluate(
    async ({ tag, config, opts }) => {
      const w = window as unknown as {
        fixture: unknown;
        makeHass: (f: unknown, o: unknown) => unknown;
        mountCard: (t: string, c: unknown, h: unknown) => Promise<HTMLElement>;
      };
      await w.mountCard(tag, config, w.makeHass(w.fixture, { darkMode: !!opts.dark, states: opts.states ?? {} }));
    },
    { tag, config, opts },
  );
  // Pin the index now: `.last()` would re-resolve to a card mounted later.
  return page.locator(tag).nth((await page.locator(tag).count()) - 1);
}

test("registers every card in the picker with a preview", async ({ page }) => {
  await setup(page);
  const cards = await page.evaluate(() => window.customCards);
  expect(cards?.map((c) => c.type).sort()).toEqual(CARDS.map((c) => c.tag).sort());
  for (const card of cards ?? []) {
    expect(card.preview).toBe(true);
    expect(card.name).toBeTruthy();
    expect(card.description).toBeTruthy();
    expect(card.documentationURL).toMatch(/^https:\/\//);
  }
  // The legacy alias is gone (#22).
  expect(await page.evaluate(() => customElements.get("aus-disaster-card"))).toBeUndefined();
});

test("every card has a form editor, grid options and a first-device stub", async ({ page }) => {
  await setup(page);
  const results = await page.evaluate(
    ({ tags }) => {
      const w = window as unknown as { fixture: unknown; makeHass: (f: unknown) => unknown };
      const hass = w.makeHass(w.fixture);
      return tags.map((tag) => {
        const ctor = customElements.get(tag) as unknown as {
          getConfigForm: () => { schema: { name: string; selector?: Record<string, unknown> }[]; computeLabel: (s: unknown) => string };
          getStubConfig: (h: unknown) => { device?: string };
        };
        const form = ctor.getConfigForm();
        const device = form.schema.find((s) => s.name === "device");
        const el = document.createElement(tag) as HTMLElement & { getGridOptions: () => { columns: number } };
        return {
          tag,
          device: device?.selector,
          label: form.computeLabel(device),
          stub: ctor.getStubConfig(hass),
          grid: el.getGridOptions(),
        };
      });
    },
    { tags: CARDS.map((c) => c.tag) },
  );
  for (const r of results) {
    expect(r.device, r.tag).toEqual({ device: { filter: { integration: "ausnz_disaster_watch" } } });
    expect(r.label).toBe("Disaster Watch location");
    // The first integration device in hass.devices order.
    expect(r.stub.device).toBe(Object.keys(fixture.devices)[0]);
    expect(r.grid.columns).toBeGreaterThanOrEqual(6);
    expect(r.grid.columns).toBeLessThanOrEqual(12);
  }
});

for (const dark of [false, true]) {
  for (const card of CARDS) {
    test(`${card.tag} renders (${dark ? "dark" : "light"})`, async ({ page }) => {
      const { errors, external } = await setup(page, { dark });
      const el = await mount(page, card.tag, { device: QLD, ...card.config }, { dark });
      await expect(el.getByText(card.text, { exact: false }).first()).toBeVisible();
      if (card.tag === "ausnz-disaster-map-card") {
        await expect(el.locator(".leaflet-container")).toBeVisible();
        await expect(el.locator(".leaflet-control-attribution")).toContainText("RainViewer");
        await expect(el.locator(".leaflet-control-attribution")).toContainText("OpenStreetMap");
      }
      await page.waitForTimeout(300);
      await el.screenshot({ path: join("test-results", "screenshots", `${card.tag}-${dark ? "dark" : "light"}.png`) });
      expect(errors).toEqual([]);
      expect(external).toEqual([]);
    });
  }
}

test("cards never mix config entries (#26)", async ({ page }) => {
  await setup(page);
  const qld = await mount(page, "ausnz-disaster-incidents-card", { device: QLD, max_items: 50 });
  const nz = await mount(page, "ausnz-disaster-incidents-card", { device: NZ, max_items: 50 });
  await expect(qld.getByText("Road Weather Alert for Brisbane").first()).toBeVisible();
  await expect(qld.getByText("Kaikoura")).toHaveCount(0);
  await expect(nz.getByText("M2.6 Earthquake", { exact: false })).toBeVisible();
  await expect(nz.getByText("Brisbane")).toHaveCount(0);
  // Titles come from attributes, never the distance state.
  await expect(nz.locator("[slot=headline]").first()).not.toHaveText(/^\d+(\.\d+)?$/);
});

test("unavailable data is never shown as all clear (#26)", async ({ page }) => {
  await setup(page);
  const level = Object.keys(fixture.states).find((id) => id.includes("qld_dev_highest_warning_level"))!;
  const el = await mount(
    page,
    "ausnz-disaster-status-card",
    { device: QLD },
    { states: { [level]: { ...fixture.states[level], state: "unavailable" } } },
  );
  await expect(el.getByText("Status unavailable")).toBeVisible();
  await expect(el.getByText("All clear")).toHaveCount(0);
});

test("tapping opens more-info for the card's own entity", async ({ page }) => {
  await setup(page);
  const el = await mount(page, "ausnz-disaster-incidents-card", { device: QLD });
  const detail = page.evaluate(
    () => new Promise((resolve) => window.addEventListener("hass-more-info", (e) => resolve((e as CustomEvent).detail), { once: true })),
  );
  await el.locator("ha-md-list-item").first().click();
  const { entityId } = (await detail) as { entityId: string };
  expect(entityId).toMatch(/^geo_location\./);
  expect(fixture.states[entityId].attributes.entry_id).toBe("entry-qld");
});

test("unsafe upstream links are not rendered as links (#26)", async ({ page }) => {
  await setup(page);
  const warnings = Object.keys(fixture.states).find((id) => id.includes("qld_dev_weather_warnings_count"))!;
  const s = fixture.states[warnings];
  const el = await mount(
    page,
    "ausnz-disaster-warnings-card",
    { device: QLD },
    {
      states: {
        [warnings]: {
          ...s,
          state: "2",
          attributes: {
            ...s.attributes,
            warnings: [
              { title: "Evil warning", link: "javascript:alert(1)", locations: "X" },
              { title: "Good warning", link: "https://www.bom.gov.au/qld/warnings/", locations: "Y" },
            ],
          },
        },
      },
    },
  );
  await expect(el.getByText("Evil warning")).toBeVisible();
  const hrefs = await el.locator("ha-icon-button.link").evaluateAll((els) => els.map((e) => (e as HTMLElement & { href: string }).href));
  expect(hrefs).toEqual(["https://www.bom.gov.au/qld/warnings/"]);
});

test("unrelated entity updates do not re-render (#33)", async ({ page }) => {
  await setup(page);
  await mount(page, "ausnz-disaster-fire-danger-card", { device: QLD });
  const renders = await page.evaluate(async () => {
    const el = document.querySelector("ausnz-disaster-fire-danger-card") as HTMLElement & {
      hass: { states: Record<string, { state: string }> };
      render: () => unknown;
      updateComplete: Promise<boolean>;
    };
    let count = 0;
    const original = el.render.bind(el);
    el.render = () => {
      count += 1;
      return original();
    };
    const states: Record<string, { state: string }> = {
      ...el.hass.states,
      "sensor.unrelated": { entity_id: "sensor.unrelated", state: "1", attributes: {} } as { state: string },
    };
    el.hass = { ...el.hass, states };
    await el.updateComplete;
    const unrelated = count;
    const fire = Object.keys(states).find((id) => id.includes("qld_dev_fire_danger_rating"))!;
    el.hass = { ...el.hass, states: { ...states, [fire]: { ...states[fire], state: "extreme" } } };
    await el.updateComplete;
    return { unrelated, related: count };
  });
  expect(renders).toEqual({ unrelated: 0, related: 1 });
});

test("map loads its lazy chunk and radar respects reduced motion (#41)", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  const chunk = page.waitForResponse((r) => /ausnz-disaster-leaflet-map-.*\.js$/.test(r.url()));
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await chunk;
  const play = el.locator(".radar-bar ha-icon-button");
  await expect(play).toHaveAttribute("aria-pressed", "false");
  const first = await el.locator(".radar-bar .time").textContent();
  await page.waitForTimeout(1500);
  expect(await el.locator(".radar-bar .time").textContent()).toBe(first);
  // Incident markers are keyboard operable from the first render.
  const marker = el.locator("path.incident").first();
  await expect(marker).toHaveAttribute("role", "button");
  await expect(marker).toHaveAttribute("tabindex", "0");
  await expect(marker).toHaveAttribute("aria-label", /.+/);
  // The basemap goes through HA's map_tiles proxy with the short-lived token.
  const tiles = await el.locator(".basemap img").evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).src));
  expect(tiles.length).toBeGreaterThan(0);
  expect(tiles.every((src) => src.includes("/api/map_tiles/raster/") && src.includes("token=test-token"))).toBe(true);
});

test("radar animates without reduced motion and hides when RainViewer is down", async ({ page }) => {
  await setup(page);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect(el.locator(".radar-bar ha-icon-button")).toHaveAttribute("aria-pressed", "true");
  // Radar frames advancing must not rebuild the markers (focus would be lost).
  const marker = el.locator("path.incident").first();
  await marker.evaluate((m) => ((m as Element & { tagged?: boolean }).tagged = true));
  await page.waitForTimeout(1200);
  expect(await el.locator("path.incident").first().evaluate((m) => !!(m as Element & { tagged?: boolean }).tagged)).toBe(
    true,
  );

  const down = await page.context().newPage();
  await setup(down);
  await down.unroute("https://api.rainviewer.com/**");
  await down.route("https://api.rainviewer.com/**", (route) => route.fulfill({ status: 429, body: "" }));
  // Module cache is per page, so this page fetches again and sees the outage.
  const map = await mount(down, "ausnz-disaster-map-card", { device: QLD });
  await expect(map.getByText("Rain radar is unavailable right now.")).toBeVisible();
  await expect(map.locator(".leaflet-container")).toBeVisible();
});

test("outage customers come from their own sensor and are never shown as 0 when missing (#26)", async ({ page }) => {
  await setup(page);
  const count = Object.keys(fixture.states).find((id) => id.includes("qld_dev_power_outages_count"))!;
  const customers = Object.keys(fixture.states).find((id) => id.includes("qld_dev_power_outages_customers_affected"))!;
  const c = fixture.states[count];
  const noAttr = { ...c, attributes: { ...c.attributes, customers_affected: undefined } };

  const fromSensor = await mount(page, "ausnz-disaster-outages-card", { device: QLD }, { states: { [count]: noAttr } });
  await expect(fromSensor.getByText("1 outage · 124 customers affected")).toBeVisible();
  await expect(fromSensor.getByText("1 outages")).toHaveCount(0);

  const missing = await mount(
    page,
    "ausnz-disaster-outages-card",
    { device: QLD },
    { states: { [count]: noAttr, [customers]: { ...fixture.states[customers], state: "unavailable" } } },
  );
  await expect(missing.getByText("1 outage", { exact: true })).toBeVisible();
  await expect(missing.getByText(/0 customers affected/)).toHaveCount(0);
});

test("radar bar stays when the frame list is unchanged while paused (#41)", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  const play = el.locator(".radar-bar ha-icon-button");
  await expect(play).toHaveAttribute("aria-pressed", "false");
  // Off screen and back: loadRadar() sees the same cached frame list.
  await el.evaluate(async (card) => {
    const map = (card as unknown as { _map: { setVisible: (v: boolean) => void } })._map;
    map.setVisible(false);
    map.setVisible(true);
    await new Promise((r) => setTimeout(r, 200));
  });
  await expect(play).toBeVisible();
  await expect(play).toHaveAttribute("aria-pressed", "false");
});

test("basemap falls back to OpenStreetMap when map_tiles keeps failing after a token refresh", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  await page.unroute("**/api/map_tiles/**");
  await page.route("**/api/map_tiles/**", (route) => route.fulfill({ status: 503, body: "" }));
  await page.route("https://tile.openstreetmap.org/**", (route) => route.fulfill({ body: PNG, contentType: "image/png" }));
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect
    .poll(async () =>
      el.locator(".basemap img").evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).src)),
    )
    .toEqual(expect.arrayContaining([expect.stringContaining("https://tile.openstreetmap.org/")]));
  const srcs = await el.locator(".basemap img").evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).src));
  expect(srcs.some((src) => src.includes("/api/map_tiles/"))).toBe(false);
});

test("map reframes when a replacement incident set is entirely out of view", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect(el.locator("path.incident").first()).toBeVisible();
  const inView = await el.evaluate(async (card) => {
    const c = card as unknown as {
      hass: { states: Record<string, { entity_id: string; attributes: Record<string, unknown> }> };
      updateComplete: Promise<unknown>;
      _map: { map: { getBounds: () => { contains: (p: [number, number]) => boolean } } };
    };
    const states = { ...c.hass.states };
    const template = Object.values(states).find(
      (s) => s.entity_id.startsWith("geo_location.") && s.attributes.entry_id === "entry-qld",
    )!;
    for (const id of Object.keys(states)) {
      if (id.startsWith("geo_location.") && states[id]!.attributes.entry_id === "entry-qld") delete states[id];
    }
    // A new incident in Perth, far outside the Brisbane view.
    states["geo_location.perth_fire"] = {
      ...template,
      entity_id: "geo_location.perth_fire",
      attributes: { ...template.attributes, latitude: -31.95, longitude: 115.86, title: "Perth fire" },
    };
    c.hass = { ...c.hass, states };
    await c.updateComplete;
    await new Promise((r) => setTimeout(r, 100));
    return c._map.map.getBounds().contains([-31.95, 115.86]);
  });
  expect(inView).toBe(true);
});

test("a single transient basemap tile error does not switch to OpenStreetMap", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  await page.unroute("**/api/map_tiles/**");
  let failed = false;
  await page.route("**/api/map_tiles/**", (route) => {
    if (!failed) {
      failed = true;
      return route.fulfill({ status: 503, body: "" });
    }
    return route.fulfill({ body: PNG, contentType: "image/png" });
  });
  await page.route("https://tile.openstreetmap.org/**", (route) => route.fulfill({ body: PNG, contentType: "image/png" }));
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect.poll(() => failed).toBe(true);
  await page.waitForTimeout(500);
  const srcs = await el.locator(".basemap img").evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).src));
  expect(srcs.length).toBeGreaterThan(0);
  expect(srcs.every((src) => src.includes("/api/map_tiles/"))).toBe(true);
});

test("scattered radar tile failures do not hide the radar; only consecutive ones do", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  await page.unroute("https://tilecache.rainviewer.com/**");
  let n = 0;
  let failures = 0;
  let pending = 0;
  // Answer one tile at a time, alternating success and failure, so load and error events
  // interleave (a 503 would otherwise settle before a PNG decodes and errors would bunch).
  let queue = Promise.resolve();
  await page.route("https://tilecache.rainviewer.com/**", (route) => {
    n += 1;
    pending += 1;
    const fail = n % 2 === 0;
    queue = queue.then(async () => {
      if (fail) failures += 1;
      await (fail ? route.fulfill({ status: 503, body: "" }) : route.fulfill({ body: PNG, contentType: "image/png" }));
      await new Promise((r) => setTimeout(r, 10));
      pending -= 1;
    });
    return queue;
  });
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect.poll(() => n).toBeGreaterThan(0);
  // A closer view makes every frame layer request several tiles.
  await el.evaluate((card) => {
    (card as unknown as { _map: { map: { setView: (c: [number, number], z: number) => void } } })._map.map.setView(
      [-27.47, 153.02],
      7,
    );
  });
  await expect.poll(() => pending, { timeout: 15000 }).toBe(0);
  // Far more failures in total than the limit of 8, but never two in a row.
  expect(failures).toBeGreaterThan(12);
  await page.waitForTimeout(200);
  await expect(el.getByText("Rain radar is unavailable right now.")).toHaveCount(0);
  await expect(el.locator(".radar-bar ha-icon-button")).toBeVisible();
});

/* ---------- Satellite layers and cyclone tracks (#71) ---------- */

const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/";
/** DescribeDomains with frames up to 10 minutes ago, so the latest seven are the last 70 minutes. */
function gibsDomains(): string {
  const end = new Date(Math.floor(Date.now() / 600000) * 600000 - 600000);
  const start = new Date(end.getTime() - 3 * 3600000);
  const iso = (d: Date) => d.toISOString().replace(/\.\d{3}Z$/, "Z");
  return `<Domains><DimensionDomain><ows:Identifier>time</ows:Identifier><Domain>${iso(start)}/${iso(end)}/PT10M</Domain></DimensionDomain></Domains>`;
}
const ALERTS_ID = "sensor.australia_and_new_zealand_disaster_watch_qld_dev_regional_disaster_alerts";
const GEOMETRY_URL = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid=1000999&episodeid=4";
const CYCLONE = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { Class: "Poly_Cones" }, geometry: { type: "Polygon", coordinates: [[[152, -20], [156, -20], [156, -16], [152, -20]]] } },
    { type: "Feature", properties: { Class: "Poly_Green" }, geometry: { type: "Polygon", coordinates: [[[152, -22], [155, -22], [155, -19], [152, -22]]] } },
    { type: "Feature", properties: { Class: "Poly_Red" }, geometry: { type: "Polygon", coordinates: [[[153, -21], [154, -21], [154, -20], [153, -21]]] } },
    { type: "Feature", properties: { Class: "Line_Line_0", forecast: false }, geometry: { type: "LineString", coordinates: [[156, -16], [154, -19]] } },
    { type: "Feature", properties: { Class: "Line_Line_1", forecast: true }, geometry: { type: "LineString", coordinates: [[154, -19], [153, -23]] } },
    { type: "Feature", properties: { Class: "Point_Centroid" }, geometry: { type: "Point", coordinates: [154, -19] } },
  ],
};

async function routeGibs(page: Page, domainRequests: string[] = [], tiles: string[] = []) {
  await page.route(`${GIBS}**`, (route) => {
    const url = route.request().url();
    if (url.endsWith(".xml")) {
      domainRequests.push(url);
      return route.fulfill({ body: gibsDomains(), contentType: "text/xml", headers: { "access-control-allow-origin": "*" } });
    }
    tiles.push(url);
    return route.fulfill({ body: PNG, contentType: "image/png" });
  });
}

const attributionText = (el: ReturnType<Page["locator"]>) => el.locator(".leaflet-control-attribution").textContent();

test("map config form offers satellite and cyclone options, both off by default (#71)", async ({ page }) => {
  await setup(page);
  const form = await page.evaluate(async () => {
    const cls = customElements.get("ausnz-disaster-map-card") as unknown as {
      getConfigForm: () => { schema: { name: string; default?: unknown; selector: Record<string, unknown> }[]; computeLabel: (s: { name: string }) => string };
      validateConfig: (c: unknown) => void;
    };
    const { schema, computeLabel } = cls.getConfigForm();
    const bad = (config: unknown) => {
      try {
        cls.validateConfig(config);
        return "";
      } catch (err) {
        return (err as Error).message;
      }
    };
    return {
      fields: schema.map((s) => [s.name, s.default ?? null, computeLabel(s)]),
      options: (schema.find((s) => s.name === "satellite_layer")!.selector.select as { options: { value: string; label: string }[] }).options,
      errors: [bad({ satellite_layer: "modis" }), bad({ show_cyclone_tracks: "yes" }), bad({ satellite_layer: "himawari_ir", show_cyclone_tracks: true })],
    };
  });
  expect(form.fields).toContainEqual(["satellite_layer", "none", "Satellite layer"]);
  expect(form.fields).toContainEqual(["show_cyclone_tracks", false, "Cyclone tracks"]);
  expect(form.options.map((o) => o.value)).toEqual(["none", "himawari_visible", "himawari_ir", "viirs_truecolor"]);
  expect(form.options.every((o) => o.label && o.label !== o.value)).toBe(true);
  expect(form.errors[0]).toContain("satellite_layer");
  expect(form.errors[1]).toContain("show_cyclone_tracks");
  expect(form.errors[2]).toBe("");
});

test("relief card links only the entry's own council unless nearby councils are asked for (#94)", async ({ page }) => {
  const { errors } = await setup(page);
  const hrefs = (el: ReturnType<Page["locator"]>) =>
    el.locator("ha-icon-button.link").evaluateAll((els) => els.map((e) => (e as HTMLElement & { href: string }).href));

  const own = await mount(page, "ausnz-disaster-relief-card", { device: QLD });
  await expect(own.getByText("Council dashboard", { exact: true })).toBeVisible();
  await expect(own.getByText("City of Moreton Bay")).toBeVisible();
  await expect(own.getByText("Nearby council dashboards")).toHaveCount(0);
  await expect(own.getByText("Noosa Shire Council")).toHaveCount(0);
  expect(await hrefs(own)).toEqual(["https://disaster.moretonbay.qld.gov.au/"]);

  const all = await mount(page, "ausnz-disaster-relief-card", { device: QLD, show_nearby_councils: true });
  await expect(all.getByText("City of Moreton Bay")).toBeVisible();
  await expect(all.getByText("Nearby council dashboards")).toBeVisible();
  await expect(all.getByText("Noosa Shire Council")).toBeVisible();
  expect(await hrefs(all)).toHaveLength(6);

  // No council dashboard: no council section, even with nearby links available
  const level = Object.keys(fixture.states).find((id) => id.includes("qld_dev_highest_warning_level"))!;
  const warnings = Object.keys(fixture.states).find((id) => id.includes("qld_dev_weather_warnings_count"))!;
  const noCouncil = Object.fromEntries(
    [level, warnings].map((id) => [id, { ...fixture.states[id], attributes: { ...fixture.states[id].attributes, council: null } }]),
  );
  const none = await mount(page, "ausnz-disaster-relief-card", { device: QLD }, { states: noCouncil });
  await expect(none.getByText("Council dashboard", { exact: true })).toHaveCount(0);
  await expect(none.getByText("Noosa Shire Council")).toHaveCount(0);
  const noneAll = await mount(page, "ausnz-disaster-relief-card", { device: QLD, show_nearby_councils: true }, { states: noCouncil });
  await expect(noneAll.getByText("Noosa Shire Council")).toBeVisible();

  // The all-in-one card passes the option to its relief section (mounted last: its
  // sections are relief cards too, which would shift the relief-card index above)
  const stacked = await mount(page, "ausnz-disaster-card", { device: QLD, cards: ["relief"] });
  await expect(stacked.getByText("City of Moreton Bay")).toBeVisible();
  await expect(stacked.getByText("Noosa Shire Council")).toHaveCount(0);
  const stackedAll = await mount(page, "ausnz-disaster-card", { device: QLD, cards: ["relief"], show_nearby_councils: true });
  await expect(stackedAll.getByText("Noosa Shire Council")).toBeVisible();

  const form = await page.evaluate(() => {
    const cls = customElements.get("ausnz-disaster-relief-card") as unknown as {
      getConfigForm: () => { schema: { name: string; selector: Record<string, unknown> }[]; computeLabel: (s: { name: string }) => string };
      validateConfig: (c: unknown) => void;
    };
    const { schema, computeLabel } = cls.getConfigForm();
    let error = "";
    try {
      cls.validateConfig({ show_nearby_councils: "yes" });
    } catch (err) {
      error = (err as Error).message;
    }
    return { fields: schema.map((s) => [s.name, computeLabel(s)]), error };
  });
  expect(form.fields).toContainEqual(["show_nearby_councils", "Show nearby councils"]);
  expect(form.error).toContain("show_nearby_councils");
  expect(errors).toEqual([]);
});

/** QLD states as the integration publishes them once the council area is known (#94). */
function councilStates(): Record<string, unknown> {
  const states = fixture.states as Record<string, { entity_id: string; state: string; attributes: Record<string, unknown> }>;
  const id = (part: string) => Object.keys(states).find((k) => k.includes(part))!;
  const withAttrs = (key: string, attrs: Record<string, unknown>) => ({
    ...states[key],
    attributes: { ...states[key]!.attributes, ...attrs },
  });
  const inside = new Set(["Bribie Island Road", "Bruce Highway", "Morayfield Road"]);
  const roads = id("qld_dev_road_closures_count");
  const outages = id("qld_dev_power_outages_count");
  const level = id("qld_dev_highest_warning_level");
  const out: Record<string, unknown> = {
    [level]: withAttrs(level, { council_area: { name: "City of Moreton Bay", code: "35010" } }),
    [roads]: withAttrs(roads, {
      council_area_count: 3,
      closures: (states[roads]!.attributes.closures as { road: string }[]).map((c) => ({ ...c, in_council_area: inside.has(c.road) })),
    }),
    [outages]: withAttrs(outages, {
      council_area_count: 0,
      council_area_customers_affected: 0,
      outages: (states[outages]!.attributes.outages as object[]).map((o) => ({ ...o, in_council_area: false })),
    }),
  };
  for (const key of Object.keys(states)) {
    if (key.startsWith("camera.") && key.includes("qld_dev")) {
      out[key] = withAttrs(key, { in_council_area: key.includes("caboolture") });
    } else if (key.startsWith("geo_location.") && states[key]!.attributes.entry_id === "entry-qld") {
      out[key] = withAttrs(key, { in_council_area: key.includes("road_weather_alert_for_brisbane") });
    }
  }
  return out;
}

test("cards show the council area by default for local services and the radius for hazards (#94)", async ({ page }) => {
  const { errors } = await setup(page);
  const states = councilStates();

  // Roads: council by default, with the council in the header and the council count
  const roads = await mount(page, "ausnz-disaster-roads-card", { device: QLD }, { states });
  await expect(roads.locator(".subtitle")).toHaveText("City of Moreton Bay");
  await expect(roads.getByText("Bribie Island Road")).toBeVisible();
  await expect(roads.getByText("Dugandan Road")).toHaveCount(0);
  await expect(roads.locator(".count")).toHaveText("3");
  const roadsRadius = await mount(page, "ausnz-disaster-roads-card", { device: QLD, area: "radius" }, { states });
  await expect(roadsRadius.getByText("Dugandan Road", { exact: false })).toBeVisible();
  await expect(roadsRadius.locator(".subtitle")).toHaveCount(0);
  await expect(roadsRadius.locator(".count")).toHaveText("5");

  // Outages: none in the council, though one in the radius
  const outages = await mount(page, "ausnz-disaster-outages-card", { device: QLD }, { states });
  await expect(outages.getByText("KURWONGBAH")).toHaveCount(0);
  await expect(outages.getByText("No power outages", { exact: false })).toBeVisible();

  // Cameras: only the one in the council
  const cameras = await mount(page, "ausnz-disaster-cameras-card", { device: QLD }, { states });
  await expect(cameras.locator(".camera")).toHaveCount(1);
  await expect(cameras.locator(".count")).toHaveText("1");

  // Incidents and status: the radius unless asked for the council
  const incidents = await mount(page, "ausnz-disaster-incidents-card", { device: QLD, max_items: 50 }, { states });
  await expect(incidents.getByText("Severe Thunderstorm Warning", { exact: false }).first()).toBeVisible();
  await expect(incidents.locator(".subtitle")).toHaveCount(0);
  const councilIncidents = await mount(
    page,
    "ausnz-disaster-incidents-card",
    { device: QLD, max_items: 50, area: "council" },
    { states },
  );
  await expect(councilIncidents.locator(".subtitle")).toHaveText("City of Moreton Bay");
  await expect(councilIncidents.locator(".count")).toHaveText("2");
  await expect(councilIncidents.getByText("Severe Thunderstorm Warning", { exact: false })).toHaveCount(0);

  const status = await mount(page, "ausnz-disaster-status-card", { device: QLD, area: "council" }, { states });
  await expect(status.getByText("2 hazards in City of Moreton Bay")).toBeVisible();
  // An unknown level (incidents without a known level) still counts the council's incidents
  const level = Object.keys(states).find((k) => k.includes("qld_dev_highest_warning_level"))!;
  const unknownLevel = { ...states, [level]: { ...(states[level] as object), state: "unknown" } };
  const statusUnknown = await mount(page, "ausnz-disaster-status-card", { device: QLD, area: "council" }, { states: unknownLevel });
  await expect(statusUnknown.getByText("2 hazards in City of Moreton Bay")).toBeVisible();
  const statusRadius = await mount(page, "ausnz-disaster-status-card", { device: QLD }, { states });
  await expect(statusRadius.getByText("in City of Moreton Bay", { exact: false })).toHaveCount(0);

  const map = await mount(page, "ausnz-disaster-map-card", { device: QLD, area: "council" }, { states });
  await expect(map.locator(".subtitle")).toHaveText("City of Moreton Bay");
  await expect(map.locator("path.incident")).toHaveCount(2);
  expect(errors).toEqual([]);
});

test("council filter falls back to the radius with a hint while the boundary is unknown (#94)", async ({ page }) => {
  const { errors } = await setup(page);
  const roads = await mount(page, "ausnz-disaster-roads-card", { device: QLD });
  await expect(roads.getByText("Your council's boundary is not known yet", { exact: false })).toBeVisible();
  await expect(roads.getByText("Dugandan Road", { exact: false })).toBeVisible();
  await expect(roads.locator(".subtitle")).toHaveCount(0);
  // No hint when the card asks for the radius
  const radius = await mount(page, "ausnz-disaster-incidents-card", { device: NZ });
  await expect(radius.getByText("Your council's boundary is not known yet", { exact: false })).toHaveCount(0);

  const form = await page.evaluate(() =>
    ["ausnz-disaster-relief-card", "ausnz-disaster-incidents-card", "ausnz-disaster-status-card", "ausnz-disaster-warnings-card"].map(
      (tag) => {
        const cls = customElements.get(tag) as unknown as {
          getConfigForm: () => {
            schema: { name: string; default?: unknown; selector?: { select?: { options: { value: string; label: string }[] } } }[];
            computeLabel: (s: { name: string }) => string;
          };
          validateConfig: (c: unknown) => void;
        };
        const { schema, computeLabel } = cls.getConfigForm();
        const field = schema.find((s) => s.name === "area");
        let error = "";
        try {
          cls.validateConfig({ area: "state" });
        } catch (err) {
          error = (err as Error).message;
        }
        return {
          tag,
          default: field?.default ?? null,
          label: field ? computeLabel(field) : null,
          options: field?.selector?.select?.options ?? [],
          error,
        };
      },
    ),
  );
  expect(form.map((f) => f.default)).toEqual(["council", "radius", "radius", null]);
  expect(form[0]!.label).toBe("Area");
  expect(form[0]!.options).toEqual([
    { value: "council", label: "My council" },
    { value: "radius", label: "Radius" },
  ]);
  expect(form.every((f) => f.error.includes("area"))).toBe(true);
  expect(errors).toEqual([]);
});

test("default map requests no satellite or GDACS data (#71)", async ({ page }) => {
  const domains: string[] = [];
  const { external } = await setup(page);
  await routeGibs(page, domains);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect(el.locator(".leaflet-container")).toBeVisible();
  await page.waitForTimeout(300);
  expect(domains).toEqual([]);
  await expect(el.locator("ha-chip-set")).toHaveCount(0);
  expect(await attributionText(el)).not.toContain("NASA");
  expect(external).toEqual([]);
});

test("Himawari infrared animates on its own timeline and the chip hides it (#71)", async ({ page }) => {
  const domains: string[] = [];
  const tiles: string[] = [];
  const { errors, external } = await setup(page);
  await routeGibs(page, domains, tiles);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, radar: false, satellite_layer: "himawari_ir" });
  await expect(el.locator(".radar-bar .time")).toContainText("Satellite");
  await expect(el.locator(".radar-bar ha-icon-button")).toHaveAttribute("aria-pressed", "true");
  await expect(el.locator(".radar-bar .frames span")).toHaveCount(7);
  expect(domains).toHaveLength(1);
  expect(domains[0]).toContain("/1.0.0/Himawari_AHI_Band13_Clean_Infrared/default/GoogleMapsCompatible_Level6/all/");
  await expect.poll(() => tiles.length).toBeGreaterThan(0);
  expect(tiles.every((u) => /Himawari_AHI_Band13_Clean_Infrared\/default\/\d{4}-\d\d-\d\dT\d\d:\d0:00Z\/GoogleMapsCompatible_Level6\//.test(u))).toBe(true);
  const attribution = await attributionText(el);
  expect(attribution).toContain("NASA GIBS / Himawari-9 (JMA)");
  expect(attribution).not.toContain("RainViewer");
  // Seven frame layers, one visible at a time at the IR opacity.
  const opacities = await el.locator(".satellite-frame").evaluateAll((els) => els.map((e) => (e as HTMLElement).style.opacity));
  expect(opacities).toHaveLength(7);
  expect(opacities.filter((o) => o === "0.6")).toHaveLength(1);
  const before = await el.locator(".radar-bar .frames span.current").evaluate((s) => [...s.parentElement!.children].indexOf(s));
  await page.waitForTimeout(1800);
  const after = await el.locator(".radar-bar .frames span.current").evaluate((s) => [...s.parentElement!.children].indexOf(s));
  expect(after).not.toBe(before);

  const chip = el.locator("ha-filter-chip", { hasText: "Himawari infrared" });
  await expect(chip).toHaveAttribute("selected", "");
  await chip.click();
  await expect(el.locator(".satellite-frame")).toHaveCount(0);
  await expect(el.locator(".radar-bar")).toHaveCount(0);
  expect(await attributionText(el)).not.toContain("NASA");
  await el.screenshot({ path: join("test-results", "screenshots", "map-himawari-hidden.png") });
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("Himawari follows the radar timeline and respects reduced motion (#71)", async ({ page }) => {
  await setup(page, { reducedMotion: true, dark: true });
  await routeGibs(page);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, satellite_layer: "himawari_visible" }, { dark: true });
  await expect(el.locator(".radar-bar .time")).toContainText("Radar");
  await expect(el.locator(".satellite-frame")).toHaveCount(7);
  await expect(el.locator(".radar-bar ha-icon-button")).toHaveAttribute("aria-pressed", "false");
  const visibleFrames = () =>
    el.locator(".satellite-frame").evaluateAll((els) => els.map((e) => (e as HTMLElement).style.opacity).filter((o) => o !== "0").length);
  expect(await visibleFrames()).toBe(1);
  const first = await el.locator(".radar-bar .time").textContent();
  await page.waitForTimeout(1500);
  expect(await el.locator(".radar-bar .time").textContent()).toBe(first);
  const attribution = await attributionText(el);
  expect(attribution).toContain("RainViewer");
  expect(attribution).toContain("Himawari-9 (JMA)");
  await page.waitForTimeout(300);
  await el.screenshot({ path: join("test-results", "screenshots", "map-himawari-radar-dark.png") });
});

test("satellite outage shows a notice and keeps the radar (#71)", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  await page.route(`${GIBS}**`, (route) => route.fulfill({ status: 503, body: "" }));
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, satellite_layer: "himawari_ir" });
  await expect(el.getByText("Satellite imagery is unavailable right now.")).toBeVisible();
  await expect(el.locator(".radar-bar .time")).toContainText("Radar");
});

test("VIIRS true colour shows one daily image with a three-day date chip (#71)", async ({ page }) => {
  const tiles: string[] = [];
  const domains: string[] = [];
  const { errors } = await setup(page, { reducedMotion: true });
  await routeGibs(page, domains, tiles);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, radar: false, satellite_layer: "viirs_truecolor" });
  await expect(el.locator(".satellite-frame")).toHaveCount(1);
  const day = (offset: number) => new Date(Date.now() - offset * 86400000).toISOString().slice(0, 10);
  // Before 09:00 UTC the default is yesterday: today's image is still empty over AU/NZ.
  const first = new Date().getUTCHours() >= 9 ? 0 : 1;
  await expect.poll(() => tiles.some((u) => u.includes(`/VIIRS_NOAA21_CorrectedReflectance_TrueColor/default/${day(first)}/GoogleMapsCompatible_Level9/`))).toBe(true);
  expect(domains).toEqual([]);
  // No animation for a daily image.
  await expect(el.locator(".radar-bar")).toHaveCount(0);
  expect(await attributionText(el)).toContain("NASA GIBS / VIIRS NOAA-21");
  const chips = el.locator("ha-filter-chip[no-leading-icon]");
  await expect(chips).toHaveCount(3);
  await expect(chips.nth(first)).toHaveAttribute("selected", "");
  tiles.length = 0;
  await chips.nth(2).click();
  await expect(chips.nth(2)).toHaveAttribute("selected", "");
  await expect.poll(() => tiles.some((u) => u.includes(`/default/${day(2)}/`))).toBe(true);
  expect(tiles.some((u) => u.includes(`/default/${day(first)}/`))).toBe(false);
  await el.screenshot({ path: join("test-results", "screenshots", "map-viirs.png") });
  expect(errors).toEqual([]);
});

test("GDACS cyclone tracks are drawn from allowlisted geometry URLs only (#71)", async ({ page }) => {
  const geometry: string[] = [];
  const { errors, external } = await setup(page, { reducedMotion: true });
  await page.route("https://www.gdacs.org/**", (route) => {
    geometry.push(route.request().url());
    return route.fulfill({ json: CYCLONE, headers: { "access-control-allow-origin": "*" } });
  });
  const alerts = fixture.states[ALERTS_ID];
  const states = {
    [ALERTS_ID]: {
      ...alerts,
      state: "3",
      attributes: {
        ...alerts.attributes,
        alerts: [
          { title: "Orange notification for tropical cyclone ALFRED-26", event_type_code: "TC", geometry_url: GEOMETRY_URL },
          { title: "Earthquake", event_type_code: "EQ", geometry_url: GEOMETRY_URL.replace("TC", "EQ") },
          { title: "Elsewhere", geometry_url: "https://evil.example/geometry.json" },
        ],
      },
    },
  };
  const off = await mount(page, "ausnz-disaster-map-card", { device: QLD }, { states });
  await expect(off.locator(".leaflet-container")).toBeVisible();
  await page.waitForTimeout(300);
  expect(geometry).toEqual([]);

  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, show_cyclone_tracks: true }, { states });
  await expect(el.locator("path.cyclone-track")).toHaveCount(1);
  await expect(el.locator("path.cyclone-track-forecast")).toHaveCount(1);
  await expect(el.locator("path.cyclone-buffer-red")).toHaveCount(1);
  await expect(el.locator("path.cyclone-cone")).toHaveCount(1);
  expect(geometry).toEqual([GEOMETRY_URL]);
  await expect(el.getByText("GDACS model estimate — follow BoM / MetService warnings.")).toBeVisible();
  expect(await attributionText(el)).toContain("GDACS (EC JRC / UN OCHA)");
  // Colours come from HA tokens, not literals.
  const fill = await el.locator("path.cyclone-buffer-red").evaluate((p) => getComputedStyle(p).fill);
  expect(fill).not.toBe("none");
  // Buffers sit below the incident markers.
  const zCyclones = await el.locator(".leaflet-cyclones-pane").evaluate((p) => Number((p as HTMLElement).style.zIndex));
  expect(zCyclones).toBeLessThan(400);
  await el.screenshot({ path: join("test-results", "screenshots", "map-cyclone.png") });

  const chip = el.locator("ha-filter-chip", { hasText: "Cyclone tracks" });
  await chip.click();
  await expect(el.locator("path.cyclone")).toHaveCount(0);
  await expect(el.getByText("GDACS model estimate", { exact: false })).toHaveCount(0);
  expect(await attributionText(el)).not.toContain("GDACS");
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("GDACS outage shows a notice (#71)", async ({ page }) => {
  await setup(page, { reducedMotion: true });
  await page.route("https://www.gdacs.org/**", (route) => route.fulfill({ status: 500, body: "" }));
  const alerts = fixture.states[ALERTS_ID];
  const states = { [ALERTS_ID]: { ...alerts, attributes: { ...alerts.attributes, alerts: [{ title: "TC", geometry_url: GEOMETRY_URL }] } } };
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD, show_cyclone_tracks: true }, { states });
  await expect(el.getByText("Cyclone tracks are unavailable right now.")).toBeVisible();
});


test("an incident with a camera within 5 km offers it next to the incident (#70)", async ({ page }) => {
  const { errors } = await setup(page);
  const incident = Object.keys(fixture.states).find(
    (id) => id.startsWith("geo_location.") && fixture.states[id].attributes.entry_id === "entry-qld",
  )!;
  const camera = Object.keys(fixture.states).find((id) => id.startsWith("camera.") && id.includes("qld_dev"))!;
  const withCamera = (cameraId: string) => ({
    [incident]: {
      ...fixture.states[incident],
      attributes: {
        ...fixture.states[incident].attributes,
        nearest_camera: { entity_id: cameraId, name: "Goodna - Ipswich Mwy East", distance_km: 1.2 },
      },
    },
  });
  const el = await mount(page, "ausnz-disaster-incidents-card", { device: QLD, max_items: 50 }, { states: withCamera(camera) });
  const button = el.locator("ha-icon-button.camera");
  await expect(button).toHaveCount(1);
  await expect(button).toHaveJSProperty("label", "Nearest camera: Goodna - Ipswich Mwy East, 1.2 km");
  const detail = page.evaluate(
    () => new Promise((resolve) => window.addEventListener("hass-more-info", (e) => resolve((e as CustomEvent).detail), { once: true })),
  );
  await button.click();
  expect(((await detail) as { entityId: string }).entityId).toBe(camera);

  // A camera entity that no longer exists, or a non-camera ID, shows no button
  for (const id of ["camera.gone", "sensor.not_a_camera"]) {
    const other = await mount(page, "ausnz-disaster-incidents-card", { device: QLD, max_items: 50 }, { states: withCamera(id) });
    await expect(other.locator("ha-icon-button.camera")).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});
