import { agentsJson, devEndpointsEnabled } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

/** Dev only: create a user, project and conversation, then start planning a topic. */
export async function POST(req: Request) {
  if (!devEndpointsEnabled()) return new Response("Not found", { status: 404 });
  const { topic } = (await req.json().catch(() => ({}))) as { topic?: string };
  if (!topic?.trim()) return Response.json({ error: "topic is required" }, { status: 400 });

  const steps: [string, unknown][] = [["/dev/user", undefined]];
  for (const [path] of steps) {
    const r = await agentsJson(path, { method: "POST" });
    if (!r.ok) return r;
  }
  const project = await agentsJson("/projects", { method: "POST", body: { name: "Dev project" } });
  if (!project.ok) return project;
  const conversation = await agentsJson("/conversations", {
    method: "POST",
    body: { project_id: ((await project.json()) as { id: string }).id },
  });
  if (!conversation.ok) return conversation;
  const conversationId = ((await conversation.json()) as { id: string }).id;
  const run = await agentsJson(`/conversations/${conversationId}/plan`, { method: "POST", body: { topic } });
  if (!run.ok) return run;
  return Response.json({ conversation_id: conversationId, run_id: ((await run.json()) as { run_id: string }).run_id });
}
