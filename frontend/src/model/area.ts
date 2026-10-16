/**
 * Council-area filtering (#94). The integration tags every located list item with
 * `in_council_area` (true/false; null without a location) and publishes the council it
 * resolved as the `council_area` attribute of the highest warning level sensor.
 */
import { stringAttr } from "../ha/format";
import { awsPresentation } from "./aws";

export const AREA_MODES = ["council", "radius"] as const;
export type AreaMode = (typeof AREA_MODES)[number];

export interface CouncilArea {
  name: string;
  code?: string;
}

/** The council the entry's point is in, or undefined while it is unknown. */
export function councilArea(value: unknown): CouncilArea | undefined {
  if (!value || typeof value !== "object") return undefined;
  const item = value as { name?: unknown; code?: unknown };
  const name = stringAttr(item.name);
  return name ? { name, code: stringAttr(item.code) } : undefined;
}

export interface AreaFilter {
  /** The council being filtered by; undefined when showing the whole radius. */
  council?: CouncilArea;
  /** `council` was asked for but the boundary is unknown, so the radius is shown. */
  fallback: boolean;
  /** Whether an item with this `in_council_area` value is shown. */
  keep: (inCouncilArea: unknown) => boolean;
}

/**
 * Filter for a card's `area` mode. Only items known to be outside the council are hidden:
 * unlocated items (`null`) and items from an older integration (no flag) stay.
 */
export function areaFilter(mode: AreaMode, council: CouncilArea | undefined): AreaFilter {
  if (mode !== "council") return { fallback: false, keep: () => true };
  if (!council) return { fallback: true, keep: () => true };
  return { council, fallback: false, keep: (flag) => flag !== false };
}

export interface IncidentSummary {
  /** Warning level as a state: the highest incident's level, `unknown`, or `all_clear`. */
  level: string;
  count: number;
  nearestKm?: number;
  nearestTitle?: string;
}

/** Headline of a set of incidents (the status card filtered to the council). */
export function summariseIncidents(
  incidents: readonly { level: unknown; distanceKm?: number; title: string }[],
): IncidentSummary {
  const first = incidents[0];
  if (!first) return { level: "all_clear", count: 0 };
  let highest = first;
  let nearest: (typeof incidents)[number] | undefined;
  for (const incident of incidents) {
    if (awsPresentation(incident.level).rank > awsPresentation(highest.level).rank) highest = incident;
    if (incident.distanceKm !== undefined && (nearest?.distanceKm === undefined || incident.distanceKm < nearest.distanceKm)) {
      nearest = incident;
    }
  }
  return {
    level: awsPresentation(highest.level).rank > 0 ? String(highest.level) : "unknown",
    count: incidents.length,
    nearestKm: nearest?.distanceKm,
    nearestTitle: nearest?.title,
  };
}
