import { agentsJson } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  return agentsJson(`/plans/${encodeURIComponent(id)}`);
}

/** Edit (creates a new version) and/or approve. Body: { plan?: SearchPlan, approve?: boolean }. */
export async function PATCH(req: Request, { params }: Ctx) {
  const { id } = await params;
  return agentsJson(`/plans/${encodeURIComponent(id)}`, { method: "PATCH", body: await req.json().catch(() => ({})) });
}
