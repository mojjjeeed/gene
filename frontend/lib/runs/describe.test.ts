import { describe, expect, it } from "vitest";
import { statusLine, stageProgress } from "./describe";
import { initialRunState, type RunState } from "./reducer";

const run = (over: Partial<RunState>): RunState => ({ ...initialRunState, ...over });

describe("statusLine", () => {
  it("says what is happening in plain words", () => {
    expect(statusLine(run({}))).toBe("Starting…");
    expect(statusLine(run({ lastSeq: 2 }))).toBe("Working…");
    expect(statusLine(run({ status: "needs_input" }))).toBe("Waiting for you to approve the search plan");
    expect(statusLine(run({ status: "running", stageOrder: ["plan", "search"], stages: { plan: { status: "finished", done: 0, total: null, partials: [] }, search: { status: "running", done: 1, total: 3, partials: [] } } }))).toBe("Working: searching sources");
  });

  it("never reports a finished run with gaps as simply finished", () => {
    expect(statusLine(run({ status: "finished" }))).toBe("Finished");
    expect(statusLine(run({ status: "finished", coverageNotes: [{ source: "arxiv", reason: "x" }, { source: "pubmed", reason: "y" }] }))).toBe("Finished with reduced coverage (arxiv, pubmed)");
    expect(statusLine(run({ status: "failed", error: "database lost" }))).toBe("The run failed: database lost");
  });

  it("reports progress only when the total is known", () => {
    const stages = { search: { status: "running" as const, done: 2, total: 7, partials: [] }, triage: { status: "running" as const, done: 1, total: null, partials: [] } };
    expect(stageProgress(run({ stages }), "search")).toBe("2 / 7");
    expect(stageProgress(run({ stages }), "triage")).toBeNull();
    expect(stageProgress(run({ stages }), "nope")).toBeNull();
  });
});
