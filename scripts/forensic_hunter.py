#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""
Zero-Trust Forensic Bug-Hunter Static Guard (scripts/forensic_hunter.py)

Scans git diffs or source files line-by-line for production booby traps across:
- Kubernetes (k8s)
- Docker (docker)
- Python (python)
- TypeScript / JavaScript (ts)
- Bun Runtime (bun)
- Rust (rust)
- Golang (go)
- React / Frontend (react)
- Shell / CI-CD (shell)
- System Architecture & SQL (arch)

Zero external dependencies (Python 3.9+ standard library only).
Exit codes:
  0 - Clean or non-blocking findings (unless strict flags enabled)
  1 - Execution / usage error
  2 - Blocking findings detected (--fail-on-critical or --strict)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import re
import sre_compile
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclasses.dataclass(frozen=True)
class TrapRule:
    code: str
    stack: str
    severity: str  # CRITICAL, HIGH, MEDIUM
    pattern: Any
    title: str
    impact: str
    remedy: str
    file_extensions: Tuple[str, ...] = ()
    file_names: Tuple[str, ...] = ()


@dataclasses.dataclass
class Finding:
    code: str
    stack: str
    severity: str
    file: str
    line: int
    snippet: str
    title: str
    impact: str
    remedy: str


DOCKER_FILENAMES: Tuple[str, ...] = ("Dockerfile", "Containerfile")
DOCKER_EXTENSIONS: Tuple[str, ...] = (".dockerfile",)


def _docker_rule(
    code: str,
    severity: str,
    pattern: Any,
    title: str,
    impact: str,
    remedy: str,
    file_extensions: Tuple[str, ...] = DOCKER_EXTENSIONS,
) -> TrapRule:
    return TrapRule(
        code=code,
        stack="docker",
        severity=severity,
        pattern=pattern,
        title=title,
        impact=impact,
        remedy=remedy,
        file_names=DOCKER_FILENAMES,
        file_extensions=file_extensions,
    )


