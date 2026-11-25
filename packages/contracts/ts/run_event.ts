/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * The one event schema for every long run. seq is monotonic per run; the stream replays from Last-Event-ID.
 */
export type RunEvent = StageStarted | Progress | PartialResult | NeedsInput | StageFinished | RunFailed | RunFinished;

export interface StageStarted {
  type: "stage_started";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  stage: string;
}
export interface Progress {
  type: "progress";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  stage: string;
  done: number;
  total: number | null;
}
export interface PartialResult {
  type: "partial_result";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  stage: string;
  payload: {
    [k: string]: unknown;
  };
}
export interface NeedsInput {
  type: "needs_input";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  stage: string;
  /**
   * Interrupt payload; the answer resumes the same thread.
   */
  question: {
    [k: string]: unknown;
  };
}
export interface StageFinished {
  type: "stage_finished";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  stage: string;
}
export interface RunFailed {
  type: "run_failed";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  error: string;
}
export interface RunFinished {
  type: "run_finished";
  run_id: string;
  seq: number;
  ts: string;
  trace_id?: string;
  coverage_notes: {
    source: string;
    reason: string;
  }[];
}
