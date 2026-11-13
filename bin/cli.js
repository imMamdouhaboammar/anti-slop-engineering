#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");
const pkgPath = resolve(rootDir, "package.json");
const pkg = existsSync(pkgPath) ? JSON.parse(readFileSync(pkgPath, "utf8")) : {};
const cliVersion = pkg.version || "1.6.0";
const diffGuardScript = resolve(rootDir, "scripts", "diff_guard.py");
const sreGuardScript = resolve(rootDir, "scripts", "sre_guard.py");
const decisionGuardScript = resolve(rootDir, "scripts", "decision_guard.py");
const rootFixGuardScript = resolve(rootDir, "scripts", "root_fix_guard.py");
const futureScaleGuardScript = resolve(rootDir, "scripts", "future_scale_guard.py");
const paranoidGuardScript = resolve(rootDir, "scripts", "paranoid_guard.py");
const perfGuardScript = resolve(rootDir, "scripts", "perf_guard.py");
const rolloutGuardScript = resolve(rootDir, "scripts", "rollout_guard.py");
const simulationGuardScript = resolve(rootDir, "scripts", "simulation_guard.py");
const privacyGuardScript = resolve(rootDir, "scripts", "privacy_guard.py");
const apiContractGuardScript = resolve(rootDir, "scripts", "api_contract_guard.py");
const appleCraftGuardScript = resolve(rootDir, "scripts", "apple_craft_guard.py");
const observabilityGuardScript = resolve(rootDir, "scripts", "observability_guard.py");
const forensicHunterScript = resolve(rootDir, "scripts", "forensic_hunter.py");
const execGuardScript = resolve(rootDir, "scripts", "exec_guard.py");
const runCasesScript = resolve(rootDir, "scripts", "run_cases.py");
const bumpVersionScript = resolve(rootDir, "scripts", "bump_version.py");
const astSlopGuardScript = resolve(rootDir, "scripts", "ast_slop_guard.py");
const contrastGuardScript = resolve(rootDir, "scripts", "contrast_guard.py");
const prBoundaryGuardScript = resolve(rootDir, "scripts", "pr_boundary_guard.py");
const honeypotTrapGuardScript = resolve(rootDir, "scripts", "honeypot_trap_guard.py");
const commentBudgetGuardScript = resolve(rootDir, "scripts", "comment_budget_guard.py");
const attentionGuardScript = resolve(rootDir, "scripts", "attention_guard.py");
const invariantStewardScript = resolve(rootDir, "scripts", "invariant_steward_guard.py");
const demockGuardScript = resolve(rootDir, "scripts", "demock_guard.py");
const mandelaGuardScript = resolve(rootDir, "scripts", "mandela_guard.py");
const reductionGuardScript = resolve(rootDir, "scripts", "reduction_guard.py");
const re0HandoffGuardScript = resolve(rootDir, "scripts", "re0_handoff_guard.py");
const backpropGuardScript = resolve(rootDir, "scripts", "backprop_guard.py");
const systemDriftGuardScript = resolve(rootDir, "scripts", "system_drift_guard.py");
const chromaDriftGuardScript = resolve(rootDir, "scripts", "chroma_drift_guard.py");
const houseTellGuardScript = resolve(rootDir, "scripts", "house_tell_guard.py");
const motionRuntimeGuardScript = resolve(rootDir, "scripts", "motion_runtime_guard.py");
const assetProvenanceGuardScript = resolve(rootDir, "scripts", "asset_provenance_guard.py");
const styleseedGuardScript = resolve(rootDir, "scripts", "styleseed_guard.py");
const tagoreGuardScript = resolve(rootDir, "scripts", "tagore_guard.py");
const auditRunnerScript = resolve(rootDir, "scripts", "audit_runner.py");
const installerScript = resolve(rootDir, "scripts", "installer.mjs");
const installOxlintScript = resolve(rootDir, "skills", "install-anti-slop", "scripts", "install.mjs");
const updateOxlintScript = resolve(rootDir, "skills", "install-anti-slop", "scripts", "update.mjs");
const nativeSuffix = process.platform === "win32" ? ".exe" : "";
const rustExecutable = "anti-slop-rust" + nativeSuffix;
const goExecutable = "toil-guard" + nativeSuffix;
const disableNative = process.env.ANTI_SLOP_DISABLE_NATIVE === "1" || process.env.ANTI_SLOP_FORCE_FALLBACK === "1";
const rustBinPath = !disableNative && existsSync(resolve(rootDir, "dist", "bin", rustExecutable))
  ? resolve(rootDir, "dist", "bin", rustExecutable)
  : (!disableNative ? resolve(rootDir, "services", "anti-slop-rust", "target", "release", rustExecutable) : "");
