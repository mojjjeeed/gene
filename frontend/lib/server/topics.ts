import "server-only";
import { agentsJson, devEndpointsEnabled } from "./agents";

export type StartResult =
  | { ok: true; conversation_id: string; run_id: string }
  | { ok: false; status: number; message: string };

async function json<T>(res: Response): Promise<T> {
  return (await res.json()) as T;
}

/**
 * Start a research topic: a project, a conversation, and a run that builds a search plan and parks for
 * the user's approval. While there is no auth provider the user row is created on demand, and only when
 * dev endpoints are enabled; otherwise the user must already exist.
 */
export async function startTopic(topic: string): Promise<StartResult> {
  const fail = async (res: Response): Promise<StartResult> => ({ ok: false, status: res.status, message: await res.text() });

  if (devEndpointsEnabled()) {
    const user = await agentsJson("/dev/user", { method: "POST" });
    if (!user.ok) return fail(user);
  }
  const project = await agentsJson("/projects", { method: "POST", body: { name: topic.slice(0, 80) } });
  if (!project.ok) return fail(project);
  const conversation = await agentsJson("/conversations", { method: "POST", body: { project_id: (await json<{ id: string }>(project)).id } });
  if (!conversation.ok) return fail(conversation);
  const conversation_id = (await json<{ id: string }>(conversation)).id;
  const run = await agentsJson(`/conversations/${conversation_id}/plan`, { method: "POST", body: { topic } });
  if (!run.ok) return fail(run);
  return { ok: true, conversation_id, run_id: (await json<{ run_id: string }>(run)).run_id };
}
