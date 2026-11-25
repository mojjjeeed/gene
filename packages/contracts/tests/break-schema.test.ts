// M0.1 "Done when": a deliberate schema change breaks compilation on BOTH the TS and Python side.
// Runs the real generator against a mutated copy of the schemas, then type-checks stand-in consumers.
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const pkgDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(pkgDir, "../..");
const env = { ...process.env, UV_PROJECT_ENVIRONMENT: process.env.UV_PROJECT_ENVIRONMENT ?? ".venv-a9" };

function run(cmd: string, args: string[], cwd: string, extraEnv: Record<string, string> = {}) {
  return spawnSync(cmd, args, { cwd, env: { ...env, ...extraEnv }, encoding: "utf8" });
}

/** Copy schemas to a temp dir, optionally mutate them, regenerate there, and type-check consumers. */
function generateAndCheck(mutate?: (schemasDir: string) => void) {
  const work = mkdtempSync(path.join(tmpdir(), "a9-contracts-"));
  const schemas = path.join(work, "schemas");
  cpSync(path.join(pkgDir, "schemas"), schemas, { recursive: true });
  mutate?.(schemas);

  const gen = run("node", [path.join(pkgDir, "scripts/generate.mjs"), "--schemas", schemas, "--out", work], pkgDir);
  expect(gen.status, gen.stdout + gen.stderr).toBe(0);

  cpSync(path.join(pkgDir, "tests/fixtures/consumer.ts"), path.join(work, "consumer.ts"));
  cpSync(path.join(pkgDir, "tests/fixtures/consumer.py"), path.join(work, "consumer.py"));

  const tsc = run(
    path.join(pkgDir, "node_modules/.bin/tsc"),
    ["--noEmit", "--strict", "--skipLibCheck", "--module", "esnext", "--moduleResolution", "bundler", "consumer.ts"],
    work,
  );
  const mypy = run(
    "uv",
    ["run", "--no-sync", "--project", repoRoot, "mypy", "--strict", "--config-file", path.join(repoRoot, "pyproject.toml"), "consumer.py"],
    work,
    { MYPYPATH: path.join(work, "python") },
  );
  return { tsc, mypy };
}

describe("contract change propagation", () => {
  it("control: untouched schemas compile on both sides", () => {
    const { tsc, mypy } = generateAndCheck();
    expect(tsc.status, tsc.stdout + tsc.stderr).toBe(0);
    expect(mypy.status, mypy.stdout + mypy.stderr).toBe(0);
  }, 120_000);

  it("renaming RunEvent.seq breaks both tsc and mypy", () => {
    const { tsc, mypy } = generateAndCheck((schemas) => {
      const file = path.join(schemas, "run-event.json");
      writeFileSync(file, readFileSync(file, "utf8").replaceAll('"seq"', '"sequence"'));
    });
    expect(tsc.status, "tsc should fail").not.toBe(0);
    expect(tsc.stdout).toContain("seq");
    expect(mypy.status, "mypy should fail").not.toBe(0);
    expect(mypy.stdout).toContain("seq");
  }, 120_000);

  it("dropping a provenance field breaks both sides", () => {
    const { tsc, mypy } = generateAndCheck((schemas) => {
      const file = path.join(schemas, "provenance-envelope.json");
      writeFileSync(file, readFileSync(file, "utf8").replaceAll('"page"', '"page_number"'));
    });
    expect(tsc.status).not.toBe(0);
    expect(mypy.status).not.toBe(0);
  }, 120_000);

  it("every schema file has a generated TS and Python module", () => {
    const names = readdirSync(path.join(pkgDir, "schemas")).map((f) => f.replace(/\.json$/, "").replaceAll("-", "_"));
    for (const n of names) {
      expect(readdirSync(path.join(pkgDir, "ts"))).toContain(`${n}.ts`);
      expect(readdirSync(path.join(pkgDir, "python/a9_contracts"))).toContain(`${n}.py`);
    }
  });
});
