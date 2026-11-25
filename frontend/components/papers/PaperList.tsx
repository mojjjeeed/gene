"use client";

import type { Paper, PaperList as PaperListData } from "@a9/contracts";
import { useCallback, useEffect, useState } from "react";
import { filterPapers, isPartial, licenceLabel, listState, retractionLabel, sourceName, type Filter } from "@/lib/papers/view";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ok"; list: PaperListData };

async function fetchList(conversationId: string): Promise<Load> {
  try {
    const res = await fetch(`/api/conversations/${conversationId}/papers`, { cache: "no-store" });
    if (res.status === 404) return { status: "error", message: "This conversation was not found." };
    if (!res.ok) return { status: "error", message: `The paper list could not be loaded (HTTP ${res.status}).` };
    return { status: "ok", list: (await res.json()) as PaperListData };
  } catch {
    return { status: "error", message: "The paper list could not be loaded: the service is not reachable." };
  }
}

const FILTERS: { id: Filter; label: string; count: (l: PaperListData) => number }[] = [
  { id: "kept", label: "Kept", count: (l) => l.counts.total - l.counts.exclude },
  { id: "include", label: "Included", count: (l) => l.counts.include },
  { id: "unsure", label: "Unsure", count: (l) => l.counts.unsure },
  { id: "unscreened", label: "Not screened", count: (l) => l.counts.unscreened },
  { id: "exclude", label: "Excluded", count: (l) => l.counts.exclude },
  { id: "all", label: "All", count: (l) => l.counts.total },
];

/**
 * A conversation's corpus. It shows what was found, what was cut and why, where it came from, how it
 * is licensed, and what is wrong with it (retracted, unchecked, partial). Nothing is hidden: excluded
 * papers are one click away and retracted papers stay in the list, flagged.
 *
 * `refreshKey` should change when new run events arrive, so the list follows a search as it happens.
 */
export default function PaperList({ conversationId, refreshKey = 0 }: { conversationId: string; refreshKey?: number }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [filter, setFilter] = useState<Filter>("kept");
  const [open, setOpen] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const reload = useCallback(() => {
    fetchList(conversationId).then((next) => setLoad((prev) => (next.status === "error" && prev.status === "ok" ? prev : next)));
  }, [conversationId]);

  useEffect(() => {
    let cancelled = false;
    fetchList(conversationId).then((next) => {
      // Keep showing the last good list if a refresh fails; only a first-load failure is an error screen.
      if (!cancelled) setLoad((prev) => (next.status === "error" && prev.status === "ok" ? prev : next));
    });
    return () => {
      cancelled = true;
    };
  }, [conversationId, refreshKey]);

  async function setVerdict(paper: Paper, verdict: "include" | "exclude" | "unsure" | null) {
    setSaving(paper.id);
    try {
      const url = `/api/conversations/${conversationId}/papers/${paper.id}/verdict`;
      await fetch(url, verdict ? { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ verdict, reason: "set by user" }) } : { method: "DELETE" });
      reload();
    } finally {
      setSaving(null);
    }
  }

  if (load.status === "loading") return <p className="text-sm">Loading papers…</p>;
  if (load.status === "error") {
    return (
      <div role="alert" className="space-y-2 rounded border border-red-300 p-3 text-sm text-red-700">
        <p>{load.message}</p>
        <button onClick={reload} className="rounded border px-2 py-1">Try again</button>
      </div>
    );
  }

  const { list } = load;
  const state = listState(list);
  const notes = list.run?.coverage_notes ?? [];
  const shown = filterPapers(list.papers, filter);

  return (
    <section className="space-y-3 text-sm" aria-label="Papers">
      {state.kind === "searching" && <p role="status" className="rounded bg-sky-50 p-2 text-sky-800">Still searching: {state.shown} papers so far. This list is partial and will keep filling in.</p>}
      {state.kind === "waiting" && <p role="status" className="rounded bg-sky-50 p-2 text-sky-800">Waiting for you to approve the search plan before anything is searched.</p>}
      {state.kind === "failed" && <p role="alert" className="rounded bg-red-50 p-2 text-red-800">The search run failed. {list.counts.total ? `${list.counts.total} papers were found before it stopped.` : "Nothing was found."}</p>}
      {isPartial(list) && notes.length > 0 && (
        <div role="alert" className="rounded border border-amber-400 bg-amber-50 p-2 text-amber-900">
          <p className="font-medium">Reduced coverage: results may be missing papers from these sources.</p>
          <ul className="list-disc pl-5">
            {notes.map((n) => (
              <li key={n.source + n.reason}><b>{sourceName(n.source)}</b>: {n.reason}</li>
            ))}
          </ul>
        </div>
      )}

      {state.kind === "empty" && (
        <p className="rounded border p-3">No papers were found{notes.length ? ", and the sources above did not all answer, so this does not mean there is nothing to find." : "."}</p>
      )}

      {list.counts.total > 0 && (
        <>
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter by screening verdict">
            {FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
                className={`rounded border px-2 py-1 ${filter === f.id ? "bg-neutral-900 text-white" : ""}`}>
                {f.label} ({f.count(list)})
              </button>
            ))}
            {list.counts.retracted > 0 && <span className="self-center font-medium text-red-700">{list.counts.retracted} retracted or flagged</span>}
          </div>
          <ul className="space-y-2">
            {shown.map((p) => (
              <PaperCard key={p.id} paper={p} expanded={open === p.id} onToggle={() => setOpen(open === p.id ? null : p.id)} busy={saving === p.id} onVerdict={setVerdict} />
            ))}
            {shown.length === 0 && <li className="p-2 text-neutral-600">Nothing in this view.</li>}
          </ul>
        </>
      )}
    </section>
  );
}

