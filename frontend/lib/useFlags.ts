"use client";

import { useEffect, useState } from "react";
import { SURFACES, type Flags } from "@/lib/flags";

const ALL_OFF = Object.fromEntries(SURFACES.map((s) => [s, false])) as Flags;

/** Server-evaluated flags for client components. Until the server answers, everything is off. */
export function useFlags(): Flags {
  const [flags, setFlags] = useState<Flags>(ALL_OFF);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/flags", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<Flags>) : ALL_OFF))
      .then((f) => !cancelled && setFlags({ ...ALL_OFF, ...f }))
      .catch(() => undefined); // stay off on any failure
    return () => {
      cancelled = true;
    };
  }, []);
  return flags;
}
