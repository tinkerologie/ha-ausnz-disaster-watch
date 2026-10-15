/** Power outage figures. */
import { isUnavailable, numberAttr } from "../ha/format";
import type { HassEntity } from "../types";

/**
 * Customers affected: the dedicated sensor first, the count sensor's attribute as a
 * fallback, and `undefined` (never 0) when neither has a value (#26).
 */
export function customersAffected(customersState: HassEntity | undefined, fallback: unknown): number | undefined {
  const fromSensor = isUnavailable(customersState) ? undefined : numberAttr(customersState?.state);
  return fromSensor ?? numberAttr(fallback);
}
