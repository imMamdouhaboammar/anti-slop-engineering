#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""
Lifecycle Hook Dispatcher for anti-slop core triage and audit loops.

Provides clean, zero-dependency lifecycle hook dispatching with strict timeout guards,
safe process execution without shell interpolation, environment sanitization,
and complete error fencing. Complies with Python stdlib (>=3.9) and Google SRE standards.
"""

import json
import os
import pathlib
import subprocess
import sys
import time
import uuid

VALID_HOOK_EVENTS = {
    "pre_scan",
    "post_scan",
    "on_finding",
    "pre_exec",
    "post_exec",
}

DEFAULT_HOOK_TIMEOUT = 5.0

SENSITIVE_ENV_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "AUTH",
    "CREDENTIAL",
)


def create_hook_event(event_type, repo, base="HEAD", payload=None, context=None):
    """Construct a normalized lifecycle hook event envelope."""
    if event_type not in VALID_HOOK_EVENTS:
        raise ValueError(
            f"Unknown hook event '{event_type}'. Valid events: {sorted(VALID_HOOK_EVENTS)}"
        )
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "timestamp": time.time(),
        "repo": str(repo),
        "base": base,
        "payload": payload if payload is not None else {},
        "context": context if context is not None else {},
    }


def sanitize_environment(base_env=None):
    """Return a sanitized copy of environment variables preventing secret leakage."""
    source = base_env if base_env is not None else os.environ
    sanitized = {}
    for key, value in source.items():
        key_upper = key.upper()
        if any(substr in key_upper for substr in SENSITIVE_ENV_SUBSTRINGS):
            continue
        sanitized[key] = value
    return sanitized


def _resolve_hook_command(target):
    """Normalize a hook file path or command list into a process argument list."""
    if isinstance(target, list):
        return [str(arg) for arg in target]
    path_obj = pathlib.Path(target)
    if path_obj.suffix == ".py":
        return [sys.executable, str(path_obj)]
    return [str(path_obj)]


def _make_hook_result(
    status,
    decision,
    duration_ms,
    error=None,
    timed_out=False,
    returncode=None,
    findings=None,
    message="",
    raw_stdout=None,
):
    """Canonical factory for lifecycle hook execution results."""
    res = {
        "status": status,
        "decision": decision,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "returncode": returncode,
        "findings": findings if findings is not None else [],
        "message": message,
    }
    if error is not None:
        res["error"] = error
    if raw_stdout is not None:
        res["raw_stdout"] = raw_stdout
    return res


def dispatch_hook(hook_cmd, event, timeout=DEFAULT_HOOK_TIMEOUT, repo=None):
    """
    Execute a single lifecycle hook subprocess with timeout and error fencing.
    Delivers event envelope via stdin and parses structured JSON decision.
    """
    cmd = _resolve_hook_command(hook_cmd)
    cwd = str(repo) if repo else None
    start_t = time.perf_counter()

    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
            env=sanitize_environment(),
        )
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return _parse_hook_process_output(proc, duration_ms)
    except subprocess.TimeoutExpired:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return _make_hook_result("timeout", "error", duration_ms, error=f"Hook timed out after {timeout}s", timed_out=True)
    except FileNotFoundError as exc:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return _make_hook_result("error", "error", duration_ms, error=f"Hook executable not found: {exc}")
    except OSError as exc:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return _make_hook_result("error", "error", duration_ms, error=f"Execution error: {exc}")


def _parse_hook_process_output(proc, duration_ms):
    """Parse and validate output from a completed hook subprocess."""
    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or f"Hook exited with code {proc.returncode}"
        return _make_hook_result("error", "error", duration_ms, error=err_msg, returncode=proc.returncode)

    stdout_text = proc.stdout.strip()
    if not stdout_text:
        return _make_hook_result("success", "allow", duration_ms, returncode=0, message="Hook completed with empty output (allow).")

    try:
        data = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        return _make_hook_result("error", "error", duration_ms, error=f"Invalid JSON output from hook: {exc}", returncode=0)

    return _make_hook_result(
        "success",
        data.get("decision", "allow"),
        duration_ms,
        returncode=0,
        findings=data.get("findings", []),
        message=data.get("message", ""),
        raw_stdout=stdout_text,
    )


def _find_hooks_in_dir(hooks_path, event_type):
    """Locate hook candidate executables or python scripts in a hooks directory."""
    results = []
    candidates = [
        hooks_path / f"{event_type}.py",
        hooks_path / f"{event_type}.sh",
        hooks_path / event_type,
    ]
    for c in candidates:
        if c.is_file():
            results.append(_resolve_hook_command(c))

    sub_dir = hooks_path / event_type
    if sub_dir.is_dir():
        for item in sorted(sub_dir.iterdir()):
            if item.is_file() and not item.name.startswith("."):
                results.append(_resolve_hook_command(item))
    return results


def _find_hooks_in_settings(repo_path, event_type):
    """Locate hook definitions declared in .anti-slop/settings.json."""
    settings_file = pathlib.Path(repo_path) / ".anti-slop" / "settings.json"
    if not settings_file.is_file():
        return []
    try:
        content = json.loads(settings_file.read_text(encoding="utf-8"))
        hooks_cfg = content.get("hooks", {})
        hook_entries = hooks_cfg.get(event_type, [])
        return [_resolve_hook_command(entry) for entry in hook_entries]
    except (json.JSONDecodeError, OSError):
        return []


def discover_hooks(repo, hooks_dir=None):
    """
    Discover registered lifecycle hooks for all events.
    Checks explicit hooks_dir, repo/.anti-slop/hooks, and repo/.anti-slop/settings.json.
    """
    repo_path = pathlib.Path(repo).resolve()
    discovered = {evt: [] for evt in VALID_HOOK_EVENTS}

    dirs_to_check = []
    if hooks_dir:
        resolved_h = pathlib.Path(hooks_dir).resolve()
        if resolved_h not in dirs_to_check:
            dirs_to_check.append(resolved_h)
    default_dir = (repo_path / ".anti-slop" / "hooks").resolve()
    if default_dir not in dirs_to_check:
        dirs_to_check.append(default_dir)

    for evt in VALID_HOOK_EVENTS:
        for d in dirs_to_check:
            if d.is_dir():
                discovered[evt].extend(_find_hooks_in_dir(d, evt))
        discovered[evt].extend(_find_hooks_in_settings(repo_path, evt))

    return discovered


def dispatch_lifecycle_event(
    event_type,
    repo,
    base="HEAD",
    payload=None,
    context=None,
    hooks_dir=None,
    extra_hooks=None,
    timeout=DEFAULT_HOOK_TIMEOUT,
):
    """
    Dispatch a lifecycle event across all discovered and extra hooks.
    Aggregates decisions, injected findings, and execution metrics.
    """
    event = create_hook_event(event_type, repo, base, payload, context)
    all_discovered = discover_hooks(repo, hooks_dir)
    hook_list = list(all_discovered.get(event_type, []))

    if extra_hooks:
        for h in extra_hooks:
            hook_list.append(_resolve_hook_command(h))

    results = []
    injected_findings = []
    aggregate_decision = "allow"

    for hook_cmd in hook_list:
        res = dispatch_hook(hook_cmd, event, timeout=timeout, repo=repo)
        results.append(res)
        if res.get("findings"):
            injected_findings.extend(res["findings"])
        decision = res.get("decision", "allow")
        if decision == "block":
            aggregate_decision = "block"
        elif decision in ("warn", "error") and aggregate_decision != "block":
            aggregate_decision = decision

    return {
        "event": event,
        "results": results,
        "findings": injected_findings,
        "decision": aggregate_decision,
    }
