import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const cli = pathToFileURL(resolve("bin/cli.js")).href;

function invoke(alias, args) {
  const code = `process.argv=[process.execPath,${JSON.stringify(resolve("bin", alias))},...${JSON.stringify(args)}]; await import(${JSON.stringify(cli)});`;
  return spawnSync(process.execPath, ["--input-type=module", "--eval", code], {
    cwd: process.cwd(),
    encoding: "utf8",
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
