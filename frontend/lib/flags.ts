/**
 * Feature flags, one per surface. Evaluated on the server from the environment, default off.
 *
 * "Off" means the surface behaves exactly as it did before the live system existed (fixtures, or the
 * legacy backend with fixture fallback). A surface is switched on only after its phase gate passes.
 * Client code never reads the environment: it asks /api/flags.
 */
export const SURFACES = [
  "topic_entry",
  "search_plan",
  "paper_list",
  "paper_detail",
  "chat_answers",
  "citations",
  "molecule_cards",
  "human_effect_panel",
  "dossier_export",
  "progress",
] as const;

export type Surface = (typeof SURFACES)[number];
export type Flags = Record<Surface, boolean>;

const ON = new Set(["1", "true", "on", "yes"]);

export function flagVar(surface: Surface): string {
  return `A9_FLAG_${surface.toUpperCase()}`;
}

export function getFlags(env: Record<string, string | undefined> = process.env): Flags {
  return Object.fromEntries(
    SURFACES.map((s) => [s, ON.has((env[flagVar(s)] ?? "").trim().toLowerCase())]),
  ) as Flags;
}
