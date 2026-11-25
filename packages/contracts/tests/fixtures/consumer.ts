// Stand-in consumer of the generated TS contract. If a schema change removes or renames a field
// this reads, `tsc` must fail. Copied next to a freshly generated ts/ by break-schema.test.ts.
import type { ProvenanceEnvelope, Run, RunEvent } from "./ts/index";

export function seqOf(event: RunEvent): number {
  return event.seq;
}

export function runIdOf(run: Run): string {
  return run.id;
}

export function pageOf(envelope: ProvenanceEnvelope): number {
  return envelope.page;
}
