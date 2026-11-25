/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * One record as returned by a literature source adapter, before identity resolution and dedup.
 */
export interface LiteratureRecord {
  source: "europe_pmc" | "pubmed" | "openalex" | "crossref" | "arxiv" | "biorxiv" | "medrxiv" | "fixture";
  /**
   * The source's own identifier for the record.
   */
  source_id: string;
  title: string;
  abstract: string | null;
  authors: string[];
  year: number | null;
  journal: string | null;
  /**
   * Lower-case, no URL prefix.
   */
  doi: string | null;
  pmid: string | null;
  /**
   * Upper-case with the PMC prefix, e.g. PMC1234567.
   */
  pmcid: string | null;
  /**
   * Without version suffix.
   */
  arxiv_id: string | null;
  /**
   * Where a reader can open the record. Must resolve.
   */
  url: string;
  /**
   * As reported by the source. null means unknown, never assumed open.
   */
  licence: string | null;
  is_open_access: boolean | null;
  is_preprint: boolean;
  publication_types: string[];
}