function PaperCard({ paper: p, expanded, onToggle, busy, onVerdict }: { paper: Paper; expanded: boolean; onToggle: () => void; busy: boolean; onVerdict: (p: Paper, v: "include" | "exclude" | "unsure" | null) => void }) {
  const flag = retractionLabel(p);
  const v = p.verdict;
  return (
    <li className={`rounded border p-3 ${flag ? "border-red-400" : ""} ${v.effective === "exclude" ? "opacity-70" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        {flag && <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">{flag}</span>}
        {p.is_preprint && <span className="rounded border px-1.5 text-xs">Preprint</span>}
        <a href={p.url} target="_blank" rel="noopener noreferrer" className="font-medium underline">{p.title}</a>
      </div>
      <p className="text-neutral-700">
        {[p.authors.slice(0, 3).join(", ") + (p.authors.length > 3 ? " et al." : ""), p.journal, p.year].filter(Boolean).join(" · ") || "Authors unknown"}
      </p>
      <p className="text-xs text-neutral-600">
        Found by {p.sources.map(sourceName).join(", ")} · {licenceLabel(p)}
        {p.is_open_access ? " · Open access" : ""}
        {!p.retraction.checked && p.retraction.status === "none" ? " · Retraction status not checked" : ""}
        {p.merge_reasons.length ? ` · ${p.sources.length > 1 ? "Merged records" : "Duplicate removed"} (${p.merge_reasons.join(", ").replaceAll("_", " ")})` : ""}
      </p>
      {flag && p.retraction.notice_dois.length > 0 && (
        <p className="text-xs text-red-700">
          Notice: {p.retraction.notice_dois.map((d) => <a key={d} href={`https://doi.org/${d}`} target="_blank" rel="noopener noreferrer" className="mr-2 underline">{d}</a>)}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="text-xs">Screening:</span>
        {(["include", "unsure", "exclude"] as const).map((choice) => (
          <button key={choice} disabled={busy} aria-pressed={v.effective === choice} onClick={() => onVerdict(p, choice)}
            className={`rounded border px-2 py-0.5 text-xs ${v.effective === choice ? "bg-neutral-900 text-white" : ""}`}>
            {choice}
          </button>
        ))}
        {v.effective === "unscreened" && <span className="text-xs text-neutral-600">not screened yet</span>}
        {v.user && <button disabled={busy} onClick={() => onVerdict(p, null)} className="text-xs underline">reset to model</button>}
      </div>
      {v.model && <p className="text-xs text-neutral-600">Model said <b>{v.model.verdict}</b>: {v.model.reason}</p>}
      {v.user && <p className="text-xs text-neutral-600">Your verdict: <b>{v.user.verdict}</b></p>}
      {p.abstract && (
        <button onClick={onToggle} className="mt-1 text-xs underline" aria-expanded={expanded}>{expanded ? "Hide abstract" : "Show abstract"}</button>
      )}
      {expanded && p.abstract && <p className="mt-1 whitespace-pre-line text-neutral-800">{p.abstract}</p>}
    </li>
  );
}