const goBinPath = !disableNative && existsSync(resolve(rootDir, "dist", "bin", goExecutable))
  ? resolve(rootDir, "dist", "bin", goExecutable)
  : (!disableNative ? resolve(rootDir, "services", "toil-guard-go", "bin", goExecutable) : "");

const invokedAs = basename(process.argv[1] ?? "").replace(/\.(?:js|cmd|exe)$/i, "");
const executableAliases = {
  "sre-guard": "sre",
  "rust-guard": "rust",
  "toil-guard": "toil",
  "paranoid-guard": "paranoid",
  "perf-guard": "perf",
  "rollout-guard": "rollout",
  "choreographer": "rollout",
  "sim-guard": "sim",
  "simulation-guard": "sim",
  "dst-guard": "sim",
  "privacy-guard": "privacy",
  "data-lineage-guard": "privacy",
  "contract-guard": "contract",
  "api-contract": "contract",
  "contract": "contract",
  "ergonomics": "contract",
  "apple-craft": "apple-craft",
  "apple-craft-guard": "apple-craft",
  "interaction-physics": "apple-craft",
  "frame-budget": "apple-craft",
  "frame-budget-guard": "apple-craft",
  "observability": "observability",
  "observability-guard": "observability",
  "slo": "observability",
  "slo-guard": "observability",
  "monarch": "observability",
  "dapper": "observability",
  "forensic-hunter": "hunter",
  "forensic": "hunter",
  "exec-guard": "exec",
  "run-cases": "cases",
  "ast-guard": "ast",
  "ast-slop": "ast",
  "ts-slop": "ast",
  "contrast-guard": "contrast",
  "contrast": "contrast",
  "pr-guard": "pr-guard",
  "pr-boundary": "pr-guard",
  "pr-check": "pr-guard",
  "honeypot-guard": "honeypot",
  "honeypot": "honeypot",
  "canary": "honeypot",
  "canary-guard": "honeypot",
  "comment-guard": "comment-guard",
  "comment-budget": "comment-guard",
  "ccr": "comment-guard",
  "attention": "attention",
  "attention-guard": "attention",
  "cognitive": "attention",
  "scannability": "attention",
  "focus": "attention",
  "steward": "steward",
  "invariant": "steward",
  "invariant-steward": "steward",
  "repo-memory": "steward",
  "demock": "demock",
  "demock-guard": "demock",
  "mandela": "mandela",
  "mandela-guard": "mandela",
  "reduction": "reduction",
  "elon": "reduction",
  "re0-handoff": "re0-handoff",
  "state-note": "re0-handoff",
  "shower-test": "re0-handoff",
  "backprop": "backprop",
  "backprop-guard": "backprop",
  "system-drift": "system-drift",
  "systemscan": "system-drift",
  "drift-guard": "system-drift",
  "variant-budget": "system-drift",
  "chroma-drift": "chroma-drift",
  "chromadiff": "chroma-drift",
  "chroma": "chroma-drift",
  "aesthetic-drift": "chroma-drift",
  "house-tell": "house-tell",
  "commit-sheet": "house-tell",
  "tell-guard": "house-tell",
  "reflex-guard": "house-tell",
  "motion-runtime": "motion-runtime",
  "motionqa": "motion-runtime",
  "runtime-motion": "motion-runtime",
  "fillrate": "motion-runtime",
  "asset-provenance": "asset-provenance",
  "provenance": "asset-provenance",
  "asset-guard": "asset-provenance",
  "source-ledger": "asset-provenance",
  "styleseed": "styleseed",
  "styleseed-guard": "styleseed",
  "styleseed-engine": "styleseed",
  "tagore": "tagore",
  "tagore-guard": "tagore",
  "discourse": "tagore",
  "deslop-prose": "tagore",
  "prose-guard": "tagore",
  "humanize": "tagore",
  "audit-guard": "audit",
  "audit": "audit",
  "diff": "diff",
  "diff-guard": "diff",
  "guard": "diff",
  "check": "check",
  "check-all": "check-all",
  "installer": "install",
  "setup": "install",
  "ruff": "ruff",
  "clippy": "clippy",
  "lint-rust": "clippy",
};
const args = process.argv.slice(2);
if (executableAliases[invokedAs]) args.unshift(executableAliases[invokedAs]);

