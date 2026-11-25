/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * A durable unit of long-running work, created in the agent service and reported back as events.
 */
export interface Run {
  id: string;
  conversation_id: string;
  kind: "ingest" | "design" | "dossier";
  status: "queued" | "running" | "needs_input" | "failed" | "finished";
  created_at: string;
  /**
   * Named reduced-coverage notes. A source outage appears here, never as a run failure.
   */
  coverage_notes: CoverageNote[];
}
export interface CoverageNote {
  /**
   * Named source, e.g. europe_pmc.
   */
  source: string;
  reason: string;
}
