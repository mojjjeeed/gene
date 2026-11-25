import { NotAuthenticated, agentsFetch, currentUserId } from "@/lib/server/agents";

// Never cache a stream.
export const dynamic = "force-dynamic";

/** Proxy a run's SSE stream. Forwards Last-Event-ID so a reconnect replays the backlog. */
export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let userId: string;
  try {
    userId = currentUserId();
  } catch (e) {
    if (e instanceof NotAuthenticated) return new Response("Unauthorized", { status: 401 });
    throw e;
  }

  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const lastEventId = req.headers.get("last-event-id");
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;

  let upstream: Response;
  try {
    // Aborting when the browser goes away closes the upstream stream too.
    upstream = await agentsFetch(`/runs/${encodeURIComponent(id)}/events`, { userId, headers, signal: req.signal });
  } catch {
    return new Response("Agents service unavailable", { status: 502 });
  }
  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.status === 404 ? "Run not found" : "Upstream error", {
      status: upstream.status === 404 ? 404 : 502,
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
