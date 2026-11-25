/**
 * Shared types and helpers for the research dossier returned by /api/research.
 */

export interface CitationItem {
  citation_index: number;
  id: string;
  title: string;
  source: string;
  authors: string[] | string;
  year: string;
  url: string;
  doi?: string;
  pmid?: string;
  abstract?: string;
  evidence_quote?: string;
}

export interface BriefingSection {
  id: string;
  title: string;
  content: string;
}

export interface ReasoningLog {
  timestamp: string;
  agent: string;
  thought: string;
  action?: string;
  status?: string;
}

/** "live" = served by the FastAPI backend, "demo" = built-in sample data used when the backend is unavailable. */
export type DataSource = "live" | "demo";

export interface ResearchResponse {
  success: boolean;
  query: string;
  execution_time_seconds: number;
  data_source: DataSource;
  fallback_reason?: string;
  notebook_data: {
    sections: BriefingSection[];
    citations: CitationItem[];
    source_count: number;
  };
  ranked_documents?: CitationItem[];
  reasoning_logs: ReasoningLog[];
}

/** Tailwind classes for a source badge (PubMed, bioRxiv, ...) in either theme. */
export function sourceBadgeClass(source: string | undefined, isDark: boolean): string {
  const s = (source || "").toLowerCase();
  if (s.includes("pubmed")) return isDark ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" : "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (s.includes("biorxiv") || s.includes("medrxiv")) return isDark ? "bg-purple-500/15 text-purple-300 border-purple-500/30" : "bg-purple-50 text-purple-700 border-purple-200";
  if (s.includes("chembl")) return isDark ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" : "bg-cyan-50 text-cyan-700 border-cyan-200";
  if (s.includes("arxiv")) return isDark ? "bg-rose-500/15 text-rose-300 border-rose-500/30" : "bg-rose-50 text-rose-700 border-rose-200";
  if (s.includes("pubchem")) return isDark ? "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" : "bg-indigo-50 text-indigo-700 border-indigo-200";
  if (s.includes("web") || s.includes("trial")) return isDark ? "bg-amber-500/15 text-amber-300 border-amber-500/30" : "bg-amber-50 text-amber-700 border-amber-200";
  return isDark ? "bg-blue-500/15 text-blue-300 border-blue-500/30" : "bg-blue-50 text-blue-700 border-blue-200";
}

export function formatAuthors(authors: string[] | string | undefined, max = 3): string {
  if (!authors) return "";
  if (typeof authors === "string") return authors;
  if (authors.length <= max) return authors.join(", ");
  return `${authors.slice(0, max).join(", ")} +${authors.length - max} more`;
}
