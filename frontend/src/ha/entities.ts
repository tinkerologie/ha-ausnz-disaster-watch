/**
 * Entity resolution through the entity and device registries (#26, #43).
 *
 * Cards never match entity IDs by suffix: entities are found by integration platform,
 * device and translation key, so renamed entities and other integrations' look-alikes
 * cannot leak in. Each card is scoped to one device, which is one config entry.
 */
import { DOMAIN, type EntityKey } from "../const";
import type { HassEntity, HomeAssistant } from "../types";

interface RegistryIndex {
  /** Integration devices, in `hass.devices` order. */
  devices: string[];
  /** device_id -> translation_key -> entity_id */
  byKey: Map<string, Map<string, string>>;
  /** device_id -> camera entity_ids */
  cameras: Map<string, string[]>;
}

const registryCache = new WeakMap<object, RegistryIndex>();

function registryIndex(hass: HomeAssistant): RegistryIndex {
  const cacheKey = hass.entities;
  const cached = registryCache.get(cacheKey);
  if (cached) return cached;

  const byKey = new Map<string, Map<string, string>>();
  const cameras = new Map<string, string[]>();
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform !== DOMAIN || !entry.device_id) continue;
    if (entry.translation_key) {
      let keys = byKey.get(entry.device_id);
      if (!keys) byKey.set(entry.device_id, (keys = new Map()));
      keys.set(entry.translation_key, entry.entity_id);
    }
    if (entry.entity_id.startsWith("camera.")) {
      const list = cameras.get(entry.device_id) ?? [];
      list.push(entry.entity_id);
      cameras.set(entry.device_id, list);
    }
  }
  const owners = new Set([...byKey.keys(), ...cameras.keys()]);
  const ordered = Object.keys(hass.devices ?? {}).filter((id) => owners.has(id));
  // Devices missing from hass.devices (should not happen) still count, after the rest.
  for (const id of owners) if (!ordered.includes(id)) ordered.push(id);

  const index = { devices: ordered, byKey, cameras };
  registryCache.set(cacheKey, index);
  return index;
}

/** Devices that belong to this integration (one per config entry). */
export function integrationDevices(hass: HomeAssistant): string[] {
  return registryIndex(hass).devices;
}

/** The configured device, or the first integration device when none is configured. */
export function resolveDevice(hass: HomeAssistant, configured?: string): string | undefined {
  if (configured) return configured;
  return integrationDevices(hass)[0];
}

export function isIntegrationDevice(hass: HomeAssistant, deviceId: string | undefined): boolean {
  return !!deviceId && integrationDevices(hass).includes(deviceId);
}

/** Config entry ID behind a device: the `(ausnz_disaster_watch, entry_id)` identifier, else its entry list. */
export function entryIdForDevice(hass: HomeAssistant, deviceId: string | undefined): string | undefined {
  if (!deviceId) return undefined;
  const device = hass.devices?.[deviceId];
  if (!device) return undefined;
  const identifier = device.identifiers?.find(([domain]) => domain === DOMAIN);
  if (identifier) return identifier[1];
  return device.config_entries?.[0];
}

export function deviceName(hass: HomeAssistant, deviceId: string | undefined): string | undefined {
  if (!deviceId) return undefined;
  const device = hass.devices?.[deviceId];
  return device?.name_by_user || device?.name || undefined;
}

/** Entity ID of the device's entity with this translation key. */
export function entityIdFor(hass: HomeAssistant, deviceId: string | undefined, key: EntityKey): string | undefined {
  if (!deviceId) return undefined;
  return registryIndex(hass).byKey.get(deviceId)?.get(key);
}

/** State object of the device's entity with this translation key. */
export function stateFor(hass: HomeAssistant, deviceId: string | undefined, key: EntityKey): HassEntity | undefined {
  const id = entityIdFor(hass, deviceId, key);
  return id ? hass.states[id] : undefined;
}

/** Camera entities of the device, sorted by name. */
export function cameraIdsFor(hass: HomeAssistant, deviceId: string | undefined): string[] {
  if (!deviceId) return [];
  const ids = registryIndex(hass).cameras.get(deviceId) ?? [];
  return [...ids].sort((a, b) => {
    const nameA = String(hass.states[a]?.attributes.friendly_name ?? a);
    const nameB = String(hass.states[b]?.attributes.friendly_name ?? b);
    return nameA.localeCompare(nameB);
  });
}

const geoCache = new WeakMap<object, Map<string, HassEntity[]>>();

/**
 * Geolocation events of one config entry, nearest first. These entities have no unique
 * ID and are not in the registry, so they are matched by their `integration` and
 * `entry_id` attributes.
 */
export function geoLocationsFor(hass: HomeAssistant, entryId: string | undefined): HassEntity[] {
  if (!entryId) return [];
  let perEntry = geoCache.get(hass.states);
  if (!perEntry) geoCache.set(hass.states, (perEntry = new Map()));
  const cached = perEntry.get(entryId);
  if (cached) return cached;

  const list = Object.values(hass.states)
    .filter(
      (s) =>
        s.entity_id.startsWith("geo_location.") &&
        s.attributes.integration === DOMAIN &&
        s.attributes.entry_id === entryId,
    )
    .sort((a, b) => (incidentDistance(a) ?? Infinity) - (incidentDistance(b) ?? Infinity));
  perEntry.set(entryId, list);
  return list;
}

/** Incident headline: the `title` attribute, never the state (which is the distance). */
export function incidentTitle(stateObj: HassEntity): string {
  const title = stateObj.attributes.title ?? stateObj.attributes.friendly_name;
  return typeof title === "string" && title ? title : stateObj.entity_id;
}

/** Incident distance in km from the numeric state, else the `distance_km` attribute. */
export function incidentDistance(stateObj: HassEntity): number | undefined {
  const fromState = Number.parseFloat(stateObj.state);
  if (Number.isFinite(fromState)) return fromState;
  const attr = stateObj.attributes.distance_km;
  return typeof attr === "number" && Number.isFinite(attr) ? attr : undefined;
}
