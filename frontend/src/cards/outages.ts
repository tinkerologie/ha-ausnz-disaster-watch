import { html, nothing, type TemplateResult } from "lit";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatDateTime, formatNumber, isUnavailable, listAttr, numberAttr, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import { alert, empty, header, list, row, showAll } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm } from "../types";
import { assertPositiveInt, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

export interface ListCardConfig extends BaseCardConfig {
  max_items?: number;
}

interface OutageItem {
  suburb?: string;
  cause?: string;
  restore_time?: string | null;
  customers_affected?: number;
}

const DEFAULT_MAX_ITEMS = 8;

/** Power outages: totals from the entity state, then the outage list. */
export class OutagesCard extends DisasterCard<ListCardConfig> {
  static override properties = { ...DisasterCard.properties, _expanded: { state: true } };
  protected declare _expanded: boolean;
  protected readonly titleKey = "outages.title" as const;

  constructor() {
    super();
    this._expanded = false;
  }

  protected override entityKeys() {
    return [KEY.powerOutagesCount, KEY.powerOutagesCustomersAffected];
  }

  static override validateConfig(config: ListCardConfig): void {
    super.validateConfig(config);
    assertPositiveInt(config as unknown as Record<string, unknown>, "max_items", 1, 100);
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [...baseSchema(), { name: "max_items", selector: { number: { min: 1, max: 100, mode: "box" } } }],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c),
    };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  protected renderBody(hass: HomeAssistant, config: ListCardConfig): TemplateResult {
    const stateObj = stateFor(hass, this.deviceId, KEY.powerOutagesCount);
    const head = header({
      title: this.cardTitle(),
      icon: "mdi:transmission-tower-off",
      detailsLabel: t(hass, "action.details"),
      onDetails: stateObj ? () => this.moreInfo(stateObj.entity_id) : undefined,
    });
    if (isUnavailable(stateObj)) {
      return html`${head}<div class="content">
          ${alert("warning", t(hass, stateObj ? "state.unavailable" : "state.entity_missing"))}
        </div>`;
    }
    const outages = listAttr<OutageItem>(stateObj!.attributes.outages);
    const count = numberAttr(stateObj!.state) ?? outages.length;
    const customers = numberAttr(stateObj!.attributes.customers_affected) ?? 0;
    const max = config.max_items ?? DEFAULT_MAX_ITEMS;
    const shown = this._expanded ? outages : outages.slice(0, max);

    return html`${head}
      <div class="content">
        ${
          count === 0
            ? empty("mdi:transmission-tower", t(hass, "outages.empty"))
            : html`<span class="secondary"
                  >${t(hass, "outages.summary", {
                    count: formatNumber(hass, count),
                    customers: formatNumber(hass, customers),
                  })}</span
                >
                ${list(
                  shown.map((o) => {
                    const restore =
                      formatDateTime(hass, o.restore_time, { weekday: "short", hour: "numeric", minute: "2-digit" }) ??
                      stringAttr(o.restore_time);
                    const affected = numberAttr(o.customers_affected);
                    return row({
                      icon: "mdi:transmission-tower-off",
                      tone: "amber",
                      headline: stringAttr(o.suburb) ?? "—",
                      supporting:
                        [stringAttr(o.cause), restore ? t(hass, "outages.restore", { time: restore }) : undefined]
                          .filter(Boolean)
                          .join(" · ") || undefined,
                      trailing:
                        affected !== undefined
                          ? html`<span class="secondary"
                              >${t(hass, "outages.customers", { count: formatNumber(hass, affected) })}</span
                            >`
                          : undefined,
                    });
                  }),
                  this.cardTitle(),
                )}
                ${outages.length > max ? showAll(hass, this._expanded, outages.length, () => (this._expanded = !this._expanded)) : nothing}`
        }
      </div>`;
  }
}