function printBanner() {
  console.log(`
🛡️  Anti-Slop Engineering CLI (v1.7.0)
   Clean-Room AI Coding Guard & High-Performance Polyglot Architecture
   Engines: Standard Library Python Guard | Rust Microservice | Go Toil Guard
   Author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
   Repo:   https://github.com/imMamdouhaboammar/anti-slop-engineering

Usage:
  npx anti-slop-engineering [command] [options]
  bunx anti-slop-engineering [command] [options]

Commands:
  rust, sts              Run native Rust Engine (Scope Creep, Hypothetical Hardening, Intent, Senior Dev Ladder)
  toil, go-guard         Run Go SRE Engine (KISS nesting, DRY token window, Toil & Error Budget)
  serve-rust             Start background Rust HTTP microservice daemon (default: :9091)
  serve-go               Start background Go HTTP SRE microservice daemon (default: :9092)
  build                  Compile both Rust and Go microservices
  sre, sre-guard         Run Python Google SRE Guard (zero-dependency stdlib fallback)
  decision audit <file>  Check a Decision Guard JSON record for missing evidence and trade-offs
  root-fix audit <file>  Check root-cause ownership, change plan and optional Git diff
  future-scale audit <file>  Check future operating envelope, reversibility and evolution proof
  paranoid audit <file>  Check a Paranoid Architect record for zero-trust and 10M scale compliance
  perf audit <file>      Check a Mechanical Sympathy & Perf Gate record for hardware and 120Hz compliance
  rollout audit <file>   Check a Rollout Choreographer record for wire compatibility and canary safety
  sim audit <file>       Check Deterministic Simulation & Property record for MSR & AWS testing rigor
  privacy audit <file>   Check Privacy & Data Lineage record for Apple Privacy & Meta Infra compliance
  contract audit <file>  Check API Contract & Ergonomics record for TypeScript & Stripe DX compliance
  apple-craft audit <file> Check Apple Craft & Interaction Physics record for 120Hz, CLS=0 and state matrix
  observability audit <file> Check Observability & SLO record for Google Monarch & Dapper compliance
  hunter, forensic       Run Zero-Trust Forensic Bug Hunter static scanner across 9 stacks
  exec, exec-guard       Run in-flight Execution Guard (PreToolUse interceptor & directive controller)
  cases, run-cases       Run declarative pairwise evaluation cases (16 SHIT/Anti-Slop test pairs)
  ast, ast-slop          Run AST & Type Slop Guard (chained casts, empty spreads, reducer copies, module mocks)
  contrast, contrast-guard Evaluate WCAG 2.2 color contrast ratios or scan files for low-contrast pairs
  pr-guard, pr-check     Run PR Boundary & Git Topology Guard (provenance, templates, branch hygiene)
  honeypot, canary       Run Honeypot Trap & Prompt Canary Guard (detect ungrounded bots & LLM traps)
  comment-guard, ccr     Run Comment Budget Guard (Comment-to-Code Ratio & syntax narration slop)
  attention, cognitive   Run Cognitive Bandwidth & Attention Economy Guard (Scannability, Blocking Asks, Purity)
  steward, invariant     Run Repo Memory & Invariant Steward (sync ledger, audit drift, validate triggers)
  demock, demock-guard   Run Demock & Silent-Fallback Guard (test doubles in prod, swallowed fallbacks, SQLite bypass)
  mandela, mandela-guard Run Mandela Test-Oracle Guard (8 leakage patterns, tautologies, circular mocks)
  reduction, elon        Run Musk 5-Step Reduction Governor & Add-Back Ledger (10% calibration gate)
  re0-handoff, state-note Run Re0 State-Note & Shower-Test Cold-Read Guard (NVIDIA 1500-token RSI context reset)
  backprop, backprop-guard Run Upstream Rule & Invariant Backpropagation Guard (error-to-rule learning)
  system-drift, systemscan Run Design System Drift & Variant Budget Guard (crawls routes, variant caps, focus-rings)
  chroma-drift, chromadiff Run Chromatic Saturation Drift & OKLCH Category Reflex Guard (cheerful drift, cream/gradient bands)
  house-tell, commit-sheet Run Agent House-Tell & Triple-Reflex Inversion Guard (Gate 0 commit-sheet contract, tells broken)
  motion-runtime, motionqa Run DPR-2 Runtime Motion & Fillrate Sentry (5.2MP retina, 4x CPU throttle, long-tasks, audio policy)
  asset-provenance, provenance Run Asset Sourcing & License Provenance Ledger Guard (cryptographic SHA-256 & open-license ledger)
  styleseed              Run StyleSeed Cognitive Grammar & Token Canon Guard (primitives, OKLCH, spatial inversion)
  tagore, discourse      Run Tagore Engineering Discourse & Substance Guard (29 tells, 8-dim rubric, voice calibration)
  diff, diff-guard       Run single Diff Guard (narrow git diff triage against --base, default: HEAD)
  check                  Run single Diff Guard (backwards-compatible alias of diff for git diff triage)
  audit                  Run unified multi-guard audit and generate numbered markdown dossier (anti-slop/audit-NNN.md)
  check-all              Run full repository quality suite across guards and polyglot tests (make check-all)
  mode [during|after|ask] Configure anti-slop execution mode (active inline vs post-hoc audit)
  install, setup         Install required core and optional skill plugins (TTY wizard or explicit flags)
  update                 Upgrade installed skills and refresh agent pointer blocks in one shot
  ruff                   Run Ruff linter on Python codebase
  oxlint                 Run Oxlint linter with configured anti-slop rules
  clippy, lint-rust      Run Cargo Clippy linter on Rust engine (-D warnings)
  install-oxlint         Install bundled Oxlint anti-slop plugin into target repo
  update-oxlint          Reconcile and update vendored Oxlint anti-slop rules preserving local edits
  bump [part]            Bump version across all 13 manifests (patch, minor, major, or explicit)
  test                   Run unit test suite
  contribute             Print guidelines on reporting noted slop or opening PRs

General Options:
  --base <commit>        Compare working tree or branch to base commit (default: HEAD)
  --repo <path>          Path to Git repository (default: current working directory)
  --json                 Output machine-readable JSON evaluation report
  --fail-on-blocker      Exit code 2 if blocker patterns are found
  --review-lines <num>   Added-line threshold prompting scope review (default: 400)
  --help, -h             Show this help menu
`);
}

