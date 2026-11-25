"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import PaperList from "@/components/papers/PaperList";
import PlanEditor from "@/components/plan/PlanEditor";
import { useRunEvents } from "@/lib/runs/useRunEvents";

/**
 * The conversation and run ids live in the URL, so reopening this link on another device shows the
 * same plan in the same state.
 */
export default function PlanPanel() {
  const router = useRouter();
  const params = useSearchParams();
  const conversationId = params.get("c");
  const runId = params.get("r");
  const run = useRunEvents(runId);
  const [topic, setTopic] = useState("EGFR T790M resistance in lung cancer");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    const res = await fetch("/api/dev/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }) });
    if (!res.ok) return setError(`${res.status} ${await res.text()}`);
    const { conversation_id, run_id } = (await res.json()) as { conversation_id: string; run_id: string };
    router.replace(`/dev/plan?c=${conversation_id}&r=${run_id}`);
  }

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-8 text-sm">
      <h1 className="text-lg font-semibold">Search plan approval (dev)</h1>
      {!conversationId && (
        <div className="flex gap-2">
          <input value={topic} onChange={(e) => setTopic(e.target.value)} className="flex-1 rounded border px-2 py-1" />
          <button onClick={start} className="rounded border px-3 py-1">Plan it</button>
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}
      {conversationId && (
        <>
          <p className="font-mono">run {run.status} · {run.connection} · seq {run.lastSeq}{run.needsInput ? " · waiting for your approval" : ""}</p>
          {run.status !== "idle" && <PlanEditor key={run.needsInput?.question.plan_id as string | undefined} conversationId={conversationId} />}
          {run.stages.plan?.status === "finished" && <PaperList conversationId={conversationId} refreshKey={run.lastSeq} />}
        </>
      )}
    </main>
  );
}
