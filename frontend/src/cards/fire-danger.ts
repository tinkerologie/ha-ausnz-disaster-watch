import { css, html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { isUnavailable, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { AFDRS_ICONS, AFDRS_SCALE, afdrsTone, parseAfdrs } from "../model/ratings";
import { toneColor } from "../model/tone";
import { alert, badge, bubble, header } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import { baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

/** Fire danger rating on the four-level AFDRS scale, district, forecast day and total fire ban. */
export class FireDangerCard extends DisasterCard {
  static override styles = [
    ...DisasterCard.styles,
    css`
      .rating {
        display: flex;
        align-items: center;
        gap: var(--ha-space-3);
      }
      .rating-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      @container (max-width: 260px) {
        .rating {
          flex-direction: column;
          align-items: flex-start;
        }
      }
      .rating-label {
        overflow-wrap: anywhere;
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-bold);
        line-height: var(--ha-line-height-condensed);
      }
      .content {
        container-type: inline-size;
      }
      .scale {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: var(--ha-space-1);
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .segment {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1);
        min-width: 0;
        font-size: var(--ha-font-size-xs);
        color: var(--secondary-text-color);
        text-align: center;
      }
      .segment .bar {
        height: var(--ha-space-2);
        border-radius: var(--ha-border-radius-pill);
        background-color: color-mix(in srgb, var(--tone) 30%, transparent);
      }
      .segment.active {
        color: var(--primary-text-color);
        font-weight: var(--ha-font-weight-bold);
      }
      .segment.active .bar {
        background-color: var(--tone);
        box-shadow: 0 0 0 var(--ha-border-width-md) var(--card-background-color, var(--ha-card-background)),
          0 0 0 calc(2 * var(--ha-border-width-md)) var(--tone);
      }
      .segment .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      /* Narrow cards name only the current level under the scale; all names stay readable to screen readers. */
      @container (max-width: 300px) {
        .segment:not(.active) .name {
          position: absolute;
          width: 1px;
          height: 1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
        }
        .segment.active .name {
          overflow: visible;
        }
      }
      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-2);
      }
    `,
  ];

  protected readonly titleKey = "fire.title" as const;

  protected override entityKeys() {
    return [KEY.fireDangerRating];
  }

  static getConfigForm(): LovelaceConfigForm {
    return { schema: baseSchema(), computeLabel, computeHelper, assertConfig: (c) => this.validateConfig(c) };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getGridOptions(): LovelaceGridOptions {
    return { columns: 6, rows: "auto", min_columns: 6 };
  }

  protected renderBody(hass: HomeAssistant, _config: BaseCardConfig): TemplateResult {
    const stateObj = stateFor(hass, this.deviceId, KEY.fireDangerRating);
    const head = header({
      title: this.cardTitle(),
      icon: "mdi:fire",
      detailsLabel: t(hass, "action.details"),
      onDetails: stateObj ? () => this.moreInfo(stateObj.entity_id) : undefined,
    });
    if (!stateObj || stateObj.state === "unavailable") {
      return html`${head}<div class="content">
          ${alert("warning", t(hass, stateObj ? "state.unavailable" : "state.entity_missing"))}
        </div>`;
    }
    const rating = parseAfdrs(isUnavailable(stateObj) ? undefined : stateObj.state);
    const tone = afdrsTone(rating);
    // The sensor's translated state name (#21); an unknown rating reads as "No rating"
    const label =
      hass.formatEntityState && !isUnavailable(stateObj)
        ? hass.formatEntityState(stateObj)
        : t(hass, `fire.rating.${rating}` as TranslationKey);
    const district = stringAttr(stateObj.attributes.district_name);
    const day = stringAttr(stateObj.attributes.day);
    const totalFireBan = stateObj.attributes.total_fire_ban === true;

    return html`${head}
      <div class="content">
        <div class="rating">
          ${bubble(AFDRS_ICONS[rating], tone, true)}
          <div class="rating-text">
            <span class="rating-label">${label}</span>
            ${
              district || day
                ? html`<span class="secondary"
                    >${[district ? t(hass, "fire.district", { district }) : undefined, day ? t(hass, "fire.forecast_for", { day }) : undefined]
                      .filter(Boolean)
                      .join(" · ")}</span
                  >`
                : nothing
            }
          </div>
        </div>
        <ol class="scale" aria-label=${t(hass, "fire.scale")}>
          ${AFDRS_SCALE.map((level) => {
            const active = level === rating;
            const name = t(hass, `fire.rating.${level}` as TranslationKey);
            return html`<li
              class="segment ${active ? "active" : ""}"
              style=${styleMap({ "--tone": toneColor(afdrsTone(level)) })}
              aria-current=${active ? "true" : nothing}
            >
              <span class="bar" aria-hidden="true"></span>
              <span class="name">${name}</span>
              ${active ? html`<span class="sr-only">${t(hass, "fire.current")}</span>` : nothing}
            </li>`;
          })}
        </ol>
        <div class="badges">
          ${
            totalFireBan
              ? badge(t(hass, "fire.total_fire_ban"), "red", "mdi:fire-off")
              : badge(t(hass, "fire.no_total_fire_ban"), "grey", "mdi:check")
          }
        </div>
      </div>`;
  }
}
