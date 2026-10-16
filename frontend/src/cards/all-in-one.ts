import { css, html, LitElement, nothing, type PropertyValues, type TemplateResult } from "lit";
import { CARD_TAGS, DEFAULT_SECTIONS, SECTION_KEYS, type SectionKey } from "../const";
import { alert } from "../components/render";
import { integrationDevices } from "../ha/entities";
import { preloadHaElements } from "../ha/preload";
import { t, type TranslationKey } from "../localize/localize";
import { cardStyles } from "../styles";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm, LovelaceGridOptions } from "../types";
import { assertBoolean, assertList, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

export interface AllInOneCardConfig extends BaseCardConfig {
  cards?: SectionKey[];
  /** Passed to the relief section (#94). */
  show_nearby_councils?: boolean;
}

const SECTION_NAMES: Record<SectionKey, TranslationKey> = {
  status: "card.status.name",
  incidents: "card.incidents.name",
  warnings: "card.warnings.name",
  fire_danger: "card.fire_danger.name",
  outages: "card.outages.name",
  roads: "card.roads.name",
  conditions: "card.conditions.name",
  relief: "card.relief.name",
  cameras: "card.cameras.name",
  map: "card.map.name",
};

/**
 * `custom:ausnz-disaster-card`: the focused cards stacked in one `ha-card`. Each section
 * is a focused card in embedded mode (no nested card frame), separated by dividers.
 */
export class AllInOneCard extends LitElement {
  static override properties = { _config: { state: true } };

  static override styles = [
    cardStyles,
    css`
      .title {
        margin: 0;
        padding: var(--ha-space-4) var(--ha-space-4) 0;
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-medium);
        line-height: var(--ha-line-height-condensed);
      }
    `,
  ];

  protected declare _config?: AllInOneCardConfig;
  private readonly _children = new Map<SectionKey, DisasterCard>();
  private _hass?: HomeAssistant;

  /** Not reactive: `hass` goes straight to the sections, which decide whether to re-render. */
  set hass(hass: HomeAssistant | undefined) {
    const setUp = (h?: HomeAssistant) => !!h && integrationDevices(h).length > 0;
    if (setUp(hass) !== setUp(this._hass) || !this._hass) this.requestUpdate();
    this._hass = hass;
    if (hass) for (const child of this._children.values()) child.hass = hass;
  }

  get hass(): HomeAssistant | undefined {
    return this._hass;
  }

  static validateConfig(config: AllInOneCardConfig): void {
    DisasterCard.validateConfig(config);
    assertList(config as unknown as Record<string, unknown>, "cards", SECTION_KEYS);
    assertBoolean(config as unknown as Record<string, unknown>, "show_nearby_councils");
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        {
          name: "cards",
          selector: {
            select: {
              multiple: true,
              reorder: true,
              mode: "list",
              options: SECTION_KEYS.map((value) => ({ value, label: t(undefined, SECTION_NAMES[value]) })),
            },
          },
        },
        { name: "show_nearby_councils", selector: { boolean: {} } },
      ],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c as AllInOneCardConfig),
    };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  setConfig(config: AllInOneCardConfig): void {
    AllInOneCard.validateConfig(config);
    // Old options (max_incidents, show_map_button) are ignored.
    this._config = { ...config };
  }

  private sections(): SectionKey[] {
    return this._config?.cards?.length ? this._config.cards : DEFAULT_SECTIONS;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    void preloadHaElements();
  }

  getCardSize(): number {
    return this.sections().length * 3;
  }

  getGridOptions(): LovelaceGridOptions {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (!this._config) return;
    if (changed.has("_config" as keyof AllInOneCard)) {
      const wanted = new Set(this.sections());
      for (const key of [...this._children.keys()]) if (!wanted.has(key)) this._children.delete(key);
      for (const key of wanted) {
        let child = this._children.get(key);
        if (!child) {
          child = document.createElement(CARD_TAGS[key]) as unknown as DisasterCard;
          child.embedded = true;
          this._children.set(key, child);
        }
        const extra = key === "relief" ? { show_nearby_councils: this._config.show_nearby_councils } : {};
        child.setConfig({ type: `custom:${CARD_TAGS[key]}`, device: this._config.device, ...extra });
      }
    }
    if (this._hass) for (const child of this._children.values()) child.hass = this._hass;
  }

  protected override render(): TemplateResult | typeof nothing {
    if (!this._config) return nothing;
    const children = this.sections()
      .map((key) => this._children.get(key))
      .filter((c): c is DisasterCard => !!c);
    if (this._hass && integrationDevices(this._hass).length === 0) {
      return html`<ha-card><div class="content">${alert("info", t(this._hass, "state.not_set_up"))}</div></ha-card>`;
    }
    return html`<ha-card>
      ${this._config.title ? html`<h2 class="title">${this._config.title}</h2>` : nothing}
      ${children.map((child, i) => html`${i ? html`<hr class="divider" />` : nothing}${child}`)}
    </ha-card>`;
  }
}
