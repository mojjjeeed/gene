import type { Paper, PaperList } from "@a9/contracts";
import { describe, expect, it } from "vitest";
import { coverageSummary, filterPapers, isPartial, licenceLabel, listState, retractionLabel, sourceName, toCitations } from "./view";

function paper(over: Partial<Paper> & { effective?: Paper["verdict"]["effective"] } = {}): Paper {
  const { effective = "include", ...rest } = over;
  return {
    id: "p", title: "A paper", abstract: "First sentence. Second sentence.", authors: ["Ada Lovelace"], year: 2024, journal: null,
    doi: "10.1/x", url: "https://doi.org/10.1/x", sources: ["europe_pmc"], licence: null, is_open_access: null, is_preprint: false,
    retraction: { status: "none", checked: false, notice_dois: [] },
    verdict: { effective, user: null, model: null }, merge_reasons: [], ...rest,
  };
}

function list(papers: Paper[], run: PaperList["run"] = { id: "r", status: "finished", coverage_notes: [] }): PaperList {
  const n = (k: string) => papers.filter((p) => p.verdict.effective === k).length;
  return {
    conversation_id: "c", run, papers,
    counts: { total: papers.length, include: n("include"), exclude: n("exclude"), unsure: n("unsure"), unscreened: n("unscreened"), retracted: papers.filter((p) => p.retraction.status !== "none").length },
  };
}

describe("filterPapers", () => {
  const papers = [paper({ id: "a", effective: "include" }), paper({ id: "b", effective: "exclude" }), paper({ id: "c", effective: "unscreened" }), paper({ id: "d", effective: "unsure" })];
  it("'kept' is everything not excluded, and excluded papers are one filter away", () => {
    expect(filterPapers(papers, "kept").map((p) => p.id)).toEqual(["a", "c", "d"]);
    expect(filterPapers(papers, "exclude").map((p) => p.id)).toEqual(["b"]);
    expect(filterPapers(papers, "all")).toHaveLength(4);
  });
});

describe("listState and isPartial", () => {
  it("distinguishes every state the UI must render differently", () => {
    expect(listState(list([], null))).toEqual({ kind: "none" });
    expect(listState(list([], { id: "r", status: "running", coverage_notes: [] }))).toEqual({ kind: "searching", shown: 0 });
    expect(listState(list([paper()], { id: "r", status: "running", coverage_notes: [] }))).toEqual({ kind: "searching", shown: 1 });
    expect(listState(list([], { id: "r", status: "needs_input", coverage_notes: [] }))).toEqual({ kind: "waiting" });
    expect(listState(list([], { id: "r", status: "failed", coverage_notes: [] }))).toEqual({ kind: "failed" });
    expect(listState(list([]))).toEqual({ kind: "empty" });
    expect(listState(list([paper()]))).toEqual({ kind: "ready" });
  });

  it("a finished run with a named gap is still partial; a clean finished run is not", () => {
    const gap = { id: "r", status: "finished" as const, coverage_notes: [{ source: "arxiv", reason: "HTTP 503" }] };
    expect(isPartial(list([paper()], gap))).toBe(true);
    expect(isPartial(list([paper()]))).toBe(false);
    expect(isPartial(list([paper()], { id: "r", status: "running", coverage_notes: [] }))).toBe(true);
    expect(isPartial(list([], null))).toBe(false);
  });
});

describe("labels", () => {
  it("flags retraction states and never hides unknown licences", () => {
    expect(retractionLabel(paper())).toBeNull();
    expect(retractionLabel(paper({ retraction: { status: "retracted", checked: true, notice_dois: [] } }))).toBe("Retracted");
    expect(retractionLabel(paper({ retraction: { status: "expression_of_concern", checked: true, notice_dois: [] } }))).toBe("Expression of concern");
    expect(licenceLabel(paper())).toBe("Licence unknown");
    expect(licenceLabel(paper({ licence: "cc by" }))).toBe("Licence: cc by");
    expect(sourceName("europe_pmc")).toBe("Europe PMC");
    expect(sourceName("someone_new")).toBe("someone_new");
  });
});

describe("the bridge to the workspace's dossier shape", () => {
  const retracted = paper({ id: "r", title: "Old claim", retraction: { status: "retracted", checked: true, notice_dois: ["10.1/n"] } });
  const data = list([paper({ id: "a" }), paper({ id: "x", effective: "exclude" }), retracted], { id: "r", status: "finished", coverage_notes: [{ source: "arxiv", reason: "unavailable after 4 attempts (HTTP 503)" }] });

  it("cites every kept paper with a working link, flags retractions in the title, and omits only excluded ones", () => {
    const cites = toCitations(data);
    expect(cites.map((c) => c.id)).toEqual(["a", "r"]);
    expect(cites.map((c) => c.citation_index)).toEqual([1, 2]);
    expect(cites[1].title).toBe("[Retracted] Old claim");
    expect(cites.every((c) => c.url.startsWith("https://"))).toBe(true);
    expect(cites[0]).toMatchObject({ source: "Europe PMC", year: "2024", evidence_quote: "First sentence.", doi: "10.1/x" });
  });

  it("summarises counts and names every coverage gap, without inventing findings", () => {
    const text = coverageSummary(data);
    expect(text).toContain("Found **3** papers: 2 included, 0 unsure, 0 not yet screened, 1 excluded.");
    expect(text).toContain("**1** paper is retracted");
    expect(text).toContain("- **Reduced coverage:** arXiv: unavailable after 4 attempts (HTTP 503)");
    expect(coverageSummary(list([paper()], { id: "r", status: "running", coverage_notes: [] }))).toContain("not finished");
  });
});
