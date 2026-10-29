import { css, html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import { KEY, type EntityKey } from "../const";
import { geoLocationsFor, incidentDistance, incidentTitle, stateFor } from "../ha/entities";
import { formatDistance, formatNumber, isUnavailable, numberAttr, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { summariseIncidents } from "../model/area";
import { headlinePresentation, headlineStatus, type HeadlineStatus } from "../model/aws";
import { toneColor } from "../model/tone";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import { areaSchema, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

const ALERT_KEYS = [
  { key: KEY.emergencyWarningNearby, icon: "mdi:alert-octagon", label: "status.chip.emergency_warning_nearby" },
  { key: KEY.activeHazardsNearby, icon: "mdi:alert", label: "status.chip.active_hazards_nearby" },
  { key: KEY.powerOutageActive, icon: "mdi:transmission-tower-off", label: "status.chip.power_outage_active" },
  { key: KEY.roadClosureNearby, icon: "mdi:traffic-cone", label: "status.chip.road_closure_nearby" },
] as const satisfies readonly { key: EntityKey; icon: string; label: TranslationKey }[];

/** Headlines that are the sensor's state as it is; the others are the card's own wording. */
const SENSOR_STATUSES = new Set<HeadlineStatus>(["all_clear", "emergency", "watch_and_act", "advice", "information"]);

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
  // Radius by default: a hazard just over the council border still matters (#94)
  static override readonly defaultArea = "radius" as const;
  // Filtered to the council, the headline is worked out from the incidents
  protected override readonly usesIncidents = true;

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
    return {
      schema: [...baseSchema(), areaSchema(this.defaultArea)],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c),
    };
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
    const area = this.areaFilter(hass);
    // Filtered to the council (#94): the headline of the incidents in it, while the sensor is available
    // (an `unknown` level, from incidents without a known level, still counts the council's incidents)
    const council =
      area.council && levelState && levelState.state !== "unavailable"
        ? summariseIncidents(
            geoLocationsFor(hass, this.entryId)
              .filter((s) => area.keep(s.attributes.in_council_area))
              .map((s) => ({ level: s.attributes.warning_level, distanceKm: incidentDistance(s), title: incidentTitle(s) })),
          )
        : undefined;
    const countState = stateFor(hass, device, KEY.activeHazardsCount);
    const count = council ? council.count : isUnavailable(countState) ? undefined : numberAttr(countState?.state);
    const status = headlineStatus(council ? council.level : levelState?.state, count);
    const presentation = headlinePresentation(status);
    // The sensor's own translated state name when the headline is that state (#21)
    const label =
      !council && levelState && hass.formatEntityState && SENSOR_STATUSES.has(status)
        ? hass.formatEntityState(levelState)
        : t(hass, STATUS_LABELS[status]);

    const distanceState = stateFor(hass, device, KEY.nearestHazardDistance);
    const titleState = stateFor(hass, device, KEY.nearestHazardTitle);
    const nearestKm = council
      ? council.nearestKm
      : isUnavailable(distanceState)
        ? undefined
        : numberAttr(distanceState?.state);
    const nearestTitle = council
      ? council.nearestTitle
      : (stringAttr(distanceState?.attributes.title) ??
        (isUnavailable(titleState) || titleState?.state === "None" ? undefined : stringAttr(titleState?.state)));

    let summary = "";
    if (status !== "unavailable" && count !== undefined) {
      const name = area.council?.name ?? "";
      summary = council
        ? count === 0
          ? t(hass, "status.no_hazards_council", { name })
          : count === 1
            ? t(hass, "status.hazard_council", { name })
            : t(hass, "status.hazards_council", { count: formatNumber(hass, count), name })
        : count === 0
          ? t(hass, "status.no_hazards")
          : count === 1
            ? t(hass, "status.hazard")
            : t(hass, "status.hazards", { count: formatNumber(hass, count) });
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
      ${this.areaHint(hass, area)}
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
