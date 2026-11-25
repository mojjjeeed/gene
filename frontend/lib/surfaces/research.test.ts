import type { PaperList } from "@a9/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getFlags } from "@/lib/flags";
import {
  SourceUnavailable,
  makeA9ResearchSource,
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
    a9: makeA9ResearchSource(async () => {
      throw new Error("not used here");
    }),
  };

  it("the fixture answers with the full response shape the UI reads", async () => {
    const r = await sources.fixture.getDossier("EGFR", ctx());
    expect(r).toMatchObject({ success: true, query: "EGFR", data_source: "demo" });
    expect(r.notebook_data.citations.length).toBeGreaterThan(0);
    expect(r.notebook_data.sections.length).toBeGreaterThan(0);
    expect(r.ranked_documents).toBeDefined();
    expect(r.reasoning_logs.length).toBeGreaterThan(0);
  });

  it("the live source refuses to answer without a conversation instead of returning empty data", async () => {
    await expect(sources.a9.getDossier("EGFR", ctx())).rejects.toBeInstanceOf(SourceUnavailable);
  });
});

const corpus: PaperList = {
  conversation_id: "c1",
  run: { id: "r1", status: "finished", coverage_notes: [{ source: "arxiv", reason: "unavailable after 4 attempts (HTTP 503)" }] },
  counts: { total: 2, include: 1, exclude: 1, unsure: 0, unscreened: 0, retracted: 0 },
  papers: [
    { id: "p1", title: "Kept paper", abstract: "It works. Truly.", authors: ["A B"], year: 2024, journal: null, doi: "10.1/k", url: "https://doi.org/10.1/k", sources: ["pubmed"], licence: null, is_open_access: null, is_preprint: false, retraction: { status: "none", checked: true, notice_dois: [] }, verdict: { effective: "include", user: null, model: null }, merge_reasons: [] },
    { id: "p2", title: "Cut paper", abstract: null, authors: [], year: null, journal: null, doi: null, url: "https://example.org/c", sources: ["openalex"], licence: null, is_open_access: null, is_preprint: false, retraction: { status: "none", checked: false, notice_dois: [] }, verdict: { effective: "exclude", user: null, model: null }, merge_reasons: [] },
  ],
};

describe("paper_list flag on", () => {
  const on = getFlags({ A9_FLAG_PAPER_LIST: "1" });

  it("serves the real corpus, labelled live, and names the coverage gap", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const fetchPaperList = vi.fn(async () => corpus);
    const r = await researchSource(on, { fetchPaperList }).getDossier("EGFR", { ...ctx(), conversationId: "c1" });
    expect(fetchSpy).not.toHaveBeenCalled(); // the legacy backend is not consulted
    expect(fetchPaperList).toHaveBeenCalledWith("c1", expect.any(AbortSignal));
    expect(r.data_source).toBe("live");
    expect(r.notebook_data.citations.map((c) => c.title)).toEqual(["Kept paper"]);
    expect(r.notebook_data.sections[0].content).toContain("Reduced coverage:** arXiv");
    expect(r.fallback_reason).toBeUndefined();
  });

  it("without a conversation, serves the labelled fixture and says why", async () => {
    const r = await researchSource(on, { fetchPaperList: async () => corpus }).getDossier("EGFR", ctx());
    expect(r.data_source).toBe("demo");
    expect(r.fallback_reason).toBe("The live paper list needs a conversation, and none was given");
  });

  it("when the A9 service is down, serves the labelled fixture with that reason, not an error", async () => {
    const down = async () => {
      throw new SourceUnavailable("The A9 service is not reachable");
    };
    const r = await researchSource(on, { fetchPaperList: down }).getDossier("EGFR", { ...ctx(), conversationId: "c1" });
    expect(r.data_source).toBe("demo");
    expect(r.fallback_reason).toBe("The A9 service is not reachable");
  });

  it("with no service wired at all, still falls back honestly", async () => {
    const r = await researchSource(on).getDossier("EGFR", { ...ctx(), conversationId: "c1" });
    expect(r).toMatchObject({ data_source: "demo", fallback_reason: "The live paper list is not wired to a service here" });
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
