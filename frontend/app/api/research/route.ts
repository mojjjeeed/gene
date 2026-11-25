import { NextRequest, NextResponse } from "next/server";
import { getFlags } from "@/lib/flags";
import { RequestAborted, researchSource } from "@/lib/surfaces/research";

export async function POST(req: NextRequest) {
  const started = Date.now();

  try {
    const body = await req.json().catch(() => ({}));
    const query: string = typeof body?.query === "string" ? body.query.trim() : "";

    if (!query) {
      return NextResponse.json({ error: "Query cannot be empty" }, { status: 400 });
    }

    // Which source answers is decided by the per-surface flag (default off = today's behaviour:
    // the legacy backend, then clearly-labelled sample data). See lib/surfaces/research.ts.
    try {
      const dossier = await researchSource(getFlags()).getDossier(query, { signal: req.signal, started });
      return NextResponse.json(dossier);
    } catch (e) {
      if (e instanceof RequestAborted) {
        // The user navigated away or started a new search; nothing to answer.
        return new NextResponse(null, { status: 499 });
      }
      throw e;
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to process research request";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
