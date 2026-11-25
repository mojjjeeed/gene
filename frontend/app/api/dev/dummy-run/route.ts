import { NotAuthenticated, agentsFetch, currentUserId, devEndpointsEnabled } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

/** Dev only: start the ten-step dummy job so the event stream can be exercised end to end. */
export async function POST(req: Request) {
  if (!devEndpointsEnabled()) return new Response("Not found", { status: 404 });
  let userId: string;
  try {
    userId = currentUserId();
  } catch (e) {
    if (e instanceof NotAuthenticated) return new Response("Unauthorized", { status: 401 });
    throw e;
  }
  const body = await req.json().catch(() => ({}));
  try {
    const upstream = await agentsFetch("/dev/dummy-run", {
      method: "POST",
      userId,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return new Response(upstream.body, { status: upstream.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return new Response("Agents service unavailable", { status: 502 });
  }
}
