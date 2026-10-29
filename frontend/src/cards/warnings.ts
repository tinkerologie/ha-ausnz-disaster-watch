import { html, nothing, type TemplateResult } from "lit";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatNumber, isUnavailable, listAttr, numberAttr, relativeTime, safeUrl, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import { alert, empty, header, list, row, showAll } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm } from "../types";
import { assertPositiveInt, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

export interface WarningsCardConfig extends BaseCardConfig {
  max_items?: number;
}

interface WarningItem {
  title?: string;
  link?: string;
  locations?: string;
  description?: string;
  pub_date?: string;
}

const DEFAULT_MAX_ITEMS = 8;

/** Weather warnings and emergency news, switched with two filter chips. */
export class WarningsCard extends DisasterCard<WarningsCardConfig> {
  static override properties = { ...DisasterCard.properties, _view: { state: true }, _expanded: { state: true } };

  protected declare _view: "warnings" | "news";
  protected declare _expanded: boolean;
  protected readonly titleKey = "warnings.title" as const;

  constructor() {
    super();
    this._view = "warnings";
    this._expanded = false;
  }

  protected override entityKeys() {
    return [KEY.weatherWarningsCount, KEY.highestWarningLevel];
  }

  static override validateConfig(config: WarningsCardConfig): void {
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

  override getCardSize(): number {
    return 5;
  }

  private renderItem(hass: HomeAssistant, item: WarningItem, icon: string): TemplateResult {
    const title = stringAttr(item.title) ?? "";
    const when = relativeTime(hass, item.pub_date);
    const detail = stringAttr(item.locations) ?? stringAttr(item.description);
    return row({
      icon,
      tone: this._view === "warnings" ? "orange" : "blue",
      headline: title,
      supporting: [detail, when].filter(Boolean).join(" · ") || undefined,
      link: safeUrl(item.link),
      linkLabel: `${t(hass, "action.open_link")}: ${title}`,
    });
  }

  protected renderBody(hass: HomeAssistant, config: WarningsCardConfig): TemplateResult {
    const warningsState = stateFor(hass, this.deviceId, KEY.weatherWarningsCount);
    const levelState = stateFor(hass, this.deviceId, KEY.highestWarningLevel);
    const unavailable = isUnavailable(warningsState);
    const warnings = listAttr<WarningItem>(warningsState?.attributes.warnings);
    const news = listAttr<WarningItem>(warningsState?.attributes.emergency_news ?? levelState?.attributes.emergency_news);
    // The count comes from the state: the attribute list is capped.
    const warningCount = unavailable ? 0 : (numberAttr(warningsState?.state) ?? warnings.length);
    const items = this._view === "warnings" ? warnings : news;
    const max = config.max_items ?? DEFAULT_MAX_ITEMS;
    const shown = this._expanded ? items : items.slice(0, max);
    const icon = this._view === "warnings" ? "mdi:weather-lightning-rainy" : "mdi:newspaper-variant-outline";

    const tab = (view: "warnings" | "news", label: string) => html`<ha-filter-chip
      no-leading-icon
      .selected=${this._view === view}
      .label=${label}
      @click=${(ev: Event) => {
        ev.preventDefault();
        this._view = view;
        this._expanded = false;
      }}
    ></ha-filter-chip>`;

    return html`${header({
        title: this.cardTitle(),
        icon: "mdi:weather-lightning-rainy",
        detailsLabel: t(hass, "action.details"),
        onDetails: warningsState ? () => this.moreInfo(warningsState.entity_id) : undefined,
      })}
      <div class="content">
        ${
          unavailable
            ? alert("warning", t(hass, warningsState ? "state.unavailable" : "state.entity_missing"))
            : html`<ha-chip-set aria-label=${t(hass, "warnings.views")}>
                  ${tab("warnings", t(hass, "warnings.tab.warnings", { count: formatNumber(hass, warningCount) }))}
                  ${tab("news", t(hass, "warnings.tab.news", { count: formatNumber(hass, news.length) }))}
                </ha-chip-set>
                ${
                  shown.length
                    ? list(shown.map((item) => this.renderItem(hass, item, icon)))
                    : empty(
                        "mdi:check-circle-outline",
                        t(hass, this._view === "warnings" ? "warnings.empty" : "warnings.news_empty"),
                      )
                }
                ${items.length > max ? showAll(hass, this._expanded, items.length, () => (this._expanded = !this._expanded)) : nothing}
`
        }
      </div>`;
  }
}