function spawnProcess(execPath, execArgs, label) {
  const child = spawn(execPath, execArgs, {
    cwd: process.cwd(),
    stdio: "inherit",
  });
  child.on("error", (err) => {
    console.error(`Failed to launch ${label}: ${err.message}`);
    process.exit(1);
  });
  child.on("close", (code) => {
    process.exit(code ?? 1); // Signal termination must never be reported as success.
  });
}

function runBinary(binPath, binArgs, binLabel, fallbackFn) {
  if (!existsSync(binPath)) {
    if (fallbackFn) {
      console.warn(`[WARN] ${binLabel} binary not found at ${binPath}. Falling back to Python engine...`);
      return fallbackFn();
    }
    console.error(`Error: ${binLabel} binary not found at ${binPath}. Run 'bunx anti-slop-engineering build' or 'make build-services'.`);
    process.exit(1);
  }
  spawnProcess(binPath, binArgs, binLabel);
}

function runPythonScript(scriptPath, scriptArgs, scriptLabel) {
  if (!existsSync(scriptPath)) {
    console.error(`Error: ${scriptLabel} script not found at ${scriptPath}`);
    process.exit(1);
  }
  spawnProcess("python3", [scriptPath, ...scriptArgs], scriptLabel);
}

function unsupportedFallback(engine, request) {
  console.error(`Error: ${engine} native binary is required for ${request}. Run 'anti-slop-engineering build'.`);
  process.exit(1);
}

