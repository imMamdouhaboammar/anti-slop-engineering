import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { reviewForwardRef } from "../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs";

const evidence = { status: "locked", resolved: "19.0.0", release: "stable" };
const usage = { module: "react", export: "forwardRef", kind: "function-component" };
const compatibility = ["19.0.0", "19.1.0"];

test("React 19 function component wrapper receives an advisory with migration evidence", () => {
  const result = reviewForwardRef(evidence, usage, compatibility);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.version, "19.0.0");
  assert.match(result.source, /^https:\/\/react\.dev\//);
  assert.match(result.suggestion, /ref prop/);
});

test("React 18, prereleases and unverified lock evidence do not trigger advice", () => {
  assert.equal(reviewForwardRef({ ...evidence, resolved: "18.3.1" }, usage, compatibility).status, "not_applicable");
  assert.equal(reviewForwardRef({ ...evidence, resolved: "19.0.0-rc.1", release: "prerelease" }, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef({ ...evidence, status: "stale_lock" }, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef({ ...evidence, resolved: "19malformed" }, usage, compatibility).status, "inconclusive");
});

test("keep wrappers for React 18 consumers and require declared support evidence", () => {
  assert.equal(reviewForwardRef(evidence, usage, ["18.3.1", "19.0.0"]).status, "compatibility_exception");
  assert.equal(reviewForwardRef(evidence, usage, []).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, usage, ["19.x"]).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, { ...usage, module: "preact/compat" }, compatibility).status, "not_applicable");
  assert.equal(reviewForwardRef(evidence, { ...usage, kind: "class-component" }, compatibility).status, "not_applicable");
});

test("CLI consumes a lock-evidence receipt and a reviewed usage record without blocking", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "react-ref-evidence-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const lock = join(dir, "lock.json");
  const example = join(dir, "usage.json");
  writeFileSync(lock, JSON.stringify(evidence));
  writeFileSync(example, JSON.stringify({ ...usage, supportedVersions: compatibility }));
  const script = new URL("../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs", import.meta.url);
  const output = Bun.spawnSync([process.execPath, script.pathname, lock, example]);
  assert.equal(output.exitCode, 0);
  assert.equal(JSON.parse(output.stdout.toString()).status, "advisory");
});

test("later majors and malformed release receipts remain inconclusive", () => {
  assert.equal(reviewForwardRef({ ...evidence, resolved: "20.0.0" }, usage, ["20.0.0"]).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, usage, ["19.0.0", "20.0.0"]).status, "inconclusive");
  assert.equal(reviewForwardRef(null, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, { ...usage, export: "memo" }, compatibility).status, "not_applicable");
});
