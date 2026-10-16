import { html, nothing, type TemplateResult } from "lit";
import { KEY } from "../const";
import { stateFor } from "../ha/entities";
import { formatDistance, isUnavailable, listAttr, numberAttr, safeUrl, stringAttr } from "../ha/format";
import { t, type TranslationKey } from "../localize/localize";
import { alert, badge, empty, header, list, row } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm } from "../types";
import { baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

interface FacilityItem {
  id?: string;
  facility_type?: string;
  name?: string;
  suburb?: string;
  address?: string;
  status?: string;
  distance_km?: number | null;
}

interface CouncilItem {
  name?: string;
  url?: string;
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

/** Relief facilities grouped by type, plus links to nearby council disaster dashboards. */
export class ReliefCard extends DisasterCard {
  protected readonly titleKey = "relief.title" as const;

  protected override entityKeys() {
    return [KEY.reliefFacilitiesCount, KEY.highestWarningLevel, KEY.weatherWarningsCount];
  }

  static getConfigForm(): LovelaceConfigForm {
    return { schema: baseSchema(), computeLabel, computeHelper, assertConfig: (c) => this.validateConfig(c) };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getCardSize(): number {
    return 5;
  }

  protected renderBody(hass: HomeAssistant, _config: BaseCardConfig): TemplateResult {
    const stateObj = stateFor(hass, this.deviceId, KEY.reliefFacilitiesCount);
    const levelState = stateFor(hass, this.deviceId, KEY.highestWarningLevel);
    const warningsState = stateFor(hass, this.deviceId, KEY.weatherWarningsCount);
    const head = header({
      title: this.cardTitle(),
      icon: "mdi:home-heart",
      detailsLabel: t(hass, "action.details"),
      onDetails: stateObj ? () => this.moreInfo(stateObj.entity_id) : undefined,
    });
    if (isUnavailable(stateObj)) {
      return html`${head}<div class="content">
          ${alert("warning", t(hass, stateObj ? "state.unavailable" : "state.entity_missing"))}
        </div>`;
    }
    const facilities = listAttr<FacilityItem>(stateObj!.attributes.facilities).sort(
      (a, b) => (numberAttr(a.distance_km) ?? Infinity) - (numberAttr(b.distance_km) ?? Infinity),
    );
    const councils = listAttr<CouncilItem>(
      levelState?.attributes.nearby_councils ?? warningsState?.attributes.nearby_councils,
    ).filter((c) => stringAttr(c.name) || stringAttr(c.url));

    return html`${head}
      <div class="content">
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
          councils.length
            ? html`<h3 class="list-title">${t(hass, "relief.councils")}</h3>
                ${list(
                  councils.map((c) => {
                    const name = stringAttr(c.name) ?? stringAttr(c.url) ?? "";
                    const url = safeUrl(c.url);
                    return row({
                      icon: "mdi:view-dashboard-outline",
                      tone: "blue",
                      headline: name,
                      supporting: url ? new URL(url).hostname : undefined,
                      link: url,
                      linkLabel: `${t(hass, "action.open_link")}: ${name}`,
                    });
                  }),
                  t(hass, "relief.councils"),
                )}`
            : nothing
        }
      </div>`;
  }
}
