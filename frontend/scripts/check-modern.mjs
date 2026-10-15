#!/usr/bin/env node
/**
 * `npm run lint:modern` (#42): fail on deprecated or non-HA-design patterns in the card
 * source. Dependency-free; prints file:line for every finding.
 *
 * Usage: node scripts/check-modern.mjs [dir...]   (default: src)
 *
 * A line may opt out of one rule with a justified marker comment:
 *   // lint-modern-ignore <rule-id>: <reason>
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

/** [rule id, regex, message] — regexes run per line (comments included). */
export const RULES = [
  ["hex-colour", /(^|[^\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b(?![-\w])/, "Hex colour: use HA tokens (--ha-color-*, palette variables)"],
  ["rgb-hsl", /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\s*\(/, "Literal colour function: use HA tokens"],
  ["named-colour", /:\s*(?:white|black|red|green|blue|orange|yellow|grey|gray)\s*[;!]/, "Named colour: use HA tokens"],
  ["paper-var", /--paper-/, "--paper-* variables were removed from HA"],
  ["legacy-elements", /<\/?(?:paper|mwc|iron)-[a-z-]+/, "paper-*/mwc-*/iron-* elements are deprecated: use ha-* components"],
  ["ha-chip", /<ha-chip(?=[\s>])/, "ha-chip was removed: use ha-assist-chip / ha-filter-chip"],
  ["emoji", /\p{Extended_Pictographic}/u, "Emoji: use ha-icon with an mdi: icon"],
  ["unsafe-html", /\b(?:unsafeHTML|unsafeSVG|innerHTML|outerHTML|insertAdjacentHTML)\b/, "Raw HTML injection: render with Lit templates"],
  ["custom-card-helpers", /from\s+["']custom-card-helpers["']/, "custom-card-helpers is unmaintained: use HA's own APIs"],
  ["decorators", /^\s*@(?:customElement|property|state|query)\b/, "Decorators: use static properties with declare fields"],
  ["camera-proxy", /\/api\/camera_proxy\//, "Bare camera proxy URL (401): use the entity_picture attribute"],
  ["href-hash", /href=["']#["']/, "href=\"#\" is not a control: use a button"],
  ["internal-href", /href=["']\/(?!\/)/, "Internal href reloads the page: use navigate() or more-info"],
  ["div-click", /<(?:div|span|li|td|img)\b[^>]*@click=/, "Click handler on a non-interactive element: use a button or HA component"],
  ["legacy-card", /\baus-disaster-card\b/, "The legacy aus-disaster-card alias was removed"],
  ["mdc-vars", /--mdc-(?!icon-size\b)[a-z-]+/, "--mdc-* variables are legacy (only --mdc-icon-size is still read by ha-svg-icon)"],
  ["get-card-size-only", /getLayoutOptions\s*\(/, "getLayoutOptions is deprecated: use getGridOptions"],
];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (/\.(?:ts|js|mjs)$/.test(name) && !name.endsWith(".d.ts")) yield path;
  }
}

export function check(text, file = "<input>") {
  const findings = [];
  text.split("\n").forEach((line, i) => {
    const ignored = /lint-modern-ignore ([a-z-]+): \S/.exec(line)?.[1];
    for (const [id, regex, message] of RULES) {
      if (id !== ignored && regex.test(line)) findings.push({ file, line: i + 1, id, message, text: line.trim() });
    }
  });
  return findings;
}

function main() {
  const dirs = process.argv.slice(2);
  const targets = (dirs.length ? dirs : ["src"]).map((d) => join(root, d));
  const findings = [];
  let files = 0;
  for (const dir of targets) {
    for (const file of walk(dir)) {
      files += 1;
      findings.push(...check(readFileSync(file, "utf8"), relative(root, file)));
    }
  }
  for (const f of findings) console.error(`${f.file}:${f.line}: [${f.id}] ${f.message}\n    ${f.text}`);
  if (findings.length) {
    console.error(`\nlint:modern: ${findings.length} finding(s) in ${files} file(s).`);
    process.exit(1);
  }
  console.log(`lint:modern: ${files} file(s) clean.`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
