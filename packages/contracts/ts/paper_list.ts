/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * A conversation's corpus as the paper list shows it: live records with source, licence, retraction state, screening verdict and counts. Excluded and retracted papers are present and labelled, never dropped.
 */
export interface PaperList {
  conversation_id: string;
  /**
   * The latest ingest run, so the UI can show 'still searching' and name reduced coverage. null before any run.
   */
  run: null | ListedRun;
  counts: PaperCounts;
  papers: Paper[];
}
export interface ListedRun {
  id: string;
  status: "queued" | "running" | "needs_input" | "failed" | "finished";
  coverage_notes: ListedCoverageNote[];
}
export interface ListedCoverageNote {
  source: string;
  reason: string;
}
export interface PaperCounts {
  total: number;
  include: number;
  exclude: number;
  unsure: number;
  unscreened: number;
  /**
   * Papers with any retraction, withdrawal or expression of concern.
   */
  retracted: number;
}
export interface Paper {
  id: string;
  title: string;
  abstract: string | null;
  authors: string[];
  year: number | null;
  journal: string | null;
  doi: string | null;
  /**
   * Always present: a DOI link, else the source's own link.
   */
  url: string;
  /**
   * Every source that returned this paper.
   */
  sources: string[];
  /**
   * null means unknown, never assumed open.
   */
  licence: string | null;
  is_open_access: boolean | null;
  is_preprint: boolean;
  retraction: {
    status: "none" | "retracted" | "withdrawn" | "expression_of_concern";
    /**
     * false means not checked, which is different from clean.
     */
    checked: boolean;
    notice_dois: string[];
  };
  verdict: {
    effective: "include" | "exclude" | "unsure" | "unscreened";
    user: null | ListedVerdict;
    model: null | ListedVerdict;
  };
  /**
   * Why several records became this one paper.
   */
  merge_reasons: string[];
}
export interface ListedVerdict {
  verdict: "include" | "exclude" | "unsure";
  reason: string;
}
