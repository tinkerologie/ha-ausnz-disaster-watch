/** Australian Warning System levels (models.WarningLevel) and their presentation. */
import type { Tone } from "./tone";

export type AwsLevel = "emergency" | "watch_and_act" | "advice" | "information" | "unknown";

export interface AwsPresentation {
  level: AwsLevel;
  tone: Tone;
  icon: string;
  rank: number;
}

const LEVELS: Record<AwsLevel, AwsPresentation> = {
  emergency: { level: "emergency", tone: "red", icon: "mdi:alert-octagon", rank: 4 },
  watch_and_act: { level: "watch_and_act", tone: "orange", icon: "mdi:alert", rank: 3 },
  advice: { level: "advice", tone: "amber", icon: "mdi:information", rank: 2 },
  information: { level: "information", tone: "blue", icon: "mdi:information-outline", rank: 1 },
  unknown: { level: "unknown", tone: "grey", icon: "mdi:help-circle-outline", rank: 0 },
};

/**
 * Parse a warning level the way the backend does (`WarningLevel.from_str`): a display name
 * (`Watch and Act`, as in hazard attributes) or a sensor state (`watch_and_act`, #21).
 */
export function parseAwsLevel(value: unknown): AwsLevel {
  if (typeof value !== "string") return "unknown";
  const v = value.trim().toLowerCase().replace(/_/g, " ");
  if (v.includes("emergency")) return "emergency";
  if (v.includes("watch and act") || v.includes("watch & act")) return "watch_and_act";
  if (v.includes("advice")) return "advice";
  if (v.includes("info") || v.includes("routine") || v.includes("notification")) return "information";
  return "unknown";
}

export function awsPresentation(value: unknown): AwsPresentation {
  return LEVELS[parseAwsLevel(value)];
}

/**
 * Headline status from the `highest_warning_level` sensor and the hazard count.
 * "All clear" is shown only when the sensor explicitly says so (`all_clear`) and no hazards
 * are counted; missing or unavailable data is never presented as all clear (#26). An
 * `unknown` sensor with hazards counted means hazards of unknown level, not missing data.
 */
export type HeadlineStatus = AwsLevel | "all_clear" | "unavailable";

export function headlineStatus(levelState: string | undefined, hazardCount: number | undefined): HeadlineStatus {
  if (levelState === "unknown" && hazardCount !== undefined && hazardCount > 0) return "unknown";
  if (levelState === undefined || levelState === "unavailable" || levelState === "unknown") return "unavailable";
  if (levelState.trim().toLowerCase().replace(/_/g, " ") === "all clear") {
    return hazardCount === undefined || hazardCount > 0 ? "unknown" : "all_clear";
  }
  return parseAwsLevel(levelState);
}

export function headlinePresentation(status: HeadlineStatus): AwsPresentation {
  if (status === "all_clear") return { level: "unknown", tone: "green", icon: "mdi:shield-check", rank: 0 };
  if (status === "unavailable") return { level: "unknown", tone: "grey", icon: "mdi:cloud-off-outline", rank: -1 };
  return LEVELS[status];
}
