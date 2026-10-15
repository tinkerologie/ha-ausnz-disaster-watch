import { en, type TranslationKey } from "./en";
import type { HomeAssistant } from "../types";

type Strings = Partial<Record<TranslationKey, string>>;

/** Translations keyed by language; English is the fallback for missing keys. */
const LANGUAGES: Record<string, Strings> = { en };

export type { TranslationKey };

/** Translate `key` for the user's language and substitute `{name}` placeholders. */
export function t(hass: HomeAssistant | undefined, key: TranslationKey, vars?: Record<string, string | number>): string {
  const lang = hass?.locale?.language || hass?.language || "en";
  const strings = LANGUAGES[lang] ?? LANGUAGES[lang.split("-")[0] ?? "en"] ?? en;
  const template = strings[key] ?? en[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}
