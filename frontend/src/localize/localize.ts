import { en, type TranslationKey } from "./en";
import type { HomeAssistant } from "../types";

type Strings = Partial<Record<TranslationKey, string>>;

/** Translations keyed by language; English is the fallback for missing keys. */
const LANGUAGES: Record<string, Strings> = { en };

export type { TranslationKey };

/** The user's strings and the language tag they belong to (English when not shipped). */
function userStrings(hass: HomeAssistant | undefined): { lang: string; strings: Strings } {
  const lang = hass?.locale?.language || hass?.language || "en";
  if (LANGUAGES[lang]) return { lang, strings: LANGUAGES[lang]! };
  const base = lang.split("-")[0] ?? "en";
  if (LANGUAGES[base]) return { lang: base, strings: LANGUAGES[base]! };
  return { lang: "en", strings: en };
}

/** The template for `key` and the language that supplied it (the same lookup for t and tCount). */
function resolve(hass: HomeAssistant | undefined, key: TranslationKey): { lang: string; strings: Strings; template?: string } {
  const user = userStrings(hass);
  if (user.strings[key] !== undefined) return { ...user, template: user.strings[key] };
  return { lang: "en", strings: en, template: en[key] };
}

function substitute(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

/** Translate `key` for the user's language and substitute `{name}` placeholders. */
export function t(hass: HomeAssistant | undefined, key: TranslationKey, vars?: Record<string, string | number>): string {
  return substitute(resolve(hass, key).template ?? key, vars);
}

function pluralRule(lang: string, count: number): Intl.LDMLPluralRule {
  try {
    return new Intl.PluralRules(lang).select(count);
  } catch {
    return count === 1 ? "one" : "other";
  }
}

/**
 * Translate a count. The plural rule comes from the language that supplies the `key`
 * template (so an English fallback uses English rules), and `<key>_one` is used when that
 * rule is "one" and the same language has the key. `{count}` becomes `formatted`.
 */
export function tCount(
  hass: HomeAssistant | undefined,
  key: TranslationKey,
  count: number,
  formatted: string = String(count),
): string {
  const { lang, strings, template } = resolve(hass, key);
  const one = strings[`${key}_one` as TranslationKey];
  const chosen = pluralRule(lang, count) === "one" && one !== undefined ? one : (template ?? key);
  return substitute(chosen, { count: formatted });
}
