#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Unified Multi-Guard Audit Runner & Mode Governor for Anti-Slop Engineering.

Governs execution modes (DURING vs AFTER vs ASK) and orchestrates all guards
via a canonical registry of zero-input, conditional, and record-based guards
to compile a structured, numbered audit report in `anti-slop/audit-NNN.md`.

Usage:
    python3 scripts/audit_runner.py mode [during|after|ask]
    python3 scripts/audit_runner.py audit [--base HEAD] [--json] [--mode during|after|ask]
"""

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__:
    from .rule_registry import catalog_owner, finding_metadata
else:
    from rule_registry import catalog_owner, finding_metadata

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "anti-slop-engineering"
GLOBAL_SETTINGS_FILE = GLOBAL_CONFIG_DIR / "settings.json"
LOCAL_CONFIG_DIR = Path.cwd() / ".anti-slop"
LOCAL_SETTINGS_FILE = LOCAL_CONFIG_DIR / "settings.json"
def _default_audit_dir() -> Path:
    """Dossiers live inside the repo's git dir when in a work tree.

    `.git/` is never tracked and never shows in `git status`, so a default
    audit leaves no untracked dossier in the consumer repository and touches
    no tracked or config file. Outside a work tree, keep the legacy
    cwd-local directory.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        git_dir = Path(result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = Path.cwd() / git_dir
        return git_dir.resolve() / "anti-slop"
    return Path.cwd() / "anti-slop"


AUDIT_DIR = _default_audit_dir()
GUARD_TIMEOUT_SECONDS = 60
GUARD_ENV_NAMES = frozenset({
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "TMPDIR", "TEMP", "TMP", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_COLLATE",
    "LC_MESSAGES", "LC_MONETARY", "LC_NUMERIC", "LC_TIME",
    "GITHUB_HEAD_REF", "GITHUB_REF_NAME",
})

GUARD_REGISTRY: Dict[str, Dict[str, Any]] = {
    "diff_guard": {
        "title": "Diff & Blast Radius Guard",
        "script": "diff_guard.py",
        "input_type": "git_diff",
        "mandatory": True,
        "description": "Enforces Seven Gates contracts, diff blast radius limits, and change safety.",
    },
    "sre_guard": {
        "title": "Google SRE Guard",
        "script": "sre_guard.py",
        "input_type": "git_diff",
        "mandatory": True,
        "description": "Enforces Google SRE discipline (KISS nesting, DRY, YAGNI, scale resilience).",
    },
    "ast_slop_guard": {
        "title": "Type-Level & AST Slop Gate",
        "script": "ast_slop_guard.py",
        "input_type": "git_diff",
        "mandatory": True,
        "description": "Eliminates chained type casts, reducer accumulator copies, and empty spreads.",
    },
    "comment_budget_guard": {
        "title": "Comment Budget Guard",
        "script": "comment_budget_guard.py",
        "input_type": "git_diff",
        "mandatory": True,
        "description": "Enforces Comment-to-Code Ratio (CCR <= 0.35) and bans syntax play-by-play comments.",
    },
    "attention_guard": {
        "title": "Cognitive Bandwidth & Attention Guard",
        "script": "attention_guard.py",
        "input_type": "git_diff",
        "mandatory": True,
        "description": "Enforces scannability metrics, terminal blocking-ask placement, and deliverable purity.",
    },
    "demock_guard": {
        "title": "Demock & Silent Fallback Guard",
        "script": "demock_guard.py",
        "input_type": "git_diff",
        "mandatory": False,
        "description": "Detects test doubles on production paths, silent fallbacks, and fail-open gates.",
    },
    "mandela_guard": {
        "title": "Mandela Test-Oracle Guard",
        "script": "mandela_guard.py",
        "input_type": "git_diff",
        "mandatory": False,
        "description": "Audits test suites for 8 Mandela leakage patterns, tautologies, and circular mocks.",
    },
    "tagore_guard": {
        "installed_skill": "tagore-guard",
        "title": "Tagore Discourse & Substance Guard",
        "script": "tagore_guard.py",
        "input_type": "git_diff",
        "mandatory": False,
        "description": "Eliminates AI prose tells, significance inflation, and copula avoidance.",
    },
    "forensic_hunter": {
        "title": "Forensic Bug Hunter",
        "script": "forensic_hunter.py",
        "input_type": "git_diff",
        "mandatory": False,
        "description": "Scans diff targets across 9 stacks for zero-trust security and injection defects.",
    },
    "contrast_guard": {
        "title": "WCAG Contrast Guard",
        "script": "contrast_guard.py",
        "input_type": "workspace_scan",
        "mandatory": True,
        "description": "Scans UI/CSS/TSX files for low-contrast color pairings failing WCAG 2.2 AA.",
    },
    "system_drift_guard": {
        "title": "Design System Drift Guard",
        "script": "system_drift_guard.py",
        "input_type": "workspace_scan",
        "mandatory": True,
        "description": "Audits cross-route design system drift, component variant explosions, and focus rings.",
    },
    "chroma_drift_guard": {
        "title": "Chromatic Drift Guard",
        "script": "chroma_drift_guard.py",
        "input_type": "workspace_scan",
        "mandatory": True,
        "description": "Audits OKLCH adherence, cheerful saturation drift, and category reflex band clichés.",
    },
    "styleseed_guard": {
        "title": "StyleSeed Token Canon Guard",
        "script": "styleseed_guard.py",
        "input_type": "workspace_scan",
        "mandatory": True,
        "description": "Enforces 4-tier token canon, 18-role semantic graph, and spatial rhythm hierarchy.",
    },
    "asset_provenance_guard": {
        "title": "Asset Provenance Guard",
        "script": "asset_provenance_guard.py",
        "input_type": "workspace_scan",
        "mandatory": False,
        "description": "Enforces cryptographic SHA-256 asset integrity and open-source license provenance.",
    },
    "pr_boundary_guard": {
        "title": "PR Boundary & Git Topology Guard",
        "script": "pr_boundary_guard.py",
        "input_type": "pr_metadata",
        "mandatory": True,
        "description": "Enforces PR branch topology, commit line limits, and radio-button template contracts.",
    },
    "honeypot_trap_guard": {
        "title": "Honeypot Trap & Prompt Canary Guard",
        "script": "honeypot_trap_guard.py",
        "input_type": "pr_metadata",
        "mandatory": False,
        "skip_reason": "No canary token provided (--canary-token)",
        "description": "Detects ungrounded LLM crawlers via HMAC-SHA256 canary tokens and decoy traps.",
    },
    "invariant_steward_guard": {
        "title": "Repo Memory & Invariant Steward",
        "script": "invariant_steward_guard.py",
        "input_type": "ledger_record",
        "mandatory": False,
        "skip_reason": "Invariant ledger (.anti-slop/invariant-ledger.json) not present",
        "description": "Tracks living invariant ledger and checks PRs for architectural drift.",
    },
    "house_tell_guard": {
        "title": "House-Tell Guard",
        "script": "house_tell_guard.py",
        "input_type": "ledger_record",
        "mandatory": False,
        "skip_reason": "Gate 0 commit-sheet (.anti-slop/commit-sheet.json) not present",
        "description": "Enforces physical Gate 0 commit-sheet and agent reflex habit breaking.",
    },
    "re0_handoff_guard": {
        "installed_skill": "re0-handoff-guard",
        "title": "Re0 State-Note Guard",
        "script": "re0_handoff_guard.py",
        "input_type": "ledger_record",
        "mandatory": False,
        "skip_reason": "Re0 state-note (.anti-slop/state-note.json) not present",
        "description": "Audits 1500-token RSI context reset and cold-read Shower Test.",
    },
    "reduction_guard": {
        "installed_skill": "reduction-guard",
        "title": "Musk Reduction & Add-Back Governor",
        "script": "reduction_guard.py",
        "input_type": "ledger_record",
        "mandatory": False,
        "skip_reason": "Add-back ledger (.anti-slop/add-back-ledger.jsonl) not present",
        "description": "Enforces 5-step reduction algorithm and 10% add-back calibration gate.",
    },
    "decision_guard": {
        "title": "Decision Guard",
        "script": "decision_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--decision-record",
        "skip_reason": "Requires dedicated Decision Guard JSON record (--decision-record <file>)",
        "description": "Validates premise evidence, user vs proposed method, and operational horizons.",
    },
    "root_fix_guard": {
        "title": "Root-Fix Gate Guard",
        "script": "root_fix_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--root-fix-record",
        "skip_reason": "Requires dedicated Root-Fix Gate JSON record (--root-fix-record <file>)",
        "description": "Traces causal ownership and boundary corrections against repeated symptom patches.",
    },
    "future_scale_guard": {
        "title": "Future-Scale Gate Guard",
        "script": "future_scale_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--future-scale-record",
        "skip_reason": "Requires dedicated Future-Scale Gate JSON record (--future-scale-record <file>)",
        "description": "Validates credible future envelopes, reversibility, and evolution proof.",
    },
    "paranoid_guard": {
        "title": "Paranoid Principal Architect Guard",
        "script": "paranoid_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--paranoid-record",
        "skip_reason": "Requires dedicated Paranoid Architect JSON record (--paranoid-record <file>)",
        "description": "Validates 10M-user zero-trust architecture, cursor pagination, and timeouts.",
    },
    "perf_guard": {
        "title": "Mechanical Sympathy & Perf Gate Guard",
        "script": "perf_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--perf-record",
        "skip_reason": "Requires dedicated Mechanical Sympathy JSON record (--perf-record <file>)",
        "description": "Enforces hardware cache locality, 120Hz frame budgets, and streaming limits.",
    },
    "rollout_guard": {
        "title": "Rollout Choreographer Guard",
        "script": "rollout_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--rollout-record",
        "skip_reason": "Requires dedicated Rollout Choreographer JSON record (--rollout-record <file>)",
        "description": "Enforces bidirectional wire compatibility, dark launches, and kill-switches.",
    },
    "simulation_guard": {
        "title": "Deterministic Simulation & Property Guard",
        "script": "simulation_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--simulation-record",
        "skip_reason": "Requires dedicated Simulation & Property JSON record (--simulation-record <file>)",
        "description": "Enforces Property-Based Testing, virtual clock seeds, and transition tables.",
    },
    "privacy_guard": {
        "title": "Privacy & Data Lineage Guard",
        "script": "privacy_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--privacy-record",
        "skip_reason": "Requires dedicated Privacy & Data Lineage JSON record (--privacy-record <file>)",
        "description": "Enforces branded Tainted PII types, crypto-shredding, and data minimization.",
    },
    "api_contract_guard": {
        "title": "API Contract & Ergonomics Governor",
        "script": "api_contract_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--contract-record",
        "skip_reason": "Requires dedicated API Contract JSON record (--contract-record <file>)",
        "description": "Enforces pit-of-success defaults, discriminated unions, and RFC 9457 errors.",
    },
    "apple_craft_guard": {
        "title": "Apple Craft & Interaction Physics Guard",
        "script": "apple_craft_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--apple-craft-record",
        "skip_reason": "Requires dedicated Apple Craft & Interaction Physics record (--apple-craft-record <file>)",
        "description": "Enforces 120Hz interaction physics, CLS=0.000, and exhaustive state matrices.",
    },
    "observability_guard": {
        "title": "Observability & SLO Architect Guard",
        "script": "observability_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--observability-record",
        "skip_reason": "Requires dedicated Observability & SLO JSON record (--observability-record <file>)",
        "description": "Enforces OpenTelemetry traceparents, low-cardinality metrics, and Multi-Burn-Rate SLOs.",
    },
    "motion_runtime_guard": {
        "title": "DPR-2 Runtime Motion & Fillrate Guard",
        "script": "motion_runtime_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--motion-record",
        "skip_reason": "Requires dedicated runtime motion profile JSON record (--motion-record <file>)",
        "description": "Validates DPR-2 retina motion performance, long tasks, and audio policy.",
    },
    "verification_oracle_guard": {
        "title": "Verification Oracle & Counterfactual Proof Guard",
        "script": "verification_oracle_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--verification-record",
        "skip_reason": "Requires dedicated Verification Oracle JSON record (--verification-record <file>)",
        "description": "Audits verified fakes, metamorphic oracles, seeded chaos, and red-green proof.",
    },
    "profiler_guard": {
        "title": "Mechanical Sympathy & Empirical Profiler Guard",
        "script": "profiler_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--profiler-record",
        "skip_reason": "Requires dedicated Mechanical Sympathy Profiler JSON record (--profiler-record <file>)",
        "description": "Validates baseline/post-change measurements, bounded streaming, and zero-allocation hot paths.",
    },
    "fault_isolation_guard": {
        "title": "Scientific Fault Isolation Guard",
        "script": "fault_isolation_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--fault-isolation-record",
        "skip_reason": "Requires dedicated Scientific Fault Isolation JSON record (--fault-isolation-record <file>)",
        "description": "Validates 3-hypothesis differential diagnosis, binary search isolation, and determinism pinning.",
    },
    "migration_guard": {
        "title": "Zero-Downtime Migration Guard",
        "script": "migration_guard.py",
        "input_type": "record_audit",
        "requires_input": True,
        "input_flag": "--migration-record",
        "skip_reason": "Requires dedicated Zero-Downtime Migration JSON record (--migration-record <file>)",
        "description": "Validates Expand-Migrate-Contract phases, lock-free DDL, and N/N-1 wire compatibility.",
    },
    "backprop_guard": {
        "title": "Rule & Invariant Backpropagation Guard",
        "script": "backprop_guard.py",
        "input_type": "reactive_tool",
        "excluded_from_audit": True,
        "exclusion_reason": "Reactive remediation tool invoked on a specific failure (--finding <id> --file <f>)",
        "description": "Backpropagates downstream code failures into upstream rules and invariant ledger.",
    },
    "exec_guard": {
        "title": "In-Flight Execution Guard",
        "script": "exec_guard.py",
        "input_type": "runtime_guard",
        "excluded_from_audit": True,
        "exclusion_reason": "In-flight agent directive interceptor executed during tool calls, not static audit",
        "description": "Intercepts agent bash/file modifications against active mode directives.",
    },
    "run_cases": {
        "title": "Pairwise Evaluation Benchmark Runner",
        "script": "run_cases.py",
        "input_type": "test_harness",
        "excluded_from_audit": True,
        "exclusion_reason": "Benchmark evaluation test runner exercising pairwise test cases, not static audit",
        "description": "Runs pairwise evaluation scenarios comparing model behavioral outcomes.",
    },
}

CLI_COMMAND_TO_GUARD_MAP: Dict[str, str] = {
    "diff": "diff_guard",
    "diff-guard": "diff_guard",
    "guard": "diff_guard",
    "rust": "diff_guard",
    "sts": "diff_guard",
    "rust-guard": "diff_guard",
    "toil": "sre_guard",
    "go-guard": "sre_guard",
    "toil-guard": "sre_guard",
    "sre": "sre_guard",
    "sre-guard": "sre_guard",
    "decision": "decision_guard",
    "decision audit": "decision_guard",
    "root-fix": "root_fix_guard",
    "root-fix audit": "root_fix_guard",
    "future-scale": "future_scale_guard",
    "future-scale audit": "future_scale_guard",
    "paranoid": "paranoid_guard",
    "paranoid audit": "paranoid_guard",
    "perf": "perf_guard",
    "perf-guard": "perf_guard",
    "perf audit": "perf_guard",
    "rollout": "rollout_guard",
    "rollout-guard": "rollout_guard",
    "rollout audit": "rollout_guard",
    "choreographer": "rollout_guard",
    "sim": "simulation_guard",
    "simulation": "simulation_guard",
    "dst": "simulation_guard",
    "sim-guard": "simulation_guard",
    "sim audit": "simulation_guard",
    "privacy": "privacy_guard",
    "privacy-guard": "privacy_guard",
    "data-lineage-guard": "privacy_guard",
    "privacy audit": "privacy_guard",
    "contract": "api_contract_guard",
    "api-contract": "api_contract_guard",
    "contract-guard": "api_contract_guard",
    "contract audit": "api_contract_guard",
    "ergonomics": "api_contract_guard",
    "apple-craft": "apple_craft_guard",
    "apple-craft-guard": "apple_craft_guard",
    "apple-craft audit": "apple_craft_guard",
    "interaction-physics": "apple_craft_guard",
    "frame-budget": "apple_craft_guard",
    "frame-budget-guard": "apple_craft_guard",
    "observability": "observability_guard",
    "observability-guard": "observability_guard",
    "observability audit": "observability_guard",
    "slo": "observability_guard",
    "slo-guard": "observability_guard",
    "monarch": "observability_guard",
    "dapper": "observability_guard",
    "hunter": "forensic_hunter",
    "forensic": "forensic_hunter",
    "forensic-hunter": "forensic_hunter",
    "exec": "exec_guard",
    "exec-guard": "exec_guard",
    "cases": "run_cases",
    "run-cases": "run_cases",
    "ast": "ast_slop_guard",
    "ast-slop": "ast_slop_guard",
    "ts-slop": "ast_slop_guard",
    "contrast": "contrast_guard",
    "contrast-guard": "contrast_guard",
    "pr-guard": "pr_boundary_guard",
    "pr-boundary": "pr_boundary_guard",
    "pr-check": "pr_boundary_guard",
    "honeypot": "honeypot_trap_guard",
    "honeypot-guard": "honeypot_trap_guard",
    "canary": "honeypot_trap_guard",
    "comment-guard": "comment_budget_guard",
    "comment-budget": "comment_budget_guard",
    "ccr": "comment_budget_guard",
    "attention": "attention_guard",
    "cognitive": "attention_guard",
    "scannability": "attention_guard",
    "focus": "attention_guard",
    "attention-guard": "attention_guard",
    "steward": "invariant_steward_guard",
    "invariant": "invariant_steward_guard",
    "invariant-steward": "invariant_steward_guard",
    "repo-memory": "invariant_steward_guard",
    "demock": "demock_guard",
    "demock-guard": "demock_guard",
    "mandela": "mandela_guard",
    "mandela-guard": "mandela_guard",
    "reduction": "reduction_guard",
    "elon": "reduction_guard",
    "re0-handoff": "re0_handoff_guard",
    "state-note": "re0_handoff_guard",
    "shower-test": "re0_handoff_guard",
    "backprop": "backprop_guard",
    "backprop-guard": "backprop_guard",
    "system-drift": "system_drift_guard",
    "systemscan": "system_drift_guard",
    "drift-guard": "system_drift_guard",
    "variant-budget": "system_drift_guard",
    "chroma-drift": "chroma_drift_guard",
    "chromadiff": "chroma_drift_guard",
    "chroma": "chroma_drift_guard",
    "aesthetic-drift": "chroma_drift_guard",
    "house-tell": "house_tell_guard",
    "commit-sheet": "house_tell_guard",
    "tell-guard": "house_tell_guard",
    "reflex-guard": "house_tell_guard",
    "motion-runtime": "motion_runtime_guard",
    "motionqa": "motion_runtime_guard",
    "runtime-motion": "motion_runtime_guard",
    "fillrate": "motion_runtime_guard",
    "asset-provenance": "asset_provenance_guard",
    "provenance": "asset_provenance_guard",
    "asset-guard": "asset_provenance_guard",
    "source-ledger": "asset_provenance_guard",
    "styleseed": "styleseed_guard",
    "styleseed-guard": "styleseed_guard",
    "styleseed-engine": "styleseed_guard",
    "tagore": "tagore_guard",
    "tagore-guard": "tagore_guard",
    "discourse": "tagore_guard",
    "deslop-prose": "tagore_guard",
    "humanize": "tagore_guard",
    "prose": "tagore_guard",
    "oracle": "verification_oracle_guard",
    "oracle-guard": "verification_oracle_guard",
    "oracle audit": "verification_oracle_guard",
    "verification-oracle": "verification_oracle_guard",
    "counterfactual": "verification_oracle_guard",
    "proof": "verification_oracle_guard",
    "profiler": "profiler_guard",
    "profiler-guard": "profiler_guard",
    "profiler audit": "profiler_guard",
    "fault-isolation": "fault_isolation_guard",
    "fault-isolation-guard": "fault_isolation_guard",
    "fault-isolation audit": "fault_isolation_guard",
    "migration": "migration_guard",
    "migration-guard": "migration_guard",
    "migration audit": "migration_guard",
}

EXCLUDED_CLI_COMMANDS: Dict[str, str] = {
    "design": "External approval boundary; run design check with trusted verifier and owner-controlled trust separately.",
    "serve-rust": "Daemon lifecycle command for background Rust HTTP microservice (:9091)",
    "serve-go": "Daemon lifecycle command for background Go HTTP microservice (:9092)",
    "mcp-server": "MCP stdio server exposing anti-slop tools to agentic IDEs and Antigravity",
    "mcp": "Alias for mcp-server subcommand",
    "neural": "Neural invariant network query router and graph inspector",
    "skills": "Universal skills compliance engine evaluating target code against all 46 skills",
    "skills-compliance": "Alias for skills compliance engine command",
    "verify": "Alias for skills compliance verification",
    "extract-skills": "Extractor tool compiling all 46 skills rules and axioms into JSON ledger",
    "explain": "Catalog entry and remediation lookup",
    "build": "Build orchestration compiling native Rust and Go microservice binaries",
    "audit": "Unified multi-guard orchestrator entrypoint (invokes canonical registry)",
    "mode": "Execution mode governor setting active inline vs post-hoc audit behavior",
    "check-engines": "Polyglot engine requirements validator checking toolchains (cargo, go, node, bun)",
    "check-engine": "Single engine toolchain validator with graceful degradation notices",
    "run-engine": "Engine execution wrapper providing graceful degradation for optional toolchains",
    "check-changed": "Run contributor checks for paths changed from a Git revision",
    "install": "Skills installation across AI coding agent configurations",
    "setup": "Alias for install command",
    "update": "Skills update and pointer block synchronization across AI coding agents",
    "ruff": "Python codebase linter wrapper",
    "oxlint": "Oxlint AST linter wrapper for JavaScript/TypeScript",
    "clippy": "Cargo Clippy linter wrapper for native Rust microservice",
    "lint-rust": "Alias for clippy command",
    "install-oxlint": "Installer script vendoring anti-slop Oxlint plugin into consumer repositories",
    "install-anti-slop": "Alias for install-oxlint vendoring installer script",
    "update-oxlint": "Updater script reconciling vendored Oxlint rules with upstream",
    "bump": "Release management script updating version across 13 repository manifests",
    "test": "Development test runner executing unittest and verification suites",
    "test-all": "Development test runner executing all test suites across polyglot engines",
    "check": "Development test runner executing test and verification gates",
    "check-all": "Development test runner executing all test suites across polyglot engines",
    "contribute": "Interactive guidelines printer for community slop reporting and PRs",
    "version": "CLI version display",
    "--version": "CLI version flag",
    "-v": "CLI version flag shorthand",
}

RECORD_FLAG_TO_GUARD_MAP: Dict[str, str] = {
    "decision_record": "decision_guard",
    "root_fix_record": "root_fix_guard",
    "future_scale_record": "future_scale_guard",
    "paranoid_record": "paranoid_guard",
    "perf_record": "perf_guard",
    "rollout_record": "rollout_guard",
    "simulation_record": "simulation_guard",
    "privacy_record": "privacy_guard",
    "contract_record": "api_contract_guard",
    "apple_craft_record": "apple_craft_guard",
    "observability_record": "observability_guard",
    "motion_record": "motion_runtime_guard",
    "profiler_record": "profiler_guard",
    "fault_isolation_record": "fault_isolation_guard",
    "migration_record": "migration_guard",
}

ENGINE_REGISTRY: Dict[str, Dict[str, str]] = {
    "cargo": {
        "name": "Rust (Cargo)",
        "binary": "cargo",
        "install_url": "https://rustup.rs",
        "hint": "Install rustup from https://rustup.rs for Rust native engine verification.",
    },
    "go": {
        "name": "Go (Go toolchain)",
        "binary": "go",
        "install_url": "https://golang.org/dl/",
        "hint": "Install Go from https://golang.org/dl/ for Go SRE engine verification.",
    },
    "node": {
        "name": "Node.js runtime",
        "binary": "node",
        "install_url": "https://nodejs.org/",
        "hint": "Install Node.js from https://nodejs.org/ for JavaScript/TypeScript tooling.",
    },
    "bun": {
        "name": "Bun runtime",
        "binary": "bun",
        "install_url": "https://bun.sh",
        "hint": "Install Bun from https://bun.sh for fast TypeScript and security test execution.",
    },
}

ENGINE_ALIASES: Dict[str, str] = {
    "rust": "cargo",
    "golang": "go",
    "js": "node",
    "javascript": "node",
    "ts": "node",
    "typescript": "node",
}


def is_strict_engine_mode() -> bool:
    """Return True if strict engine requirements are enforced (CI or STRICT_ENGINE_CHECK)."""
    ci_val = os.environ.get("CI", "").strip().lower()
    gh_val = os.environ.get("GITHUB_ACTIONS", "").strip().lower()
    strict_val = os.environ.get("STRICT_ENGINE_CHECK", "").strip().lower()
    return ci_val in ("true", "1", "yes") or gh_val in ("true", "1", "yes") or strict_val in ("true", "1", "yes")


def check_engine(engine: str, strict: Optional[bool] = None) -> Tuple[bool, str]:
    """Check availability of a polyglot engine toolchain.

    Returns:
        (is_available, message)
    """
    key = engine.strip().lower()
    canonical = ENGINE_ALIASES.get(key, key)
    if canonical not in ENGINE_REGISTRY:
        return False, f"Unknown engine requirement: {engine}"

    if strict is None:
        strict = is_strict_engine_mode()

    spec = ENGINE_REGISTRY[canonical]
    bin_name = spec["binary"]
    bin_path = shutil.which(bin_name)

    if bin_path:
        return True, f"{spec['name']} is available ({bin_path})"

    if strict:
        return (
            False,
            f"Error: Required engine '{canonical}' ({spec['name']}) not found on PATH. "
            f"In CI or strict mode, all polyglot engines are mandatory. {spec['hint']}",
        )
    return (
        False,
        f"[NOTICE] Optional engine '{canonical}' ({spec['name']}) not found. "
        f"Skipping engine run. {spec['hint']}",
    )


def check_engines(
    engines: Optional[List[str]] = None,
    strict: Optional[bool] = None,
) -> Dict[str, Tuple[bool, str]]:
    """Check multiple engines, returning mapping of canonical engine name to (available, message)."""
    target_engines = engines or list(ENGINE_REGISTRY.keys())
    return {eng: check_engine(eng, strict=strict) for eng in target_engines}


def _emit_engine_message(msg: str, strict: Optional[bool]) -> int:
    """Print engine notice/error and return exit code based on strict mode."""
    if msg.startswith("Unknown engine requirement:"):
        print(msg, file=sys.stderr)
        return 2
    if strict if strict is not None else is_strict_engine_mode():
        print(msg, file=sys.stderr)
        return 1
    print(msg)
    return 0


def run_engine_command(
    engine: str,
    command: List[str],
    strict: Optional[bool] = None,
    title: Optional[str] = None,
    cwd: Optional[str] = None,
) -> int:
    """Run a command guarded by an engine toolchain check.

    If the engine is available:
        Executes the command and returns the process exit code.
    If the engine is absent and strict:
        Prints error to stderr and returns 1.
    If the engine is absent and non-strict:
        Prints informative notice to stdout and returns 0 (gracefully skipped).
    """
    available, msg = check_engine(engine, strict=strict)
    if not available:
        return _emit_engine_message(msg, strict=strict)

    if title:
        print(f"=== {title} ===")
    res = subprocess.run(command, cwd=cwd)
    return res.returncode


def changed_check_targets(base: str, root: str = ".") -> List[str]:
    commands = (
        ["diff", "--name-only", "--no-renames", "-z", "--end-of-options", base, "HEAD", "--"],
        ["diff", "--name-only", "--no-renames", "-z", "--cached", "--"],
        ["diff", "--name-only", "--no-renames", "-z", "--"],
        ["ls-files", "-z", "--others", "--exclude-standard"],
    )
    paths = set()
    for args in commands:
        result = subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE)
        paths.update(os.fsdecode(path) for path in result.stdout.split(b"\0") if path)

    selected = set()
    for path in paths:
        if path in {"Makefile", "AGENTS.md", "SKILL.md"} or path.startswith(".github/workflows/"):
            return ["check-all"]
        if path.endswith(".py") or path in {"pyproject.toml", "ruff.toml", "install.sh"}:
            selected.add("check")
        if path.startswith("services/anti-slop-rust/"):
            selected.update(("test-rust", "clippy"))
        if path.startswith("services/toil-guard-go/"):
            selected.add("test-go")
        if path.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx")) or path in {
            "package.json", "bun.lock", "bun.lockb", ".oxlintrc.json", "skills.sh.json",
        }:
            selected.update(("oxlint", "test-security", "test-node"))

    order = ("check", "oxlint", "test-security", "test-node", "test-rust", "clippy", "test-go")
    return [target for target in order if target in selected]


