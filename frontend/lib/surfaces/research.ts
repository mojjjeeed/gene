/**
 * The research dossier surface (paper list, briefing, citations) behind one interface.
 *
 * Every source - the fixture, the legacy FastAPI backend, and the live A9 pipeline - answers the same
 * call and returns the same shape, so the UI never knows which one it got. When a source cannot
 * answer it throws SourceUnavailable and the fixture takes over, labelled as sample data.
 */
import { buildDemoDossier } from "@/lib/fixtures/research";
import type { Flags } from "@/lib/flags";
import type { ResearchResponse } from "@/lib/research";

export interface ResearchContext {
  signal: AbortSignal;
  /** Date.now() when the request began, for execution_time_seconds. */
  started: number;
}

export interface ResearchSource {
  getDossier(query: string, ctx: ResearchContext): Promise<ResearchResponse>;
}

/** The source could not answer; `reason` is shown to the user. */
export class SourceUnavailable extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

/** The caller went away (navigated off, started a new search). Nothing to answer. */
export class RequestAborted extends Error {}

/* ---------------------------------- fixture ---------------------------------- */

export const fixtureResearchSource: ResearchSource = {
  async getDossier(query, { started }) {
    return {
      ...buildDemoDossier(query),
      execution_time_seconds: +((Date.now() - started) / 1000).toFixed(2),
      data_source: "demo",
    } satisfies ResearchResponse;
  },
};

/* ------------------------- legacy FastAPI backend (today) ------------------------- */

// The FastAPI backend fans out to six public APIs (ChEMBL alone can take ~30s), so allow it time to answer.
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_TIMEOUT_MS = 60_000;

export const legacyResearchSource: ResearchSource = {
  async getDossier(query, { signal }) {
    try {
      const backendResponse = await fetch(`${BACKEND_URL}/api/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal: AbortSignal.any([signal, AbortSignal.timeout(BACKEND_TIMEOUT_MS)]),
      });

      if (backendResponse.ok) {
        const data = await backendResponse.json();
        return { ...data, data_source: "live" };
      }
      throw new SourceUnavailable(`Backend responded with HTTP ${backendResponse.status}`);
    } catch (backendError) {
      if (backendError instanceof SourceUnavailable) throw backendError;
      if (signal.aborted) throw new RequestAborted();
      const timedOut = backendError instanceof DOMException && backendError.name === "TimeoutError";
      const fallbackReason = timedOut
        ? `Backend did not answer within ${BACKEND_TIMEOUT_MS / 1000}s`
        : `Backend is not reachable at ${BACKEND_URL}`;
      console.warn(`[Next.js API] ${fallbackReason}; serving clearly-labelled demo data.`, backendError);
      throw new SourceUnavailable(fallbackReason);
    }
  },
};

/* ------------------------- live A9 pipeline (arrives in M0.9) ------------------------- */

export const a9ResearchSource: ResearchSource = {
  async getDossier() {
    throw new SourceUnavailable("The live A9 paper list is not available yet");
  },
};

/* ---------------------------------- selection ---------------------------------- */

/** Try `primary`; if it is unavailable, serve the fixture and say why. */
export function withFixtureFallback(primary: ResearchSource, fixture: ResearchSource): ResearchSource {
  return {
    async getDossier(query, ctx) {
      try {
        return await primary.getDossier(query, ctx);
      } catch (e) {
        if (!(e instanceof SourceUnavailable)) throw e;
        return { ...(await fixture.getDossier(query, ctx)), fallback_reason: e.reason };
      }
    },
  };
}

/** Flag off: exactly today's behaviour. Flag on: the live A9 pipeline, with the same fixture fallback. */
export function researchSource(flags: Flags): ResearchSource {
  return withFixtureFallback(flags.paper_list ? a9ResearchSource : legacyResearchSource, fixtureResearchSource);
}
