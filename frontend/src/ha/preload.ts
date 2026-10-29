/**
 * Native Home Assistant elements the cards render.
 *
 * Verified against HA 2026.10 (frontend 20260930.4) and 2026.11 (frontend 20261028.0):
 * every tag here is defined on a dashboard (sections and masonry views) before any
 * custom card loads. The list elements come with the sidebar (`ha-list-nav` extends
 * `ha-list-base`); they replace `ha-md-list`/`ha-md-list-item`, which 2026.11 removed
 * (home-assistant/frontend#54569). `loadCardHelpers()` is still awaited once, as the
 * custom card docs recommend, so a card rendered outside a dashboard (card picker,
 * editor preview) gets the same set.
 */
export const HA_ELEMENTS = [
  "ha-card",
  "ha-icon",
  "ha-icon-button",
  "ha-button",
  "ha-alert",
  "ha-assist-chip",
  "ha-filter-chip",
  "ha-chip-set",
  "ha-list-base",
  "ha-list-item-base",
  "ha-list-item-button",
  "ha-tooltip",
] as const;

let preload: Promise<void> | undefined;

export function preloadHaElements(timeoutMs = 5000): Promise<void> {
  preload ??= (async () => {
    try {
      await window.loadCardHelpers?.();
    } catch {
      // Not on a dashboard; elements upgrade whenever HA defines them.
    }
    await Promise.race([
      Promise.all(HA_ELEMENTS.map((tag) => customElements.whenDefined(tag))),
      new Promise((resolve) => setTimeout(resolve, timeoutMs)),
    ]);
  })();
  return preload;
}
