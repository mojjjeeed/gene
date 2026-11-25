import { NextResponse } from "next/server";
import { getFlags } from "@/lib/flags";

// Flags are read from the server environment on every request; never cache them.
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(getFlags(), { headers: { "Cache-Control": "no-store" } });
}