function extractCommonFlags(flags, engine, onUnrecognized) {
  const mapped = [];
  for (let i = 0; i < flags.length; i++) {
    const flag = flags[i];
    if (flag === "--base" && flags[i + 1]) {
      mapped.push("--base", flags[++i]);
    } else if (flag === "--format" && flags[i + 1] === "json") {
      mapped.push("--json");
      i++;
    } else if (flag === "--format" && flags[i + 1] === "text") {
      i++;
    } else if (onUnrecognized) {
      onUnrecognized(flag);
    } else {
      unsupportedFallback(engine, `option ${flag}`);
    }
  }
  return mapped;
}

function runRustFallback(request) {
  const [command, ...flags] = request;
  if (command !== "triage") unsupportedFallback("Rust", command);
  const mapped = ["--fail-on-blocker", ...extractCommonFlags(flags, "Rust")];
  runPythonScript(diffGuardScript, mapped, "diff_guard");
}

function runGoFallback(request) {
  const [command, ...flags] = request;
  if (command !== "audit") unsupportedFallback("Go", command);
  const paths = [];
  const mapped = extractCommonFlags(flags, "Go", (flag) => {
    if (flag.startsWith("-")) unsupportedFallback("Go", `audit option ${flag}`);
    else paths.push(flag);
  });
  if (paths.length > 0) {
    if (mapped.includes("--base")) unsupportedFallback("Go", "audit with both --base and paths");
    mapped.push("--files", ...paths);
  } else if (!mapped.includes("--base")) mapped.push("--base", "HEAD");
  mapped.push("--strict");
  runPythonScript(sreGuardScript, mapped, "sre_guard");
}

function runBuild() {
  console.log("Compiling Rust microservice...");
  const cargo = spawn("cargo", ["build", "--release"], {
    cwd: resolve(rootDir, "services", "anti-slop-rust"),
    stdio: "inherit",
  });

  cargo.on("close", (cargoCode) => {
    if (cargoCode !== 0) {
      console.error(`Cargo build failed with exit code ${cargoCode}`);
      process.exit(cargoCode ?? 1);
    }

    console.log("Compiling Go microservice...");
    mkdirSync(resolve(rootDir, "services", "toil-guard-go", "bin"), { recursive: true });
    const goBuild = spawn("go", ["build", "-o", "bin/" + goExecutable, "./cmd/toil-guard"], {
      cwd: resolve(rootDir, "services", "toil-guard-go"),
      stdio: "inherit",
    });

    goBuild.on("close", (goCode) => {
      if (goCode !== 0) {
        console.error(`Go build failed with exit code ${goCode}`);
        process.exit(goCode ?? 1);
      }
      mkdirSync(resolve(rootDir, "dist", "bin"), { recursive: true });
      copyFileSync(
        resolve(rootDir, "services", "anti-slop-rust", "target", "release", rustExecutable),
        resolve(rootDir, "dist", "bin", rustExecutable)
      );
      copyFileSync(
        resolve(rootDir, "services", "toil-guard-go", "bin", goExecutable),
        resolve(rootDir, "dist", "bin", goExecutable)
      );
      console.log("All native microservices built successfully and staged in dist/bin/.");
      process.exit(0);
    });
  });
}

