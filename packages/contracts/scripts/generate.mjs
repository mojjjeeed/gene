#!/usr/bin/env node
// One generator, two outputs: TypeScript types and Pydantic models, both from packages/contracts/schemas.
//   node scripts/generate.mjs [--schemas <dir>] [--out <dir>]
// Defaults write into this package (ts/ and python/a9_contracts/). Generated files are committed and
// CI fails if they drift from the schemas (make check-generated).
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { compileFromFile } from "json-schema-to-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const pkgDir = path.resolve(here, "..");
const repoRoot = path.resolve(pkgDir, "../..");

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : path.resolve(args[i + 1]);
};
const schemasDir = opt("schemas", path.join(pkgDir, "schemas"));
const outDir = opt("out", pkgDir);
const tsOut = path.join(outDir, "ts");
const pyOut = path.join(outDir, "python", "a9_contracts");

const BANNER = "GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.";
const schemaFiles = readdirSync(schemasDir)
  .filter((f) => f.endsWith(".json"))
  .sort();
const moduleName = (file) => path.basename(file, ".json").replaceAll("-", "_");

// Start from a clean output directory so a deleted schema cannot leave a stale module behind.
const clean = (dir) => {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
};

// --- TypeScript -----------------------------------------------------------------------------
// Compile everything in memory first; only a fully successful compile replaces the committed files.
const tsFiles = new Map();
for (const file of schemaFiles) {
  const ts = await compileFromFile(path.join(schemasDir, file), {
    bannerComment: `/* ${BANNER} */`,
    cwd: schemasDir,
    additionalProperties: false,
    style: { singleQuote: false },
  });
  tsFiles.set(`${moduleName(file)}.ts`, ts);
}
tsFiles.set(
  "index.ts",
  `/* ${BANNER} */\n` + schemaFiles.map((f) => `export * from "./${moduleName(f)}";\n`).join(""),
);
clean(tsOut);
for (const [name, content] of tsFiles) writeFileSync(path.join(tsOut, name), content);

// --- Pydantic -------------------------------------------------------------------------------
// Generate into a temp directory and swap it in only on success, so a failed run (missing uv env,
// bad schema) never leaves the committed models deleted.
const pyTmp = `${pyOut}_generating`;
rmSync(pyTmp, { recursive: true, force: true });
mkdirSync(path.dirname(pyOut), { recursive: true });
const py = spawnSync(
  "uv",
  [
    "run",
    "--no-sync",
    "datamodel-codegen",
    "--input",
    schemasDir,
    "--input-file-type",
    "jsonschema",
    "--output",
    pyTmp,
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--target-python-version",
    "3.12",
    "--use-annotated",
    "--use-standard-collections",
    "--use-union-operator",
    "--field-constraints",
    "--disable-timestamp",
    "--formatters",
    "black",
    "isort",
    "--custom-file-header",
    `# ${BANNER}`,
  ],
  {
    cwd: repoRoot,
    stdio: "inherit",
    // Never fall back to the repo's legacy .venv: A9's Python environment is .venv-a9.
    env: { ...process.env, UV_PROJECT_ENVIRONMENT: process.env.UV_PROJECT_ENVIRONMENT ?? ".venv-a9" },
  },
);
if (py.status !== 0) {
  rmSync(pyTmp, { recursive: true, force: true });
  console.error("datamodel-codegen failed (is `uv sync` done? try `make setup`). Python models left untouched.");
  process.exit(py.status ?? 1);
}
rmSync(pyOut, { recursive: true, force: true });
renameSync(pyTmp, pyOut);
console.log(`generated ${schemaFiles.length} schema(s) -> ${tsOut}, ${pyOut}`);
