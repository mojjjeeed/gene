/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * Whether a paper meets a search plan's criteria, with the reason. A user's verdict overrides the model's and both are kept.
 */
export interface ScreeningVerdict {
  verdict: "include" | "exclude" | "unsure";
  reason: string;
  decided_by: "model" | "user";
  /**
   * Which model or heuristic decided. Required when decided_by is model.
   */
  model: string | null;
}
