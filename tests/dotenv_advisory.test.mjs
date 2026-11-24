// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { reviewDotenv } from "../skills/type-level-and-ast-slop-gate/examples/dotenv-advisory.mjs";

const script = fileURLToPath(
  new URL("../skills/type-level-and-ast-slop-gate/examples/dotenv-advisory.mjs", import.meta.url));

const lock = {
  status: "locked", declared: "^16.4.5", resolved: "16.4.5", release: "stable",
  installed: { status: "installed", name: "dotenv", version: "16.4.5" },
};
const usage = {
  module: "dotenv",
  imports: [{ export: "config", file: "src/main.ts", line: 1 }],
  calls: [{ export: "config", file: "src/main.ts", line: 3, signature: "no_args" }],
};
const runtimes = [{ name: "node", version: "20.12.0" }, { name: "bun", version: "1.1.0" }];

test("config-only dotenv usage on capable runtimes receives an advisory", () => {
  const result = reviewDotenv(lock, usage, runtimes);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.rule, "DOTENV_RUNTIME_LOAD_ENV_FILE");
  assert.equal(result.version, "16.4.5");
  assert.equal(result.source, "https://nodejs.org/api/process.html#processloadenvfilepath");
  assert.match(result.suggestion, /process\.loadEnvFile/);
  assert.match(result.suggestion, /remove the dotenv dependency/);
});

test("a lone path option stays advisory; unverified signatures get the review suggestion", () => {
  const pathOnly = {
    ...usage,
    calls: [{ export: "config", file: "src/main.ts", line: 3, hasOptions: true, options: ["path"] }],
  };
  const pathResult = reviewDotenv(lock, pathOnly, runtimes);
  assert.equal(pathResult.status, "advisory");
  assert.match(pathResult.suggestion, /remove the dotenv dependency/);

  const unverified = { ...usage, calls: [{ export: "config", file: "src/main.ts", line: 3 }] };
  const result = reviewDotenv(lock, unverified, runtimes);
  assert.equal(result.status, "advisory");
  assert.match(result.suggestion, /Review recorded dotenv config call signatures/);
});

test("other dotenv APIs and expressive options keep the dependency applicable", () => {
  const parseUsage = {
    module: "dotenv",
    imports: [{ export: "parse", file: "src/env.ts", line: 1 }],
    calls: [{ export: "parse", file: "src/env.ts", line: 5, signature: "no_args" }],
  };
  assert.equal(reviewDotenv(lock, parseUsage, runtimes).status, "not_applicable");
  const vault = {
    ...usage,
    calls: [{ export: "config", file: "src/main.ts", line: 3, hasOptions: true, options: ["DOTENV_KEY"] }],
  };
  assert.equal(reviewDotenv(lock, vault, runtimes).status, "not_applicable");
  const override = {
    ...usage,
    calls: [{ export: "config", file: "src/main.ts", line: 3, hasOptions: true, options: ["path", "override"] }],
  };
  assert.equal(reviewDotenv(lock, override, runtimes).status, "not_applicable");
});

test("below-floor runtimes are a compatibility exception", () => {
  const result = reviewDotenv(lock, usage, [{ name: "node", version: "18.19.0" }]);
  assert.equal(result.status, "compatibility_exception");
  assert.equal(result.version, "16.4.5");
  assert.equal(result.source, "https://nodejs.org/api/process.html#processloadenvfilepath");
});

test("missing evidence is inconclusive, never an advisory", () => {
  assert.equal(reviewDotenv(lock, usage, undefined).status, "inconclusive");
  assert.equal(reviewDotenv(lock, usage, []).status, "inconclusive");
  assert.equal(reviewDotenv(lock, usage, [{ name: "deno", version: "2.0.0" }]).status, "inconclusive");
  assert.equal(reviewDotenv({ status: "stale_lock" }, usage, runtimes).status, "inconclusive");
  assert.equal(reviewDotenv(lock, { module: "dotenv" }, runtimes).status, "inconclusive");
  assert.equal(reviewDotenv(lock, { module: "other" }, runtimes).status, "not_applicable");
});

test("CLI prints the advisory verdict from evidence files", () => {
  const dir = mkdtempSync(join(tmpdir(), "dotenv-advisory-"));
  try {
    writeFileSync(join(dir, "lock.json"), JSON.stringify(lock));
    writeFileSync(join(dir, "usage.json"), JSON.stringify({ ...usage, runtimes }));
    const output = spawnSync(process.execPath, [script, join(dir, "lock.json"), join(dir, "usage.json")],
      { encoding: "utf8" });
    assert.equal(output.status, 0, output.stderr);
    assert.equal(JSON.parse(output.stdout).status, "advisory");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
