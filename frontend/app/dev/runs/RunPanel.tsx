"use client";

import { useState } from "react";
import { useRunEvents } from "@/lib/runs/useRunEvents";

export default function RunPanel() {
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useRunEvents(runId);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch("/api/dev/dummy-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ steps: 10, step_delay: 0.8 }),
      });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      setRunId((await res.json()).run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl p-8 font-mono text-sm">
      <h1 className="mb-4 text-lg font-semibold">Run stream (dev)</h1>
      <button onClick={start} disabled={starting} className="rounded border px-3 py-1 disabled:opacity-50">
        {starting ? "Starting…" : "Start dummy run"}
      </button>
      {error && <p className="mt-3 text-red-600">{error}</p>}

      {runId && (
        <section className="mt-6 space-y-3">
          <p>run {runId.slice(0, 8)} · status <b>{run.status}</b> · connection {run.connection} · seq {run.lastSeq}</p>
          {run.gap && <p className="text-red-600">Event gap detected.</p>}
          {run.stageOrder.map((name) => {
            const s = run.stages[name];
            const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
            return (
              <div key={name}>
                <div>{name}: {s.status} ({s.done}/{s.total ?? "?"})</div>
                <div className="h-2 w-full rounded bg-neutral-200">
                  <div className="h-2 rounded bg-emerald-600 transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
          {run.error && <p className="text-red-600">{run.error}</p>}
          {run.coverageNotes.map((n) => (
            <p key={n.source}>Reduced coverage: {n.source} ({n.reason})</p>
          ))}
        </section>
      )}
    </main>
  );
}
