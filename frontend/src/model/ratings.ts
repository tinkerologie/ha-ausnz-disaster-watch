/** Fire danger (AFDRS), air quality and road status scales. */
import type { Tone } from "./tone";

export type AfdrsRating = "moderate" | "high" | "extreme" | "catastrophic" | "no_rating";

/** The four AFDRS levels in order, as drawn on the scale. */
export const AFDRS_SCALE: Exclude<AfdrsRating, "no_rating">[] = ["moderate", "high", "extreme", "catastrophic"];

const AFDRS_TONES: Record<AfdrsRating, Tone> = {
  moderate: "green",
  high: "yellow",
  extreme: "orange",
  catastrophic: "red",
  no_rating: "grey",
};

export const AFDRS_ICONS: Record<AfdrsRating, string> = {
  moderate: "mdi:fire",
  high: "mdi:fire",
  extreme: "mdi:fire-alert",
  catastrophic: "mdi:fire-alert",
  no_rating: "mdi:fire-off",
};

/** Parse an AFDRS rating: a display name (`Extreme`, as in forecast days) or a sensor state (`extreme`, #21). */
export function parseAfdrs(value: unknown): AfdrsRating {
  if (typeof value !== "string") return "no_rating";
  const v = value.trim().toLowerCase();
  if (v.includes("catastrophic")) return "catastrophic";
  if (v.includes("extreme")) return "extreme";
  if (v.includes("high")) return "high";
  if (v.includes("moderate")) return "moderate";
  return "no_rating";
}

export function afdrsTone(rating: AfdrsRating): Tone {
  return AFDRS_TONES[rating];
}

export type AirQualityRating = "good" | "fair" | "poor" | "very_poor" | "extremely_poor" | "unknown";

const AIR_TONES: Record<AirQualityRating, Tone> = {
  good: "green",
  fair: "yellow",
  poor: "orange",
  very_poor: "red",
  extremely_poor: "purple",
  unknown: "grey",
};

export function parseAirQuality(value: unknown): AirQualityRating {
  if (typeof value !== "string") return "unknown";
  const v = value.trim().toLowerCase();
  if (v.includes("extremely") || v.includes("hazardous")) return "extremely_poor";
  if (v.includes("very poor") || v.includes("very_poor")) return "very_poor";
  if (v.includes("poor")) return "poor";
  if (v.includes("fair") || v.includes("moderate")) return "fair";
  if (v.includes("good") || v.includes("very good")) return "good";
  return "unknown";
}

export function airQualityTone(rating: AirQualityRating): Tone {
  return AIR_TONES[rating];
}

/** Road status is a free upstream string: known words map to a tone, anything else is neutral. */
export function roadStatusTone(status: unknown): Tone {
  if (typeof status !== "string") return "grey";
  const v = status.toLowerCase();
  if (v.includes("closed") || v.includes("closure")) return "red";
  if (v.includes("flood")) return "blue";
  if (v.includes("hazard") || v.includes("caution") || v.includes("restrict") || v.includes("lane")) return "amber";
  if (v.includes("open")) return "green";
  return "grey";
}

export function roadStatusIcon(status: unknown): string {
  const tone = roadStatusTone(status);
  if (tone === "red") return "mdi:road-variant";
  if (tone === "blue") return "mdi:waves";
  if (tone === "amber") return "mdi:traffic-cone";
  return "mdi:road";
}
