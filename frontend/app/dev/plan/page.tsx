import { notFound } from "next/navigation";
import { Suspense } from "react";
import { devEndpointsEnabled } from "@/lib/server/agents";
import PlanPanel from "./PlanPanel";

export const dynamic = "force-dynamic";

/** Dev-only page for the plan approval flow. 404s unless A9_ENABLE_DEV_ENDPOINTS=1. */
export default function DevPlanPage() {
  if (!devEndpointsEnabled()) notFound();
  return (
    <Suspense>
      <PlanPanel />
    </Suspense>
  );
}
