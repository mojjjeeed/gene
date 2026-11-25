import { devEndpointsEnabled } from "@/lib/server/agents";
import { startTopic } from "@/lib/server/topics";

export const dynamic = "force-dynamic";

/** Dev only: create a user, project and conversation, then start planning a topic. */
export async function POST(req: Request) {
  if (!devEndpointsEnabled()) return new Response("Not found", { status: 404 });
  const { topic } = (await req.json().catch(() => ({}))) as { topic?: string };
  if (!topic?.trim()) return Response.json({ error: "topic is required" }, { status: 400 });
  const result = await startTopic(topic.trim());
  return result.ok
    ? Response.json({ conversation_id: result.conversation_id, run_id: result.run_id })
    : new Response(result.message, { status: result.status });
}
