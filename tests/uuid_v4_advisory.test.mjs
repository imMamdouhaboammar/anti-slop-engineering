import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { reviewUuidV4 } from "../skills/type-level-and-ast-slop-gate/examples/uuid-v4-advisory.mjs";

const lock = {
  status: "locked", declared: "^9.0.0", resolved: "9.0.1", release: "stable",
  installed: { status: "installed", name: "uuid", version: "9.0.1" },
};
const usage = {
  module: "uuid",
  imports: [{ export: "v4", file: "src/id.ts", line: 1 }],
  calls: [
    { export: "v4", file: "src/id.ts", line: 7 },
    { export: "v4", file: "src/session.ts", line: 3 },
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
  assert.match(result.suggestion, /randomUUID/);
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
  assert.equal(reviewUuidV4(lock, usage, [{ name: "node", version: "20.x" }]).status, "inconclusive");
});

test("a supported runtime below the verified randomUUID floor is a compatibility exception", () => {
  const result = reviewUuidV4(lock, usage, [{ name: "node", version: "16.20.2" }]);
  assert.equal(result.status, "compatibility_exception");
  assert.equal(result.version, "9.0.1");
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
  const output = Bun.spawnSync([process.execPath, script.pathname, lockPath, usagePath]);
  assert.equal(output.exitCode, 0);
  const result = JSON.parse(output.stdout.toString());
  assert.equal(result.status, "advisory");
  assert.equal(result.rule, "UUID_V4_RUNTIME_RANDOMUUID");
});
