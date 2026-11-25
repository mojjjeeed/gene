// Manual check that with every flag OFF the existing workspace runs and the live endpoints do not exist.
// Start the frontend with no A9_FLAG_* set on port 3100, then:  node frontend/e2e/flag-off.mjs
import { chromium } from "playwright";
import assert from "node:assert/strict";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 1000 } });
const problems = [];
p.on("pageerror", (e) => problems.push("pageerror: " + e.message));
const calls = [];
p.on("request", (r) => /\/api\//.test(r.url()) && calls.push(r.method() + " " + new URL(r.url()).pathname));
await p.goto("http://localhost:3100/", { waitUntil: "networkidle", timeout: 120000 });
await p.getByRole("button", { name: /open workspace/i }).first().click();
await p.getByPlaceholder(/ask a research question/i).fill("EGFR T790M resistance in lung cancer");
await p.getByRole("button", { name: "Run research" }).click();
await p.waitForTimeout(6000);
const body = await p.locator("body").innerText();
assert.ok(!/Search plan/.test(body), "the live workspace must not appear");
assert.ok(!calls.some((c) => c.includes("/api/topics")), "no call to the live topic endpoint: " + calls);
assert.ok(calls.some((c) => c === "POST /api/research"), "the existing workspace calls /api/research: " + calls);
console.log("✓ flag off: the existing workspace runs; calls made:", [...new Set(calls)]);
await p.screenshot({ path: "flagoff.png" });
console.log(problems.length ? "PROBLEMS " + problems : "no page errors");
await b.close();
