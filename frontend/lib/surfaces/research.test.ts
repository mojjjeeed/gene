import { afterEach, describe, expect, it, vi } from "vitest";
import { getFlags } from "@/lib/flags";
import {
  SourceUnavailable,
  a9ResearchSource,
  fixtureResearchSource,
  legacyResearchSource,
  researchSource,
  type ResearchSource,
} from "./research";

const ctx = () => ({ signal: new AbortController().signal, started: Date.now() });

afterEach(() => vi.unstubAllGlobals());

describe("the fixture and the live source are interchangeable", () => {
  // Compile-time: all three satisfy one interface.
  const sources: Record<string, ResearchSource> = {
    fixture: fixtureResearchSource,
    legacy: legacyResearchSource,
    a9: a9ResearchSource,
  };

  it("the fixture answers with the full response shape the UI reads", async () => {
    const r = await sources.fixture.getDossier("EGFR", ctx());
    expect(r).toMatchObject({ success: true, query: "EGFR", data_source: "demo" });
    expect(r.notebook_data.citations.length).toBeGreaterThan(0);
    expect(r.notebook_data.sections.length).toBeGreaterThan(0);
    expect(r.ranked_documents).toBeDefined();
    expect(r.reasoning_logs.length).toBeGreaterThan(0);
  });

  it("the not-yet-built live source says so instead of returning empty data", async () => {
    await expect(sources.a9.getDossier("EGFR", ctx())).rejects.toBeInstanceOf(SourceUnavailable);
  });
});

describe("paper_list flag on", () => {
  it("skips the legacy backend, serves the fixture, and labels it with why", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const r = await researchSource(getFlags({ A9_FLAG_PAPER_LIST: "1" })).getDossier("EGFR", ctx());
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(r.data_source).toBe("demo");
    expect(r.fallback_reason).toBe("The live A9 paper list is not available yet");
  });
});

describe("paper_list flag off", () => {
  it("asks the legacy backend first", async () => {
    const fetchSpy = vi.fn(async () => new Response(JSON.stringify({ success: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);
    const r = await researchSource(getFlags({})).getDossier("EGFR", ctx());
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(r.data_source).toBe("live");
  });
});
