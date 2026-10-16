#!/usr/bin/env node
/**
 * `npm run lint:drift` (#42): every HA design token (`--ha-*`, palette and theme
 * variables) and every `ha-*` element the cards use must exist in the installed Home
 * Assistant frontend, so a future HA release cannot silently break styling.
 *
 * Looks for `hass_frontend` in HASS_FRONTEND, else in the repository's `.local/ha-venv`,
 * else in `~/.local/ha-venv` (the two virtualenv locations the scripts support).
 * An explicit HASS_FRONTEND that does not exist is an error. Without one, it skips (exit 0)
 * with a notice when no installed frontend is found, e.g. in the Node-only CI job, unless
 * LINT_DRIFT_REQUIRED=1 is set: `script/check` sets it, so a missing frontend fails there.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

function findFrontend() {
  if (process.env.HASS_FRONTEND) return process.env.HASS_FRONTEND;
  for (const venv of [join(root, "..", ".local", "ha-venv"), join(homedir(), ".local", "ha-venv")]) {
    const lib = join(venv, "lib");
    if (!existsSync(lib)) continue;
    for (const py of readdirSync(lib)) {
      const candidate = join(lib, py, "site-packages", "hass_frontend", "frontend_latest");
      if (existsSync(candidate)) return candidate;
    }
  }
  return undefined;
}

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (name.endsWith(".ts")) yield path;
  }
}

/** Variables the cards read that HA itself defines (not ones the cards define). */
const OWN_VARIABLES = new Set(["--tone"]);

const frontend = findFrontend();
if (process.env.HASS_FRONTEND && !(existsSync(frontend) && statSync(frontend).isDirectory())) {
  console.error(`lint:drift: HASS_FRONTEND=${frontend} is not a directory.`);
  process.exit(1);
}
if (!frontend) {
  if (process.env.LINT_DRIFT_REQUIRED === "1") {
    console.error("lint:drift: no installed hass_frontend found (set HASS_FRONTEND).");
    process.exit(1);
  }
  console.log("lint:drift: no installed hass_frontend found (set HASS_FRONTEND); skipped.");
  process.exit(0);
}

const tokens = new Set();
const elements = new Set();
for (const file of walk(join(root, "src"))) {
  const text = readFileSync(file, "utf8");
  for (const [, name] of text.matchAll(/var\((--[a-z0-9-]+)/g)) if (!OWN_VARIABLES.has(name)) tokens.add(name);
  for (const [, name] of text.matchAll(/--(?:ha|mdc|md)-[a-z0-9-]+(?=\s*:)/g)) tokens.add(name);
  for (const [, tag] of text.matchAll(/<(ha-[a-z-]+)/g)) elements.add(tag);
  for (const [, tag] of text.matchAll(/["'](ha-[a-z-]+)["'],?\s*$/gm)) elements.add(tag);
}
// Palette names built at runtime by toneColor().
for (const tone of ["red", "orange", "amber", "yellow", "green", "blue", "purple", "grey"]) tokens.add(`--${tone}-color`);

let corpus = "";
for (const name of readdirSync(frontend)) {
  if (name.endsWith(".js")) corpus += readFileSync(join(frontend, name), "utf8");
}

const missing = [];
for (const token of tokens) if (!corpus.includes(token)) missing.push(`token ${token}`);
for (const tag of elements) if (!corpus.includes(`"${tag}"`)) missing.push(`element <${tag}>`);

if (missing.length) {
  console.error(`lint:drift: not found in ${frontend}:\n  ${missing.join("\n  ")}`);
  process.exit(1);
}
console.log(`lint:drift: ${tokens.size} tokens and ${elements.size} elements verified against ${frontend}.`);
