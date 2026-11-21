// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { runPythonGuard } from "./python_driver.js";
import { runRustGuard, pingRustDaemon } from "./rust_driver.js";
import { runGoGuard, pingGoDaemon } from "./go_driver.js";

/**
 * Orchestrates guard execution across available polyglot engines.
 */
export async function executeGuard(guardName, args = [], options = {}) {
  // If native Rust engine is requested or applicable
  if (guardName === "rust" || guardName === "sts") {
    const rustResult = await runRustGuard(args, options);
    if (rustResult.available) return rustResult;
    // Fallback to Python if native binary unavailable
    return runPythonGuard("diff_guard.py", args, options);
  }

  // If Go Toil guard is requested
  if (guardName === "toil" || guardName === "go") {
    const goResult = await runGoGuard(args, options);
    if (goResult.available) return goResult;
    return runPythonGuard("sre_guard.py", args, options);
  }

  // Map known guard aliases to Python scripts
  const scriptMap = {
    "diff": "diff_guard.py",
    "diff_guard": "diff_guard.py",
    "sre": "sre_guard.py",
    "sre_guard": "sre_guard.py",
    "ast": "ast_slop_guard.py",
    "ast_guard": "ast_slop_guard.py",
    "comment": "comment_budget_guard.py",
    "comment_guard": "comment_budget_guard.py",
    "contrast": "contrast_guard.py",
    "demock": "demock_guard.py",
    "mandela": "mandela_guard.py",
    "reduction": "reduction_guard.py",
    "re0": "re0_handoff_guard.py",
    "steward": "invariant_steward_guard.py",
    "attention": "attention_guard.py",
    "paranoid": "paranoid_guard.py",
    "apple-craft": "apple_craft_guard.py",
    "hunter": "forensic_hunter.py",
    "audit": "audit_runner.py",
    "backprop": "backprop_guard.py",
  };

  const script = scriptMap[guardName] || `${guardName}.py`;
  return runPythonGuard(script, args, options);
}

export async function checkPolyglotHealth() {
  const [rustOk, goOk] = await Promise.all([
    pingRustDaemon(),
    pingGoDaemon(),
  ]);

  return {
    python: { available: true, runtime: "Python 3 stdlib" },
    rust: { available: rustOk, daemonPort: 9091 },
    go: { available: goOk, daemonPort: 9092 },
  };
}
