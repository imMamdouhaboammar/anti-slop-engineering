import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
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

test("perf audit command routes to the mechanical sympathy and perf guard", () => {
  const example = resolve("skills/mechanical-sympathy-and-perf-gate/examples/perf-gate-record.json");
  const result = invoke("anti-slop-engineering", ["perf", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("rollout audit command routes to the safe evolution and rollout guard", () => {
  const example = resolve("skills/safe-evolution-and-rollout-choreographer/examples/safe-evolution-record.json");
  const result = invoke("anti-slop-engineering", ["rollout", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("sim audit command routes to the deterministic simulation and property testing guard", () => {
  const example = resolve("skills/deterministic-simulation-and-property-testing/examples/deterministic-simulation-record.json");
  const result = invoke("anti-slop-engineering", ["sim", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("privacy audit command routes to the privacy and data lineage guard", () => {
  const example = resolve("skills/privacy-and-data-lineage-gate/examples/privacy-lineage-record.json");
  const result = invoke("anti-slop-engineering", ["privacy", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("contract audit command routes to the api ergonomics and contract governor guard", () => {
  const example = resolve("skills/api-ergonomics-and-contract-governor/examples/api-contract-record.json");
  const result = invoke("anti-slop-engineering", ["contract", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("apple-craft audit command routes to the apple craft and interaction physics guard", () => {
  const example = resolve("skills/apple-craft-and-interaction-physics/examples/apple-craft-record.json");
  const result = invoke("anti-slop-engineering", ["apple-craft", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
});

test("observability audit command routes to the Google Monarch and Dapper telemetry guard", () => {
  const example = resolve("skills/observability-and-slo-architect/examples/observability-slo-record.json");
  const source = resolve("skills/observability-and-slo-architect/examples/dapper-monarch-telemetry-pipeline.ts");
  const result = invoke("anti-slop-engineering", ["observability", "audit", example, "--source", source, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.verdict_action, "proceed");
  assert.equal(output.machine_check_only, true);
  assert.equal(output.source_findings_count, 0);
});

test("bump command routes to the automated version bumper in dry-run mode", () => {
  const result = invoke("anti-slop-engineering", ["bump", "patch", "--dry-run", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.dry_run, true);
  assert.equal(output.updated_files.length, 10);
});

test("hunter command routes to the zero-trust forensic bug hunter", () => {
  const result = invoke("anti-slop-engineering", ["hunter", "--base", "HEAD", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.ok(output.verdict);
  assert.ok(typeof output.total_findings === "number");
});

test("install-oxlint command copies the bundled anti-slop plugin to target directory", () => {
  const tempDir = mkdtempSync(join(tmpdir(), "oxlint-test-"));
  try {
    const target = join(tempDir, "tools/oxlint/anti-slop");
    const result = invoke("anti-slop-engineering", ["install-oxlint", target]);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Copied the anti-slop plugin to/);
    assert.ok(existsSync(join(target, "index.ts")));
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("ast command routes to the AST and Type Slop Guard", () => {
  const result = invoke("anti-slop-engineering", ["ast", "--base", "HEAD", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.tool, "anti-slop-ast-guard");
  assert.ok(output.verdict);
});

test("update-oxlint command performs dry-run reconciliation on existing target", () => {
  const tempDir = mkdtempSync(join(tmpdir(), "oxlint-update-"));
  try {
    const target = join(tempDir, "tools/oxlint/anti-slop");
    invoke("anti-slop-engineering", ["install-oxlint", target]);
    const result = invoke("anti-slop-engineering", ["update-oxlint", target]);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Anti-Slop Vendored Update Reconciliation/);
    assert.match(result.stdout, /Identical files:/);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("cases command runs the 16 declarative evaluation cases cleanly", () => {
  const result = invoke("anti-slop-engineering", ["cases"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /All Anti-Slop evaluation cases passed successfully!/);
});

test("exec command routes to the in-flight execution guard status", () => {
  const result = invoke("exec-guard", ["status"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.ok(output.contract);
  assert.ok(typeof output.active_agents === "number");
});

test("oxlint command routes to oxlint binary", () => {
  const result = invoke("anti-slop-engineering", ["oxlint", "--version"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /1\.93\.0/);
});

test("contrast command routes to the WCAG contrast guard", () => {
  const result = invoke("anti-slop-engineering", ["contrast", "#FFFFFF", "#1E293B", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.overall_status, "PASS");
  assert.equal(output.wcag_aa_normal, true);
});

test("mode command manages anti-slop execution modes", () => {
  const result = invoke("anti-slop-engineering", ["mode"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Current anti-slop-engineering mode:/);
});

test("install command routes to universal multi-agent installer dry-run", () => {
  const result = invoke("anti-slop-engineering", ["install", "--dry-run", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.ok(Array.isArray(output.agents));
  assert.ok(Array.isArray(output.skills));
  assert.ok(output.skills.includes("anti-slop-engineering"));
});

test("pr-guard command routes to the PR boundary guard", () => {
  const result = invoke("anti-slop-engineering", ["pr-guard", "--base", "HEAD", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.type, "https://anti-slop.org/problem/pr-boundary");
  assert.ok(output.git_topology);
});

test("honeypot command routes to the honeypot trap guard", () => {
  const result = invoke("anti-slop-engineering", ["honeypot", "--generate-canary", "--secret", "test-secret"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Generated Canary Token: canary-/);
});

test("comment-guard command routes to the comment budget guard", () => {
  const result = invoke("anti-slop-engineering", ["comment-guard", "--base", "HEAD", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.type, "https://anti-slop.org/problem/comment-budget");
  assert.ok(output.metrics);
});

test("attention command routes to the cognitive bandwidth & attention guard", () => {
  const result = invoke("anti-slop-engineering", ["attention", "--text", "**Verdict.** Deploy succeeded.", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.type, "https://anti-slop-engineering.org/errors/attention-budget");
  assert.equal(output.status, 200);
  assert.equal(output.code, "NO_ATTENTION_FINDINGS");
  assert.ok(output.metrics.answer_first);
});

test("steward audit command routes to the invariant steward guard", () => {
  const example = resolve("skills/repo-memory-and-invariant-steward/examples/invariant-ledger-example.json");
  const result = invoke("anti-slop-engineering", ["steward", "audit", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.ok(output.invariants_count > 0);
});

test("steward reassess command routes to the reassessment trigger validator", () => {
  const example = resolve("skills/repo-memory-and-invariant-steward/examples/reassessment-trigger-example.json");
  const result = invoke("anti-slop-engineering", ["steward", "reassess", example, "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.record_status, "complete");
  assert.equal(output.target_invariant_id, "INV-PARANOID-IDEMPOTENCY");
});

test("demock command routes to the demock guard", () => {
  const result = invoke("anti-slop-engineering", ["demock", "--json", "tests/"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.schema_version, "1.0.0");
  assert.ok(typeof output.verdict === "string");
});

test("mandela command routes to the mandela test-oracle guard", () => {
  const result = invoke("anti-slop-engineering", ["mandela", "--json", "tests/test_clean.py"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.schema_version, "1.0.0");
  assert.ok(typeof output.verdict === "string");
});

test("reduction command routes to the reduction governor", () => {
  const result = invoke("anti-slop-engineering", ["reduction", "status", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.ok(typeof output.addback_rate === "number");
  assert.ok(typeof output.calibration_status === "string");
});

test("re0-handoff command routes to the state-note & shower-test guard", () => {
  const tempDir = mkdtempSync(join(tmpdir(), "re0-cli-"));
  const noteFile = join(tempDir, "state-note.json");
  try {
    const compileRes = invoke("anti-slop-engineering", [
      "re0-handoff", "compile",
      "--goal", "Pass all test assertions",
      "--action", "Run python test suite",
      "--target", "tests/test_demock_guard.py",
      "--out", noteFile,
    ]);
    assert.equal(compileRes.status, 0, compileRes.stderr);

    const showerRes = invoke("anti-slop-engineering", ["re0-handoff", "shower-test", "--file", noteFile, "--json"]);
    assert.equal(showerRes.status, 0, showerRes.stderr);
    const output = JSON.parse(showerRes.stdout);
    assert.equal(output.passed, true);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("backprop command routes to the upstream invariant backpropagation guard", () => {
  const result = invoke("anti-slop-engineering", [
    "backprop",
    "--finding", "DEMOCK_TEST_DOUBLE",
    "--file", "src/payment.ts",
    "--line", "12",
    "--excerpt", "new MockClient()",
    "--json",
  ]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.schema_version, "1.0.0");
  assert.equal(output.trigger_error, "DEMOCK_TEST_DOUBLE");
  assert.equal(output.upstream_rule_implicated, "RULE_NO_TEST_DOUBLES_IN_PROD");
});

test("system-drift command routes to the design system drift guard", () => {
  const result = invoke("anti-slop-engineering", ["system-drift", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: System drift guard selftest green/);
});

test("chroma-drift command routes to the chromatic saturation drift guard", () => {
  const result = invoke("anti-slop-engineering", ["chroma-drift", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: Chroma drift guard selftest green/);
});

test("house-tell command routes to the agent house-tell guard", () => {
  const result = invoke("anti-slop-engineering", ["house-tell", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: House tell guard selftest green/);
});

test("motion-runtime command routes to the DPR-2 runtime motion sentry", () => {
  const result = invoke("anti-slop-engineering", ["motion-runtime", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: Motion runtime guard selftest green/);
});

test("asset-provenance command routes to the asset license provenance guard", () => {
  const result = invoke("anti-slop-engineering", ["asset-provenance", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: Asset provenance guard selftest green/);
});

test("styleseed command routes to the StyleSeed cognitive grammar and token canon guard", () => {
  const result = invoke("anti-slop-engineering", ["styleseed", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /PASS: StyleSeed guard selftest green/);
});

test("tagore command routes to the Tagore engineering discourse & substance guard", () => {
  const result = invoke("anti-slop-engineering", ["tagore", "--selftest"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Self-test passed: Tagore Engineering Discourse Guard operational/);
});

test("clippy command routes to cargo clippy runner", () => {
  const result = invoke("anti-slop-engineering", ["clippy", "--help"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout + result.stderr, /clippy/i);
});

test("ruff command routes to ruff runner", () => {
  const result = invoke("anti-slop-engineering", ["ruff", "--version"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout + result.stderr, /ruff/i);
});
