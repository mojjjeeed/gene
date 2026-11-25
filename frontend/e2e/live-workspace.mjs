// Manual end-to-end check of the LIVE workspace in a real browser (headless Chromium). Not part of CI.
//
// Needs the stack running with fixture sources, and the frontend with the flag on:
//   make dev-up
//   A9_INTERNAL_KEY=k A9_ENABLE_DEV_ENDPOINTS=1 make api
//   A9_INTERNAL_KEY=k A9_SOURCES=fixture,fixture_down,fixture_partial A9_RETRACTION_CHECK=fixture make worker
//   A9_INTERNAL_KEY=k A9_ENABLE_DEV_ENDPOINTS=1 A9_FLAG_PAPER_LIST=1 pnpm --filter frontend dev -p 3100
// then, once:  npm i playwright && npx playwright install chromium   (outside the repo is fine)
//   node frontend/e2e/live-workspace.mjs
import { chromium } from "playwright";
import assert from "node:assert/strict";

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 1000 } });
const problems = [];
p.on("pageerror", (e) => problems.push("pageerror: " + e.message));
p.on("console", (m) => m.type() === "error" && problems.push("console: " + m.text().slice(0, 160)));
const step = (s) => console.log("✓", s);
const TOPIC = "EGFR T790M resistance in lung cancer";

await p.goto("http://localhost:3100/", { waitUntil: "networkidle", timeout: 120000 });
await p.getByRole("button", { name: /open workspace/i }).first().click();
await p.getByPlaceholder(/ask a research question/i).fill(TOPIC);
await p.getByRole("button", { name: "Run research" }).click();
await p.getByRole("heading", { name: TOPIC }).waitFor({ timeout: 30000 });
step("search box launches the live workspace (A9), not the fixture one");

await p.getByText("Waiting for you to approve the search plan").first().waitFor({ timeout: 60000 });
await p.getByText(/Placeholder plan \(no model connected\)/).waitFor();
step("run parks for approval; the plan is labelled as a placeholder");
assert.equal(await p.getByText("Search plan · version 1").count(), 1);
await p.getByText("Waiting for you to approve the search plan").first().waitFor();
assert.equal(await p.getByText("Papers").count() >= 0, true);
await p.screenshot({ path: "1-plan.png", fullPage: true });

await p.getByLabel("Synonyms (comma separated)").first().fill("ERBB1, HER1");
await p.getByRole("button", { name: "Save as new version" }).click();
await p.getByText("Search plan · version 2").waitFor({ timeout: 20000 });
step("editing the plan saves a new version (v2)");

await p.getByRole("button", { name: "Approve and search" }).click();
await p.getByText("Approved").first().waitFor({ timeout: 20000 });
step("approving locks the plan");

await p.getByText(/Finished with reduced coverage/).waitFor({ timeout: 90000 });
step("run finishes, and says it finished WITH reduced coverage");

const banner = p.getByRole("alert").filter({ hasText: "Reduced coverage" });
await banner.waitFor({ timeout: 20000 });
const bannerText = await banner.innerText();
assert.match(bannerText, /fixture_down/);
assert.match(bannerText, /fixture_partial/);
assert.match(bannerText, /HTTP 503/);
step("paper list names both degraded sources and why");

const cards = p.getByRole("listitem").filter({ has: p.getByRole("link") });
await p.getByRole("tab", { name: /Kept \(3\)/ }).waitFor();
assert.equal(await p.locator("section[aria-label='Papers'] li:has(a[target='_blank'])").count(), 3);
step("three papers (five records from two sources, de-duplicated), counts in the filter tabs");

await p.getByText("Retracted", { exact: true }).first().waitFor();
assert.match(await p.getByText(/retracted or flagged/).innerText(), /1 retracted or flagged/);
step("the retracted paper is in the list, flagged");

assert.ok((await p.getByText(/Licence unknown/).count()) >= 3);
assert.ok((await p.getByText(/Merged records|Duplicate removed/).count()) >= 2);
for (const href of await p.locator("section[aria-label='Papers'] a[target='_blank']").evaluateAll((as) => as.map((a) => a.href))) assert.match(href, /^https:\/\//);
step("licence shown as unknown, merges explained, every link is https");
await p.screenshot({ path: "2-papers.png", fullPage: true });

// user override: exclude the first paper, see counts move and the paper stay available
await p.getByRole("button", { name: "exclude", exact: true }).first().click();
await p.getByRole("tab", { name: /Kept \(2\)/ }).waitFor({ timeout: 15000 });
await p.getByRole("tab", { name: /Excluded \(1\)/ }).click();
assert.equal(await p.locator("section[aria-label='Papers'] li:has(a[target='_blank'])").count(), 1);
await p.getByText(/Model said include/).first().waitFor();
step("excluding a paper moves it to Excluded (1) but keeps it; the model's call stays visible");
await p.getByRole("button", { name: "reset to model" }).click();
await p.getByRole("tab", { name: /Kept \(3\)/ }).waitFor({ timeout: 15000 });
step("'reset to model' restores it");

// back button returns to the search screen
await p.getByRole("button", { name: "Back to search" }).click();
await p.getByPlaceholder(/ask a research question/i).waitFor();
step("back returns to the search screen");

console.log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "no console or page errors");
await b.close();
process.exit(problems.length ? 1 : 0);