def handle_check_changed(args: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Run checks for paths changed against a Git revision")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--make", default="make")
    options = parser.parse_args(args)
    try:
        targets = changed_check_targets(options.base)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    if not targets:
        print("No runtime checks selected for changed paths.")
        return 0
    print("Selected checks: " + ", ".join(targets), flush=True)
    return subprocess.run([options.make, *targets]).returncode


def get_settings_file(max_depth: int = 5) -> Path:
    if LOCAL_SETTINGS_FILE.exists():
        return LOCAL_SETTINGS_FILE
    return GLOBAL_SETTINGS_FILE


def load_settings() -> Dict[str, Any]:
    file_path = get_settings_file()
    if not file_path.exists():
        return {"mode": "during"}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError) as exc:
        print(f"Invalid settings file {file_path}: {exc}; using default mode", file=sys.stderr)
    return {"mode": "during"}


def save_settings(settings: Dict[str, Any], global_scope: bool = False) -> None:
    file_path = GLOBAL_SETTINGS_FILE if global_scope else (
        LOCAL_SETTINGS_FILE if LOCAL_CONFIG_DIR.exists() else GLOBAL_SETTINGS_FILE
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def handle_mode(args: List[str]) -> int:
    if not args:
        current = load_settings().get("mode", "during")
        print(f"Current anti-slop-engineering mode: {current}")
        return 0

    mode = args[0].lower()
    if mode in ("during", "after", "ask"):
        settings = load_settings()
        settings["mode"] = mode
        save_settings(settings)
        print(f"anti-slop-engineering mode set to: {mode}")
        return 0
    else:
        print(f"Error: Invalid mode '{mode}'. Choose 'during', 'after', or 'ask'.", file=sys.stderr)
        return 2


def run_command(cmd: List[str], *, restricted_env: bool = False) -> Dict[str, Any]:
    env = None
    if restricted_env:
        # Windows exposes its case-insensitive environment under uppercase keys.
        env = {name: value for name, value in os.environ.items() if name in GUARD_ENV_NAMES}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=GUARD_TIMEOUT_SECONDS, env=env)
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
                "timed_out": False, "error": None}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {"exit_code": None, "stdout": stdout, "stderr": stderr,
                "timed_out": True, "error": f"Timed out after {GUARD_TIMEOUT_SECONDS} seconds"}
    except OSError as exc:
        return {"exit_code": None, "stdout": "", "stderr": "", "timed_out": False,
                "error": f"Unable to execute child process: {exc}"}


