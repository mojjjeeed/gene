/**
 * M0.4 "Done when": with every flag off the app is byte-identical to today's behaviour.
 *
 * The goldens in __golden__/research-route.json were captured from the route handler BEFORE it was
 * refactored behind the surface interface. This test replays the same requests (clock and timezone
 * pinned, the legacy backend mocked) and compares status and body byte for byte.
 * Regenerate only on purpose: UPDATE_GOLDEN=1 pnpm --filter frontend test
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/research/route";

process.env.TZ = "UTC";
const GOLDEN = path.join(__dirname, "__golden__", "research-route.json");

const backendOk = {
  success: true,
  query: "q",
  execution_time_seconds: 1.23,
  notebook_data: { sections: [], citations: [], source_count: 0 },
  ranked_documents: [],
  reasoning_logs: [],
};

type Backend = "down" | "timeout" | "http500" | "ok";
interface Case {
  name: string;
  body: unknown;
  backend: Backend;
  abort?: boolean;
}

const cases: Case[] = [
  { name: "demo-egfr", body: { query: "EGFR T790M resistance" }, backend: "down" },
  { name: "demo-kras", body: { query: "KRAS G12D pancreatic" }, backend: "down" },
  { name: "demo-generic", body: { query: "Alzheimer's amyloid clearance" }, backend: "down" },
  { name: "demo-generic-needs-encoding", body: { query: "a&b c/d?" }, backend: "down" },
  { name: "backend-timeout", body: { query: "EGFR" }, backend: "timeout" },
  { name: "backend-http-500", body: { query: "EGFR" }, backend: "http500" },
  { name: "backend-ok", body: { query: "EGFR" }, backend: "ok" },
  { name: "empty-query", body: { query: "   " }, backend: "down" },
  { name: "no-body", body: undefined, backend: "down" },
  { name: "client-aborted", body: { query: "EGFR" }, backend: "down", abort: true },
];

function mockBackend(kind: Backend, controller: AbortController, abort?: boolean) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (abort) controller.abort();
      if (kind === "down") throw new TypeError("fetch failed");
      if (kind === "timeout") throw new DOMException("timed out", "TimeoutError");
      if (kind === "http500") return new Response("boom", { status: 500 });
      return new Response(JSON.stringify(backendOk), { status: 200, headers: { "content-type": "application/json" } });
    }),
  );
}

async function run(c: Case) {
  const controller = new AbortController();
  mockBackend(c.backend, controller, c.abort);
  const req = new NextRequest("http://localhost/api/research", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: c.body === undefined ? undefined : JSON.stringify(c.body),
    signal: controller.signal,
  });
  const res = await POST(req);
  return { status: res.status, body: await res.text() };
}

describe("/api/research with every flag off", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T12:00:00Z"));
    for (const k of Object.keys(process.env)) if (k.startsWith("A9_FLAG_")) delete process.env[k];
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  if (process.env.UPDATE_GOLDEN === "1") {
    it("writes goldens", async () => {
      const out: Record<string, unknown> = {};
      for (const c of cases) out[c.name] = await run(c);
      writeFileSync(GOLDEN, JSON.stringify(out, null, 2) + "\n");
    });
    return;
  }

  const golden = JSON.parse(readFileSync(GOLDEN, "utf8")) as Record<string, { status: number; body: string }>;
  it.each(cases)("$name is byte-identical to the captured behaviour", async (c) => {
    expect(await run(c)).toEqual(golden[c.name]);
  });
});
