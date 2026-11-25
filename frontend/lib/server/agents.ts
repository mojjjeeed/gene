import "server-only";

/**
 * Server-side client for the Python agents service. The service is never exposed to the browser:
 * route handlers authenticate the user, then call it with an internal key and the user id.
 */
const AGENTS_URL = process.env.AGENTS_URL ?? "http://127.0.0.1:8100";

export class NotAuthenticated extends Error {}

/**
 * Who is calling. There is no auth provider yet (it arrives with the project and conversation
 * endpoints), so outside production this is a fixed development user; in production it refuses.
 */
export function currentUserId(): string {
  const dev = process.env.A9_DEV_USER_ID ?? "00000000-0000-4000-8000-000000000001";
  if (process.env.NODE_ENV === "production" && !process.env.A9_DEV_USER_ID) throw new NotAuthenticated();
  return dev;
}

export function devEndpointsEnabled(): boolean {
  return process.env.A9_ENABLE_DEV_ENDPOINTS === "1";
}

export function agentsFetch(path: string, init: RequestInit & { userId: string }): Promise<Response> {
  const { userId, headers, ...rest } = init;
  return fetch(`${AGENTS_URL}${path}`, {
    ...rest,
    cache: "no-store",
    headers: {
      ...(headers as Record<string, string> | undefined),
      "X-A9-Internal-Key": process.env.A9_INTERNAL_KEY ?? "",
      "X-A9-User-Id": userId,
    },
  });
}
