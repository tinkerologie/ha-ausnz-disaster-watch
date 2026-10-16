/**
 * Shared templates built from native Home Assistant elements (`ha-icon`,
 * `ha-icon-button`, `ha-md-list-item`, `ha-alert`). Colour always comes with an icon
 * and text, so meaning is never carried by colour alone.
 */
import { html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
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
 * List row: an `ha-md-list-item` (a button when it has an action) plus an optional
 * external link as its own `ha-icon-button`, so interactive elements never nest.
 */
export function row(options: RowOptions): TemplateResult {
  return html`<div class="row" role="listitem">
    <ha-md-list-item
      type=${options.onActivate ? "button" : "text"}
      @click=${options.onActivate ?? nothing}
    >
      <span slot="start">${bubble(options.icon, options.tone)}</span>
      <span slot="headline" class="headline">${options.headline}</span>
      ${options.badge ? html`<span slot="supporting-text" class="row-badge">${options.badge}</span>` : nothing}
      ${options.supporting ? html`<span slot="supporting-text" class="supporting">${options.supporting}</span>` : nothing}
      ${options.trailing ? html`<span slot="end" class="trailing">${options.trailing}</span>` : nothing}
    </ha-md-list-item>
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

export function list(rows: TemplateResult[], label?: string): TemplateResult {
  return html`<div class="list" role="list" aria-label=${label ?? nothing}>${rows}</div>`;
}

/** "Show all N" / "Show less" toggle for capped lists. */
export function showAll(hass: HomeAssistant, expanded: boolean, total: number, toggle: () => void): TemplateResult {
  return html`<ha-button
    class="more"
    appearance="plain"
    size="s"
    aria-expanded=${expanded ? "true" : "false"}
    @click=${toggle}
    >${expanded ? t(hass, "action.show_less") : t(hass, "action.show_all", { count: total })}</ha-button
  >`;
}
