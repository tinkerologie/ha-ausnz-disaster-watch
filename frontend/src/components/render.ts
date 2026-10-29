/**
 * Shared templates built from native Home Assistant elements (`ha-icon`,
 * `ha-icon-button`, `ha-list-base` with `ha-list-item-button`/`ha-list-item-base`,
 * `ha-alert`). Colour always comes with an icon
 * and text, so meaning is never carried by colour alone.
 */
import { html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import { formatNumber } from "../ha/format";
import { t } from "../localize/localize";
import { toneColor, type Tone } from "../model/tone";
import type { HomeAssistant } from "../types";

const toneStyle = (tone: Tone) => styleMap({ "--tone": toneColor(tone) });

/** Tinted circle with an icon, like the tile card's icon. */
export function bubble(icon: string, tone: Tone, large = false): TemplateResult {
  return html`<span class="bubble ${large ? "large" : ""}" style=${toneStyle(tone)} aria-hidden="true">
    <ha-icon .icon=${icon}></ha-icon>
  </span>`;
}

/** Text badge with a tone-coloured icon. */
export function badge(label: string, tone: Tone, icon?: string): TemplateResult {
  return html`<span class="badge" style=${toneStyle(tone)}>
    ${icon ? html`<ha-icon .icon=${icon} aria-hidden="true"></ha-icon>` : nothing}<span>${label}</span>
  </span>`;
}

export function empty(icon: string, text: string): TemplateResult {
  return html`<div class="empty"><ha-icon .icon=${icon} aria-hidden="true"></ha-icon><span>${text}</span></div>`;
}

export function alert(type: "info" | "warning" | "error" | "success", text: string): TemplateResult {
  return html`<ha-alert alert-type=${type}>${text}</ha-alert>`;
}

export interface HeaderOptions {
  title: string;
  icon: string;
  count?: string;
  /** Second line under the title, e.g. the council the card is filtered to (#94). */
  subtitle?: string;
  /** Label for the details button; shown when `onDetails` is set. */
  detailsLabel?: string;
  onDetails?: () => void;
}

export function header(options: HeaderOptions): TemplateResult {
  return html`<div class="header">
    <ha-icon .icon=${options.icon} aria-hidden="true"></ha-icon>
    <div class="heading">
      <h2 class="title">${options.title}${
        options.count ? html` <span class="count">${options.count}</span>` : nothing
      }</h2>
      ${options.subtitle ? html`<span class="subtitle">${options.subtitle}</span>` : nothing}
    </div>
    ${
      options.onDetails
        ? html`<div class="actions">
            <ha-icon-button .label=${options.detailsLabel ?? ""} @click=${options.onDetails}>
              <ha-icon icon="mdi:information-outline"></ha-icon>
            </ha-icon-button>
          </div>`
        : nothing
    }
  </div>`;
}

export interface RowOptions {
  icon: string;
  tone: Tone;
  headline: string;
  supporting?: unknown;
  /** Status badge shown above the supporting text (text + icon, never colour alone). */
  badge?: TemplateResult;
  trailing?: unknown;
  /** Row opens this entity's more-info dialog. */
  onActivate?: () => void;
  /** Already validated with `safeUrl`; rendered as a separate link button. */
  link?: string;
  linkLabel?: string;
  /** Extra action buttons after the link (e.g. the incident's nearest camera, #70). */
  actions?: TemplateResult;
}

/**
 * List row. HA 2026.11 removed `ha-md-list-item`, so rows use the list items HA's own
 * cards use: `ha-list-item-button` when the row opens more-info (the whole row is the
 * hit target and the list's roving tab stop), `ha-list-item-base` otherwise. An external
 * link or extra action stays a separate `ha-icon-button` beside the item, never inside
 * it, so interactive elements never nest: the wrapper is the `listitem`, the item is
 * the row's button (or presentational).
 */
export function row(options: RowOptions): TemplateResult {
  const content = html`<span slot="start">${bubble(options.icon, options.tone)}</span>
    <span slot="headline" class="headline">${options.headline}</span>
    ${options.badge ? html`<span slot="supporting-text" class="row-badge">${options.badge}</span>` : nothing}
    ${options.supporting ? html`<span slot="supporting-text" class="supporting">${options.supporting}</span>` : nothing}
    ${options.trailing ? html`<span slot="end" class="trailing">${options.trailing}</span>` : nothing}`;
  return html`<div class="row" role="listitem">
    ${
      options.onActivate
        ? html`<ha-list-item-button class="item" role="button" @click=${options.onActivate}
            >${content}</ha-list-item-button
          >`
        : html`<ha-list-item-base class="item" role="none">${content}</ha-list-item-base>`
    }
    ${
      options.link
        ? html`<ha-icon-button
            class="link"
            .label=${options.linkLabel ?? ""}
            .href=${options.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ha-icon icon="mdi:open-in-new"></ha-icon>
          </ha-icon-button>`
        : nothing
    }
    ${options.actions ?? nothing}
  </div>`;
}

/**
 * `ha-list-base` (role `list`) gives the rows HA's list keyboard handling: one tab stop
 * for the rows, arrow keys and Home/End move between them, Enter/Space activate.
 */
export function list(rows: TemplateResult[], label?: string): TemplateResult {
  return html`<ha-list-base class="list" aria-label=${label ?? nothing}>${rows}</ha-list-base>`;
}

/** "Show all N" / "Show less" toggle for capped lists. */
export function showAll(hass: HomeAssistant, expanded: boolean, total: number, toggle: () => void): TemplateResult {
  return html`<ha-button
    class="more"
    appearance="plain"
    size="s"
    aria-expanded=${expanded ? "true" : "false"}
    @click=${toggle}
    >${expanded ? t(hass, "action.show_less") : t(hass, "action.show_all", { count: formatNumber(hass, total) })}</ha-button
  >`;
}
