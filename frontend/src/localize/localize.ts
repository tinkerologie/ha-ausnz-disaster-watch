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

/**
 * Translate a count: uses `<key>_one` when the language's plural rule for `count` is
 * "one" and that key exists, else `key`. `{count}` is replaced by `formatted` (or `count`).
 */
export function tCount(
  hass: HomeAssistant | undefined,
  key: TranslationKey,
  count: number,
  formatted: string = String(count),
): string {
  const lang = hass?.locale?.language || hass?.language || "en";
  let rule = "other";
  try {
    rule = new Intl.PluralRules(lang).select(count);
  } catch {
    rule = count === 1 ? "one" : "other";
  }
  const one = `${key}_one`;
  const chosen = rule === "one" && one in en ? (one as TranslationKey) : key;
  return t(hass, chosen, { count: formatted });
}
