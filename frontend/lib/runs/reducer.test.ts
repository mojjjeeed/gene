import type { RunEvent } from "@a9/contracts";
import { describe, expect, it } from "vitest";
import { initialRunState, runReducer, type RunState } from "./reducer";

const ts = "2026-01-01T00:00:00Z";
const base = { run_id: "r1", ts };

const started = (seq: number, stage = "search"): RunEvent => ({ ...base, seq, type: "stage_started", stage });
const progress = (seq: number, done: number, total: number | null = 10, stage = "search"): RunEvent => ({
  ...base, seq, type: "progress", stage, done, total,
});

const apply = (events: RunEvent[], from: RunState = initialRunState) =>
  events.reduce((s, event) => runReducer(s, { type: "event", event }), from);

describe("runReducer", () => {
  it("tracks stages in the order they appear, with progress", () => {
    const s = apply([started(1), progress(2, 3), started(3, "triage"), progress(4, 1, null, "triage")]);
    expect(s.stageOrder).toEqual(["search", "triage"]);
    expect(s.stages.search).toMatchObject({ status: "running", done: 3, total: 10 });
    expect(s.stages.triage).toMatchObject({ done: 1, total: null });
    expect(s.status).toBe("running");
    expect(s.lastSeq).toBe(4);
    expect(s.gap).toBe(false);
  });

  it("ignores duplicates, so a replay that overlaps what we hold changes nothing", () => {
    const first = apply([started(1), progress(2, 1), progress(3, 2)]);
    const replayed = apply([progress(2, 1), progress(3, 2)], first);
    expect(replayed).toBe(first);
  });

  it("converges: live events and a reconnect-replay of the whole backlog give the same state", () => {
    const events = [started(1), progress(2, 1), progress(3, 2), progress(4, 3)];
    const live = apply(events);
    const droppedAfterTwo = apply(events.slice(0, 2));
    const afterReconnect = apply(events.slice(2), droppedAfterTwo); // server replays seq > lastSeq
    const fullReplay = apply(events, droppedAfterTwo); // or even the whole thing again
    expect(afterReconnect).toEqual(live);
    expect(fullReplay).toEqual(live);
  });

  it("flags a seq gap instead of hiding it", () => {
    expect(apply([started(1), progress(3, 1)]).gap).toBe(true);
  });

  it("accumulates partial results in order", () => {
    const s = apply([
      started(1),
      { ...base, seq: 2, type: "partial_result", stage: "search", payload: { kept: 3 } },
      { ...base, seq: 3, type: "partial_result", stage: "search", payload: { kept: 9 } },
    ]);
    expect(s.stages.search.partials).toEqual([{ kept: 3 }, { kept: 9 }]);
  });

  it("parks on needs_input and resumes on the next event of the same run", () => {
    const parked = apply([
      started(1, "plan"),
      { ...base, seq: 2, type: "needs_input", stage: "plan", question: { kind: "approve_plan" } },
    ]);
    expect(parked.status).toBe("needs_input");
    expect(parked.needsInput).toEqual({ stage: "plan", question: { kind: "approve_plan" } });
    const resumed = apply([progress(3, 0, null, "search")], parked);
    expect(resumed.status).toBe("running");
    expect(resumed.needsInput).toBeNull();
  });

  it("finishes with named coverage notes so reduced coverage is visible", () => {
    const s = apply([
      started(1),
      { ...base, seq: 2, type: "stage_finished", stage: "search" },
      { ...base, seq: 3, type: "run_finished", coverage_notes: [{ source: "arxiv", reason: "timeout" }] },
    ]);
    expect(s.status).toBe("finished");
    expect(s.stages.search.status).toBe("finished");
    expect(s.coverageNotes).toEqual([{ source: "arxiv", reason: "timeout" }]);
  });

  it("records a failure and then ignores anything that arrives after a terminal event", () => {
    const failed = apply([started(1), { ...base, seq: 2, type: "run_failed", error: "database lost" }]);
    expect(failed).toMatchObject({ status: "failed", error: "database lost" });
    expect(apply([progress(3, 1)], failed)).toBe(failed);
  });

  it("reset starts a clean state for a new run", () => {
    const s = runReducer(apply([started(1)]), { type: "reset", runId: "r2" });
    expect(s).toEqual({ ...initialRunState, runId: "r2" });
  });

  it("tracks the connection separately from the run", () => {
    const s = runReducer(initialRunState, { type: "connection", state: "reconnecting" });
    expect(s.connection).toBe("reconnecting");
    expect(s.status).toBe("idle");
  });
});
