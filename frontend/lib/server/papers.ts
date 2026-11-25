import "server-only";
import type { PaperList } from "@a9/contracts";
import { SourceUnavailable } from "@/lib/surfaces/research";
import { agentsFetch, currentUserId } from "./agents";

/** Fetch a conversation's paper list from the agents service, turning every failure into a named reason. */
export async function fetchPaperList(conversationId: string, signal: AbortSignal): Promise<PaperList> {
  let response: Response;
  try {
    response = await agentsFetch(`/conversations/${encodeURIComponent(conversationId)}/papers`, { userId: currentUserId(), signal });
  } catch {
    throw new SourceUnavailable("The A9 service is not reachable");
  }
  if (response.status === 404) throw new SourceUnavailable("That conversation was not found");
  if (!response.ok) throw new SourceUnavailable(`The A9 service responded with HTTP ${response.status}`);
  return (await response.json()) as PaperList;
}
