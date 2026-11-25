"use client";

import { ArrowLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import PaperList from "@/components/papers/PaperList";
import PlanEditor from "@/components/plan/PlanEditor";
import ThemeToggle from "@/components/ThemeToggle";
import { stageLabel, stageProgress, statusLine } from "@/lib/runs/describe";
import { useRunEvents } from "@/lib/runs/useRunEvents";

interface A9WorkspaceProps {
  initialQuery: string;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
  onBackToSearch: () => void;
  onOpenApiKeys?: () => void;
}

/**
 * The live research workspace: the topic becomes a search plan the user reviews and approves, then a
 * screened, de-duplicated paper list that fills in as sources answer. It replaces the fixture-backed
 * workspace when the paper_list flag is on. Same props as DrugDiscoveryWorkspace, so the page can swap.
 */
export default function A9Workspace({ initialQuery, theme = "light", onToggleTheme, onBackToSearch }: A9WorkspaceProps) {
  const isDark = theme === "dark";
  const [ids, setIds] = useState<{ conversationId: string; runId: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false); // React strict mode runs effects twice in development: start once
  const run = useRunEvents(ids?.runId ?? null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    fetch("/api/topics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: initialQuery }) })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? `HTTP ${res.status}`);
        const body = (await res.json()) as { conversation_id: string; run_id: string };
        setIds({ conversationId: body.conversation_id, runId: body.run_id });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [initialQuery]);

  const planReady = run.stageOrder.includes("plan");
  const shell = isDark ? "bg-[#121316] text-neutral-100" : "bg-[#FAFAFC] text-neutral-900";

  return (
    <div className={`min-h-screen ${shell}`}>
      <header className="mx-auto flex max-w-4xl items-center gap-3 px-6 py-4">
        <button type="button" onClick={onBackToSearch} className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm" aria-label="Back to search">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold">{initialQuery}</h1>
          <p role="status" className="text-sm opacity-80">{error ? "Could not start" : ids ? statusLine(run) : "Starting…"}</p>
        </div>
        {onToggleTheme && <ThemeToggle theme={theme} onToggle={onToggleTheme} />}
      </header>

      <main className="mx-auto max-w-4xl space-y-4 px-6 pb-16">
        {error && (
          <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
            <p className="font-medium">The research service could not start this search.</p>
            <p>{error}</p>
            <p className="mt-1">Nothing was searched. Check that the agents service and worker are running, then go back and try again.</p>
          </div>
        )}

        {run.stageOrder.length > 0 && (
          <ol className="flex flex-wrap gap-2 text-xs" aria-label="Progress">
            {run.stageOrder.map((stage) => {
              const s = run.stages[stage];
              const progress = stageProgress(run, stage);
              return (
                <li key={stage} className={`rounded-full border px-2.5 py-1 ${s.status === "finished" ? "border-emerald-500 text-emerald-600" : ""}`}>
                  {stageLabel(stage)}{progress ? ` ${progress}` : ""}{s.status === "finished" ? " ✓" : ""}
                </li>
              );
            })}
          </ol>
        )}

        {/* The panels below are light cards on both themes, so the lists stay readable. */}
        {ids && planReady && (
          <details open={run.status === "needs_input"} className="rounded-xl border bg-white p-4 text-neutral-900 shadow-sm">
            <summary className="cursor-pointer text-sm font-medium">Search plan</summary>
            <div className="mt-3">
              <PlanEditor key={run.needsInput ? "pending" : "approved"} conversationId={ids.conversationId} />
            </div>
          </details>
        )}

        {ids && run.stages.plan?.status === "finished" && (
          <section aria-label="Papers" className="rounded-xl border bg-white p-4 text-neutral-900 shadow-sm">
            <PaperList conversationId={ids.conversationId} refreshKey={run.lastSeq} />
          </section>
        )}

        {ids && run.connection === "reconnecting" && <p role="status" className="text-xs opacity-70">Reconnecting to the live updates…</p>}
        <p className="text-xs opacity-60">Research use only. Screening and planning here are placeholders until a language model is connected; every verdict can be overridden.</p>
      </main>
    </div>
  );
}
