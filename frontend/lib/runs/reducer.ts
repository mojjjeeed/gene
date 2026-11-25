/**
 * The one reducer for every long run. Every stage (search, triage, parse, extract, design...) emits the
 * same event types, so the UI never needs a per-stage reducer. Applying events is idempotent: replays
 * after a reconnect overlap what we already hold, and duplicates are ignored by `seq`.
 */
import type { RunEvent } from "@a9/contracts";

export type RunStatus = "idle" | "running" | "needs_input" | "finished" | "failed";
export type Connection = "connecting" | "open" | "reconnecting" | "closed";

export interface CoverageNote {
  source: string;
  reason: string;
}

export interface StageState {
  status: "running" | "finished";
  done: number;
  total: number | null;
  /** Partial results as they landed, in order: the UI renders these before the stage is done. */
  partials: Record<string, unknown>[];
}

export interface RunState {
  runId: string | null;
  /** Highest seq applied. Sent back as Last-Event-ID on reconnect. */
  lastSeq: number;
  status: RunStatus;
  stages: Record<string, StageState>;
  /** Stage names in the order they first appeared. */
  stageOrder: string[];
  needsInput: { stage: string; question: Record<string, unknown> } | null;
  /** Named reduced-coverage notes, e.g. a source that timed out. Shown, never hidden. */
  coverageNotes: CoverageNote[];
  error: string | null;
  /** True if an event arrived with a seq gap. Should never happen; surfaced rather than ignored. */
  gap: boolean;
  connection: Connection;
}

export type RunAction =
  | { type: "reset"; runId: string | null }
  | { type: "event"; event: RunEvent }
  | { type: "connection"; state: Connection };

export const initialRunState: RunState = {
  runId: null,
  lastSeq: 0,
  status: "idle",
  stages: {},
  stageOrder: [],
  needsInput: null,
  coverageNotes: [],
  error: null,
  gap: false,
  connection: "connecting",
};

const isTerminal = (s: RunStatus) => s === "finished" || s === "failed";

function withStage(state: RunState, name: string, patch: Partial<StageState>): RunState {
  const existing = state.stages[name];
  const stage: StageState = existing
    ? { ...existing, ...patch }
    : { status: "running", done: 0, total: null, partials: [], ...patch };
  return {
    ...state,
    stages: { ...state.stages, [name]: stage },
    stageOrder: existing ? state.stageOrder : [...state.stageOrder, name],
  };
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "reset":
      return { ...initialRunState, runId: action.runId };
    case "connection":
      // A closed stream after a terminal event is just the end; don't let it overwrite anything.
      return { ...state, connection: action.state };
    case "event": {
      const e = action.event;
      if (e.seq <= state.lastSeq) return state; // duplicate from a replay overlap
      if (isTerminal(state.status)) return state;

      let next: RunState = {
        ...state,
        lastSeq: e.seq,
        gap: state.gap || e.seq !== state.lastSeq + 1,
        // Any event after an interrupt means the answer arrived and the same run resumed.
        status: state.status === "needs_input" ? "running" : state.status === "idle" ? "running" : state.status,
        needsInput: null,
      };

      switch (e.type) {
        case "stage_started":
          return withStage(next, e.stage, { status: "running" });
        case "progress":
          return withStage(next, e.stage, { done: e.done, total: e.total });
        case "partial_result": {
          const prior = next.stages[e.stage]?.partials ?? [];
          return withStage(next, e.stage, { partials: [...prior, e.payload] });
        }
        case "needs_input":
          next = withStage(next, e.stage, {});
          return { ...next, status: "needs_input", needsInput: { stage: e.stage, question: e.question } };
        case "stage_finished":
          return withStage(next, e.stage, { status: "finished" });
        case "run_failed":
          return { ...next, status: "failed", error: e.error };
        case "run_finished":
          return { ...next, status: "finished", coverageNotes: e.coverage_notes };
      }
    }
  }
}
