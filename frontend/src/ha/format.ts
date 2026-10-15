/** Locale-aware formatting through Home Assistant's own formatters where it has them. */
import type { HassEntity, HomeAssistant } from "../types";

const UNAVAILABLE = new Set(["unavailable", "unknown"]);

/** True for a missing entity or one whose state is `unavailable`/`unknown`. */
export function isUnavailable(stateObj: HassEntity | undefined): boolean {
  return !stateObj || UNAVAILABLE.has(stateObj.state);
}

export function language(hass: HomeAssistant): string {
  return hass.locale?.language || hass.language || "en";
}

/** Time zone for absolute times: HA's zone when the user profile says "server". */
export function timeZone(hass: HomeAssistant): string | undefined {
  return hass.locale?.time_zone === "server" ? hass.config?.time_zone : undefined;
}

/** Entity state with unit, as Home Assistant shows it. */
export function formatState(hass: HomeAssistant, stateObj: HassEntity): string {
  if (hass.formatEntityState) return hass.formatEntityState(stateObj);
  const unit = stateObj.attributes.unit_of_measurement;
  return unit ? `${stateObj.state} ${unit}` : stateObj.state;
}

/** Attribute value as Home Assistant formats it (numbers grouped per the user's locale). */
export function formatAttribute(hass: HomeAssistant, stateObj: HassEntity, attribute: string, value?: unknown): string {
  const raw = value === undefined ? stateObj.attributes[attribute] : value;
  if (hass.formatEntityAttributeValue) return hass.formatEntityAttributeValue(stateObj, attribute, raw);
  return typeof raw === "number" ? formatNumber(hass, raw) : String(raw ?? "");
}

export function formatNumber(hass: HomeAssistant, value: number, options?: Intl.NumberFormatOptions): string {
  try {
    return new Intl.NumberFormat(language(hass), options).format(value);
  } catch {
    return String(value);
  }
}

/** Distance in km with at most one decimal. */
export function formatDistance(hass: HomeAssistant, km: number | undefined | null): string | undefined {
  if (km === undefined || km === null || !Number.isFinite(km)) return undefined;
  return `${formatNumber(hass, km, { maximumFractionDigits: km < 10 ? 1 : 0 })} km`;
}

export function parseDate(value: unknown): Date | undefined {
  if (typeof value !== "string" && typeof value !== "number") return undefined;
  // Some upstream feeds pass .NET JSON dates through: "/Date(1792116000000)/".
  const dotNet = typeof value === "string" ? /^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/.exec(value.trim()) : null;
  if (dotNet) return new Date(Number(dotNet[1]));
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
  ["second", 1],
];

/** "5 minutes ago" in the user's language; undefined for unparsable input. */
export function relativeTime(hass: HomeAssistant, value: unknown, now: number = Date.now()): string | undefined {
  const date = parseDate(value);
  if (!date) return undefined;
  const seconds = Math.round((date.getTime() - now) / 1000);
  const format = new Intl.RelativeTimeFormat(language(hass), { numeric: "auto" });
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size || unit === "second") {
      return format.format(Math.round(seconds / size), unit);
    }
  }
  return undefined;
}

/** Absolute date and time in the user's language and time zone preference. */
export function formatDateTime(
  hass: HomeAssistant,
  value: unknown,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" },
): string | undefined {
  const date = parseDate(value);
  if (!date) return undefined;
  try {
    return new Intl.DateTimeFormat(language(hass), { ...options, timeZone: timeZone(hass) }).format(date);
  } catch {
    return date.toISOString();
  }
}

/**
 * Only absolute http(s) URLs from upstream feeds may become links (#26): anything else,
 * including `javascript:` and `data:` URLs, renders as plain text.
 */
export function safeUrl(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return undefined;
  }
  return url.protocol === "http:" || url.protocol === "https:" ? url.href : undefined;
}

/** Number from an attribute, keeping 0 (never treated as missing). */
export function numberAttr(value: unknown): number | undefined {
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

export function stringAttr(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function listAttr<T = Record<string, unknown>>(value: unknown): T[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as T[]) : [];
}
