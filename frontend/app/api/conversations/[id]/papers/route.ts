import { agentsJson } from "@/lib/server/agents";

export const dynamic = "force-dynamic";

/** The conversation's corpus: papers with source, licence, retraction state, verdict and counts. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return agentsJson(`/conversations/${encodeURIComponent(id)}/papers`);
}
