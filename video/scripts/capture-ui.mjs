/**
 * Capture high-resolution TraceForge UI frames from the local frontend.
 * Does not touch SigNoz authentication.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../assets/captures");
const base = process.env.TRACEFORGE_WEB_URL ?? "http://127.0.0.1:3000";
const lockRun = "50ef7693-1eb8-4050-8ae8-1de5c76f83b2";
const latencyRun = "45674c9c-bc70-4e64-9664-8bb9ae0ad1bf";
const controlRun = "a53f317c-a4c9-4843-8441-9cb3fa0f3da9";

const shots = [
  { name: "control-room.png", url: `${base}/`, waitText: "Recent runs" },
  { name: "lock-release-proof.png", url: `${base}/runs/${lockRun}/proof`, waitText: "SHIP" },
  { name: "lock-live.png", url: `${base}/runs/${lockRun}`, waitText: "Release proof" },
  { name: "lock-diagnosis.png", url: `${base}/runs/${lockRun}/diagnosis`, waitText: null },
  { name: "lock-patch.png", url: `${base}/runs/${lockRun}/patch`, waitText: null },
  { name: "lock-evidence.png", url: `${base}/runs/${lockRun}/evidence`, waitText: null },
  { name: "latency-release-proof.png", url: `${base}/runs/${latencyRun}/proof`, waitText: "SHIP" },
  { name: "control-release-proof.png", url: `${base}/runs/${controlRun}/proof`, waitText: "SHIP" },
];

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
});

page.on("pageerror", (err) => console.error("pageerror:", err.message));

const results = [];
for (const shot of shots) {
  try {
    await page.goto(shot.url, { waitUntil: "domcontentloaded", timeout: 90_000 });
    if (shot.waitText) {
      await page.getByText(shot.waitText, { exact: false }).first().waitFor({
        timeout: 45_000,
        state: "visible",
      });
    } else {
      await page.waitForTimeout(4000);
    }
    await page.waitForTimeout(800);
    const body = await page.locator("body").innerText();
    if (body.includes("couldn't load") || body.includes("Application error")) {
      throw new Error(`error page for ${shot.url}: ${body.slice(0, 120)}`);
    }
    const dest = path.join(outDir, shot.name);
    await page.screenshot({ path: dest, fullPage: false, type: "png" });
    results.push({ name: shot.name, ok: true, bytes: (await import("node:fs")).statSync(dest).size });
    console.log(`captured ${shot.name}`);
  } catch (error) {
    results.push({ name: shot.name, ok: false, error: String(error) });
    console.error(`failed ${shot.name}: ${error}`);
  }
}

await browser.close();
console.log(JSON.stringify(results, null, 2));
