import { describe, expect, it } from "vitest";
import {
  cameraIdsFor,
  deviceName,
  entityIdFor,
  entryIdForDevice,
  geoLocationsFor,
  incidentDistance,
  incidentTitle,
  integrationDevices,
  isIntegrationDevice,
  resolveDevice,
  stateFor,
} from "../../src/ha/entities";
import type { HassEntity, HomeAssistant } from "../../src/types";

const st = (entity_id: string, state: string, attributes: Record<string, unknown> = {}): HassEntity => ({
  entity_id,
  state,
  attributes,
  last_changed: "",
  last_updated: "",
});

function makeHass(): HomeAssistant {
  const states: Record<string, HassEntity> = {};
  const add = (s: HassEntity) => (states[s.entity_id] = s);
  add(st("sensor.home_level", "Watch and Act"));
  add(st("sensor.beach_level", "Advice"));
  // Another integration's look-alike must never be picked up (#26).
  add(st("sensor.other_highest_warning_level", "Emergency Warning"));
  add(st("camera.home_b", "idle", { friendly_name: "B cam" }));
  add(st("camera.home_a", "idle", { friendly_name: "A cam" }));
  add(st("geo_location.near", "4.2", { integration: "ausnz_disaster_watch", entry_id: "entry-a", title: "Near fire" }));
  add(st("geo_location.far", "40", { integration: "ausnz_disaster_watch", entry_id: "entry-a", title: "Far flood" }));
  add(st("geo_location.no_state", "unknown", { integration: "ausnz_disaster_watch", entry_id: "entry-a", distance_km: 12 }));
  add(st("geo_location.beach", "1", { integration: "ausnz_disaster_watch", entry_id: "entry-b", title: "Beach" }));
  add(st("geo_location.usgs", "2", { integration: "usgs", entry_id: "entry-a", title: "Quake" }));
  return {
    states,
    entities: {
      "sensor.home_level": {
        entity_id: "sensor.home_level",
        device_id: "dev-a",
        platform: "ausnz_disaster_watch",
        translation_key: "highest_warning_level",
      },
      "sensor.beach_level": {
        entity_id: "sensor.beach_level",
        device_id: "dev-b",
        platform: "ausnz_disaster_watch",
        translation_key: "highest_warning_level",
      },
      "sensor.other_highest_warning_level": {
        entity_id: "sensor.other_highest_warning_level",
        device_id: "dev-x",
        platform: "other",
        translation_key: "highest_warning_level",
      },
      "camera.home_b": { entity_id: "camera.home_b", device_id: "dev-a", platform: "ausnz_disaster_watch" },
      "camera.home_a": { entity_id: "camera.home_a", device_id: "dev-a", platform: "ausnz_disaster_watch" },
    },
    devices: {
      "dev-x": { id: "dev-x", config_entries: ["entry-x"] },
      "dev-b": { id: "dev-b", name: "Beach", config_entries: ["entry-b"] },
      "dev-a": {
        id: "dev-a",
        name: "Home",
        name_by_user: "My home",
        config_entries: ["entry-other", "entry-a"],
        identifiers: [["ausnz_disaster_watch", "entry-a"]],
      },
    },
    locale: { language: "en" },
    config: { latitude: 0, longitude: 0, time_zone: "UTC" },
    connection: { sendMessagePromise: async () => ({}) },
  } as HomeAssistant;
}

describe("registry resolution", () => {
  it("lists integration devices in hass.devices order", () => {
    const hass = makeHass();
    expect(integrationDevices(hass)).toEqual(["dev-b", "dev-a"]);
    expect(isIntegrationDevice(hass, "dev-a")).toBe(true);
    expect(isIntegrationDevice(hass, "dev-x")).toBe(false);
    expect(isIntegrationDevice(hass, undefined)).toBe(false);
  });

  it("defaults to the first device and keeps an explicit one", () => {
    const hass = makeHass();
    expect(resolveDevice(hass)).toBe("dev-b");
    expect(resolveDevice(hass, "dev-a")).toBe("dev-a");
  });

  it("resolves entities by translation key per device", () => {
    const hass = makeHass();
    expect(entityIdFor(hass, "dev-a", "highest_warning_level")).toBe("sensor.home_level");
    expect(entityIdFor(hass, "dev-b", "highest_warning_level")).toBe("sensor.beach_level");
    expect(entityIdFor(hass, "dev-x", "highest_warning_level")).toBeUndefined();
    expect(entityIdFor(hass, undefined, "highest_warning_level")).toBeUndefined();
    expect(entityIdFor(hass, "dev-a", "fire_danger_rating")).toBeUndefined();
    expect(stateFor(hass, "dev-a", "highest_warning_level")?.state).toBe("Watch and Act");
    expect(stateFor(hass, "dev-a", "fire_danger_rating")).toBeUndefined();
  });

  it("maps devices to config entries", () => {
    const hass = makeHass();
    expect(entryIdForDevice(hass, "dev-a")).toBe("entry-a");
    expect(entryIdForDevice(hass, "dev-b")).toBe("entry-b");
    expect(entryIdForDevice(hass, "missing")).toBeUndefined();
    expect(entryIdForDevice(hass, undefined)).toBeUndefined();
    expect(deviceName(hass, "dev-a")).toBe("My home");
    expect(deviceName(hass, "dev-b")).toBe("Beach");
    expect(deviceName(hass, undefined)).toBeUndefined();
  });

  it("lists the device's cameras sorted by name", () => {
    const hass = makeHass();
    expect(cameraIdsFor(hass, "dev-a")).toEqual(["camera.home_a", "camera.home_b"]);
    expect(cameraIdsFor(hass, "dev-b")).toEqual([]);
    expect(cameraIdsFor(hass, undefined)).toEqual([]);
  });

  it("isolates geolocation incidents per entry, nearest first (#26)", () => {
    const hass = makeHass();
    expect(geoLocationsFor(hass, "entry-a").map((s) => s.entity_id)).toEqual([
      "geo_location.near",
      "geo_location.no_state",
      "geo_location.far",
    ]);
    expect(geoLocationsFor(hass, "entry-b").map((s) => s.entity_id)).toEqual(["geo_location.beach"]);
    expect(geoLocationsFor(hass, undefined)).toEqual([]);
    // Memoised per states object.
    expect(geoLocationsFor(hass, "entry-a")).toBe(geoLocationsFor(hass, "entry-a"));
  });

  it("reads incident titles from attributes, never the distance state (#26)", () => {
    expect(incidentTitle(st("geo_location.a", "17.6", { title: "Smoke alert" }))).toBe("Smoke alert");
    expect(incidentTitle(st("geo_location.a", "17.6", { friendly_name: "Friendly" }))).toBe("Friendly");
    expect(incidentTitle(st("geo_location.a", "17.6"))).toBe("geo_location.a");
    expect(incidentDistance(st("geo_location.a", "17.6"))).toBe(17.6);
    expect(incidentDistance(st("geo_location.a", "unknown", { distance_km: 3 }))).toBe(3);
    expect(incidentDistance(st("geo_location.a", "unknown"))).toBeUndefined();
  });
});
