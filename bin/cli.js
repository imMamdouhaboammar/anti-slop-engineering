#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");
const diffGuardScript = resolve(rootDir, "scripts", "diff_guard.py");
const sreGuardScript = resolve(rootDir, "scripts", "sre_guard.py");
const nativeSuffix = process.platform === "win32" ? ".exe" : "";
const rustExecutable = "anti-slop-rust" + nativeSuffix;
const goExecutable = "toil-guard" + nativeSuffix;
const rustBinPath = existsSync(resolve(rootDir, "dist", "bin", rustExecutable))
  ? resolve(rootDir, "dist", "bin", rustExecutable)
  : resolve(rootDir, "services", "anti-slop-rust", "target", "release", rustExecutable);
const goBinPath = existsSync(resolve(rootDir, "dist", "bin", goExecutable))
  ? resolve(rootDir, "dist", "bin", goExecutable)
  : resolve(rootDir, "services", "toil-guard-go", "bin", goExecutable);

const invokedAs = basename(process.argv[1] ?? "").replace(/\.(?:js|cmd|exe)$/i, "");
const executableAliases = { "sre-guard": "sre", "rust-guard": "rust", "toil-guard": "toil" };
const args = process.argv.slice(2);
if (executableAliases[invokedAs]) args.unshift(executableAliases[invokedAs]);

function printBanner() {
  console.log(`
🛡️  Anti-Slop Engineering CLI (v0.4.0)
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

function runRustFallback(request) {
  const [command, ...flags] = request;
  if (command !== "triage") unsupportedFallback("Rust", command);
  const mapped = ["--fail-on-blocker"];
  for (let i = 0; i < flags.length; i++) {
    if (flags[i] === "--base" && flags[i + 1]) mapped.push("--base", flags[++i]);
    else if (flags[i] === "--format" && flags[i + 1] === "json") { mapped.push("--json"); i++; }
    else if (flags[i] === "--format" && flags[i + 1] === "text") i++;
    else unsupportedFallback("Rust", `triage option ${flags[i]}`);
  }
  runPythonScript(diffGuardScript, mapped, "diff_guard");
}

function runGoFallback(request) {
  const [command, ...flags] = request;
  if (command !== "audit") unsupportedFallback("Go", command);
  const mapped = [];
  const paths = [];
  for (let i = 0; i < flags.length; i++) {
    if (flags[i] === "--base" && flags[i + 1]) mapped.push("--base", flags[++i]);
    else if (flags[i] === "--format" && flags[i + 1] === "json") { mapped.push("--json"); i++; }
    else if (flags[i] === "--format" && flags[i + 1] === "text") i++;
    else if (flags[i].startsWith("-")) unsupportedFallback("Go", `audit option ${flags[i]}`);
    else paths.push(flags[i]);
  }
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
      console.log("All native microservices built successfully.");
      process.exit(0);
    });
  });
}

const cmd = args[0];

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
} else if (cmd === "check") {
  const forwardArgs = args.slice(1).length > 0 ? args.slice(1) : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
} else {
  const forwardArgs = args.length > 0 ? args : ["--base", "HEAD"];
  runPythonScript(diffGuardScript, forwardArgs, "diff_guard");
}
