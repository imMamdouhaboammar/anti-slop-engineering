// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { reviewUuidV4 } from "../skills/type-level-and-ast-slop-gate/examples/uuid-v4-advisory.mjs";

const lock = {
  status: "locked", declared: "^9.0.0", resolved: "9.0.1", release: "stable",
  installed: { status: "installed", name: "uuid", version: "9.0.1" },
};
const usage = {
  module: "uuid",
  imports: [{ export: "v4", file: "src/id.ts", line: 1 }],
  calls: [
    { export: "v4", file: "src/id.ts", line: 7, signature: "no_args" },
    { export: "v4", file: "src/session.ts", line: 3, signature: "no_args" },
  ],
};
const runtimes = [{ name: "node", version: "20.11.0" }, { name: "bun", version: "1.1.0" }];

test("v4-only uuid usage on runtimes with randomUUID receives an advisory", () => {
  const result = reviewUuidV4(lock, usage, runtimes);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.rule, "UUID_V4_RUNTIME_RANDOMUUID");
  assert.equal(result.version, "9.0.1");
  assert.match(result.source, /^https:\/\/nodejs\.org\/api\/crypto\.html#cryptorandomuuidoptions$/);
  assert.match(result.suggestion, /Replace the uuid import with randomUUID/);
});

test("unverified call signature evidence requests a call-signature review", () => {
  const unverified = {
    ...usage,
    calls: [
      { export: "v4", file: "src/id.ts", line: 7 },
      { export: "v4", file: "src/session.ts", line: 3 },
    ],
  };
  const result = reviewUuidV4(lock, unverified, runtimes);
  assert.equal(result.status, "advisory");
  assert.match(result.suggestion, /Review recorded uuid v4 call signatures/);

  const optionsFalseOnly = {
    ...usage,
    calls: [{ export: "v4", file: "src/id.ts", line: 7, hasOptions: false }],
  };
  const resultOptionsFalse = reviewUuidV4(lock, optionsFalseOnly, runtimes);
  assert.equal(resultOptionsFalse.status, "advisory");
  assert.match(resultOptionsFalse.suggestion, /Review recorded uuid v4 call signatures/);
});

test("calls using options, arguments, or buffer outputs keep the dependency applicable", () => {
  const withOptions = { ...usage, calls: [{ export: "v4", file: "src/id.ts", line: 7, hasOptions: true }] };
  assert.equal(reviewUuidV4(lock, withOptions, runtimes).status, "not_applicable");
  const withBuffer = { ...usage, calls: [{ export: "v4", file: "src/id.ts", line: 7, buffer: true }] };
  assert.equal(reviewUuidV4(lock, withBuffer, runtimes).status, "not_applicable");
  const withPosArgs = { ...usage, calls: [{ export: "v4", file: "src/id.ts", line: 7, args: 1 }] };
  assert.equal(reviewUuidV4(lock, withPosArgs, runtimes).status, "not_applicable");
  const withArgsArray = { ...usage, calls: [{ export: "v4", file: "src/id.ts", line: 7, args: ["seed"] }] };
  assert.equal(reviewUuidV4(lock, withArgsArray, runtimes).status, "not_applicable");
});

test("any other uuid API in the evidence keeps the dependency applicable", () => {
  const withCall = { ...usage, calls: [...usage.calls, { export: "v1", file: "src/id.ts", line: 9 }] };
  assert.equal(reviewUuidV4(lock, withCall, runtimes).status, "not_applicable");
  const withImport = { ...usage, imports: [...usage.imports, { export: "parse", file: "src/id.ts", line: 2 }] };
  assert.equal(reviewUuidV4(lock, withImport, runtimes).status, "not_applicable");
  assert.equal(reviewUuidV4(lock, { ...usage, module: "uuidv4" }, runtimes).status, "not_applicable");
});

test("missing or unverified runtime evidence is inconclusive, never advice", () => {
  assert.equal(reviewUuidV4(lock, usage, []).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, usage, undefined).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, usage, [{ name: "quickjs", version: "1.0.0" }]).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, usage, [{ name: "constructor", version: "1.0.0" }]).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, usage, [{ name: "node", version: "20.x" }]).status, "inconclusive");
});

test("a supported runtime below the verified randomUUID floor is a compatibility exception", () => {
  const result = reviewUuidV4(lock, usage, [{ name: "node", version: "16.20.2" }]);
  assert.equal(result.status, "compatibility_exception");
  assert.equal(result.version, "9.0.1");
});

test("Deno boundary: 1.10.0 is rejected as compatibility exception and 1.11.0 is accepted", () => {
  const below = reviewUuidV4(lock, usage, [{ name: "deno", version: "1.10.0" }]);
  assert.equal(below.status, "compatibility_exception");
  assert.equal(below.version, "9.0.1");

  const accepted = reviewUuidV4(lock, usage, [{ name: "deno", version: "1.11.0" }]);
  assert.equal(accepted.status, "advisory");
});

test("incomplete dependency or usage evidence is inconclusive", () => {
  assert.equal(reviewUuidV4({ ...lock, status: "stale_lock" }, usage, runtimes).status, "inconclusive");
  assert.equal(reviewUuidV4(null, usage, runtimes).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, { ...usage, imports: [] }, runtimes).status, "inconclusive");
  assert.equal(reviewUuidV4(lock, { ...usage, calls: [] }, runtimes).status, "inconclusive");
  assert.equal(reviewUuidV4({ ...lock, installed: { status: "missing" } }, usage, runtimes).status, "inconclusive");
  assert.equal(reviewUuidV4(
    { ...lock, installed: { status: "installed", name: "uuidv4", version: "9.0.1" } }, usage, runtimes,
  ).status, "inconclusive");
});

test("CLI consumes a lock receipt and a reviewed usage record without blocking", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "uuid-v4-evidence-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const lockPath = join(dir, "lock.json");
  const usagePath = join(dir, "usage.json");
  writeFileSync(lockPath, JSON.stringify(lock));
  writeFileSync(usagePath, JSON.stringify({ ...usage, runtimes }));
  const script = new URL("../skills/type-level-and-ast-slop-gate/examples/uuid-v4-advisory.mjs", import.meta.url);
  const runner = typeof Bun !== "undefined" ? process.execPath : "bun";
  const output = spawnSync(runner, [fileURLToPath(script), lockPath, usagePath], { encoding: "utf8" });
  assert.equal(output.status ?? output.exitCode, 0);
  const result = JSON.parse(output.stdout.toString());
  assert.equal(result.status, "advisory");
  assert.equal(result.rule, "UUID_V4_RUNTIME_RANDOMUUID");
});
