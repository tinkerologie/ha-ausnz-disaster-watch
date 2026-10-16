/**
 * Colour roles. Official scales (Australian Warning System, AFDRS) keep their published
 * colours through HA's palette variables; everything else uses neutral tokens. Colour is
 * never the only signal: every tone is shown with an icon and a text label.
 */
export type Tone = "red" | "orange" | "amber" | "yellow" | "green" | "blue" | "purple" | "grey";

/** CSS colour for a tone, from HA's theme palette (`--red-color`, …). */
export function toneColor(tone: Tone): string {
  return `var(--${tone}-color)`;
}
