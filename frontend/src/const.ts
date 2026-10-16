/** Integration domain; also the platform of every registry entry the cards read. */
export const DOMAIN = "ausnz_disaster_watch";

export const DOCUMENTATION_URL = "https://github.com/tinkerologie/ha-ausnz-disaster-watch#dashboard-cards";

/** Entity translation keys (`_attr_translation_key`) used to resolve entities through the registry. */
export const KEY = {
  emergencyWarningNearby: "emergency_warning_nearby",
  activeHazardsNearby: "active_hazards_nearby",
  powerOutageActive: "power_outage_active",
  roadClosureNearby: "road_closure_nearby",
  nearestHazardDistance: "nearest_hazard_distance",
  activeHazardsCount: "active_hazards_count",
  highestWarningLevel: "highest_warning_level",
  nearestHazardTitle: "nearest_hazard_title",
  powerOutagesCount: "power_outages_count",
  powerOutagesCustomersAffected: "power_outages_customers_affected",
  roadClosuresCount: "road_closures_count",
  weatherWarningsCount: "weather_warnings_count",
  fireDangerRating: "fire_danger_rating",
  airQualityRating: "air_quality_rating",
  primaryWeatherObservation: "primary_weather_observation",
  reliefFacilitiesCount: "relief_facilities_count",
} as const;

export type EntityKey = (typeof KEY)[keyof typeof KEY];

/** Focused cards, in the order they appear in the card picker. */
export const CARD_TAGS = {
  status: "ausnz-disaster-status-card",
  incidents: "ausnz-disaster-incidents-card",
  warnings: "ausnz-disaster-warnings-card",
  fire_danger: "ausnz-disaster-fire-danger-card",
  outages: "ausnz-disaster-outages-card",
  roads: "ausnz-disaster-roads-card",
  conditions: "ausnz-disaster-conditions-card",
  relief: "ausnz-disaster-relief-card",
  cameras: "ausnz-disaster-cameras-card",
  map: "ausnz-disaster-map-card",
} as const;

export type SectionKey = keyof typeof CARD_TAGS;

export const ALL_IN_ONE_TAG = "ausnz-disaster-card";

/** Sections the all-in-one card shows when `cards` is not configured. */
export const DEFAULT_SECTIONS: SectionKey[] = ["status", "incidents", "warnings", "fire_danger", "roads", "outages"];

export const SECTION_KEYS = Object.keys(CARD_TAGS) as SectionKey[];
