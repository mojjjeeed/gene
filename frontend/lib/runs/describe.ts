import type { RunState } from "./reducer";

/** One honest line about where a run is, for the header of the workspace. */
export function statusLine(run: RunState): string {
  if (run.status === "failed") return `The run failed${run.error ? `: ${run.error}` : ""}`;
  if (run.status === "needs_input") return "Waiting for you to approve the search plan";
  if (run.status === "finished") {
    return run.coverageNotes.length
      ? `Finished with reduced coverage (${run.coverageNotes.map((n) => n.source).join(", ")})`
      : "Finished";
  }
  const running = run.stageOrder.filter((s) => run.stages[s].status === "running");
  if (running.length) return `Working: ${running.map(stageLabel).join(", ")}`;
  return run.lastSeq === 0 ? "Starting…" : "Working…";
}

const LABELS: Record<string, string> = {
  plan: "planning",
  search: "searching sources",
  resolve: "removing duplicates",
  triage: "screening papers",
  retractions: "checking for retractions",
};

export function stageLabel(stage: string): string {
  return LABELS[stage] ?? stage;
}

/** "3 / 7" style progress for a stage, or null when the total is not known. */
export function stageProgress(run: RunState, stage: string): string | null {
  const s = run.stages[stage];
  return s && s.total ? `${s.done} / ${s.total}` : null;
}
