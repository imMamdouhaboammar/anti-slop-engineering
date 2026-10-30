#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");
const diffGuardScript = resolve(rootDir, "scripts", "diff_guard.py");
const sreGuardScript = resolve(rootDir, "scripts", "sre_guard.py");

const args = process.argv.slice(2);

function printBanner() {
  console.log(`
🛡️  Anti-Slop Engineering CLI (v0.3.0)
   An Engineering Discipline Playbook, Agent Skill & Triage Guard for AI Coding Agents
   Enforcing Google Site Reliability Engineering (SRE): KISS, DRY, YAGNI, Fix Issues at Scale
   Author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
   Repo:   https://github.com/imMamdouhaboammar/anti-slop-engineering

Usage:
  npx anti-slop-engineering [command] [options]
  bunx anti-slop-engineering [command] [options]

Commands:
  sre, sre-guard         Run Google SRE Guard (KISS, DRY, YAGNI, Scale Invariants & Toil)
  test                   Run the automated unit test suite
  contribute             Print guidelines on reporting noted slop or opening PRs

General Options:
  --base <commit>        Compare working tree or branch to base commit (default: HEAD)
  --repo <path>          Path to Git repository (default: current working directory)
  --json                 Output machine-readable JSON evaluation report
  --fail-on-blocker      Exit code 2 if blocker patterns (e.g. skipped tests) are found
  --review-lines <num>   Added-line threshold prompting scope review (default: 400)
  --help, -h             Show this help menu

SRE Guard Options (for 'sre' command):
  --strict               Exit code 2 if any SRE blocker is identified
  --files <paths...>     Specific file paths or directories to analyze
  --max-nesting <num>    Max nesting depth for KISS check (default: 4)
  --min-dup-lines <num>  Min consecutive lines for DRY duplication check (default: 4)
  --max-function-lines   Max function lines before flagging KISS bloat (default: 80)

Seven Gates of Anti-Slop:
  Gate 0: Discover; do not improvise the repo (Use official boilerplates & installers)
  Gate 1: Establish an explicit change contract (what changes vs what stays invariant)
  Gate 2: Lock baseline tests & protect test oracles (repro first, never tamper assertions)
  Gate 3: Implement minimum complexity (pin latest dependencies, zero dev-notes in UI, zero obviousness, SRE KISS/DRY/YAGNI)
  Gate 4: Verify beyond green tests (test negative paths, contracts, and regressions)
  Gate 5: Audit diff as a skeptical reviewer (run diff_guard & sre_guard triage)
  Gate 6: Evidence & structured release decision (BLOCK / REWORK / REVIEW / PASS)
`);
}

function runPythonScript(scriptPath, scriptArgs, scriptLabel) {
  if (!existsSync(scriptPath)) {
    console.error(`Error: ${scriptLabel} script not found at ${scriptPath}`);
    process.exit(1);
  }

  const child = spawn("python3", [scriptPath, ...scriptArgs], {
    cwd: process.cwd(),
    stdio: "inherit",
  });

  child.on("error", (err) => {
    console.error(`Failed to launch python3 ${scriptLabel}: ${err.message}`);
    process.exit(1);
  });

  child.on("close", (code) => {
    process.exit(code ?? 0);
  });
}

if (args[0] === "sre" || args[0] === "sre-guard") {
  runPythonScript(sreGuardScript, args.slice(1), "sre_guard");
} else if (args.includes("--help") || args.includes("-h")) {
  printBanner();
  process.exit(0);
} else if (args[0] === "contribute") {
  console.log(`
🤝 How to Contribute "Noted Slop" to Anti-Slop Engineering:

Path A: Report Observed Slop (No code required)
  Spotted a new recurring AI slop pattern in Claude, Cursor, Copilot, etc.?
  Open an issue: https://github.com/imMamdouhaboammar/anti-slop-engineering/issues/new?template=noted_slop.yml

Path B: Submit a PR (Problem + Solution Integrated)
  1. Add diagnostic pattern to references/anti-pattern-catalog.md
  2. Update SKILL.md & AGENTS.md with concise agent directives
  3. (Optional) Add heuristic to scripts/diff_guard.py or scripts/sre_guard.py & unit tests
  4. Run verification: make check
  5. Open a Pull Request: https://github.com/imMamdouhaboammar/anti-slop-engineering/pulls

Full Contributor Guide: https://github.com/imMamdouhaboammar/anti-slop-engineering/blob/main/CONTRIBUTING.md
`);
  process.exit(0);
} else if (args[0] === "test") {
  const pyTest = spawn("python3", ["-m", "unittest", "discover", "-s", "tests", "-v"], {
    cwd: rootDir,
    stdio: "inherit",
  });
  pyTest.on("close", (code) => process.exit(code ?? 0));
} else {
  const forwardArgs = args.length > 0 ? args : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
}
