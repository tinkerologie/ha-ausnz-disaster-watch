import { html, nothing, type TemplateResult } from "lit";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatDistance, isUnavailable, listAttr, numberAttr, relativeTime, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import { roadStatusIcon, roadStatusTone } from "../model/ratings";
import { alert, badge, empty, header, list, row, showAll } from "../components/render";
import type { HomeAssistant, LovelaceConfigForm } from "../types";
import { assertPositiveInt, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";
import type { ListCardConfig } from "./outages";

interface ClosureItem {
  road?: string;
  suburb?: string;
  status?: string;
  reason?: string | null;
  description?: string | null;
  advice?: string | null;
  updated_at?: string | null;
  distance_km?: number | null;
}

const DEFAULT_MAX_ITEMS = 8;

/** Road closures and hazards with a status badge, advice and distance. */
export class RoadsCard extends DisasterCard<ListCardConfig> {
  static override properties = { ...DisasterCard.properties, _expanded: { state: true } };
  protected declare _expanded: boolean;
  protected readonly titleKey = "roads.title" as const;

  constructor() {
    super();
    this._expanded = false;
  }

  protected override entityKeys() {
    return [KEY.roadClosuresCount];
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
    const stateObj = stateFor(hass, this.deviceId, KEY.roadClosuresCount);
    const unavailable = isUnavailable(stateObj);
    const closures = unavailable ? [] : listAttr<ClosureItem>(stateObj!.attributes.closures);
    const count = unavailable ? undefined : (numberAttr(stateObj!.state) ?? closures.length);
    const head = header({
      title: this.cardTitle(),
      icon: "mdi:traffic-cone",
      count: count ? String(count) : undefined,
      detailsLabel: t(hass, "action.details"),
      onDetails: stateObj ? () => this.moreInfo(stateObj.entity_id) : undefined,
    });
    if (unavailable) {
      return html`${head}<div class="content">
          ${alert("warning", t(hass, stateObj ? "state.unavailable" : "state.entity_missing"))}
        </div>`;
    }
    const sorted = [...closures].sort(
      (a, b) => (numberAttr(a.distance_km) ?? Infinity) - (numberAttr(b.distance_km) ?? Infinity),
    );
    const max = config.max_items ?? DEFAULT_MAX_ITEMS;
    const shown = this._expanded ? sorted : sorted.slice(0, max);

    return html`${head}
      <div class="content">
        ${
          sorted.length
            ? list(
                shown.map((c) => {
                  const status = stringAttr(c.status) ?? "—";
                  const tone = roadStatusTone(status);
                  const updated = relativeTime(hass, c.updated_at);
                  return row({
                    icon: roadStatusIcon(status),
                    tone,
                    headline: [stringAttr(c.road), stringAttr(c.suburb)].filter(Boolean).join(", ") || status,
                    supporting:
                      [stringAttr(c.advice) ?? stringAttr(c.description) ?? stringAttr(c.reason), updated]
                        .filter(Boolean)
                        .join(" · ") || undefined,
                    badge: badge(status, tone),
                    trailing: formatDistance(hass, numberAttr(c.distance_km)),
                  });
                }),
                this.cardTitle(),
              )
            : empty("mdi:road-variant", t(hass, "roads.empty"))
        }
        ${sorted.length > max ? showAll(hass, this._expanded, sorted.length, () => (this._expanded = !this._expanded)) : nothing}
      </div>`;
  }
}
