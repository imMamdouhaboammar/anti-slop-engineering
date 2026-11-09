import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const cli = pathToFileURL(resolve("bin/cli.js")).href;

function invoke(alias, args, extraEnv = {}) {
  const code = `process.argv=[process.execPath,${JSON.stringify(resolve("bin", alias))},...${JSON.stringify(args)}]; await import(${JSON.stringify(cli)});`;
  return spawnSync(process.execPath, ["--input-type=module", "--eval", code], {
    cwd: process.cwd(),
    encoding: "utf8",
    env: { ...process.env, ANTI_SLOP_DISABLE_NATIVE: "1", ...extraEnv },
  });
}

test("rust-guard alias rejects unsupported native-only requests without substituting an audit", () => {
  const result = invoke("rust-guard", ["shit-check", "--diff", "example.diff"]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /native binary is required for shit-check/);
});

test("toil-guard alias passes audit options into the Python SRE fallback", () => {
  const result = invoke("toil-guard", ["audit", "--format", "json", "--base", "HEAD"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.base, "HEAD");
});

test("Rust triage fallback reports an invalid base instead of silently auditing HEAD", () => {
  const result = invoke("rust-guard", ["triage", "--base", "nonexistent-revision-123"]);
  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /ERROR:/);
});

test("decision audit command routes to the stdlib decision guard", () => {
  const example = resolve("skills/decision-guard/examples/architecture-record.json");
  const result = invoke("anti-slop-engineering", ["decision", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.decision_action, "pause");
  assert.equal(output.machine_check_only, true);
});

test("root-fix audit command routes to the ownership and diff guard", () => {
  const example = resolve("skills/root-fix-gate/examples/email-checkout-record.json");
  const result = invoke("anti-slop-engineering", ["root-fix", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.decision_action, "pause");
  assert.equal(output.machine_check_only, true);
});

test("future-scale audit command routes to the lifetime architecture guard", () => {
  const example = resolve("skills/future-scale-gate/examples/runtime-envelope-record.json");
  const result = invoke("anti-slop-engineering", ["future-scale", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.decision_action, "pause");
  assert.equal(output.machine_check_only, true);
});

test("paranoid audit command routes to the zero-trust 10M scale guard", () => {
  const example = resolve("skills/paranoid-principal-architect/examples/paranoid-architecture-record.json");
  const result = invoke("anti-slop-engineering", ["paranoid", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("bump command routes to the automated version bumper in dry-run mode", () => {
  const result = invoke("anti-slop-engineering", ["bump", "patch", "--dry-run", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.dry_run, true);
  assert.equal(output.updated_files.length, 10);
});
