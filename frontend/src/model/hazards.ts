/** Hazard types (models.HazardType) grouped into the incident filter categories. */

export type HazardCategory = "fire" | "flood_storm" | "geological" | "roads" | "other";

export const HAZARD_CATEGORIES: HazardCategory[] = ["fire", "flood_storm", "geological", "roads", "other"];

const TYPES: Record<string, { category: HazardCategory; icon: string }> = {
  Bushfire: { category: "fire", icon: "mdi:fire" },
  "Grass Fire": { category: "fire", icon: "mdi:grass" },
  "Structure Fire": { category: "fire", icon: "mdi:fire-alert" },
  Flood: { category: "flood_storm", icon: "mdi:water-alert" },
  "Severe Storm": { category: "flood_storm", icon: "mdi:weather-lightning" },
  "Tropical Cyclone": { category: "flood_storm", icon: "mdi:weather-hurricane" },
  Earthquake: { category: "geological", icon: "mdi:pulse" },
  Volcano: { category: "geological", icon: "mdi:volcano" },
  Tsunami: { category: "geological", icon: "mdi:tsunami" },
  "Road Hazard / Crash": { category: "roads", icon: "mdi:car-emergency" },
  "Hazmat Incident": { category: "other", icon: "mdi:biohazard" },
  Other: { category: "other", icon: "mdi:alert-decagram" },
};

export const CATEGORY_ICONS: Record<HazardCategory, string> = {
  fire: "mdi:fire",
  flood_storm: "mdi:weather-pouring",
  geological: "mdi:earth",
  roads: "mdi:car-emergency",
  other: "mdi:alert-decagram",
};

export function hazardCategory(hazardType: unknown): HazardCategory {
  return (typeof hazardType === "string" && TYPES[hazardType]?.category) || "other";
}

export function hazardIcon(hazardType: unknown): string {
  return (typeof hazardType === "string" && TYPES[hazardType]?.icon) || "mdi:alert-decagram";
}
