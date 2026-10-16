/**
 * Australia and New Zealand Disaster Watch card suite (#43).
 *
 * One bundle, registered by the integration as a Lovelace resource, defines ten focused
 * cards and the all-in-one `custom:ausnz-disaster-card`, and lists each in the card picker.
 */
import { ALL_IN_ONE_TAG, CARD_TAGS, DOCUMENTATION_URL, type SectionKey } from "./const";
import { t, type TranslationKey } from "./localize/localize";
import { AllInOneCard } from "./cards/all-in-one";
import { CamerasCard } from "./cards/cameras";
import { ConditionsCard } from "./cards/conditions";
import { FireDangerCard } from "./cards/fire-danger";
import { IncidentsCard } from "./cards/incidents";
import { MapCard } from "./cards/map-card";
import { OutagesCard } from "./cards/outages";
import { ReliefCard } from "./cards/relief";
import { RoadsCard } from "./cards/roads";
import { StatusCard } from "./cards/status";
import { WarningsCard } from "./cards/warnings";

const FOCUSED: Record<SectionKey, CustomElementConstructor> = {
  status: StatusCard,
  incidents: IncidentsCard,
  warnings: WarningsCard,
  fire_danger: FireDangerCard,
  outages: OutagesCard,
  roads: RoadsCard,
  conditions: ConditionsCard,
  relief: ReliefCard,
  cameras: CamerasCard,
  map: MapCard,
};

const cards: { tag: string; ctor: CustomElementConstructor; key: string }[] = [
  { tag: ALL_IN_ONE_TAG, ctor: AllInOneCard, key: "all" },
  ...(Object.keys(FOCUSED) as SectionKey[]).map((key) => ({ tag: CARD_TAGS[key], ctor: FOCUSED[key], key })),
];

window.customCards = window.customCards || [];
for (const { tag, ctor, key } of cards) {
  if (!customElements.get(tag)) customElements.define(tag, ctor);
  if (!window.customCards.some((card) => card.type === tag)) {
    window.customCards.push({
      type: tag,
      name: t(undefined, `card.${key}.name` as TranslationKey),
      description: t(undefined, `card.${key}.description` as TranslationKey),
      preview: true,
      documentationURL: DOCUMENTATION_URL,
    });
  }
}