RULES: List[TrapRule] = [
    # --- DOCKER ---
    _docker_rule(
        code="DCK-01",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"(?i)^\s*FROM\s+[^\s:@]+(?::latest|\s*$)"),
        title="Unpinned or ':latest' Docker base image",
        impact="Non-reproducible builds and silent upstream breaking changes or supply-chain compromise.",
        remedy="Pin an explicit semantic version tag and immutable @sha256 digest.",
    ),
    _docker_rule(
        code="DCK-02",
        severity="HIGH",
        pattern=sre_compile.compile(r"(?i)^\s*(?:ENTRYPOINT|CMD)\s+(?!\[).+"),
        title="Shell-form ENTRYPOINT/CMD (PID 1 SIGTERM blackhole)",
        impact="Spawns /bin/sh as PID 1, swallowing SIGTERM signals and causing ungraceful SIGKILL drops during K8s rollouts.",
        remedy='Use JSON exec-form: ENTRYPOINT ["binary", "--arg"] or wrap with tini.',
    ),
    _docker_rule(
        code="DCK-03",
        severity="CRITICAL",
        pattern=sre_compile.compile(
            r"(?i)^\s*(?:ARG|ENV)\s+[A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|PRIVATE_KEY|API_KEY)[A-Z0-9_]*\s*="
        ),
        title="Secret baked into Docker ARG/ENV layer",
        impact="Secrets persist permanently in image layer metadata (`docker history`) and registry caches.",
        remedy="Use BuildKit secret mounts (`RUN --mount=type=secret,id=...`) or inject at runtime.",
    ),
    _docker_rule(
        code="DCK-04",
        severity="HIGH",
        pattern=sre_compile.compile(r"(?i)curl\s+[^|\n]*\|\s*(?:ba)?sh"),
        title="Unverified curl-pipe-shell execution",
        impact="Partial network reads or MITM/upstream tampering execute arbitrary shell commands during build.",
        remedy="Download the artifact, verify `sha256sum --check`, and execute explicitly.",
        file_extensions=(".dockerfile", ".sh", ".bash"),
    ),
    # --- KUBERNETES ---
    TrapRule(
        code="K8S-01",
        stack="k8s",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"^\s*(?:privileged|hostNetwork|hostPID|hostIPC)\s*:\s*true\b"),
        title="Privileged or host-namespace breakout enabled in Pod spec",
        impact="Container compromise immediately escalates to full underlying Kubernetes node takeover.",
        remedy="Set privileged/hostNetwork/hostPID to false and drop ALL capabilities.",
        file_extensions=(".yaml", ".yml"),
    ),
    TrapRule(
        code="K8S-02",
        stack="k8s",
        severity="HIGH",
        pattern=sre_compile.compile(r"^\s*image\s*:\s*[^\s:@]+:latest\b"),
        title="Mutable ':latest' container image tag in manifest",
        impact="Rollbacks become impossible and nodes pull inconsistent image versions across the cluster.",
        remedy="Pin an immutable release tag or @sha256 digest.",
        file_extensions=(".yaml", ".yml"),
    ),
    TrapRule(
        code="K8S-03",
        stack="k8s",
        severity="HIGH",
        pattern=sre_compile.compile(r"^\s*allowPrivilegeEscalation\s*:\s*true\b"),
        title="Privilege escalation explicitly permitted in securityContext",
        impact="Allows setuid binaries inside the container to elevate privileges.",
        remedy="Set `allowPrivilegeEscalation: false` and `runAsNonRoot: true`.",
        file_extensions=(".yaml", ".yml"),
    ),
    # --- PYTHON ---
    TrapRule(
        code="PY-01",
        stack="python",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"^\s*def\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\}|set\(\))"),
        title="Mutable default argument in Python function",
        impact="Default list/dict/set is instantiated once at import time and shared across all future calls, leaking state across requests.",
        remedy="Use `None` as the default (`param: Optional[list] = None`) and initialize inside the function.",
        file_extensions=(".py",),
    ),
    TrapRule(
        code="PY-02",
        stack="python",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"^\s*except\b[^:\n]*:\s*(?:pass|\.\.\.)\s*(?:#.*)?$"),
        title="Silent exception swallow in try-except block",
        impact="Swallows fatal crashes, database corruption, or KeyboardInterrupt without logging or recovery.",
        remedy="Catch specific exception types, log structured context, or re-raise.",
        file_extensions=(".py",),
    ),
    TrapRule(
        code="PY-03",
        stack="python",
        severity="HIGH",
        pattern=sre_compile.compile(r"^\s*asyncio\.create_task\s*\("),
        title="Unreferenced `asyncio.create_task()` fire-and-forget",
        impact="Python's event loop holds only weak references to tasks; the GC can silently destroy the task mid-execution.",
        remedy="Assign the task to a variable and store it in a live set with `task.add_done_callback(tasks.discard)`.",
        file_extensions=(".py",),
    ),
    TrapRule(
        code="PY-04",
        stack="python",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\bsubprocess\.(?:Popen|run|call|check_output)\s*\([^)]*shell\s*=\s*True"),
        title="Subprocess execution with `shell=True`",
        impact="Enables command injection when any interpolated argument originates from external input.",
        remedy="Pass arguments as a sequence (`['cmd', arg1]`) with `shell=False` and `check=True`.",
        file_extensions=(".py",),
    ),
    TrapRule(
        code="PY-05",
        stack="python",
        severity="HIGH",
        pattern=sre_compile.compile(r"\brequests\.(?:get|post|put|delete|patch|head|request)\s*\((?![^)]*timeout\s*=)[^)]*\)"),
        title="Synchronous HTTP request without explicit `timeout=`",
        impact="Socket hangs indefinitely when upstream stalls, exhausting worker threads/processes.",
        remedy="Always pass an explicit `timeout=(connect_sec, read_sec)` tuple.",
        file_extensions=(".py",),
    ),
    TrapRule(
        code="PY-06",
        stack="python",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\b(?:pickle\.loads?|yaml\.load\s*\([^)]*(?!Loader\s*=\s*yaml\.SafeLoader))\b"),
        title="Unsafe deserialization (`pickle` or `yaml.load`)",
        impact="Arbitrary Remote Code Execution (RCE) when parsing untrusted payloads.",
        remedy="Use `yaml.safe_load()` or strict schema-validated JSON/MsgPack.",
        file_extensions=(".py",),
    ),
    # --- TYPESCRIPT / JAVASCRIPT ---
    TrapRule(
        code="TS-01",
        stack="ts",
        severity="HIGH",
        pattern=sre_compile.compile(r"(?:\bas\s+any\b|:\s*any\b|@ts-ignore|@ts-nocheck)"),
        title="Type-safety suppression (`any` or `@ts-ignore`)",
        impact="Disables static type verification, allowing undefined property access and contract drift into runtime.",
        remedy="Use `unknown` with runtime schema parsing (Zod/Valibot) or narrow via type guards.",
        file_extensions=(".ts", ".tsx", ".mts", ".cts"),
    ),
    TrapRule(
        code="TS-02",
        stack="ts",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\.forEach\s*\(\s*async\b"),
        title="Async callback inside `.forEach()`",
        impact="`Array.prototype.forEach` does not await promises; rejections go unhandled and execution continues prematurely.",
        remedy="Use `for (const item of items)` for sequential work or bounded `Promise.all`.",
        file_extensions=(".ts", ".tsx", ".js", ".jsx", ".mjs"),
    ),
    TrapRule(
        code="TS-03",
        stack="ts",
        severity="HIGH",
        pattern=sre_compile.compile(r"\bPromise\.all\s*\(\s*\w+\.map\s*\("),
        title="Unbounded concurrency via Promise.all mapping",
        impact="Spawns N simultaneous I/O requests proportional to input size, exhausting DB pools, file descriptors, or rate limits.",
        remedy="Enforce a bounded concurrency limiter / semaphore pool (e.g., max 10-20 concurrent workers).",
        file_extensions=(".ts", ".tsx", ".js", ".jsx", ".mjs"),
    ),
    TrapRule(
        code="TS-04",
        stack="ts",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*(?://.*)?\}"),
        title="Empty `catch {}` block swallowing exceptions",
        impact="Silently discards runtime errors and corrupted state.",
        remedy="Log structured error details with causal context or rethrow a typed domain error.",
        file_extensions=(".ts", ".tsx", ".js", ".jsx", ".mjs"),
    ),
    # --- BUN ---
    TrapRule(
        code="BUN-01",
        stack="bun",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\bBun\.spawn(?:Sync)?\s*\(\s*\[\s*['\"](?:sh|bash)['\"]\s*,\s*['\"]-c['\"]\s*,\s*`"),
        title="Shell command interpolation inside `Bun.spawn(['sh', '-c', ...])`",
        impact="Unsanitized template interpolation inside `sh -c` enables arbitrary command injection.",
        remedy="Pass arguments directly as array elements to `Bun.spawn([cmd, arg1])` or use `Bun.$` tagged templates.",
        file_extensions=(".ts", ".tsx", ".js", ".mjs"),
    ),
    TrapRule(
        code="BUN-02",
        stack="bun",
        severity="MEDIUM",
        pattern=sre_compile.compile(r"\bBun\.serve\s*\(\s*\{(?![^}]*idleTimeout)[^}]*\}"),
        title="`Bun.serve` initialized without explicit `idleTimeout` or `maxRequestBodySize`",
        impact="Default connection settings can leave server exposed to Slowloris or oversized payload memory exhaustion.",
        remedy="Explicitly configure `idleTimeout` and `maxRequestBodySize` in `Bun.serve({...})`.",
        file_extensions=(".ts", ".tsx", ".js", ".mjs"),
    ),
    # --- REACT ---
    TrapRule(
        code="RCT-01",
        stack="react",
        severity="HIGH",
        pattern=sre_compile.compile(r"\bkey\s*=\s*\{\s*(?:index|idx|i)\s*\}"),
        title="Array index used as React `key={index}`",
        impact="List reordering, insertion, or deletion corrupts component state and binds DOM inputs to the wrong items.",
        remedy="Use a stable, unique domain identifier (`key={item.id}`).",
        file_extensions=(".tsx", ".jsx"),
    ),
    TrapRule(
        code="RCT-02",
        stack="react",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\bdangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:\s*(?!DOMPurify\.sanitize)"),
        title="Unsanitized `dangerouslySetInnerHTML` XSS sink",
        impact="Direct DOM injection of unverified strings enables Cross-Site Scripting (XSS) session hijacking.",
        remedy="Sanitize HTML with `DOMPurify.sanitize(content)` or render safe React nodes.",
        file_extensions=(".tsx", ".jsx"),
    ),
    TrapRule(
        code="RCT-03",
        stack="react",
        severity="HIGH",
        pattern=sre_compile.compile(
            r"(?i)>(?:[^<]*\b(?:TODO|FIXME|Mock data|In production|Developer note|Agent note)\b[^<]*)</(?:p|span|div|small|label)>"
        ),
        title="Internal developer/agent note leaked into user-facing JSX/HTML",
        impact="Exposes internal implementation disclaimers or unfinished scaffolding to end users.",
        remedy="Remove developer notes from DOM elements immediately.",
        file_extensions=(".tsx", ".jsx", ".html"),
    ),
    # --- RUST ---
    TrapRule(
        code="RS-01",
        stack="rust",
        severity="HIGH",
        pattern=sre_compile.compile(r"\.(?:unwrap|expect)\s*\("),
        title="Panic bomb (`.unwrap()` / `.expect()`) in Rust code",
        impact="Crashes the worker thread or entire process when an unexpected `None` or `Err` occurs in production.",
        remedy="Propagate errors via `?`, `.context(...)`, or handle explicitly with `match` / `if let`.",
        file_extensions=(".rs",),
    ),
    TrapRule(
        code="RS-02",
        stack="rust",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"\bunsafe\s*\{"),
        title="`unsafe` block requires explicit invariant audit",
        impact="Bypasses Rust borrow checker and memory safety guarantees; risks UB, data races, or segfaults.",
        remedy="Avoid `unsafe` if a safe abstraction exists, or precede with a rigorous `// SAFETY:` proof comment.",
        file_extensions=(".rs",),
    ),
    TrapRule(
        code="RS-03",
        stack="rust",
        severity="HIGH",
        pattern=sre_compile.compile(r"\b(?:std::thread::sleep|std::fs::\w+)\s*\("),
        title="Blocking stdlib call (`std::thread::sleep` / `std::fs`) potentially starving async executor",
        impact="Blocks Tokio/async worker threads, stalling all concurrent tasks scheduled on that core.",
        remedy="Use `tokio::time::sleep`, `tokio::fs`, or `tokio::task::spawn_blocking`.",
        file_extensions=(".rs",),
    ),
    TrapRule(
        code="RS-04",
        stack="rust",
        severity="HIGH",
        pattern=sre_compile.compile(r"\bunbounded_channel\s*\("),
        title="Unbounded channel (`unbounded_channel`) without backpressure",
        impact="Fast producers overwhelm slow consumers, growing queue memory until the process is OOMKilled.",
        remedy="Use bounded `mpsc::channel(capacity)` to enforce backpressure.",
        file_extensions=(".rs",),
    ),
    # --- GOLANG ---
    TrapRule(
        code="GO-01",
        stack="go",
        severity="CRITICAL",
        pattern=sre_compile.compile(r"^\s*_[^=\n]*=\s*[\w.]+\s*\("),
        title="Explicitly ignored error return (`_ = fn()`)",
        impact="Silently drops I/O, serialization, or transaction failures, causing undetected state corruption.",
        remedy="Capture `err`, check `if err != nil`, and wrap with `fmt.Errorf(\"...: %w\", err)`.",
        file_extensions=(".go",),
    ),
    TrapRule(
        code="GO-02",
        stack="go",
        severity="HIGH",
        pattern=sre_compile.compile(r"\bhttp\.(?:Get|Post|PostForm|Head)\s*\("),
        title="Package-level `http.Get`/`http.Post` using `http.DefaultClient` (infinite timeout)",
        impact="`http.DefaultClient` has no timeout; a stalled upstream leaks goroutines and sockets forever.",
        remedy="Use an explicit `&http.Client{Timeout: 10 * time.Second}` with `http.NewRequestWithContext`.",
        file_extensions=(".go",),
    ),
    TrapRule(
        code="GO-03",
        stack="go",
        severity="HIGH",
        pattern=sre_compile.compile(r"^\s*go\s+func\s*\("),
        title="Anonymous goroutine spawned (`go func()`) — verify lifecycle & cancellation",
        impact="Unbounded or uncancelled goroutines leak memory and cause data races on shutdown.",
        remedy="Bind goroutines to `errgroup.WithContext(ctx)` or ensure deterministic `ctx.Done()` exit.",
        file_extensions=(".go",),
    ),
    # --- SHELL / CI-CD ---
    TrapRule(
        code="SH-01",
        stack="shell",
        severity="HIGH",
        pattern=sre_compile.compile(r'\brm\s+-rf\s+\$\{' + r'?\w+\}?/'),
        title="Unwarded deletion command without parameter expansion guard",
        impact="If the variable is unset, unwarded deletion expands to root or wipes critical directories.",
        remedy='Use `set -u` and parameter guard: `rm -rf "${VAR:?Error: VAR is unset}/"`.',
        file_extensions=(".sh", ".bash"),
    ),
    # --- ARCHITECTURE & DATA ---
    TrapRule(
        code="ARC-01",
        stack="arch",
        severity="CRITICAL",
        pattern=sre_compile.compile(
            r"(?i)(?:SELECT|UPDATE|DELETE|INSERT)\s+.*(?:\+\s*\w+|\$\{[^}]+\}|%s|\.format\()"
        ),
        title="Dynamic string interpolation inside SQL statement",
        impact="Direct SQL Injection vulnerability and query plan cache pollution.",
        remedy="Use parameterized queries (bind parameters or prepared statements) exclusively.",
        file_extensions=(".py", ".ts", ".js", ".go", ".rs"),
    ),
    TrapRule(
        code="ARC-02",
        stack="arch",
        severity="HIGH",
        pattern=sre_compile.compile(r"(?i)\bSELECT\s+\*\s+FROM\s+\w+(?![^\n;]*\bLIMIT\b)"),
        title="Unbounded `SELECT * FROM` without `LIMIT` clause",
        impact="Full table scan loads unbounded rows into application memory, triggering OOM under production growth.",
        remedy="Specify explicit column names and enforce cursor-based pagination with `LIMIT <= 100`.",
        file_extensions=(".py", ".ts", ".js", ".go", ".rs", ".sql"),
    ),
    TrapRule(
        code="ARC-03",
        stack="arch",
        severity="HIGH",
        pattern=sre_compile.compile(
            r"(?i)(?:process\.env\.[A-Z0-9_]+|os\.getenv\([^)]+\))\s*(?:\|\||\?\?|,)\s*['\"](?:secret|password|admin|default|changeme|123456|dev)"
        ),
        title="Insecure fallback default for secret or environment configuration",
        impact="Missing production env var silently boots the service with a known default credential.",
        remedy="Fail fast at startup if required environment variables are missing.",
        file_extensions=(".py", ".ts", ".tsx", ".js", ".go", ".rs"),
    ),
]


def matches_file_target(rule: TrapRule, filepath: str) -> bool:
    path_obj = pathlib.Path(filepath)
    if rule.file_names and path_obj.name in rule.file_names:
        return True
    if rule.file_extensions and path_obj.suffix.lower() in rule.file_extensions:
        return True
    if not rule.file_names and not rule.file_extensions:
        return True
    return False


def check_shell_missing_pipefail(filepath: str, lines: Sequence[str]) -> List[Finding]:
    path_obj = pathlib.Path(filepath)
    if path_obj.suffix.lower() not in (".sh", ".bash"):
        return []
    head = "\n".join(lines[:15])
    if "set -euo pipefail" not in head and "set -e" not in head:
        return [
            Finding(
                code="SH-02",
                stack="shell",
                severity="HIGH",
                file=filepath,
                line=1,
                snippet=lines[0].strip() if lines else "",
                title="Shell script missing strict `set -euo pipefail` header",
                impact="Failed intermediate commands and unset variables silently continue execution, corrupting deployments.",
                remedy="Add `set -euo pipefail` immediately after the shebang line.",
            )
        ]
    return []


def _make_k8s_manifest_finding(code: str, title: str, impact: str, remedy: str, snippet: str, filepath: str) -> Finding:
    return Finding(
        code=code,
        stack="k8s",
        severity="HIGH",
        file=filepath,
        line=1,
        snippet=snippet,
        title=title,
        impact=impact,
        remedy=remedy,
    )


def check_k8s_missing_limits(filepath: str, lines: Sequence[str]) -> List[Finding]:
    path_obj = pathlib.Path(filepath)
    if path_obj.suffix.lower() not in (".yaml", ".yml"):
        return []
    content = "\n".join(lines)
    if not re.search(r"^\s*kind\s*:\s*(?:Deployment|StatefulSet|DaemonSet|Job|Pod)\b", content, re.MULTILINE):
        return []
    findings: List[Finding] = []
    if "resources:" not in content or "limits:" not in content:
        findings.append(
            _make_k8s_manifest_finding(
                code="K8S-04",
                title="Kubernetes workload manifest missing `resources.limits`",
                impact="Unbounded CPU/memory consumption enables noisy-neighbor starvation and node-level OOM instability.",
                remedy="Define explicit `resources.requests` and `resources.limits` for memory and CPU.",
                snippet="kind: Workload (missing resources.limits)",
                filepath=filepath,
            )
        )
    if "securityContext:" not in content or "runAsNonRoot:" not in content:
        findings.append(
            _make_k8s_manifest_finding(
                code="K8S-05",
                title="Kubernetes workload missing `runAsNonRoot: true` in `securityContext`",
                impact="Containers may execute as UID 0 (root) by default, increasing container breakout severity.",
                remedy="Configure pod/container `securityContext` with `runAsNonRoot: true` and `readOnlyRootFilesystem: true`.",
                snippet="kind: Workload (missing runAsNonRoot securityContext)",
                filepath=filepath,
            )
        )
    return findings


def scan_lines(
    filepath: str,
    indexed_lines: Iterable[Tuple[int, str]],
    allowed_stacks: Optional[Set[str]] = None,
    full_file_lines: Optional[Sequence[str]] = None,
) -> List[Finding]:
    findings: List[Finding] = []
    applicable_rules = [
        r
        for r in RULES
        if matches_file_target(r, filepath)
        and (allowed_stacks is None or r.stack in allowed_stacks)
    ]

    for line_no, raw_line in indexed_lines:
        stripped = raw_line.strip()
        if not stripped or (stripped.startswith("#") and not filepath.endswith((".py", ".sh", ".yaml", ".yml"))):
            continue
        for rule in applicable_rules:
            if rule.pattern.search(raw_line):
                findings.append(
                    Finding(
                        code=rule.code,
                        stack=rule.stack,
                        severity=rule.severity,
                        file=filepath,
                        line=line_no,
                        snippet=stripped[:140],
                        title=rule.title,
                        impact=rule.impact,
                        remedy=rule.remedy,
                    )
                )

    if full_file_lines is not None:
        if allowed_stacks is None or "shell" in allowed_stacks:
            findings.extend(check_shell_missing_pipefail(filepath, full_file_lines))
        if allowed_stacks is None or "k8s" in allowed_stacks:
            findings.extend(check_k8s_missing_limits(filepath, full_file_lines))

    return findings


def parse_git_diff(base: str) -> Dict[str, List[Tuple[int, str]]]:
    cmd = ["git", "diff", "--unified=0", "--no-color", base]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")

    added_by_file: Dict[str, List[Tuple[int, str]]] = {}
    current_file: Optional[str] = None
    current_line = 0

    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            added_by_file.setdefault(current_file, [])
        elif line.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,\d+)?\s+@@", line)
            if match:
                current_line = int(match.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file is not None:
                added_by_file[current_file].append((current_line, line[1:]))
                current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    return added_by_file


def collect_files(paths: Sequence[str]) -> List[str]:
    ignored_dirs = {".git", "node_modules", "target", "dist", "build", ".next", "__pycache__", ".venv", "venv"}
    collected: List[str] = []
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_file():
            collected.append(str(p))
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for f in files:
                    collected.append(os.path.join(root, f))
    return sorted(set(collected))


def _scan_target_files(
    target_files: Sequence[str],
    allowed_stacks: Optional[Set[str]],
) -> List[Finding]:
    findings: List[Finding] = []
    for fp in target_files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        indexed = list(enumerate(lines, start=1))
        findings.extend(scan_lines(fp, indexed, allowed_stacks=allowed_stacks, full_file_lines=lines))
    return findings


def _scan_git_diff_targets(
    base: str,
    allowed_stacks: Optional[Set[str]],
) -> List[Finding]:
    findings: List[Finding] = []
    diff_map = parse_git_diff(base)
    for fp, indexed_lines in diff_map.items():
        full_lines: Optional[List[str]] = None
        if os.path.isfile(fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                    full_lines = fh.read().splitlines()
            except OSError:
                full_lines = None
        findings.extend(scan_lines(fp, indexed_lines, allowed_stacks=allowed_stacks, full_file_lines=full_lines))
    return findings


def _render_report(
    findings: Sequence[Finding],
    as_json: bool,
) -> Tuple[str, Dict[str, int]]:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    verdict = "FORTIFIED (PASS)"
    if counts["CRITICAL"] > 0:
        verdict = "COMPROMISED (BLOCK)"
    elif counts["HIGH"] > 0 or counts["MEDIUM"] > 0:
        verdict = "PARTIAL DEFUSAL (REVIEW)"

    if as_json:
        payload = {
            "verdict": verdict,
            "counts": counts,
            "total_findings": len(findings),
            "findings": [dataclasses.asdict(f) for f in findings],
        }
        print(json.dumps(payload, indent=2))
    else:
        print("=== ZERO-TRUST FORENSIC BUG-HUNTER REPORT ===")
        print(
            f"Verdict: {verdict} | Critical: {counts['CRITICAL']} | High: {counts['HIGH']} | Medium: {counts['MEDIUM']}"
        )
        print("-" * 75)
        for f in findings:
            print(f"[{f.severity}] [{f.code}] ({f.stack}) {f.file}:{f.line} — {f.title}")
            print(f"  Snippet : {f.snippet}")
            print(f"  Impact  : {f.impact}")
            print(f"  Remedy  : {f.remedy}\n")
    return verdict, counts


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-Trust Forensic Bug-Hunter CLI Scanner (K8s, Docker, Python, TS, Bun, Rust, Go, React, Arch)"
    )
    parser.add_argument("--base", default="HEAD", help="Git ref to diff against when --files is not provided.")
    parser.add_argument("--files", nargs="*", help="Specific files or directories to audit line-by-line.")
    parser.add_argument(
        "--stack",
        help="Comma-separated list of stacks to filter (k8s,docker,python,ts,bun,react,rust,go,shell,arch).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with code 2 if any CRITICAL booby trap is detected.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 if any CRITICAL or HIGH booby trap is detected.",
    )
    args = parser.parse_args(argv)

    allowed_stacks = {s.strip().lower() for s in args.stack.split(",") if s.strip()} if args.stack else None

    try:
        if args.files:
            all_findings = _scan_target_files(collect_files(args.files), allowed_stacks)
        else:
            all_findings = _scan_git_diff_targets(args.base, allowed_stacks)
    except Exception as exc:
        sys.stderr.write(f"[FORENSIC-HUNTER ERROR] {exc}\n")
        return 1

    _, counts = _render_report(all_findings, args.json)

    if args.strict and (counts["CRITICAL"] > 0 or counts["HIGH"] > 0):
        return 2
    if args.fail_on_critical and counts["CRITICAL"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
