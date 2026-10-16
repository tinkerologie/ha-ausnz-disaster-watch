import { html, nothing, type TemplateResult } from "lit";
import { geoLocationsFor, incidentDistance, incidentTitle } from "../ha/entities";
import { formatDistance, numberAttr, relativeTime, safeUrl, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { awsPresentation } from "../model/aws";
import { CATEGORY_ICONS, HAZARD_CATEGORIES, hazardCategory, hazardIcon, type HazardCategory } from "../model/hazards";
import { badge, empty, header, list, row, showAll } from "../components/render";
import type { BaseCardConfig, HassEntity, HomeAssistant, LovelaceConfigForm } from "../types";
import {
  areaSchema,
  assertBoolean,
  assertList,
  assertPositiveInt,
  baseSchema,
  computeHelper,
  computeLabel,
  DisasterCard,
  stubConfig,
} from "./base";

export interface IncidentsCardConfig extends BaseCardConfig {
  max_items?: number;
  show_planned_burns?: boolean;
  categories?: HazardCategory[];
}

const DEFAULT_MAX_ITEMS = 10;

export const LEVEL_LABELS: Record<string, TranslationKey> = {
  emergency: "status.level.emergency",
  watch_and_act: "status.level.watch_and_act",
  advice: "status.level.advice",
  information: "status.level.information",
  unknown: "status.level.unknown",
};

/** Incidents of the entry nearest first, with category filters and AWS level badges. */
export class IncidentsCard extends DisasterCard<IncidentsCardConfig> {
  static override properties = {
    ...DisasterCard.properties,
    _category: { state: true },
    _showBurns: { state: true },
    _expanded: { state: true },
  };

  protected declare _category: HazardCategory | "all";
  protected declare _showBurns: boolean | undefined;
  protected declare _expanded: boolean;

  protected readonly titleKey = "incidents.title" as const;
  // Radius by default: a hazard just over the council border still matters (#94)
  static override readonly defaultArea = "radius" as const;
  protected override readonly usesIncidents = true;

  constructor() {
    super();
    this._category = "all";
    this._showBurns = undefined;
    this._expanded = false;
  }

  static override validateConfig(config: IncidentsCardConfig): void {
    super.validateConfig(config);
    const c = config as unknown as Record<string, unknown>;
    assertPositiveInt(c, "max_items", 1, 100);
    assertBoolean(c, "show_planned_burns");
    assertList(c, "categories", HAZARD_CATEGORIES);
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        areaSchema(this.defaultArea),
        { name: "max_items", selector: { number: { min: 1, max: 100, mode: "box" } } },
        { name: "show_planned_burns", selector: { boolean: {} } },
        {
          name: "categories",
          selector: {
            select: {
              multiple: true,
              mode: "list",
              options: HAZARD_CATEGORIES.map((value) => ({
                value,
                label: t(undefined, `incidents.category.${value}` as TranslationKey),
              })),
            },
          },
        },
      ],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c),
    };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getCardSize(): number {
    return 2 + Math.min(this._config?.max_items ?? DEFAULT_MAX_ITEMS, 6);
  }

  private get showBurns(): boolean {
    return this._showBurns ?? this._config?.show_planned_burns ?? false;
  }

  private categories(): HazardCategory[] {
    const configured = this._config?.categories;
    return configured?.length ? configured : HAZARD_CATEGORIES;
  }

  private renderIncident(hass: HomeAssistant, stateObj: HassEntity): TemplateResult {
    const a = stateObj.attributes;
    const level = awsPresentation(a.warning_level);
    const title = incidentTitle(stateObj);
    const updated = relativeTime(hass, a.updated_at);
    const supporting = [
      stringAttr(a.location_name),
      formatDistance(hass, incidentDistance(stateObj)),
      updated ? t(hass, "incidents.updated", { time: updated }) : undefined,
    ]
      .filter(Boolean)
      .join(" · ");
    return row({
      icon: stringAttr(a.icon) ?? hazardIcon(a.hazard_type),
      tone: level.tone,
      headline: title,
      supporting: html`${a.is_hazard_reduction ? html`${t(hass, "incidents.planned_burn")} · ` : nothing}${supporting}`,
      badge: badge(t(hass, LEVEL_LABELS[level.level]!), level.tone, level.icon),
      onActivate: () => this.moreInfo(stateObj.entity_id),
      link: safeUrl(a.web_url),
      linkLabel: `${t(hass, "action.open_link")}: ${title}`,
      actions: this.renderNearestCamera(hass, stateObj),
    });
  }

  /** Button to the camera the integration found within 5 km of the incident (#70). */
  private renderNearestCamera(hass: HomeAssistant, stateObj: HassEntity): TemplateResult | undefined {
    const camera = stateObj.attributes.nearest_camera as { entity_id?: unknown; name?: unknown; distance_km?: unknown } | undefined;
    const entityId = stringAttr(camera?.entity_id);
    if (!entityId?.startsWith("camera.") || !hass.states[entityId]) return undefined;
    const name = stringAttr(camera?.name) ?? String(hass.states[entityId]?.attributes.friendly_name ?? entityId);
    const distance = formatDistance(hass, numberAttr(camera?.distance_km));
    const label = t(hass, "incidents.nearest_camera", { name: distance ? `${name}, ${distance}` : name });
    return html`<ha-icon-button class="link camera" .label=${label} @click=${() => this.moreInfo(entityId)}>
      <ha-icon icon="mdi:cctv"></ha-icon>
    </ha-icon-button>`;
  }

  protected renderBody(hass: HomeAssistant, config: IncidentsCardConfig): TemplateResult {
    const categories = this.categories();
    const area = this.areaFilter(hass);
    const all = geoLocationsFor(hass, this.entryId).filter(
      (s) => categories.includes(hazardCategory(s.attributes.hazard_type)) && area.keep(s.attributes.in_council_area),
    );
    const hasBurns = all.some((s) => s.attributes.is_hazard_reduction === true);
    const visible = this.showBurns ? all : all.filter((s) => s.attributes.is_hazard_reduction !== true);
    const counts = new Map<HazardCategory, number>();
    for (const s of visible) {
      const category = hazardCategory(s.attributes.hazard_type);
      counts.set(category, (counts.get(category) ?? 0) + 1);
    }
    const selected = this._category !== "all" && categories.includes(this._category) ? this._category : "all";
    const filtered =
      selected === "all" ? visible : visible.filter((s) => hazardCategory(s.attributes.hazard_type) === selected);
    const max = config.max_items ?? DEFAULT_MAX_ITEMS;
    const shown = this._expanded ? filtered : filtered.slice(0, max);

    const chip = (key: HazardCategory | "all", count: number) => html`<ha-filter-chip
      .selected=${selected === key}
      .label=${`${t(hass, `incidents.category.${key}` as TranslationKey)} ${count}`}
      @click=${(ev: Event) => {
        ev.preventDefault();
        this._category = key;
        this._expanded = false;
      }}
    >
      ${key === "all" ? nothing : html`<ha-icon slot="icon" .icon=${CATEGORY_ICONS[key]}></ha-icon>`}
    </ha-filter-chip>`;

    return html`${header({
        title: this.cardTitle(),
        icon: "mdi:alert-decagram",
        count: String(visible.length),
        subtitle: area.council?.name,
      })}
      <div class="content">
        ${this.areaHint(hass, area)}
        ${
          all.length
            ? html`<ha-chip-set aria-label=${t(hass, "incidents.filters")}>
                ${chip("all", visible.length)}
                ${categories.length > 1 ? categories.map((c) => chip(c, counts.get(c) ?? 0)) : nothing}
                ${
                  hasBurns
                    ? html`<ha-filter-chip
                        .selected=${this.showBurns}
                        .label=${t(hass, "incidents.planned_burns")}
                        @click=${(ev: Event) => {
                          ev.preventDefault();
                          this._showBurns = !this.showBurns;
                        }}
                      >
                        <ha-icon slot="icon" icon="mdi:fire-circle"></ha-icon>
                      </ha-filter-chip>`
                    : nothing
                }
              </ha-chip-set>`
            : nothing
        }
        ${
          shown.length
            ? list(
                shown.map((s) => this.renderIncident(hass, s)),
                this.cardTitle(),
              )
            : empty("mdi:shield-check-outline", t(hass, all.length ? "incidents.empty_filtered" : "incidents.empty"))
        }
        ${filtered.length > max ? showAll(hass, this._expanded, filtered.length, () => (this._expanded = !this._expanded)) : nothing}
      </div>`;
  }
}
