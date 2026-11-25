import { notFound } from "next/navigation";
import { devEndpointsEnabled } from "@/lib/server/agents";
import RunPanel from "./RunPanel";

export const dynamic = "force-dynamic";

/** Dev-only page for watching a run stream. 404s unless A9_ENABLE_DEV_ENDPOINTS=1. */
export default function DevRunsPage() {
  if (!devEndpointsEnabled()) notFound();
  return <RunPanel />;
}
