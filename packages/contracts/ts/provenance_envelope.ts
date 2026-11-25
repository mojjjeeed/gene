/* GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`. */

/**
 * Carried by every stored unit (chunk, claim). Nothing enters the index without a complete envelope; a citation is a lookup against it.
 */
export interface ProvenanceEnvelope {
  paper_id: string;
  /**
   * Heading path from the document root, e.g. ["Methods", "Assay"].
   *
   * @minItems 1
   */
  section_path: [string, ...string[]];
  page: number;
  char_start: number;
  char_end: number;
  parser_version: string;
  extraction_model: string;
  prompt_version: string;
  run_id: string;
}
