import { describe, expect, it } from "vitest";
import { awsPresentation, headlinePresentation, headlineStatus, parseAwsLevel } from "../../src/model/aws";
import { hazardCategory, hazardIcon } from "../../src/model/hazards";
import { customersAffected } from "../../src/model/outages";
import {
  AFDRS_SCALE,
  afdrsTone,
  airQualityTone,
  parseAfdrs,
  parseAirQuality,
  roadStatusTone,
} from "../../src/model/ratings";
import { toneColor } from "../../src/model/tone";
import type { HassEntity } from "../../src/types";

describe("Australian Warning System", () => {
  it.each([
    ["Emergency Warning", "emergency", "red"],
    ["Watch and Act", "watch_and_act", "orange"],
    ["Watch & Act", "watch_and_act", "orange"],
    ["Advice", "advice", "amber"],
    ["Information", "information", "blue"],
    ["Unknown", "unknown", "grey"],
    [undefined, "unknown", "grey"],
  ])("%s -> %s", (value, level, tone) => {
    expect(parseAwsLevel(value)).toBe(level);
    expect(awsPresentation(value).tone).toBe(tone);
  });

  it("only says all clear when the sensor says so and no hazards are counted (#26)", () => {
    expect(headlineStatus("All Clear", 0)).toBe("all_clear");
    expect(headlineStatus("All Clear", 3)).toBe("unknown");
    expect(headlineStatus("All Clear", undefined)).toBe("unknown");
    expect(headlineStatus("unavailable", 0)).toBe("unavailable");
    expect(headlineStatus("unknown", 0)).toBe("unavailable");
    expect(headlineStatus(undefined, 0)).toBe("unavailable");
    expect(headlineStatus("Information", 2)).toBe("information");
    expect(headlineStatus("Unknown", 2)).toBe("unknown");
    expect(headlinePresentation("all_clear").tone).toBe("green");
    expect(headlinePresentation("unavailable").tone).toBe("grey");
    expect(headlinePresentation("emergency").tone).toBe("red");
  });
});

describe("hazard categories", () => {
  it.each([
    ["Bushfire", "fire"],
    ["Grass Fire", "fire"],
    ["Structure Fire", "fire"],
    ["Flood", "flood_storm"],
    ["Severe Storm", "flood_storm"],
    ["Tropical Cyclone", "flood_storm"],
    ["Earthquake", "geological"],
    ["Volcano", "geological"],
    ["Tsunami", "geological"],
    ["Road Hazard / Crash", "roads"],
    ["Hazmat Incident", "other"],
    ["Other", "other"],
    ["Something new", "other"],
    [undefined, "other"],
  ])("%s -> %s", (type, category) => {
    expect(hazardCategory(type)).toBe(category);
  });

  it("maps icons with a fallback", () => {
    expect(hazardIcon("Volcano")).toBe("mdi:volcano");
    expect(hazardIcon("nope")).toBe("mdi:alert-decagram");
  });
});

describe("ratings", () => {
  it("parses AFDRS ratings, including no rating", () => {
    expect(AFDRS_SCALE).toEqual(["moderate", "high", "extreme", "catastrophic"]);
    expect(parseAfdrs("Moderate")).toBe("moderate");
    expect(parseAfdrs("HIGH")).toBe("high");
    expect(parseAfdrs("Extreme")).toBe("extreme");
    expect(parseAfdrs("Catastrophic")).toBe("catastrophic");
    expect(parseAfdrs("No Rating")).toBe("no_rating");
    expect(parseAfdrs(undefined)).toBe("no_rating");
    expect(afdrsTone("moderate")).toBe("green");
    expect(afdrsTone("catastrophic")).toBe("red");
    // A missing rating is never shown as the green Moderate (#26).
    expect(afdrsTone("no_rating")).toBe("grey");
  });

  it("maps air quality per value with a neutral fallback", () => {
    expect(parseAirQuality("Good")).toBe("good");
    expect(parseAirQuality("Fair")).toBe("fair");
    expect(parseAirQuality("Poor")).toBe("poor");
    expect(parseAirQuality("Very Poor")).toBe("very_poor");
    expect(parseAirQuality("Extremely poor")).toBe("extremely_poor");
    expect(parseAirQuality("Hazardous")).toBe("extremely_poor");
    expect(parseAirQuality("n/a")).toBe("unknown");
    expect(parseAirQuality(4)).toBe("unknown");
    expect(airQualityTone("good")).toBe("green");
    expect(airQualityTone("unknown")).toBe("grey");
  });

  it("maps free-text road statuses", () => {
    expect(roadStatusTone("Closed")).toBe("red");
    expect(roadStatusTone("Flooded")).toBe("blue");
    expect(roadStatusTone("Hazard")).toBe("amber");
    expect(roadStatusTone("Open")).toBe("green");
    expect(roadStatusTone("Published")).toBe("grey");
    expect(roadStatusTone(undefined)).toBe("grey");
  });

  it("uses HA palette variables only", () => {
    expect(toneColor("red")).toBe("var(--red-color)");
  });
});

describe("Power outages customers affected (#26)", () => {
  const sensor = (state: string): HassEntity => ({
    entity_id: "sensor.x_customers_affected",
    state,
    attributes: {},
    last_changed: "",
    last_updated: "",
  });

  it("reads the dedicated sensor first", () => {
    expect(customersAffected(sensor("120"), 7)).toBe(120);
    expect(customersAffected(sensor("0"), 7)).toBe(0);
  });

  it.each([
    ["missing", undefined],
    ["unavailable", sensor("unavailable")],
    ["unknown", sensor("unknown")],
    ["non-numeric", sensor("n/a")],
  ])("falls back to the count attribute when the sensor is %s", (_label, state) => {
    expect(customersAffected(state, 7)).toBe(7);
    expect(customersAffected(state, "42")).toBe(42);
  });

  it("returns undefined, never 0, when both are missing", () => {
    expect(customersAffected(undefined, undefined)).toBeUndefined();
    expect(customersAffected(sensor("unavailable"), null)).toBeUndefined();
  });
});
