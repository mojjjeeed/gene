import { agentsJson } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

/** Latest search plan for a conversation. */
export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  return agentsJson(`/conversations/${encodeURIComponent(id)}/plan`);
}

/** Start planning: creates a run that builds a plan and parks for approval. */
export async function POST(req: Request, { params }: Ctx) {
  const { id } = await params;
  return agentsJson(`/conversations/${encodeURIComponent(id)}/plan`, { method: "POST", body: await req.json().catch(() => ({})) });
}
