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
  { tag: "ausnz-disaster-relief-card", text: "Brisbane City Council" },
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
    el.hass = { ...el.hass, states: { ...states, [fire]: { ...states[fire], state: "Extreme" } } };
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
  // The basemap goes through HA's map_tiles proxy with the short-lived token.
  const tiles = await el.locator(".basemap img").evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).src));
  expect(tiles.length).toBeGreaterThan(0);
  expect(tiles.every((src) => src.includes("/api/map_tiles/raster/") && src.includes("token=test-token"))).toBe(true);
});

test("radar animates without reduced motion and hides when RainViewer is down", async ({ page }) => {
  await setup(page);
  const el = await mount(page, "ausnz-disaster-map-card", { device: QLD });
  await expect(el.locator(".radar-bar ha-icon-button")).toHaveAttribute("aria-pressed", "true");

  const down = await page.context().newPage();
  await setup(down);
  await down.unroute("https://api.rainviewer.com/**");
  await down.route("https://api.rainviewer.com/**", (route) => route.fulfill({ status: 429, body: "" }));
  // Module cache is per page, so this page fetches again and sees the outage.
  const map = await mount(down, "ausnz-disaster-map-card", { device: QLD });
  await expect(map.getByText("Rain radar is unavailable right now.")).toBeVisible();
  await expect(map.locator(".leaflet-container")).toBeVisible();
});
