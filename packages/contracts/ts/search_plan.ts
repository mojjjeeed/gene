/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * A structured literature search plan: shown to the user, editable, and approved before any search fires.
 */
export interface SearchPlan {
  topic: string;
  /**
   * @minItems 1
   */
  concepts: [Concept, ...Concept[]];
  include_criteria: string[];
  exclude_criteria: string[];
  date_from: string | null;
  date_to: string | null;
  /**
   * Which planner produced this plan. A stub plan is a placeholder and is labelled as such in the UI.
   */
  generated_by: "stub" | "llm";
  model?: string | null;
}
export interface Concept {
  label: string;
  synonyms: string[];
  mesh_terms: string[];
}
