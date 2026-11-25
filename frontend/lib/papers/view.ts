/**
 * Pure helpers for the paper list: what to show, in which state, and how the corpus maps onto the
 * dossier shape the existing workspace reads. Kept free of React and of server-only code so it is
 * easy to test.
 */
import type { Paper, PaperList } from "@a9/contracts";

export type Filter = "kept" | "include" | "unsure" | "unscreened" | "exclude" | "all";

/** "kept" is everything not excluded: excluded papers stay one click away, never gone. */
export function filterPapers(papers: Paper[], filter: Filter): Paper[] {
  switch (filter) {
    case "all":
      return papers;
    case "kept":
      return papers.filter((p) => p.verdict.effective !== "exclude");
    default:
      return papers.filter((p) => p.verdict.effective === filter);
  }
}

export type ListState =
  | { kind: "none" } //          no run yet
  | { kind: "searching"; shown: number } // run in progress, results so far
  | { kind: "waiting" } //       run parked for the user (plan approval)
  | { kind: "failed" } //        the run itself failed
  | { kind: "empty" } //         finished, nothing found
  | { kind: "ready" };

export function listState(list: PaperList): ListState {
  const run = list.run;
  if (!run) return { kind: "none" };
  if (run.status === "failed") return { kind: "failed" };
  if (run.status === "needs_input") return { kind: "waiting" };
  if (run.status !== "finished") return list.counts.total ? { kind: "searching", shown: list.counts.total } : { kind: "searching", shown: 0 };
  return list.counts.total ? { kind: "ready" } : { kind: "empty" };
}

/** A corpus is partial while the run is still going, or if any source was down, slow or cut short. */
export function isPartial(list: PaperList): boolean {
  const run = list.run;
  return !!run && (run.status !== "finished" || run.coverage_notes.length > 0);
}

/** "Retracted", "Withdrawn", ... or null when there is nothing to flag. */
export function retractionLabel(p: Paper): string | null {
  switch (p.retraction.status) {
    case "retracted":
      return "Retracted";
    case "withdrawn":
      return "Withdrawn";
    case "expression_of_concern":
      return "Expression of concern";
    default:
      return null;
  }
}

export function licenceLabel(p: Paper): string {
  return p.licence ? `Licence: ${p.licence}` : "Licence unknown";
}

/* ----------------- the bridge to the existing workspace's dossier shape ----------------- */

export interface DossierCitation {
  citation_index: number;
  id: string;
  title: string;
  source: string;
  authors: string[];
  year: string;
  url: string;
  doi?: string;
  abstract?: string;
  evidence_quote?: string;
}

const SOURCE_NAMES: Record<string, string> = {
  europe_pmc: "Europe PMC",
  pubmed: "PubMed",
  openalex: "OpenAlex",
  crossref: "Crossref",
  arxiv: "arXiv",
  biorxiv: "bioRxiv",
  medrxiv: "medRxiv",
};

export function sourceName(source: string | undefined): string {
  return source ? (SOURCE_NAMES[source] ?? source) : "Unknown source";
}

function firstSentence(text: string | null): string | undefined {
  if (!text) return undefined;
  const m = text.match(/^(.+?[.!?])(\s|$)/);
  return (m ? m[1] : text.slice(0, 200)).trim();
}

/** Excluded papers are left out of the briefing view but counted in it; the paper list still has them. */
export function toCitations(list: PaperList): DossierCitation[] {
  return filterPapers(list.papers, "kept").map((p, i) => ({
    citation_index: i + 1,
    id: p.id,
    title: p.retraction.status !== "none" ? `[${retractionLabel(p)}] ${p.title}` : p.title,
    source: sourceName(p.sources[0]),
    authors: p.authors,
    year: p.year ? String(p.year) : "",
    url: p.url,
    doi: p.doi ?? undefined,
    abstract: p.abstract ?? undefined,
    evidence_quote: firstSentence(p.abstract),
  }));
}

/** A plain account of what the search found. It states facts from the corpus and synthesises nothing. */
export function coverageSummary(list: PaperList): string {
  const c = list.counts;
  const lines = [
    `Found **${c.total}** papers: ${c.include} included, ${c.unsure} unsure, ${c.unscreened} not yet screened, ${c.exclude} excluded.`,
  ];
  if (c.retracted) lines.push(`**${c.retracted}** ${c.retracted === 1 ? "paper is" : "papers are"} retracted, withdrawn or carry an expression of concern. They are flagged, not removed.`);
  if (list.run && list.run.status !== "finished") lines.push(`The search is **not finished** (${list.run.status.replace("_", " ")}); this list is partial.`);
  for (const n of list.run?.coverage_notes ?? []) lines.push(`- **Reduced coverage:** ${sourceName(n.source)}: ${n.reason}`);
  return lines.join("\n");
}
