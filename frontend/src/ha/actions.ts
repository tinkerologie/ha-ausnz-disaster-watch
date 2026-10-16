/** Home Assistant interaction conventions: more-info dialogs and in-app navigation. */

export function fireEvent(node: EventTarget, type: string, detail: unknown): void {
  node.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
}

/** Open the entity's more-info dialog. */
export function openMoreInfo(node: EventTarget, entityId: string | undefined): void {
  if (entityId) fireEvent(node, "hass-more-info", { entityId });
}

/** Navigate inside the HA app without a page reload (history + `location-changed`). */
export function navigate(path: string): void {
  history.pushState(null, "", path);
  fireEvent(window, "location-changed", { replace: false });
}
