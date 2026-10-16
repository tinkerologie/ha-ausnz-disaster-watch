import { html, nothing, type TemplateResult } from "lit";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatDistance, isUnavailable, listAttr, numberAttr, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { alert, badge, empty, header, list, row } from "../components/render";
import { councilLinks, type CouncilLink } from "../model/councils";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm } from "../types";
import { areaSchema, assertBoolean, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

interface FacilityItem {
  id?: string;
  facility_type?: string;
  name?: string;
  suburb?: string;
  address?: string;
  status?: string;
  distance_km?: number | null;
  in_council_area?: boolean | null;
}

export interface ReliefCardConfig extends BaseCardConfig {
  /** Also list the neighbouring council dashboards (#94). Off: only the entry's own one. */
  show_nearby_councils?: boolean;
}

type Group = "evacuation_centre" | "place_of_refuge" | "sandbag_station" | "other";

const GROUPS: { key: Group; icon: string }[] = [
  { key: "evacuation_centre", icon: "mdi:home-group" },
  { key: "place_of_refuge", icon: "mdi:home-heart" },
  { key: "sandbag_station", icon: "mdi:sack" },
  { key: "other", icon: "mdi:home-alert" },
];

function groupOf(type: unknown): Group {
  return type === "evacuation_centre" || type === "place_of_refuge" || type === "sandbag_station" ? type : "other";
}

function councilRows(hass: HomeAssistant, councils: CouncilLink[]): TemplateResult[] {
  return councils.map((c) =>
    row({
      icon: "mdi:view-dashboard-outline",
      tone: "blue",
      headline: c.name,
      supporting: c.url ? new URL(c.url).hostname : undefined,
      link: c.url,
      linkLabel: `${t(hass, "action.open_link")}: ${c.name}`,
    }),
  );
}

/**
 * Relief facilities grouped by type, plus a link to the entry's own council disaster
 * dashboard and, optionally, the neighbouring ones (#94).
 */
export class ReliefCard extends DisasterCard<ReliefCardConfig> {
  protected readonly titleKey = "relief.title" as const;
  static override readonly defaultArea = "council" as const;

  protected override entityKeys() {
    return [KEY.reliefFacilitiesCount, KEY.highestWarningLevel, KEY.weatherWarningsCount];
  }

  static override validateConfig(config: ReliefCardConfig): void {
    super.validateConfig(config);
    assertBoolean(config as unknown as Record<string, unknown>, "show_nearby_councils");
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        areaSchema(this.defaultArea),
        { name: "show_nearby_councils", selector: { boolean: {} } },
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
    return 5;
  }

  protected renderBody(hass: HomeAssistant, config: ReliefCardConfig): TemplateResult {
    const stateObj = stateFor(hass, this.deviceId, KEY.reliefFacilitiesCount);
    const levelState = stateFor(hass, this.deviceId, KEY.highestWarningLevel);
    const warningsState = stateFor(hass, this.deviceId, KEY.weatherWarningsCount);
    const area = this.areaFilter(hass);
    const head = header({
      title: this.cardTitle(),
      icon: "mdi:home-heart",
      subtitle: area.council?.name,
      detailsLabel: t(hass, "action.details"),
      onDetails: stateObj ? () => this.moreInfo(stateObj.entity_id) : undefined,
    });
    if (isUnavailable(stateObj)) {
      return html`${head}<div class="content">
          ${alert("warning", t(hass, stateObj ? "state.unavailable" : "state.entity_missing"))}
        </div>`;
    }
    const facilities = listAttr<FacilityItem>(stateObj!.attributes.facilities)
      .filter((f) => area.keep(f.in_council_area))
      .sort(
      (a, b) => (numberAttr(a.distance_km) ?? Infinity) - (numberAttr(b.distance_km) ?? Infinity),
    );
    const councils = councilLinks(
      levelState?.attributes.council ?? warningsState?.attributes.council,
      levelState?.attributes.nearby_councils ?? warningsState?.attributes.nearby_councils,
      config.show_nearby_councils ?? false,
    );

    return html`${head}
      <div class="content">
        ${this.areaHint(hass, area)}
        ${facilities.length === 0 ? empty("mdi:home-search-outline", t(hass, "relief.empty")) : nothing}
        ${GROUPS.map(({ key, icon }) => {
          const items = facilities.filter((f) => groupOf(f.facility_type) === key);
          if (!items.length) return nothing;
          const label = t(hass, `relief.group.${key}` as TranslationKey);
          return html`<h3 class="list-title">${label}</h3>
            ${list(
              items.map((f) => {
                const open = (stringAttr(f.status) ?? "Open").toLowerCase() !== "closed";
                const name = stringAttr(f.name) ?? label;
                return row({
                  icon,
                  tone: open ? "green" : "grey",
                  headline: name,
                  supporting: stringAttr(f.address) ?? stringAttr(f.suburb),
                  badge: badge(
                    t(hass, open ? "relief.open" : "relief.closed"),
                    open ? "green" : "grey",
                    open ? "mdi:door-open" : "mdi:door-closed",
                  ),
                  trailing: formatDistance(hass, numberAttr(f.distance_km)),
                });
              }),
              label,
            )}`;
        })}
        ${
          councils.own
            ? html`<h3 class="list-title">${t(hass, "relief.own_council")}</h3>
                ${list(councilRows(hass, [councils.own]), t(hass, "relief.own_council"))}`
            : nothing
        }
        ${
          councils.nearby.length
            ? html`<h3 class="list-title">${t(hass, "relief.councils")}</h3>
                ${list(councilRows(hass, councils.nearby), t(hass, "relief.councils"))}`
            : nothing
        }
      </div>`;
  }
}
