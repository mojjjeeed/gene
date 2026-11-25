import { getFlags } from "@/lib/flags";
import { startTopic } from "@/lib/server/topics";

export const dynamic = "force-dynamic";

/**
 * Start researching a topic with the live pipeline. Returns the conversation and run to follow.
 * 404 unless the paper_list flag is on, so with every flag off this endpoint does not exist.
 */
export async function POST(req: Request) {
  if (!getFlags().paper_list) return new Response("Not found", { status: 404 });
  const { topic } = (await req.json().catch(() => ({}))) as { topic?: string };
  if (typeof topic !== "string" || !topic.trim()) return Response.json({ error: "topic is required" }, { status: 400 });
  const result = await startTopic(topic.trim());
  return result.ok
    ? Response.json({ conversation_id: result.conversation_id, run_id: result.run_id })
    : Response.json({ error: result.message || "Could not start the search" }, { status: result.status >= 400 ? result.status : 502 });
}
