import { css, html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import { KEY, type EntityKey } from "../const";
import { stateFor } from "../ha/entities";
import { formatDistance, isUnavailable, numberAttr, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { headlinePresentation, headlineStatus, type HeadlineStatus } from "../model/aws";
import { toneColor } from "../model/tone";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import { baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

const ALERT_KEYS = [
  { key: KEY.emergencyWarningNearby, icon: "mdi:alert-octagon", label: "status.chip.emergency_warning_nearby" },
  { key: KEY.activeHazardsNearby, icon: "mdi:alert", label: "status.chip.active_hazards_nearby" },
  { key: KEY.powerOutageActive, icon: "mdi:transmission-tower-off", label: "status.chip.power_outage_active" },
  { key: KEY.roadClosureNearby, icon: "mdi:traffic-cone", label: "status.chip.road_closure_nearby" },
] as const satisfies readonly { key: EntityKey; icon: string; label: TranslationKey }[];

const STATUS_LABELS: Record<HeadlineStatus, TranslationKey> = {
  all_clear: "status.all_clear",
  unavailable: "status.unavailable",
  emergency: "status.level.emergency",
  watch_and_act: "status.level.watch_and_act",
  advice: "status.level.advice",
  information: "status.level.information",
  unknown: "status.level.unknown",
};

/** Headline: Australian Warning System level, hazard count, nearest hazard and active alerts. */
export class StatusCard extends DisasterCard {
  static override styles = [
    ...DisasterCard.styles,
    css`
      .hero {
        display: flex;
        align-items: center;
        gap: var(--ha-space-4);
        padding: var(--ha-space-2);
        margin: calc(-1 * var(--ha-space-2));
        width: calc(100% + 2 * var(--ha-space-2));
      }
      .hero:hover {
        background-color: var(--ha-color-fill-neutral-quiet-hover);
      }
      .hero-text {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1);
        min-width: 0;
      }
      .level {
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-bold);
        line-height: var(--ha-line-height-condensed);
      }
      .summary {
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-m);
        line-height: var(--ha-line-height-normal);
      }
      .nearest {
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }
      .content.status {
        padding-top: var(--ha-space-4);
      }
    `,
  ];

  protected readonly titleKey = "card.status.name" as const;

  protected override entityKeys() {
    return [
      KEY.highestWarningLevel,
      KEY.activeHazardsCount,
      KEY.nearestHazardDistance,
      KEY.nearestHazardTitle,
      ...ALERT_KEYS.map((a) => a.key),
    ];
  }

  static getConfigForm(): LovelaceConfigForm {
    return { schema: baseSchema(), computeLabel, computeHelper, assertConfig: (c) => this.validateConfig(c) };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getGridOptions(): LovelaceGridOptions {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  override getCardSize(): number {
    return 2;
  }

  protected renderBody(hass: HomeAssistant, _config: BaseCardConfig): TemplateResult {
    const device = this.deviceId;
    const levelState = stateFor(hass, device, KEY.highestWarningLevel);
    const countState = stateFor(hass, device, KEY.activeHazardsCount);
    const count = isUnavailable(countState) ? undefined : numberAttr(countState?.state);
    const status = headlineStatus(isUnavailable(levelState) ? undefined : levelState?.state, count);
    const presentation = headlinePresentation(status);
    const label = t(hass, STATUS_LABELS[status]);

    const distanceState = stateFor(hass, device, KEY.nearestHazardDistance);
    const titleState = stateFor(hass, device, KEY.nearestHazardTitle);
    const nearestKm = isUnavailable(distanceState) ? undefined : numberAttr(distanceState?.state);
    const nearestTitle =
      stringAttr(distanceState?.attributes.title) ??
      (isUnavailable(titleState) || titleState?.state === "None" ? undefined : stringAttr(titleState?.state));

    let summary = "";
    if (status !== "unavailable" && count !== undefined) {
      summary =
        count === 0
          ? t(hass, "status.no_hazards")
          : count === 1
            ? t(hass, "status.hazard")
            : t(hass, "status.hazards", { count });
    }
    const distance = formatDistance(hass, nearestKm);
    const nearest =
      count && distance
        ? `${t(hass, "status.nearest", { distance })}${nearestTitle ? ` — ${nearestTitle}` : ""}`
        : undefined;

    const alerts = ALERT_KEYS.map((a) => ({ ...a, stateObj: stateFor(hass, device, a.key) })).filter(
      (a) => a.stateObj?.state === "on",
    );

    return html`<div class="content status">
      <button
        class="plain hero"
        aria-label=${`${label}. ${summary}${nearest ? `, ${nearest}` : ""}. ${t(hass, "action.details")}`}
        @click=${() => this.moreInfo(levelState?.entity_id)}
      >
        <span class="bubble large" style=${styleMap({ "--tone": toneColor(presentation.tone) })} aria-hidden="true">
          <ha-icon .icon=${presentation.icon}></ha-icon>
        </span>
        <span class="hero-text">
          <span class="level">${label}</span>
          ${summary ? html`<span class="summary">${summary}</span>` : nothing}
          ${nearest ? html`<span class="summary nearest">${nearest}</span>` : nothing}
        </span>
      </button>
      ${
        alerts.length
          ? html`<ha-chip-set aria-label=${t(hass, "status.alerts")}>
              ${alerts.map(
                (a) => html`<ha-assist-chip
                  filled
                  .label=${t(hass, a.label)}
                  @click=${() => this.moreInfo(a.stateObj?.entity_id)}
                >
                  <ha-icon slot="icon" .icon=${a.icon}></ha-icon>
                </ha-assist-chip>`,
              )}
            </ha-chip-set>`
          : nothing
      }
    </div>`;
  }
}
