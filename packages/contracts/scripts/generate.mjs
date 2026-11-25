#!/usr/bin/env node
// One generator, two outputs: TypeScript types and Pydantic models, both from packages/contracts/schemas.
//   node scripts/generate.mjs [--schemas <dir>] [--out <dir>]
// Defaults write into this package (ts/ and python/a9_contracts/). Generated files are committed and
// CI fails if they drift from the schemas (make check-generated).
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
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
clean(tsOut);
for (const file of schemaFiles) {
  const ts = await compileFromFile(path.join(schemasDir, file), {
    bannerComment: `/* ${BANNER} */`,
    cwd: schemasDir,
    additionalProperties: false,
    style: { singleQuote: false },
  });
  writeFileSync(path.join(tsOut, `${moduleName(file)}.ts`), ts);
}
writeFileSync(
  path.join(tsOut, "index.ts"),
  `/* ${BANNER} */\n` + schemaFiles.map((f) => `export * from "./${moduleName(f)}";\n`).join(""),
);

// --- Pydantic -------------------------------------------------------------------------------
clean(path.dirname(pyOut));
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
    pyOut,
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
  { cwd: repoRoot, stdio: "inherit" },
);
if (py.status !== 0) {
  console.error("datamodel-codegen failed (is `uv sync` done? try `make setup`).");
  process.exit(py.status ?? 1);
}
console.log(`generated ${schemaFiles.length} schema(s) -> ${tsOut}, ${pyOut}`);
