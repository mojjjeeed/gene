import { describe, expect, it } from "vitest";
import { SURFACES, flagVar, getFlags } from "./flags";

describe("getFlags", () => {
  it("is all off by default", () => {
    const flags = getFlags({});
    expect(Object.keys(flags).sort()).toEqual([...SURFACES].sort());
    expect(Object.values(flags).every((v) => v === false)).toBe(true);
  });

  it("turns on only the surface whose variable is set", () => {
    const flags = getFlags({ A9_FLAG_PAPER_LIST: "1" });
    expect(flags.paper_list).toBe(true);
    expect(Object.entries(flags).filter(([, v]) => v).map(([k]) => k)).toEqual(["paper_list"]);
  });

  it.each(["1", "true", "TRUE", " on ", "yes"])("treats %j as on", (v) => {
    expect(getFlags({ [flagVar("citations")]: v }).citations).toBe(true);
  });

  it.each(["", "0", "false", "off", "no", "2", "enabled"])("treats %j as off", (v) => {
    expect(getFlags({ [flagVar("citations")]: v }).citations).toBe(false);
  });

  it("ignores unrelated and misspelled variables", () => {
    expect(Object.values(getFlags({ A9_FLAG_NOPE: "1", FLAG_PAPER_LIST: "1", A9_PAPER_LIST: "1" })).some(Boolean)).toBe(false);
  });

  it("has a flag for every surface in the PRD scope table", () => {
    expect(SURFACES).toEqual([
      "topic_entry", "search_plan", "paper_list", "paper_detail", "chat_answers",
      "citations", "molecule_cards", "human_effect_panel", "dossier_export", "progress",
    ]);
  });
});
