"use client";

import type { Concept, SearchPlan } from "@a9/contracts";
import { useCallback, useEffect, useState } from "react";

interface PlanRecord {
  id: string;
  version: number;
  plan: SearchPlan;
  approved: boolean;
  approved_at: string | null;
}

async function fetchLatest(conversationId: string): Promise<{ rec: PlanRecord } | { error: string }> {
  const res = await fetch(`/api/conversations/${conversationId}/plan`, { cache: "no-store" });
  if (res.status === 404) return { error: "No plan yet." };
  if (!res.ok) return { error: `Could not load the plan (${res.status}).` };
  return { rec: (await res.json()) as PlanRecord };
}

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/**
 * The search plan, shown and editable before any search fires. Every save creates a new version;
 * approving it resumes the parked run. State lives on the server, so it can be closed here and
 * reopened from another device.
 */
export default function PlanEditor({ conversationId, onApproved }: { conversationId: string; onApproved?: () => void }) {
  const [record, setRecord] = useState<PlanRecord | null>(null);
  const [draft, setDraft] = useState<SearchPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const apply = useCallback((result: { rec: PlanRecord } | { error: string }) => {
    if ("error" in result) return setMessage(result.error);
    setRecord(result.rec);
    setDraft(result.rec.plan);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchLatest(conversationId).then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [conversationId, apply]);

  async function patch(body: { plan?: SearchPlan; approve?: boolean }) {
    if (!record) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/plans/${record.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 409) {
        setMessage("This plan changed elsewhere. Reloaded the latest version.");
        return apply(await fetchLatest(conversationId));
      }
      if (!res.ok) return setMessage(`Request failed (${res.status}).`);
      const rec = (await res.json()) as PlanRecord;
      setRecord(rec);
      setDraft(rec.plan);
      if (rec.approved) onApproved?.();
    } finally {
      setBusy(false);
    }
  }

  if (!record || !draft) return <p className="text-sm">{message ?? "Loading plan…"}</p>;

  const locked = record.approved;
  const dirty = JSON.stringify(draft) !== JSON.stringify(record.plan);
  const setConcept = (i: number, patchConcept: Partial<Concept>) =>
    setDraft({ ...draft, concepts: draft.concepts.map((c, j) => (j === i ? { ...c, ...patchConcept } : c)) as SearchPlan["concepts"] });

  return (
    <section className="space-y-4 text-sm" aria-label="Search plan">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">Search plan · version {record.version}</h2>
        {draft.generated_by === "stub" && (
          <span className="rounded border border-amber-500 px-2 py-0.5 text-xs text-amber-700">
            Placeholder plan (no model connected): review everything
          </span>
        )}
        {locked && <span className="rounded border border-emerald-600 px-2 py-0.5 text-xs text-emerald-700">Approved</span>}
      </header>

      <div className="space-y-2">
        <h3 className="font-medium">Concepts</h3>
        {draft.concepts.map((c, i) => (
          <div key={i} className="grid gap-1 rounded border p-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1">Concept
              <input disabled={locked} value={c.label} onChange={(e) => setConcept(i, { label: e.target.value })} className="rounded border px-2 py-1" />
            </label>
            <label className="flex flex-col gap-1">Synonyms (comma separated)
              <input disabled={locked} value={c.synonyms.join(", ")} onChange={(e) => setConcept(i, { synonyms: list(e.target.value) })} className="rounded border px-2 py-1" />
            </label>
            <label className="flex flex-col gap-1">MeSH terms
              <input disabled={locked} value={c.mesh_terms.join(", ")} onChange={(e) => setConcept(i, { mesh_terms: list(e.target.value) })} className="rounded border px-2 py-1" />
            </label>
          </div>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">Include (one per line)
          <textarea disabled={locked} rows={3} value={draft.include_criteria.join("\n")} onChange={(e) => setDraft({ ...draft, include_criteria: lines(e.target.value) })} className="rounded border px-2 py-1" />
        </label>
        <label className="flex flex-col gap-1">Exclude (one per line)
          <textarea disabled={locked} rows={3} value={draft.exclude_criteria.join("\n")} onChange={(e) => setDraft({ ...draft, exclude_criteria: lines(e.target.value) })} className="rounded border px-2 py-1" />
        </label>
        <label className="flex flex-col gap-1">From
          <input disabled={locked} type="date" value={draft.date_from ?? ""} onChange={(e) => setDraft({ ...draft, date_from: e.target.value || null })} className="rounded border px-2 py-1" />
        </label>
        <label className="flex flex-col gap-1">To
          <input disabled={locked} type="date" value={draft.date_to ?? ""} onChange={(e) => setDraft({ ...draft, date_to: e.target.value || null })} className="rounded border px-2 py-1" />
        </label>
      </div>

      {!locked && (
        <div className="flex gap-2">
          <button disabled={busy || !dirty} onClick={() => patch({ plan: draft })} className="rounded border px-3 py-1 disabled:opacity-50">
            Save as new version
          </button>
          <button disabled={busy || dirty} onClick={() => patch({ approve: true })} className="rounded bg-emerald-600 px-3 py-1 text-white disabled:opacity-50" title={dirty ? "Save your edits first" : undefined}>
            Approve and search
          </button>
        </div>
      )}
      {message && <p className="text-amber-700">{message}</p>}
    </section>
  );
}