def _validate_out_dir(directory: Path) -> Path:
    directory = Path(directory)
    if directory.exists() and not directory.is_dir():
        raise ValueError(f"Audit output path is not a directory: {directory}")
    return directory


def get_next_audit_file(directory: Optional[Path] = None) -> Path:
    out_dir = _validate_out_dir(directory) if directory is not None else AUDIT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("audit-*.md"))
    max_idx = 0
    for p in existing:
        m = re.match(r"audit-(\d+)", p.name)
        if m:
            max_idx = max(max_idx, int(m.group(1)))
    next_idx = max_idx + 1
    today = datetime.date.today().isoformat()
    return out_dir / f"audit-{next_idx:03d}-{today}.md"


def build_guard_command(
    name: str,
    base: str,
    pr_title: str = "",
    pr_body_file: str = "",
    template_file: str = "",
    canary_token: str = "",
    record_file: Optional[str] = None,
) -> Optional[List[str]]:
    spec = GUARD_REGISTRY.get(name)
    if not spec or spec.get("excluded_from_audit"):
        return None

    scripts_dir = Path(__file__).resolve().parent
    script_path = scripts_dir / spec["script"]

    if spec.get("requires_input"):
        if not record_file:
            return None
        if name == "motion_runtime_guard":
            return [sys.executable, str(script_path), "--file", record_file, "--json"]
        return [sys.executable, str(script_path), "audit", record_file, "--json"]

    if spec["input_type"] == "ledger_record":
        if name == "invariant_steward_guard":
            ledger = Path.cwd() / ".anti-slop" / "invariant-ledger.json"
            if not ledger.exists():
                return None
            return [sys.executable, str(script_path), "drift", "--base", base, "--ledger", str(ledger), "--json"]
        if name == "house_tell_guard":
            sheet = Path.cwd() / ".anti-slop" / "commit-sheet.json"
            if not sheet.exists():
                return None
            return [sys.executable, str(script_path), "--file", str(sheet), "--json"]
        if name == "re0_handoff_guard":
            state_note = Path.cwd() / ".anti-slop" / "state-note.json"
            if not state_note.exists():
                return None
            return [sys.executable, str(script_path), "shower-test", "--json"]
        if name == "reduction_guard":
            ledger = Path.cwd() / ".anti-slop" / "add-back-ledger.jsonl"
            if not ledger.exists():
                return None
            return [sys.executable, str(script_path), "status", "--json"]
        return None

    if spec["input_type"] == "pr_metadata":
        if name == "pr_boundary_guard":
            args = ["--base", base]
            if pr_title:
                args.extend(["--pr-title", pr_title])
            if pr_body_file:
                args.extend(["--pr-body-file", pr_body_file])
            if template_file:
                args.extend(["--template-file", template_file])
            return [sys.executable, str(script_path), *args, "--json"]
        if name == "honeypot_trap_guard":
            if not canary_token:
                return None
            args = ["--pr-title", pr_title, "--canary-token", canary_token]
            if pr_body_file:
                args.extend(["--pr-body-file", pr_body_file])
            return [sys.executable, str(script_path), *args, "--json"]
        return None

    if spec["input_type"] == "workspace_scan":
        if name == "styleseed_guard":
            tokens = Path.cwd() / ".anti-slop" / "tokens.json"
            extra = ["--tokens", str(tokens)] if tokens.exists() else []
            spacing = Path.cwd() / ".anti-slop" / "spacing.json"
            if spacing.exists():
                extra.extend(["--spacing", str(spacing)])
            return [sys.executable, str(script_path), "--scan", ".", *extra, "--json"]
        return [sys.executable, str(script_path), "--scan", ".", "--json"]

    if spec["input_type"] == "git_diff":
        return [sys.executable, str(script_path), "--base", base, "--json"]

    return None