const cmd = args[0];

if (cmd === "--version" || cmd === "-v" || cmd === "version" || (args.length === 1 && (args[0] === "--version" || args[0] === "-v"))) {
  console.log(cliVersion);
  process.exit(0);
}

if (cmd === "build") {
  runBuild();
} else if (cmd === "rust" || cmd === "rust-guard" || cmd === "sts") {
  const subArgs = args.slice(1);
  const forwardArgs = subArgs.length > 0 ? subArgs : ["triage"];
  runBinary(rustBinPath, forwardArgs, "anti-slop-rust", () => runRustFallback(forwardArgs));
} else if (cmd === "toil" || cmd === "toil-guard" || cmd === "go-guard") {
  const subArgs = args.slice(1);
  const forwardArgs = subArgs.length > 0 ? subArgs : ["audit"];
  runBinary(goBinPath, forwardArgs, "toil-guard-go", () => runGoFallback(forwardArgs));
} else if (cmd === "serve-rust") {
  runBinary(rustBinPath, ["serve", ...args.slice(1)], "anti-slop-rust daemon", null);
} else if (cmd === "serve-go") {
  runBinary(goBinPath, ["serve", ...args.slice(1)], "toil-guard-go daemon", null);
} else if (cmd === "sre" || cmd === "sre-guard") {
  runPythonScript(sreGuardScript, args.slice(1), "sre_guard");
} else if (cmd === "decision") {
  runPythonScript(decisionGuardScript, args.slice(1), "decision_guard");
} else if (cmd === "root-fix") {
  runPythonScript(rootFixGuardScript, args.slice(1), "root_fix_guard");
} else if (cmd === "future-scale") {
  runPythonScript(futureScaleGuardScript, args.slice(1), "future_scale_guard");
} else if (cmd === "paranoid") {
  runPythonScript(paranoidGuardScript, args.slice(1), "paranoid_guard");
} else if (cmd === "perf" || cmd === "perf-guard") {
  runPythonScript(perfGuardScript, args.slice(1), "perf_guard");
} else if (cmd === "rollout" || cmd === "rollout-guard" || cmd === "choreographer") {
  runPythonScript(rolloutGuardScript, args.slice(1), "rollout_guard");
} else if (cmd === "sim" || cmd === "simulation" || cmd === "dst" || cmd === "sim-guard") {
  runPythonScript(simulationGuardScript, args.slice(1), "simulation_guard");
} else if (cmd === "privacy" || cmd === "privacy-guard" || cmd === "data-lineage-guard") {
  runPythonScript(privacyGuardScript, args.slice(1), "privacy_guard");
} else if (cmd === "contract" || cmd === "api-contract" || cmd === "contract-guard" || cmd === "ergonomics") {
  runPythonScript(apiContractGuardScript, args.slice(1), "api_contract_guard");
} else if (cmd === "apple-craft" || cmd === "apple-craft-guard" || cmd === "interaction-physics" || cmd === "frame-budget" || cmd === "frame-budget-guard") {
  runPythonScript(appleCraftGuardScript, args.slice(1), "apple_craft_guard");
} else if (cmd === "observability" || cmd === "observability-guard" || cmd === "slo" || cmd === "slo-guard" || cmd === "monarch" || cmd === "dapper") {
  runPythonScript(observabilityGuardScript, args.slice(1), "observability_guard");
} else if (cmd === "hunter" || cmd === "forensic" || cmd === "forensic-hunter") {
  runPythonScript(forensicHunterScript, args.slice(1), "forensic_hunter");
} else if (cmd === "exec" || cmd === "exec-guard") {
  runPythonScript(execGuardScript, args.slice(1), "exec_guard");
} else if (cmd === "cases" || cmd === "run-cases") {
  runPythonScript(runCasesScript, args.slice(1), "run_cases");
} else if (cmd === "ast" || cmd === "ast-slop" || cmd === "ts-slop") {
  runPythonScript(astSlopGuardScript, args.slice(1), "ast_slop_guard");
} else if (cmd === "contrast" || cmd === "contrast-guard") {
  runPythonScript(contrastGuardScript, args.slice(1), "contrast_guard");
} else if (cmd === "pr-guard" || cmd === "pr-boundary" || cmd === "pr-check") {
  runPythonScript(prBoundaryGuardScript, args.slice(1), "pr_boundary_guard");
} else if (cmd === "honeypot" || cmd === "honeypot-guard" || cmd === "canary") {
  runPythonScript(honeypotTrapGuardScript, args.slice(1), "honeypot_trap_guard");
} else if (cmd === "comment-guard" || cmd === "comment-budget" || cmd === "ccr") {
  runPythonScript(commentBudgetGuardScript, args.slice(1), "comment_budget_guard");
} else if (cmd === "attention" || cmd === "cognitive" || cmd === "scannability" || cmd === "focus" || cmd === "attention-guard") {
  runPythonScript(attentionGuardScript, args.slice(1), "attention_guard");
} else if (cmd === "steward" || cmd === "invariant" || cmd === "invariant-steward" || cmd === "repo-memory") {
  runPythonScript(invariantStewardScript, args.slice(1), "invariant_steward_guard");
} else if (cmd === "demock" || cmd === "demock-guard") {
  runPythonScript(demockGuardScript, args.slice(1), "demock_guard");
} else if (cmd === "mandela" || cmd === "mandela-guard") {
  runPythonScript(mandelaGuardScript, args.slice(1), "mandela_guard");
} else if (cmd === "reduction" || cmd === "elon") {
  runPythonScript(reductionGuardScript, args.slice(1), "reduction_guard");
} else if (cmd === "re0-handoff" || cmd === "state-note" || cmd === "shower-test") {
  runPythonScript(re0HandoffGuardScript, args.slice(1), "re0_handoff_guard");
} else if (cmd === "backprop" || cmd === "backprop-guard") {
  runPythonScript(backpropGuardScript, args.slice(1), "backprop_guard");
} else if (cmd === "system-drift" || cmd === "systemscan" || cmd === "drift-guard" || cmd === "variant-budget") {
  runPythonScript(systemDriftGuardScript, args.slice(1), "system_drift_guard");
} else if (cmd === "chroma-drift" || cmd === "chromadiff" || cmd === "chroma" || cmd === "aesthetic-drift") {
  runPythonScript(chromaDriftGuardScript, args.slice(1), "chroma_drift_guard");
} else if (cmd === "house-tell" || cmd === "commit-sheet" || cmd === "tell-guard" || cmd === "reflex-guard") {
  runPythonScript(houseTellGuardScript, args.slice(1), "house_tell_guard");
} else if (cmd === "motion-runtime" || cmd === "motionqa" || cmd === "runtime-motion" || cmd === "fillrate") {
  runPythonScript(motionRuntimeGuardScript, args.slice(1), "motion_runtime_guard");
} else if (cmd === "asset-provenance" || cmd === "provenance" || cmd === "asset-guard" || cmd === "source-ledger") {
  runPythonScript(assetProvenanceGuardScript, args.slice(1), "asset_provenance_guard");
} else if (cmd === "styleseed" || cmd === "styleseed-guard" || cmd === "styleseed-engine") {
  runPythonScript(styleseedGuardScript, args.slice(1), "styleseed_guard");
} else if (cmd === "tagore" || cmd === "tagore-guard" || cmd === "discourse" || cmd === "deslop-prose" || cmd === "humanize" || cmd === "prose") {
  runPythonScript(tagoreGuardScript, args.slice(1), "tagore_guard");
} else if (cmd === "audit") {
  runPythonScript(auditRunnerScript, ["audit", ...args.slice(1)], "audit_runner");
} else if (cmd === "mode") {
  runPythonScript(auditRunnerScript, ["mode", ...args.slice(1)], "audit_runner");
} else if (cmd === "install" || cmd === "setup") {
  spawnProcess("node", [installerScript, ...args.slice(1)], "installer");
} else if (cmd === "update") {
  spawnProcess("node", [installerScript, "update", ...args.slice(1)], "installer");
} else if (cmd === "ruff") {
  const ruffArgs = args.slice(1);
  if (ruffArgs.includes("--version") || ruffArgs.includes("-V")) {
    spawnProcess("ruff", ["--version"], "ruff");
  } else {
    spawnProcess("ruff", ["check", ...(ruffArgs.length ? ruffArgs : ["."])], "ruff");
  }
} else if (cmd === "oxlint") {
  const isBun = typeof process.versions.bun !== "undefined";
  const runner = isBun ? "bunx" : "npx";
  spawnProcess(runner, ["oxlint", ...args.slice(1)], "oxlint");
} else if (cmd === "clippy" || cmd === "lint-rust") {
  const rustDir = resolve(rootDir, "services", "anti-slop-rust");
  const child = spawn("cargo", ["clippy", "--all-targets", "--all-features", "--", "-D", "warnings", ...args.slice(1)], {
    cwd: rustDir,
    stdio: "inherit",
  });
  child.on("error", (err) => {
    console.error(`Failed to launch cargo clippy: ${err.message}`);
    process.exit(1);
  });
  child.on("close", (code) => {
    process.exit(code ?? 1);
  });
} else if (cmd === "update-oxlint") {
  if (!existsSync(updateOxlintScript)) {
    console.error(`Error: update script not found at ${updateOxlintScript}`);
    process.exit(1);
  }
  spawnProcess("node", [updateOxlintScript, ...args.slice(1)], "update_oxlint");
} else if (cmd === "install-oxlint" || cmd === "install-anti-slop") {
  if (!existsSync(installOxlintScript)) {
    console.error(`Error: install script not found at ${installOxlintScript}`);
    process.exit(1);
  }
  spawnProcess("node", [installOxlintScript, ...args.slice(1)], "install_oxlint");
} else if (cmd === "bump") {
  runPythonScript(bumpVersionScript, args.slice(1), "bump_version");
} else if (args.includes("--help") || args.includes("-h")) {
  printBanner();
  process.exit(0);
} else if (cmd === "contribute") {
  console.log(`
🤝 How to Contribute "Noted Slop" to Anti-Slop Engineering:

Path A: Report Observed Slop (No code required)
  Spotted a new recurring AI slop pattern in Claude, Cursor, Copilot, etc.?
  Open an issue: https://github.com/imMamdouhaboammar/anti-slop-engineering/issues/new?template=noted_slop.yml

Path B: Submit a PR (Problem + Solution Integrated)
  1. Add diagnostic pattern to references/anti-pattern-catalog.md
  2. Update SKILL.md & AGENTS.md with concise agent directives
  3. (Optional) Add heuristic to scripts/diff_guard.py or scripts/sre_guard.py or native Rust/Go services
  4. Run verification: make check-all
  5. Open a Pull Request: https://github.com/imMamdouhaboammar/anti-slop-engineering/pulls
`);
  process.exit(0);
} else if (cmd === "test") {
  const pyTest = spawn("python3", ["-m", "unittest", "discover", "-s", "tests", "-v"], {
    cwd: rootDir,
    stdio: "inherit",
  });
  pyTest.on("close", (code) => process.exit(code ?? 1));
} else if (cmd === "test-all") {
  spawnProcess("make", ["test-all"], "test-all");
} else if (cmd === "check-all") {
  spawnProcess("make", ["check-all"], "check-all");
} else if (cmd === "diff" || cmd === "diff-guard" || cmd === "guard") {
  const forwardArgs = args.slice(1).length > 0 ? args.slice(1) : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
} else if (cmd === "check") {
  const forwardArgs = args.slice(1).length > 0 ? args.slice(1) : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
} else {
  const forwardArgs = args.length > 0 ? args : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
}
