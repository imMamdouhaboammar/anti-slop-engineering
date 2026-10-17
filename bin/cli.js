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

const args = process.argv.slice(2);

function printBanner() {
  console.log(`
🛡️  Anti-Slop Engineering CLI (v0.1.2)
   An Engineering Discipline Playbook & Guard System for AI Coding Agents
   Author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
   Repo:   https://github.com/imMamdouhaboammar/anti-slop-engineering

Usage:
  npx anti-slop-engineering [options]
  bunx anti-slop-engineering [options]

Commands & Options:
  --base <commit>        Compare working tree or branch to base commit (default: HEAD)
  --repo <path>          Path to Git repository (default: current working directory)
  --json                 Output machine-readable JSON evaluation report
  --fail-on-blocker      Exit code 2 if blocker patterns (e.g. skipped tests) are found
  --review-lines <num>   Added-line threshold prompting scope review (default: 400)
  test                   Run the automated unit test suite
  --help, -h             Show this help menu

Seven Gates of Anti-Slop:
  Gate 0: Discover; do not improvise the repo (Use official boilerplates & installers)
  Gate 1: Establish an explicit change contract (what changes vs what stays invariant)
  Gate 2: Lock baseline tests & protect test oracles (repro first, never tamper assertions)
  Gate 3: Implement with minimum justified complexity (strictly pin latest stable dependencies)
  Gate 4: Verify beyond green tests (test negative paths, contracts, and regressions)
  Gate 5: Audit diff as a skeptical reviewer (run diff_guard triage)
  Gate 6: Evidence & structured release decision (BLOCK / REWORK / REVIEW / PASS)
`);
}

if (args.includes("--help") || args.includes("-h")) {
  printBanner();
  process.exit(0);
}

if (args[0] === "test") {
  const pyTest = spawn("python3", ["-m", "unittest", "discover", "-s", "tests", "-v"], {
    cwd: rootDir,
    stdio: "inherit",
  });
  pyTest.on("close", (code) => process.exit(code ?? 0));
} else {
  if (!existsSync(diffGuardScript)) {
    console.error(`Error: diff_guard.py script not found at ${diffGuardScript}`);
    process.exit(1);
  }

  // Forward all args to python3 scripts/diff_guard.py
  const forwardArgs = args.length > 0 ? args : ["--base", "HEAD"];
  const child = spawn("python3", [diffGuardScript, ...forwardArgs], {
    cwd: process.cwd(),
    stdio: "inherit",
  });

  child.on("error", (err) => {
    console.error(`Failed to launch python3 diff_guard: ${err.message}`);
    process.exit(1);
  });

  child.on("close", (code) => {
    process.exit(code ?? 0);
  });
}
