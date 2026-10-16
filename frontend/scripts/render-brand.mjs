// Render the brand SVG masters in branding/ to PNG with Playwright's Chromium.
// Usage (from frontend/): node scripts/render-brand.mjs <svg> <out.png> <height>
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const [svgPath, out, heightArg] = process.argv.slice(2);
const svg = readFileSync(svgPath, "utf8");
const [, , vbWidth, vbHeight] = svg.match(/viewBox="([\d.\s-]+)"/)[1].split(/\s+/).map(Number);
const height = Number(heightArg);
const width = Math.round((height * vbWidth) / vbHeight);
const sized = svg.replace(/width="[\d.]+" height="[\d.]+"/, `width="${width}" height="${height}"`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
await page.setContent(`<html><body style="margin:0;background:transparent">${sized}</body></html>`);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: out, omitBackground: true, clip: { x: 0, y: 0, width, height } });
await browser.close();
