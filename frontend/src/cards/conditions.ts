import { css, html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatAttribute, formatState, isUnavailable, listAttr, numberAttr, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { airQualityTone, parseAirQuality } from "../model/ratings";
import { badge, empty, header } from "../components/render";
import type { BaseCardConfig, HassEntity, HomeAssistant, LovelaceConfigForm } from "../types";
import { baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

export function compassPoint(degrees: number): string {
  return COMPASS[Math.round((((degrees % 360) + 360) % 360) / 22.5) % 16]!;
}

const POLLUTANTS = [
  { attr: "pm2_5", label: "PM2.5" },
  { attr: "pm10", label: "PM10" },
  { attr: "no2", label: "NO₂" },
  { attr: "o3", label: "O₃" },
];

/** Local weather observation and air quality. */
export class ConditionsCard extends DisasterCard {
  static override styles = [
    ...DisasterCard.styles,
    css`
      .group {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
      }
      .group-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
      }
      .group-title {
        margin: 0;
        font-size: var(--ha-font-size-m);
        font-weight: var(--ha-font-weight-medium);
      }
      .temperature {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: var(--ha-space-2);
      }
      .temperature .value {
        font-size: var(--ha-font-size-3xl);
        font-weight: var(--ha-font-weight-normal);
        line-height: var(--ha-line-height-condensed);
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(calc(var(--ha-space-20) + var(--ha-space-8)), 1fr));
        gap: var(--ha-space-2) var(--ha-space-4);
        margin: 0;
      }
      .metric {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      .metric dt {
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .metric dd {
        margin: 0;
        display: flex;
        align-items: center;
        gap: var(--ha-space-1);
        font-size: var(--ha-font-size-m);
        font-weight: var(--ha-font-weight-medium);
      }
      .metric dd ha-icon {
        --mdc-icon-size: var(--ha-space-4);
        color: var(--secondary-text-color);
      }
    `,
  ];

  protected readonly titleKey = "conditions.title" as const;

  protected override entityKeys() {
    return [KEY.primaryWeatherObservation, KEY.airQualityRating];
  }

  static getConfigForm(): LovelaceConfigForm {
    return { schema: baseSchema(), computeLabel, computeHelper, assertConfig: (c) => this.validateConfig(c) };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getCardSize(): number {
    return 4;
  }

  private metric(label: string, value: TemplateResult | string | undefined): TemplateResult | typeof nothing {
    if (value === undefined || value === "") return nothing;
    return html`<div class="metric"><dt>${label}</dt><dd>${value}</dd></div>`;
  }

  private renderWeather(hass: HomeAssistant, s: HassEntity | undefined): TemplateResult {
    if (!s || isUnavailable(s)) return empty("mdi:weather-cloudy-alert", t(hass, "conditions.no_weather"));
    const a = s.attributes;
    const num = (attr: string, unit: string) => {
      const value = numberAttr(a[attr]);
      return value === undefined ? undefined : `${formatAttribute(hass, s, attr, value)} ${unit}`;
    };
    const direction = numberAttr(a.wind_direction_deg);
    const speed = num("wind_speed_avg_kph", "km/h");
    const rain = numberAttr(listAttr<{ rain_since_9am?: number | null }>(a.stations)[0]?.rain_since_9am);
    const station = stringAttr(a.station_name);
    const wind =
      speed === undefined
        ? undefined
        : html`${
              direction === undefined
                ? nothing
                : html`<ha-icon
                    icon="mdi:navigation"
                    style=${styleMap({ transform: `rotate(${direction + 180}deg)` })}
                    aria-hidden="true"
                  ></ha-icon>`
            }<span>${speed}${direction === undefined ? "" : ` ${compassPoint(direction)}`}</span>${
              direction === undefined
                ? nothing
                : html`<span class="sr-only">${t(hass, "conditions.wind_from", { direction: compassPoint(direction) })}</span>`
            }`;

    return html`<button
        class="plain temperature"
        aria-label=${`${t(hass, "conditions.temperature")} ${formatState(hass, s)}. ${t(hass, "action.details")}`}
        @click=${() => this.moreInfo(s.entity_id)}
      >
        <span class="value">${formatState(hass, s)}</span>
        ${station ? html`<span class="secondary">${t(hass, "conditions.station", { name: station })}</span>` : nothing}
      </button>
      <dl class="metrics">
        ${this.metric(t(hass, "conditions.feels_like"), num("apparent_temperature", "°C"))}
        ${this.metric(t(hass, "conditions.humidity"), num("relative_humidity", "%"))}
        ${this.metric(t(hass, "conditions.wind"), wind)}
        ${this.metric(t(hass, "conditions.gust"), num("wind_speed_max_kph", "km/h"))}
        ${this.metric(t(hass, "conditions.pressure"), num("pressure_hpa", "hPa"))}
        ${this.metric(t(hass, "conditions.rain"), rain === undefined ? undefined : `${formatAttribute(hass, s, "rain_since_9am", rain)} mm`)}
      </dl>`;
  }

  private renderAirQuality(hass: HomeAssistant, s: HassEntity | undefined): TemplateResult {
    if (!s || isUnavailable(s)) return empty("mdi:air-filter", t(hass, "conditions.no_air_quality"));
    const station = stringAttr(s.attributes.station_name);
    return html`<dl class="metrics">
        ${POLLUTANTS.map((p) => this.metric(p.label, stringAttr(s.attributes[p.attr]) ?? (numberAttr(s.attributes[p.attr]) !== undefined ? formatAttribute(hass, s, p.attr) : undefined)))}
      </dl>
      ${station ? html`<span class="secondary">${t(hass, "conditions.station", { name: station })}</span>` : nothing}`;
  }

  protected renderBody(hass: HomeAssistant, _config: BaseCardConfig): TemplateResult {
    const weather = stateFor(hass, this.deviceId, KEY.primaryWeatherObservation);
    const air = stateFor(hass, this.deviceId, KEY.airQualityRating);
    const rating = parseAirQuality(isUnavailable(air) ? undefined : air?.state);
    const ratingLabel = isUnavailable(air)
      ? undefined
      : rating === "unknown"
        ? stringAttr(air?.state)
        : t(hass, `conditions.aq.${rating}` as TranslationKey);
    return html`${header({ title: this.cardTitle(), icon: "mdi:weather-partly-cloudy" })}
      <div class="content">
        <section class="group" aria-label=${t(hass, "conditions.weather")}>${this.renderWeather(hass, weather)}</section>
        <hr class="divider" />
        <section class="group" aria-label=${t(hass, "conditions.air_quality")}>
          <div class="group-head">
            <h3 class="group-title">${t(hass, "conditions.air_quality")}</h3>
            ${
              ratingLabel
                ? html`<button class="plain" aria-label=${`${t(hass, "conditions.air_quality")}: ${ratingLabel}. ${t(hass, "action.details")}`} @click=${() => this.moreInfo(air?.entity_id)}>
                    ${badge(ratingLabel, airQualityTone(rating), "mdi:air-filter")}
                  </button>`
                : nothing
            }
          </div>
          ${this.renderAirQuality(hass, air)}
        </section>
      </div>`;
  }
}
