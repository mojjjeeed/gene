import { agentsJson } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string; paperId: string }> };

const path = async (params: Ctx["params"]) => {
  const { id, paperId } = await params;
  return `/conversations/${encodeURIComponent(id)}/papers/${encodeURIComponent(paperId)}/verdict`;
};

/** Override the model's screening verdict. Body: { verdict: "include" | "exclude" | "unsure", reason?: string }. */
export async function PUT(req: Request, { params }: Ctx) {
  return agentsJson(await path(params), { method: "PUT", body: await req.json().catch(() => ({})) });
}

/** Withdraw the override so the model's verdict applies again. */
export async function DELETE(_req: Request, { params }: Ctx) {
  return agentsJson(await path(params), { method: "DELETE" });
}