def guard_commands(
    base: str, pr_title: str = "", pr_body_file: str = "",
    template_file: str = "", canary_token: str = "",
) -> List[Tuple[str, Optional[List[str]]]]:
    return [
        (name, build_guard_command(name, base, pr_title, pr_body_file, template_file, canary_token))
        for name in GUARD_REGISTRY
    ]


def normalize_finding(name: str, finding: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    severity = str(finding.get("severity", finding.get("level", ""))).lower()
    fallback = "MEDIUM" if name in {
        "ast_slop_guard", "contrast_guard", "system_drift_guard",
        "chroma_drift_guard", "styleseed_guard", "tagore_guard",
    } else "HIGH"
    if severity in {"blocker", "block", "blocking", "error", "critical"}:
        level = "BLOCKER"
    elif severity == "high":
        level = "HIGH"
    elif severity == "low":
        level = "LOW"
    elif severity in {"medium", "warning"}:
        level = "MEDIUM"
    else:
        level = fallback

    default_targets = {
        "pr_boundary_guard": "git://topology",
        "invariant_steward_guard": "ledger://invariants",
        "attention_guard": "doc://markdown",
        "reduction_guard": "ledger://add-back",
        "house_tell_guard": "sheet://commit-sheet",
        "re0_handoff_guard": "state://state-note",
        "asset_provenance_guard": "assets://provenance",
    }
    message = (
        finding.get("message")
        or finding.get("evidence")
        or finding.get("description")
        or finding.get("detail")
        or finding.get("title")
        or finding.get("impact")
        or ""
    )
    if name == "contrast_guard" and finding.get("fg") and finding.get("bg"):
        message = (
            f"Low contrast color pairing: {finding.get('fg')} on {finding.get('bg')} "
            f"({finding.get('ratio')}:1 fails AA)"
        )
    remediation = (
        finding.get("remediation")
        or finding.get("action")
        or finding.get("recommendation")
        or finding.get("independence_fix")
        or finding.get("suggested_replacement")
        or finding.get("remedy")
    )
    if not remediation and isinstance(report.get("remediation"), dict):
        remediation = report["remediation"].get("guidance") or report["remediation"].get("action")

    rule = (
        finding.get("rule")
        or finding.get("rule_id")
        or finding.get("trap_id")
        or finding.get("pattern")
        or finding.get("id")
        or finding.get("category")
        or finding.get("principle")
        or finding.get("class")
        or "AUDIT-FINDING"
    )

    return {
        "guard": name,
        "rule": str(rule),
        **finding_metadata(str(rule), name),
        "severity": level,
        "file": str(finding.get("file") or default_targets.get(name, "")),
        "line": finding.get("line", 1 if name in default_targets else 0),
        "message": str(message),
        "snippet": str(finding.get("snippet") or finding.get("line_content")
                       or finding.get("evidence") or finding.get("matched_text") or ""),
        "remediation": str(remediation or "Review and remediate the reported guard finding"),
    }


def redact_command(command: List[str]) -> List[str]:
    safe = list(command)
    for flag in ("--canary-token", "--pr-title"):
        if flag in safe:
            index = safe.index(flag)
            if index + 1 < len(safe):
                safe[index + 1] = "<redacted>"
    return safe


def _extract_raw_findings(report: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    container_keys = [k for k in ("findings", "issues", "violations") if k in report]
    if container_keys:
        for k in container_keys:
            if not isinstance(report[k], list):
                return None
        raw: Optional[List[Any]] = None
        for k in ("findings", "issues", "violations"):
            if k in report and isinstance(report[k], list):
                raw = report[k]
                break
    else:
        if report.get("verdict") or report.get("status") or report.get("passed") is not None:
            raw = []
        else:
            return None

    if raw is None or not isinstance(raw, list):
        return None
    normalized: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            normalized.append({"message": item, "severity": "WARNING", "rule": "ISSUE"})
        elif isinstance(item, dict):
            normalized.append(item)
        else:
            return None
    return normalized


def _validate_finding_severities(items: List[Dict[str, Any]]) -> Optional[str]:
    known_severities = {
        "blocker", "block", "blocking", "error", "critical",
        "high", "medium", "low", "warning", "review",
    }
    for item in items:
        raw_severity = item.get("severity", item.get("level"))
        if raw_severity is not None and str(raw_severity).lower() not in known_severities:
            return f"Invalid JSON report schema: unknown severity {raw_severity!r}"
    return None


def _validate_report_outcome(
    process: Dict[str, Any],
    report: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Optional[str]:
    blockers = any(item["severity"] == "BLOCKER" for item in findings)
    code = process["exit_code"]
    if not ((code == 0) or (code in (1, 2) and bool(findings))):
        return f"Guard exited with code {code} without a valid finding outcome"

    reported_status = str(report.get("status", "")).upper()
    reported_verdict = str(report.get("verdict", "")).upper()
    if report.get("passed") is False and not findings:
        return "Guard reported passed=false without findings"
    if (reported_status == "FINDINGS" or reported_verdict == "FINDINGS") and not findings:
        return "Guard reported FINDINGS status without findings"
    if (reported_status in {"FAIL", "BLOCKED"} or reported_verdict in {"FAIL", "REJECT"}) and not blockers:
        return "Guard reported FAIL without matching blocker findings"
    if reported_status in {"ERROR", "INCOMPLETE"} or reported_verdict in {"ERROR", "INCOMPLETE"}:
        return f"Guard reported unsuccessful status: {reported_status or reported_verdict}"
    return None


def _make_inactive_guard_entry(
    spec: Dict[str, Any],
    skip_type: str,
    reason: str,
) -> Dict[str, Any]:
    return {
        "title": spec.get("title", ""),
        "status": "SKIPPED",
        "skip_type": skip_type,
        "applicable": False,
        "input_type": spec.get("input_type", "unknown"),
        "input_flag": spec.get("input_flag"),
        "reason": reason,
        "command": None,
        "exit_code": None,
        "findings_count": 0,
        "error": None,
    }


def _parse_guard_report(
    process: Dict[str, Any],
    result: Dict[str, Any],
) -> Optional[Tuple[Dict[str, Any], List[Any]]]:
    if not process["stdout"].strip():
        result["error"] = "Missing JSON output from mandatory guard"
        result["status"] = "ERROR"
        return None
    try:
        report = json.loads(process["stdout"])
    except (ValueError, TypeError) as exc:
        result["error"] = f"Invalid JSON from guard: {exc}"
        result["stdout_excerpt"] = process["stdout"][:500]
        result["status"] = "ERROR"
        return None
    if not isinstance(report, dict):
        result["error"] = "Invalid JSON report schema: root must be an object"
        result["status"] = "ERROR"
        return None

    raw_items = _extract_raw_findings(report)
    if raw_items is None:
        result["error"] = "Invalid JSON report schema: required findings array"
        result["status"] = "ERROR"
        return None

    severity_err = _validate_finding_severities(raw_items)
    if severity_err:
        result["error"] = severity_err
        result["status"] = "ERROR"
        return None

    if report.get("error"):
        result["error"] = f"Guard reported error: {report['error']}"
        result["status"] = "ERROR"
        return None

    return report, raw_items


def evaluate_guard(
    name: str,
    command: Optional[List[str]],
    spec: Optional[Dict[str, Any]] = None,
    *,
    restricted_env: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    spec = spec or GUARD_REGISTRY.get(name, {})
    result: Dict[str, Any] = {
        "title": spec.get("title", name),
        "status": "SKIPPED" if command is None else "ERROR",
        "applicable": command is not None,
        "input_type": spec.get("input_type", "unknown"),
        "exit_code": None,
        "stderr": "",
        "timed_out": False,
        "error": None,
        "command": redact_command(command) if command is not None else None,
        "findings_count": 0,
    }
    if command is None:
        if spec.get("skip_reason"):
            result["reason"] = spec["skip_reason"]
        result["skip_type"] = "optional-target-absent"
        return result, []

    script_path = Path(command[1])
    if not script_path.is_file():
        if spec.get("mandatory"):
            result["error"] = f"Mandatory guard script missing: {command[1]}"
            result["status"] = "ERROR"
        else:
            result["status"] = "SKIPPED"
            result["applicable"] = False
            result["reason"] = f"Guard script not present in scripts directory: {script_path.name}"
        return result, []

    process = run_command(command, restricted_env=restricted_env)
    result.update({key: process[key] for key in ("exit_code", "stderr", "timed_out", "error")})
    if result["error"]:
        result["status"] = "ERROR"
        return result, []

    parsed = _parse_guard_report(process, result)
    if parsed is None:
        return result, []
    report, raw_items = parsed

    if name == "pr_boundary_guard" and isinstance(report.get("pr_metadata"), dict):
        result["pr_metadata"] = report["pr_metadata"]

    findings = [normalize_finding(name, item, report) for item in raw_items]
    result["findings_count"] = len(findings)

    outcome_err = _validate_report_outcome(process, report, findings)
    if outcome_err:
        result["error"] = outcome_err
        result["stdout_excerpt"] = process["stdout"][:500]
        result["status"] = "ERROR"
        return result, findings

    result["status"] = "FINDINGS" if findings else "PASS"
    return result, findings


def read_installed_skills(manifest: Path) -> set[str]:
    if manifest.name != ".anti-slop-selection.json" or manifest.is_symlink():
        raise ValueError("Expected a regular .anti-slop-selection.json installer manifest")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(manifest, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("The installer selection must be a regular file")
        with open(descriptor, encoding="utf-8", closefd=False) as source:
            state = json.load(source)
    finally:
        os.close(descriptor)
    if (
        not isinstance(state, dict)
        or type(state.get("format")) is not int
        or state["format"] != 1
        or state.get("scope") not in ("project", "global")
        or not isinstance(state.get("version"), str)
        or not isinstance(state.get("agents"), list)
    ):
        raise ValueError("Expected an installer selection in format 1")
    skills = state.get("skills")
    if (
        not isinstance(skills, list)
        or "anti-slop-engineering" not in skills
        or any(not isinstance(skill, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill) for skill in skills)
    ):
        raise ValueError("Expected explicit skill IDs including anti-slop-engineering")
    installed = {
        skill for skill in skills
        if (manifest.parent / skill / "SKILL.md").is_file()
    }
    if "anti-slop-engineering" not in installed:
        raise ValueError("Required core skill is absent beside the installer manifest")
    return installed


def _catalog_keeper(
    findings: List[Dict[str, Any]], indexes: List[int], catalog_id: str,
) -> Optional[int]:
    """Return the registered owner’s index when it reported this location."""
    owner = catalog_owner(catalog_id)
    if owner is not None:
        for index in indexes:
            entry = findings[index]
            if entry.get("guard") == owner.engine and entry.get("rule") == owner.engine_code:
                return index
    return None


def _suppress_catalog_duplicates(
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collapse cross-guard duplicates that share one catalog identity.

    Two guards can report the same catalog rule at the same file and line
    (a registered owner and one of its fallbacks). Keep the owner's entry,
    with its severity, and record each suppressed entry on it. Preserve
    fallback-only groups, same-guard findings, and distinct locations.
    """
    groups: Dict[Tuple[str, str, int], List[int]] = {}
    for index, finding in enumerate(findings):
        catalog_id = finding.get("catalog_id")
        line = finding.get("line")
        if not catalog_id or not finding.get("mapped") or not finding.get("file"):
            continue
        if not isinstance(line, int) or line < 1:
            continue
        key = (str(catalog_id), str(finding["file"]), line)
        groups.setdefault(key, []).append(index)

    dropped = set()
    suppressed: Dict[int, List[Dict[str, Any]]] = {}
    for (catalog_id, _file, _line), indexes in groups.items():
        if len(indexes) < 2:
            continue
        keeper = _catalog_keeper(findings, indexes, catalog_id)
        if keeper is None:
            continue
        for index in indexes:
            if findings[index].get("guard") == findings[keeper].get("guard"):
                continue
            dropped.add(index)
            entry = findings[index]
            suppressed.setdefault(keeper, []).append({
                "guard": entry.get("guard"),
                "rule": entry.get("rule"),
                "severity": entry.get("severity"),
            })

    result: List[Dict[str, Any]] = []
    for index, finding in enumerate(findings):
        if index in dropped:
            continue
        if index in suppressed:
            finding["suppressed_duplicates"] = suppressed[index]
        result.append(finding)
    return result


def collect_audit_findings(
    base: str = "HEAD", pr_title: str = "", pr_body_file: str = "",
    template_file: str = "", canary_token: str = "",
    records: Optional[Dict[str, str]] = None,
    installed_skills: Optional[set[str]] = None,
    restricted_env: bool = False,
    **extra_records: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    records_map: Dict[str, str] = {}
    for source in (records or {}, extra_records):
        for k, v in source.items():
            if not (v and isinstance(v, (str, Path))):
                continue
            norm_k = str(k).lstrip("-").replace("-", "_")
            val = str(v)
            records_map[norm_k] = val
            guard_key = RECORD_FLAG_TO_GUARD_MAP.get(norm_k)
            if guard_key:
                records_map[guard_key] = val

    findings: List[Dict[str, Any]] = []
    guards: Dict[str, Dict[str, Any]] = {}

    for name, spec in GUARD_REGISTRY.items():
        if spec.get("excluded_from_audit"):
            reason = spec.get("exclusion_reason", "Excluded from static audit runner")
            guards[name] = _make_inactive_guard_entry(spec, "not-applicable", reason)
            continue

        skill = spec.get("installed_skill")
        if skill and installed_skills is not None and skill not in installed_skills and not spec.get("mandatory"):
            guards[name] = _make_inactive_guard_entry(spec, "not-selected", f"Skill not installed: {skill}")
            continue

        record_path: Optional[str] = None
        if spec.get("requires_input"):
            record_path = (
                records_map.get(name)
                or records_map.get(spec.get("input_flag", "").lstrip("-").replace("-", "_"))
            )
            if not record_path:
                reason = spec.get("skip_reason", f"Requires dedicated assessment record ({spec.get('input_flag')})")
                guards[name] = _make_inactive_guard_entry(spec, "requires-input", reason)
                continue

        resolved_record = record_path or records_map.get(name)
        command = build_guard_command(
            name, base, pr_title=pr_title, pr_body_file=pr_body_file,
            template_file=template_file, canary_token=canary_token,
            record_file=resolved_record,
        )

        outcome, child_findings = evaluate_guard(name, command, spec, restricted_env=restricted_env)
        guards[name] = outcome
        findings.extend(child_findings)

    findings = _suppress_catalog_duplicates(findings)
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"FINDING-{index:03d}"
    return findings, guards


def _format_guard_badge_and_detail(
    st: str,
    g: Dict[str, Any],
    title: str,
    f_count: str,
) -> Tuple[str, str]:
    if st == "PASS":
        return "**PASS**", title
    if st in ("FINDINGS", "BLOCKED"):
        return f"**{st}**", f"{f_count} finding(s) detected"
    if st == "SKIPPED":
        skip_type = g.get("skip_type")
        reason = g.get("reason", "Optional target or ledger not present")
        if skip_type:
            return "*SKIPPED*", f"[{skip_type}] {reason}"
        return "*SKIPPED*", reason
    if st == "requires-input":
        return "*requires-input*", g.get("reason", "Requires dedicated assessment record")
    if st == "not-applicable":
        return "*not-applicable*", g.get("reason", "Specialized non-audit tool")
    if st == "ERROR":
        return "🚨 **ERROR**", g.get("error", "Execution failure")
    return f"`{st}`", title


def _render_guards_coverage_table(guards: Dict[str, Dict[str, Any]]) -> List[str]:
    lines = [
        "## Guards Coverage & Execution Status",
        "",
        "| Guard | Category | Status | Findings | Details |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for name, g in guards.items():
        title = g.get("title", name)
        cat = g.get("input_type", "unknown")
        st = g.get("status", "UNKNOWN")
        f_count = str(g.get("findings_count", 0)) if st in ("PASS", "FINDINGS", "BLOCKED") else "—"
        badge, detail = _format_guard_badge_and_detail(st, g, title, f_count)
        lines.append(f"| `{name}` | `{cat}` | {badge} | {f_count} | {detail} |")
    lines.append("")
    return lines


def _render_mode_banner(mode: str) -> str:
    normalized_mode = mode.lower() if mode else "during"
    if normalized_mode == "during":
        return (
            "In **DURING Mode** (in-flight development), resolve findings iteratively "
            "in your working tree before committing or submitting a pull request."
        )
    if normalized_mode == "after":
        return (
            "In **AFTER Mode** (post-implementation review), review all reported findings "
            "and apply manual, reviewable remediation before approving or merging changes."
        )
    return (
        f"In **{normalized_mode.upper()} Mode** (interactive triage), review each finding "
        "interactively and confirm manual remediation before proceeding."
    )


def _render_req_input_items(req_input: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    lines = []
    for name, g in req_input:
        flag = g.get("input_flag") or f"--{name.replace('_', '-')}-record"
        reason = g.get("reason", "Requires assessment record")
        lines.append(f"- [ ] `{name}`: Provide `{flag} <file>` ({reason})")
    return lines


def _render_remediation_workflow(
    findings: List[Dict[str, Any]],
    mode: str,
    guards: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    lines = [
        "---",
        "",
        "## Remediation & Review Workflow",
        "",
        _render_mode_banner(mode),
        "",
    ]
    if findings:
        lines.append("### Manual Remediation Checklist")
        lines.append("")
        lines.append("Review the detailed finding dossiers above and address each item:")
        lines.append("")
        for f in findings:
            target = f"{f['file']}:{f['line']}" if f.get("file") else "System"
            remediation = f.get("remediation", "Review and remediate finding")
            lines.append(f"- [ ] `{f['id']}` [{f['severity']}]: {remediation} (`{target}`)")
        lines.append("")
        lines.append("After applying manual fixes, re-run the multi-guard audit to verify resolution:")
        lines.append("")
        lines.append("```bash")
        lines.append("# Re-run multi-guard audit to verify fixes:")
        lines.append("python3 scripts/audit_runner.py audit --base HEAD")
        lines.append("```")
    else:
        errors = [
            (n, g) for n, g in (guards or {}).items()
            if g.get("status") == "ERROR"
        ]
        req_input = [
            (n, g) for n, g in (guards or {}).items()
            if g.get("skip_type") == "requires-input" or g.get("status") == "requires-input"
        ]
        if errors:
            lines.append("### Guard Execution Errors")
            lines.append("")
            lines.append(
                "One or more guards encountered execution errors during audit. "
                "Resolve the underlying errors and re-run:"
            )
            lines.append("")
            for name, g in errors:
                err_msg = g.get("error") or "Execution failed"
                lines.append(f"- [ ] `{name}`: {err_msg}")
            lines.append("")
            if req_input:
                lines.append("Additionally, the following guards require dedicated assessment records:")
                lines.append("")
                lines.extend(_render_req_input_items(req_input))
                lines.append("")
        elif req_input:
            lines.append("### Input Assessment Records Required")
            lines.append("")
            lines.append(
                "All evaluated guards passed with 0 findings. However, the following "
                "guards require dedicated assessment records for full audit coverage:"
            )
            lines.append("")
            lines.extend(_render_req_input_items(req_input))
            lines.append("")
            lines.append("To run full audit with all assessment records:")
            lines.append("")
            lines.append("```bash")
            lines.append("python3 scripts/audit_runner.py audit --base HEAD <record-flags>")
            lines.append("```")
        else:
            lines.append("All guards passed with 0 findings. No remediation required.")
            lines.append("")
            lines.append("```bash")
            lines.append("# Verify audit status before committing:")
            lines.append("python3 scripts/audit_runner.py audit --base HEAD")
            lines.append("```")
    return lines


def _render_findings_table(findings: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "## Findings Index",
        "",
        "| ID | Severity | Guard | Rule | Target | Message |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for f in findings:
        target = f"{f['file']}:{f['line']}" if f['file'] else "System"
        msg = f['message'].replace("|", "\\|")
        lines.append(f"| `{f['id']}` | **{f['severity']}** | `{f['guard']}` | `{f['rule']}` | `{target}` | {msg} |")
    return lines


def _render_detailed_dossiers(
    findings: List[Dict[str, Any]],
    guards: Optional[Dict[str, Dict[str, Any]]],
) -> List[str]:
    lines = [
        "",
        "---",
        "",
        "## Detailed Finding Dossiers",
        "",
    ]
    for name, result in (guards or {}).items():
        if result.get("status") == "ERROR":
            lines.append(f"- **{name} execution error:** {result.get('error')}")
    if guards and any(result.get("status") == "ERROR" for result in guards.values()):
        lines.append("")

    for f in findings:
        target = f"{f['file']}:{f['line']}" if f['file'] else "System"
        lines.extend([
            f"### [{f['id']}] {f['rule']}: {f['message']}",
            f"- **Target:** `{target}`",
            f"- **Severity:** {f['severity']}",
            f"- **Guard:** `{f['guard']}`",
        ])
        if f.get("catalog_id"):
            lines.append(f"- **Catalog:** `{f['catalog_id']}` · `{f['skill_path']}`")
        lines.extend([
            "",
            "```text",
            f.get("snippet", "(no snippet available)").strip(),
            "```",
            "",
            f"**Remediation:** {f['remediation']}",
            "",
        ])
    return lines


SCOPE_BY_INPUT_TYPE = {
    "git_diff": "diff",
    "pr_metadata": "diff",
    "workspace_scan": "workspace",
    "ledger_record": "record",
    "record_audit": "record",
}


def guard_scope(guard_name: Optional[str]) -> str:
    """Map a guard to its audit scope via the registry input type."""
    spec = GUARD_REGISTRY.get(guard_name or "", {})
    return SCOPE_BY_INPUT_TYPE.get(spec.get("input_type", ""), "other")


def _guard_bucket(entry: Dict[str, Any]) -> str:
    """Classify one guard into exactly one summary bucket."""
    if entry.get("status") == "ERROR" or entry.get("error"):
        return "errors"
    if entry.get("status") in ("PASS", "FINDINGS", "BLOCKED"):
        return "evaluated"
    if entry.get("skip_type") == "requires-input" or entry.get("status") == "requires-input":
        return "requires_input"
    if entry.get("skip_type") == "not-applicable" or entry.get("status") == "not-applicable":
        return "not_applicable"
    return "skipped"


def build_audit_summary(
    findings: List[Dict[str, Any]],
    guards: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """One scope-aware summary shared by the Markdown, JSON and console reports.

    Totals keep their legacy all-scope meaning. Each scope reports its own
    findings, blockers and verdict; the overall status stays legacy (any
    blocker in any scope blocks, any guard error errors), so no existing
    blocker is silently downgraded.
    """
    guards = guards or {}
    scopes: Dict[str, Dict[str, Any]] = {
        name: {"findings": 0, "blockers": 0, "status": "PASS"}
        for name in ("diff", "workspace", "record")
    }
    for finding in findings:
        bucket = scopes.setdefault(
            guard_scope(finding.get("guard")),
            {"findings": 0, "blockers": 0, "status": "PASS"},
        )
        bucket["findings"] += 1
        if finding.get("severity") == "BLOCKER":
            bucket["blockers"] += 1
    for bucket in scopes.values():
        bucket["status"] = "BLOCKED" if bucket["blockers"] else "PASS"

    guard_buckets = {
        "total_registered": len(guards),
        "evaluated": 0,
        "requires_input": 0,
        "skipped": 0,
        "not_applicable": 0,
        "errors": 0,
    }
    for entry in guards.values():
        guard_buckets[_guard_bucket(entry)] += 1

    blockers = sum(1 for f in findings if f.get("severity") == "BLOCKER")
    return {
        "total_findings": len(findings),
        "blockers_count": blockers,
        "high": sum(1 for f in findings if f.get("severity") == "HIGH"),
        "medium": sum(1 for f in findings if f.get("severity") == "MEDIUM"),
        "low": sum(1 for f in findings if f.get("severity") == "LOW"),
        "guards_summary": guard_buckets,
        "scopes": scopes,
        "diff_status": scopes["diff"]["status"],
        "status": "ERROR" if guard_buckets["errors"] else ("BLOCKED" if blockers else "PASS"),
    }


def generate_audit_markdown(
    findings: List[Dict[str, Any]], audit_file: Path,
    status: Optional[str] = None, guards: Optional[Dict[str, Dict[str, Any]]] = None,
    mode: Optional[str] = None,
) -> str:
    today = datetime.date.today().isoformat()
    summary = build_audit_summary(findings, guards)
    total = summary["total_findings"]
    blockers = summary["blockers_count"]
    guard_buckets = summary["guards_summary"]

    lines = [
        f"# Anti-Slop Engineering Audit Report — {audit_file.stem}",
        "",
        f"> Generated on {today} by Anti-Slop Engineering Multi-Guard Audit Runner.",
        "",
        "## Summary",
        "",
        f"- **Total Findings:** {total}",
        f"- **Blockers:** {blockers}",
        f"- **High Severity:** {summary['high']}",
        f"- **Medium Severity:** {summary['medium']}",
        f"- **Low Severity:** {summary['low']}",
        f"- **Guards Evaluated:** {guard_buckets['evaluated']}",
        f"- **Guards Requiring Input:** {guard_buckets['requires_input']}",
        f"- **Guards Skipped / Inapplicable:** {guard_buckets['skipped'] + guard_buckets['not_applicable']}",
        f"- **Guards Errors:** {guard_buckets['errors']}",
        "- **Guard Buckets:** evaluated = ran against the change; requiring input = needs a JSON record file (see the `--*-record` options) or manual evidence before it can run; skipped = did not run in this mode; inapplicable = the change has no targets for the guard.",
        f"- **Status:** {status or ('BLOCKED' if blockers > 0 else 'PASS')}",
        "",
        "| Scope | Findings | Blockers | Status |",
        "| :--- | ---: | ---: | :--- |",
    ]
    for scope_name in ("diff", "workspace", "record", "other"):
        scope = summary["scopes"].get(scope_name)
        if scope is None:
            continue
        lines.append(
            f"| {scope_name} | {scope['findings']} | {scope['blockers']} | {scope['status']} |")
    lines.append("")

    if guards:
        lines.extend(_render_guards_coverage_table(guards))

    lines.extend(_render_findings_table(findings))
    lines.extend(_render_detailed_dossiers(findings, guards))

    effective_mode = mode if mode is not None else load_settings().get("mode", "during")
    lines.extend(_render_remediation_workflow(findings, effective_mode, guards=guards))

    content = "\n".join(lines) + "\n"
    with audit_file.open("x", encoding="utf-8") as out_f:
        out_f.write(content)
    return content


def run_audit(
    base: str = "HEAD", json_output: bool = False, pr_title: str = "",
    pr_body_file: str = "", template_file: str = "", canary_token: str = "",
    mode: Optional[str] = None, records: Optional[Dict[str, str]] = None,
    installed_selection: Optional[Path] = None,
    restricted_env: bool = False,
    out_dir: Optional[Path] = None,
    **extra_records: Any,
) -> int:
    if out_dir is not None:
        _validate_out_dir(out_dir)
    installed_skills = None
    audit_error = None
    if installed_selection is not None:
        try:
            installed_skills = read_installed_skills(installed_selection)
        except (OSError, ValueError) as exc:
            audit_error = f"Unable to read installed skill selection: {exc}"
    findings, guards = collect_audit_findings(
        base, pr_title=pr_title, pr_body_file=pr_body_file,
        template_file=template_file, canary_token=canary_token,
        records=records, installed_skills=installed_skills, restricted_env=restricted_env, **extra_records
    )
    summary = build_audit_summary(findings, guards)
    blockers = summary["blockers_count"]
    status = "ERROR" if audit_error else summary["status"]
    audit_file = None
    effective_mode = mode if mode is not None else load_settings().get("mode", "during")
    try:
        while audit_file is None:
            candidate = get_next_audit_file(out_dir) if out_dir is not None else get_next_audit_file()
            try:
                generate_audit_markdown(findings, candidate, status=status, guards=guards, mode=effective_mode)
            except FileExistsError:
                # A concurrent audit claimed this name after we selected it.
                continue
            audit_file = candidate
    except OSError as exc:
        status = "ERROR"
        audit_error = f"Unable to write audit report: {exc}"

    report = {
        "audit_file": str(audit_file) if audit_file is not None else None,
        "total_findings": len(findings),
        "blockers_count": blockers,
        "guards_summary": summary["guards_summary"],
        "scopes": summary["scopes"],
        "diff_status": summary["diff_status"],
        "findings": findings,
        "guards": guards,
        "status": status,
    }
    if audit_error:
        report["error"] = audit_error

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print("\n📋 Multi-Guard Audit Complete.")
        print(f"   Dossier:         {audit_file or 'not written'}")
        print(f"   Guards:          {report['guards_summary']['evaluated']} evaluated, "
              f"{report['guards_summary']['requires_input']} require input, "
              f"{report['guards_summary']['skipped'] + report['guards_summary']['not_applicable']} skipped/inapplicable")
        print(f"   Total Findings:  {len(findings)}")
        scopes = summary["scopes"]
        print(f"   Scope Findings:  diff {scopes['diff']['findings']} · "
              f"workspace {scopes['workspace']['findings']} · record {scopes['record']['findings']}")
        print(f"   Status:          {status} ({blockers} blockers)")
        print(f"   Scope Status:    diff {scopes['diff']['status']} · "
              f"workspace {scopes['workspace']['status']} · record {scopes['record']['status']}")
        for name, result in guards.items():
            if result.get("status") == "ERROR":
                print(f"   ERROR {name}: {result.get('error')}", file=sys.stderr)
        if audit_error:
            print(f"   ERROR: {audit_error}", file=sys.stderr)
    return {"PASS": 0, "BLOCKED": 1, "ERROR": 2}[status]


def handle_audit(args: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the unified Anti-Slop audit")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--restricted-env", action="store_true",
        help="Pass only runtime, locale, temp, and CI branch variables to audit guards",
    )
    parser.add_argument("--installed-selection", type=Path,
                        help="Opt in to installed optional review skills using a format-1 selection manifest")
    parser.add_argument("--out", default="",
                        help="Directory for the audit dossier (default: inside the repo's .git directory)")
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--pr-body-file", default="")
    parser.add_argument("--template-file", default="")
    parser.add_argument("--canary-token", default="")
    parser.add_argument("--mode", default=None, choices=["during", "after", "ask"],
                        help="Override audit execution mode (during, after, ask)")
    parser.add_argument("--decision-record", default="", help="Path to Decision Guard JSON record")
    parser.add_argument("--root-fix-record", default="", help="Path to Root-Fix Gate JSON record")
    parser.add_argument("--future-scale-record", default="", help="Path to Future-Scale Gate JSON record")
    parser.add_argument("--paranoid-record", default="", help="Path to Paranoid Architect JSON record")
    parser.add_argument("--perf-record", default="", help="Path to Mechanical Sympathy JSON record")
    parser.add_argument("--rollout-record", default="", help="Path to Rollout Choreographer JSON record")
    parser.add_argument("--simulation-record", default="", help="Path to Deterministic Simulation JSON record")
    parser.add_argument("--privacy-record", default="", help="Path to Privacy & Data Lineage JSON record")
    parser.add_argument("--contract-record", default="", help="Path to API Contract JSON record")
    parser.add_argument("--apple-craft-record", default="", help="Path to Apple Craft JSON record")
    parser.add_argument("--observability-record", default="", help="Path to Observability & SLO JSON record")
    parser.add_argument("--motion-record", default="", help="Path to Runtime Motion profile JSON record")
    parser.add_argument("--profiler-record", default="", help="Path to Mechanical Sympathy Profiler JSON record")
    parser.add_argument("--fault-isolation-record", default="", help="Path to Scientific Fault Isolation JSON record")
    parser.add_argument("--migration-record", default="", help="Path to Zero-Downtime Migration JSON record")
    options = parser.parse_args(args)
    try:
        return run_audit(
            options.base, options.json, options.pr_title,
            options.pr_body_file, options.template_file, options.canary_token,
            mode=options.mode,
            installed_selection=options.installed_selection,
            restricted_env=options.restricted_env,
            out_dir=Path(options.out) if options.out else None,
            decision_record=options.decision_record,
            root_fix_record=options.root_fix_record,
            future_scale_record=options.future_scale_record,
            paranoid_record=options.paranoid_record,
            perf_record=options.perf_record,
            rollout_record=options.rollout_record,
            simulation_record=options.simulation_record,
            privacy_record=options.privacy_record,
            contract_record=options.contract_record,
            apple_craft_record=options.apple_craft_record,
            observability_record=options.observability_record,
            motion_record=options.motion_record,
            profiler_record=options.profiler_record,
            fault_isolation_record=options.fault_isolation_record,
            migration_record=options.migration_record,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def handle_check_engines(args: List[str]) -> int:
    """Parse check-engines options and display polyglot engine status."""
    parser = argparse.ArgumentParser(description="Check polyglot engine toolchains")
    parser.add_argument("--engine", default="", help="Specific engine to check (cargo, go, node, bun)")
    parser.add_argument("--strict", action="store_const", const=True, default=None, help="Enforce strict requirements (exit non-zero if missing)")
    parser.add_argument("--no-strict", dest="strict", action="store_const", const=False, help="Disable strict requirements")
    options = parser.parse_args(args)
    if options.engine:
        avail, msg = check_engine(options.engine, strict=options.strict)
        if avail:
            print(f"✓ {msg}")
            return 0
        return _emit_engine_message(msg, strict=options.strict)
    results = check_engines(strict=options.strict)
    any_missing = False
    print("Polyglot Engine Requirements Status:")
    for eng, (avail, msg) in results.items():
        if avail:
            print(f"  ✓ {msg}")
        else:
            any_missing = True
            print(f"  ✗ {msg}")
    if any_missing and (options.strict if options.strict is not None else is_strict_engine_mode()):
        return 1
    return 0


def handle_run_engine(args: List[str]) -> int:
    """Parse run-engine options and execute command guarded by engine check."""
    if "--" in args:
        idx = args.index("--")
        opt_args = args[:idx]
        cmd_args = args[idx + 1:]
    else:
        opt_args = args
        cmd_args = []
    parser = argparse.ArgumentParser(description="Run command guarded by engine toolchain check")
    parser.add_argument("--engine", required=True, help="Engine name (cargo, go, node, bun)")
    parser.add_argument("--strict", action="store_const", const=True, default=None, help="Enforce strict check")
    parser.add_argument("--no-strict", dest="strict", action="store_const", const=False, help="Disable strict check")
    parser.add_argument("--title", default="", help="Optional title displayed before command execution")
    parser.add_argument("--cwd", default=None, help="Working directory for command execution")
    parser.add_argument("cmd", nargs="*", help="Command to run")
    options = parser.parse_args(opt_args)
    final_cmd = cmd_args if cmd_args else options.cmd
    if not final_cmd:
        print("Error: No command provided to run-engine after --", file=sys.stderr)
        return 2
    return run_engine_command(
        engine=options.engine,
        command=final_cmd,
        strict=options.strict,
        title=options.title,
        cwd=options.cwd,
    )


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    command = args[0]
    if command == "mode":
        return handle_mode(args[1:])
    elif command in ("audit", "run"):
        return handle_audit(args[1:])
    elif command in ("check-engines", "check-engine"):
        return handle_check_engines(args[1:])
    elif command == "check-changed":
        return handle_check_changed(args[1:])
    elif command == "run-engine":
        return handle_run_engine(args[1:])
    elif command == "fix":
        print(
            "Error: 'fix' command is not supported. Anti-slop engineering requires "
            "reviewable, manual remediation of findings according to the audit report.",
            file=sys.stderr,
        )
        return 2
    else:
        print(f"Error: Unknown audit_runner command '{command}'", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
