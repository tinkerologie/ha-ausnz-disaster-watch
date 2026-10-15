import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
// @ts-expect-error -- plain ES module without types
import { check } from "../../scripts/check-modern.mjs";
import { fetchRadarFrames, parseRadarFrames, radarTileUrl, resetRadarCache } from "../../src/cards/map/rainviewer";

const ids = (text: string) => (check(text) as { id: string }[]).map((f) => f.id);

describe("lint:modern (#42)", () => {
  it.each([
    ["color: #fff;", "hex-colour"],
    ["background: rgba(0, 0, 0, 0.5);", "rgb-hsl"],
    ["font-family: var(--paper-font-body1_-_font-family);", "paper-var"],
    ["<paper-button>", "legacy-elements"],
    ["<mwc-button>", "legacy-elements"],
    ["<ha-chip label=x>", "ha-chip"],
    ["return '\u{1F6A8}';", "emoji"],
    ["el.innerHTML = x;", "unsafe-html"],
    ['import { x } from "custom-card-helpers";', "custom-card-helpers"],
    ["  @property() foo;", "decorators"],
    ["src=/api/camera_proxy/camera.x", "camera-proxy"],
    ['<a href="#">', "href-hash"],
    ['<a href="/map">', "internal-href"],
    ["<div @click=${x}>", "div-click"],
    ["custom:aus-disaster-card", "legacy-card"],
    ["--mdc-theme-primary: x;", "mdc-vars"],
  ])("flags %s", (text, rule) => {
    expect(ids(text)).toContain(rule);
  });

  it.each([
    "color: var(--primary-text-color);",
    "--mdc-icon-size: var(--ha-space-4);",
    "<ha-chip-set>",
    "<ha-assist-chip>",
    "custom:ausnz-disaster-card",
    "`&#${c}`;",
    '<a href="https://example.com">',
    "x // lint-modern-ignore camera-proxy: signed /api/camera_proxy/",
  ])("allows %s", (text) => {
    expect(ids(text)).toEqual([]);
  });
});

describe("RainViewer (#41)", () => {
  const json = {
    host: "https://tilecache.rainviewer.com",
    generated: 10,
    radar: {
      past: Array.from({ length: 13 }, (_, i) => ({ time: 1000 + i * 600, path: `/v2/radar/${i}` })),
      nowcast: [],
    },
  };

  it("keeps the latest past frames, oldest first", () => {
    const data = parseRadarFrames(json, 7);
    expect(data.frames).toHaveLength(7);
    expect(data.frames[0]!.path).toBe("/v2/radar/6");
    expect(data.frames.at(-1)!.path).toBe("/v2/radar/12");
    expect(radarTileUrl(data.host, data.frames[0]!)).toBe(
      "https://tilecache.rainviewer.com/v2/radar/6/256/{z}/{x}/{y}/2/1_1.png",
    );
  });

  it("rejects unusable payloads", () => {
    expect(() => parseRadarFrames({})).toThrow();
    expect(() => parseRadarFrames({ host: "http://insecure", radar: { past: json.radar.past } })).toThrow();
    expect(() => parseRadarFrames({ host: json.host, radar: { past: [] } })).toThrow();
  });

  it("fetches at most every 10 minutes and shares the result", async () => {
    resetRadarCache();
    let calls = 0;
    const fetcher = (async () => {
      calls += 1;
      return { ok: true, json: async () => json } as Response;
    }) as typeof fetch;
    await Promise.all([fetchRadarFrames(0, fetcher), fetchRadarFrames(0, fetcher)]);
    await fetchRadarFrames(9 * 60 * 1000, fetcher);
    expect(calls).toBe(1);
    await fetchRadarFrames(11 * 60 * 1000, fetcher);
    expect(calls).toBe(2);
  });

  it("surfaces outages", async () => {
    resetRadarCache();
    const fetcher = (async () => ({ ok: false, status: 429 }) as Response) as typeof fetch;
    await expect(fetchRadarFrames(0, fetcher)).rejects.toThrow("429");
  });
});

describe("lint:drift (#42)", () => {
  const script = fileURLToPath(new URL("../../scripts/check-ha-drift.mjs", import.meta.url));
  const venv = fileURLToPath(new URL("../../../.local/ha-venv/lib", import.meta.url));
  const run = (env: Record<string, string>) =>
    spawnSync(process.execPath, [script], { env: { PATH: process.env.PATH ?? "", ...env }, encoding: "utf8" });

  it("fails when an explicit HASS_FRONTEND does not exist", () => {
    const result = run({ HASS_FRONTEND: join(tmpdir(), "adw-no-such-frontend") });
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("is not a directory");
  });

  it("checks against an explicit HASS_FRONTEND", () => {
    const dir = mkdtempSync(join(tmpdir(), "adw-frontend-"));
    try {
      writeFileSync(join(dir, "app.js"), "// no tokens here");
      const result = run({ HASS_FRONTEND: dir });
      expect(result.status).toBe(1);
      expect(result.stderr).toContain(`not found in ${dir}`);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it.skipIf(existsSync(venv))("fails instead of skipping when required and no frontend is found", () => {
    expect(run({}).status).toBe(0);
    const result = run({ LINT_DRIFT_REQUIRED: "1" });
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("no installed hass_frontend found");
  });
});
