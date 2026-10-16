import { describe, expect, it } from "vitest";
import {
  formatAttribute,
  formatDateTime,
  formatDistance,
  formatState,
  isUnavailable,
  listAttr,
  numberAttr,
  parseDate,
  relativeTime,
  safeUrl,
  stringAttr,
  timeZone,
} from "../../src/ha/format";
import { t, tCount } from "../../src/localize/localize";
import type { HassEntity, HomeAssistant } from "../../src/types";

const hass = (extra: Partial<HomeAssistant> = {}) =>
  ({
    states: {},
    entities: {},
    devices: {},
    locale: { language: "en", time_zone: "server" },
    config: { latitude: 0, longitude: 0, time_zone: "Australia/Brisbane" },
    connection: { sendMessagePromise: async () => ({}) },
    ...extra,
  }) as HomeAssistant;

const entity = (state: string, attributes: Record<string, unknown> = {}): HassEntity => ({
  entity_id: "sensor.x",
  state,
  attributes,
  last_changed: "",
  last_updated: "",
});

describe("safeUrl (#26)", () => {
  it.each([
    ["https://www.fire.qld.gov.au/x", "https://www.fire.qld.gov.au/x"],
    ["http://disaster.somerset.qld.gov.au", "http://disaster.somerset.qld.gov.au/"],
    ["javascript:alert(1)", undefined],
    ["JaVaScRiPt:alert(1)", undefined],
    ["data:text/html,<b>x</b>", undefined],
    ["/relative/path", undefined],
    ["not a url", undefined],
    ["", undefined],
    [42, undefined],
    [undefined, undefined],
  ])("%s", (value, expected) => {
    expect(safeUrl(value)).toBe(expected);
  });
});

describe("states", () => {
  it("treats unknown, unavailable and missing as unavailable", () => {
    expect(isUnavailable(undefined)).toBe(true);
    expect(isUnavailable(entity("unknown"))).toBe(true);
    expect(isUnavailable(entity("unavailable"))).toBe(true);
    expect(isUnavailable(entity("0"))).toBe(false);
  });

  it("uses HA formatters when present and falls back otherwise", () => {
    const withFormatters = hass({
      formatEntityState: (s) => `F(${s.state})`,
      formatEntityAttributeValue: (_s, a, v) => `A(${a}=${String(v)})`,
    });
    expect(formatState(withFormatters, entity("5"))).toBe("F(5)");
    expect(formatAttribute(withFormatters, entity("5", { x: 1 }), "x")).toBe("A(x=1)");
    expect(formatState(hass(), entity("5", { unit_of_measurement: "km" }))).toBe("5 km");
    expect(formatState(hass(), entity("5"))).toBe("5");
    expect(formatAttribute(hass(), entity("5", { x: 1234 }), "x")).toBe("1,234");
    expect(formatAttribute(hass(), entity("5", { x: "a" }), "x")).toBe("a");
  });

  it("keeps zero values (#26)", () => {
    expect(numberAttr(0)).toBe(0);
    expect(numberAttr("0")).toBe(0);
    expect(numberAttr("")).toBeUndefined();
    expect(numberAttr(Number.NaN)).toBeUndefined();
    expect(numberAttr(null)).toBeUndefined();
    expect(stringAttr("  x ")).toBe("x");
    expect(stringAttr(" ")).toBeUndefined();
    expect(listAttr([{ a: 1 }, null, 2])).toEqual([{ a: 1 }]);
    expect(listAttr("x")).toEqual([]);
  });
});

describe("distance and time", () => {
  it("formats distances", () => {
    expect(formatDistance(hass(), 4.26)).toBe("4.3 km");
    expect(formatDistance(hass(), 140.58)).toBe("141 km");
    expect(formatDistance(hass(), 0)).toBe("0 km");
    expect(formatDistance(hass(), undefined)).toBeUndefined();
    expect(formatDistance(hass(), Number.POSITIVE_INFINITY)).toBeUndefined();
  });

  it("formats relative time in the user's language", () => {
    const now = Date.parse("2026-10-16T00:00:00Z");
    expect(relativeTime(hass(), "2026-10-15T23:55:00Z", now)).toBe("5 minutes ago");
    expect(relativeTime(hass(), "2026-10-15T21:00:00Z", now)).toBe("3 hours ago");
    expect(relativeTime(hass(), "2026-10-15T00:00:00Z", now)).toBe("yesterday");
    expect(relativeTime(hass(), "2026-10-16T00:00:00Z", now)).toBe("now");
    expect(relativeTime(hass(), "garbage", now)).toBeUndefined();
    expect(relativeTime(hass(), undefined, now)).toBeUndefined();
  });

  it("parses .NET JSON dates from upstream feeds", () => {
    expect(parseDate("/Date(1792116000000)/")?.toISOString()).toBe("2026-10-16T02:00:00.000Z");
    expect(parseDate("/Date(1792116000000+1000)/")?.getTime()).toBe(1792116000000);
  });

  it("uses HA's time zone when the profile says server", () => {
    expect(timeZone(hass())).toBe("Australia/Brisbane");
    expect(timeZone(hass({ locale: { language: "en", time_zone: "local" } }))).toBeUndefined();
    expect(formatDateTime(hass(), "2026-10-16T02:00:00Z", { hour: "numeric", minute: "2-digit", hour12: false })).toBe(
      "12:00",
    );
    expect(formatDateTime(hass(), "x")).toBeUndefined();
  });
});

describe("localize", () => {
  it("substitutes placeholders and falls back to English", () => {
    expect(t(hass(), "status.hazards", { count: 3 })).toBe("3 hazards nearby");
    expect(t(hass({ locale: { language: "en-GB" } }), "status.all_clear")).toBe("All clear");
    expect(t(hass({ locale: { language: "xx" } }), "status.all_clear")).toBe("All clear");
    expect(t(undefined, "action.show_all", {})).toBe("Show all {count}");
  });
});

describe("tCount plurals", () => {
  const en = { language: "en", locale: { language: "en" } } as unknown as HomeAssistant;

  it("uses the singular key for one", () => {
    expect(tCount(en, "outages.count", 1)).toBe("1 outage");
    expect(tCount(en, "outages.customers", 1)).toBe("1 customer");
    expect(tCount(en, "outages.customers_affected", 1)).toBe("1 customer affected");
  });

  it("uses the plural key otherwise, with the formatted number", () => {
    expect(tCount(en, "outages.count", 0)).toBe("0 outages");
    expect(tCount(en, "outages.count", 2)).toBe("2 outages");
    expect(tCount(en, "outages.customers", 1240, "1,240")).toBe("1,240 customers");
  });

  it("falls back to the plain key when there is no singular key", () => {
    expect(tCount(en, "status.hazards", 1)).toBe("1 hazards nearby");
  });

  it("survives an invalid language tag", () => {
    const bad = { language: "not a tag!", locale: { language: "not a tag!" } } as unknown as HomeAssistant;
    expect(tCount(bad, "outages.count", 1)).toBe("1 outage");
    expect(tCount(bad, "outages.count", 3)).toBe("3 outages");
  });
});
