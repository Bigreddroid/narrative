// Headless smoke test of the running dev app (http://localhost:5173).
// Validates the code-split routes load live and the app reaches real data.
// Run: node web/scripts/smoke.mjs   (dev server + backend must be up)
import { chromium } from "playwright";

const BASE = process.env.SMOKE_BASE || "http://localhost:5173";
const results = [];
const consoleErrors = [];
const pageErrors = [];

function check(name, cond) {
  results.push({ name, ok: !!cond });
  console.log(`  ${cond ? "ok " : "XX "} ${name}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => pageErrors.push(e.message));

try {
  // 1. Landing (eager chunk)
  const landing = await page.goto(`${BASE}/`, { waitUntil: "networkidle", timeout: 20000 });
  check("landing responds 200", landing && landing.status() === 200);
  check("landing rendered a root node", await page.$("#root *") !== null);

  // 2. World view (lazy chunk; PrivateRoute auto dev-logs-in)
  await page.goto(`${BASE}/world`, { waitUntil: "networkidle", timeout: 30000 });
  // Give the auto dev-login + first data fetch a moment to resolve.
  await page.waitForTimeout(3500);
  const worldText = await page.innerText("body");
  check("world view left the loading spinner", worldText.trim().length > 40);
  check("world view did not redirect to landing/auth", /\/world/.test(page.url()));

  // 3. A token was acquired and stored (proves dev auto-login ran)
  const token = await page.evaluate(() => localStorage.getItem("narrative_token"));
  check("auth token present in localStorage (narrative_token)", !!token);

  // 3b. With that token, an authenticated API call must succeed (proves the
  // 401s were just the pre-login race, not a persistent auth failure).
  const authedStatus = await page.evaluate(async (t) => {
    const r = await fetch("/api/v1/exposure", { headers: { Authorization: `Bearer ${t}` } });
    return r.status;
  }, token);
  check("authenticated /exposure call returns 200", authedStatus === 200);

  // 4. Settings (separate lazy chunk) loads without crashing
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1000);
  check("settings route rendered", (await page.innerText("body")).trim().length > 20);

  check("no uncaught page errors", pageErrors.length === 0);

  // 5. Reload /world with the token already in localStorage (the real
  // logged-in-user scenario). This load should NOT produce 401s — if it
  // does, auth attachment is broken beyond the first-mount race.
  const before401 = consoleErrors.filter((e) => /401/.test(e)).length;
  await page.goto(`${BASE}/world`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);
  const after401 = consoleErrors.filter((e) => /401/.test(e)).length;
  check("warm reload (token present) adds no new 401s", after401 === before401);
} catch (err) {
  check(`navigation threw: ${err.message}`, false);
} finally {
  await browser.close();
}

if (consoleErrors.length) {
  console.log(`\n  console.error output (${consoleErrors.length}):`);
  consoleErrors.slice(0, 10).forEach((e) => console.log(`    - ${e.slice(0, 200)}`));
}
if (pageErrors.length) {
  console.log(`\n  uncaught page errors (${pageErrors.length}):`);
  pageErrors.slice(0, 10).forEach((e) => console.log(`    - ${e.slice(0, 200)}`));
}

const failed = results.filter((r) => !r.ok).length;
console.log(`\nsmoke: ${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
