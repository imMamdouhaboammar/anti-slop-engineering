#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Unified Multi-Guard Audit Runner & Mode Governor for Anti-Slop Engineering.

Governs execution modes (DURING vs AFTER vs ASK) and orchestrates all guards
(Diff, SRE, AST Slop, Contrast, Privacy, Contract) to compile a structured,
numbered audit report in `anti-slop/audit-NNN.md`.

Usage:
    python3 scripts/audit_runner.py mode [during|after|ask]
    python3 scripts/audit_runner.py audit [--base HEAD] [--json]
    python3 scripts/audit_runner.py fix --finding 1,3
"""

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "anti-slop-engineering"
GLOBAL_SETTINGS_FILE = GLOBAL_CONFIG_DIR / "settings.json"
LOCAL_CONFIG_DIR = Path.cwd() / ".anti-slop"
LOCAL_SETTINGS_FILE = LOCAL_CONFIG_DIR / "settings.json"
AUDIT_DIR = Path.cwd() / "anti-slop"
GUARD_TIMEOUT_SECONDS = 60


def get_settings_file() -> Path:
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


def run_command(cmd: List[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=GUARD_TIMEOUT_SECONDS)
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


def get_next_audit_file() -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(AUDIT_DIR.glob("audit-*.md"))
    max_idx = 0
    for p in existing:
        m = re.match(r"audit-(\d+)", p.name)
        if m:
            max_idx = max(max_idx, int(m.group(1)))
    next_idx = max_idx + 1
    today = datetime.date.today().isoformat()
    return AUDIT_DIR / f"audit-{next_idx:03d}-{today}.md"


def guard_commands(base: str) -> List[Tuple[str, Optional[List[str]]]]:
    scripts_dir = Path(__file__).resolve().parent
    ledger = Path.cwd() / ".anti-slop" / "invariant-ledger.json"
    commands = [
        ("diff_guard", ["--base", base]),
        ("sre_guard", ["--base", base]),
        ("ast_slop_guard", ["--base", base]),
        ("contrast_guard", ["--scan", "."]),
        ("comment_budget_guard", ["--base", base]),
        ("pr_boundary_guard", ["--base", base]),
        ("invariant_steward_guard", ["drift", "--base", base, "--ledger", str(ledger)] if ledger.exists() else None),
        ("attention_guard", ["--base", base]),
        ("system_drift_guard", ["--scan", "."]),
        ("chroma_drift_guard", ["--scan", "."]),
        ("styleseed_guard", ["--scan", "."] + (["--tokens", ".anti-slop/tokens.json"] if Path(".anti-slop/tokens.json").exists() else [])),
    ]
    return [
        (name, [sys.executable, str(scripts_dir / f"{name}.py"), *args, "--json"] if args is not None else None)
        for name, args in commands
    ]


def normalize_finding(name: str, finding: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    severity = str(finding.get("severity", finding.get("level", ""))).lower()
    fallback = "MEDIUM" if name in {
        "ast_slop_guard", "contrast_guard", "system_drift_guard",
        "chroma_drift_guard", "styleseed_guard",
    } else "HIGH"
    if severity in {"blocker", "block", "blocking", "error", "critical"}:
        level = "BLOCKER"
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
    }
    message = finding.get("message") or finding.get("evidence") or ""
    if name == "contrast_guard":
        message = (
            f"Low contrast color pairing: {finding.get('fg')} on {finding.get('bg')} "
            f"({finding.get('ratio')}:1 fails AA)"
        )
    remediation = finding.get("remediation") or finding.get("action") or finding.get("recommendation")
    if not remediation and isinstance(report.get("remediation"), dict):
        remediation = report["remediation"].get("guidance")
    return {
        "guard": name,
        "rule": str(finding.get("rule") or finding.get("rule_id") or finding.get("id")
                    or finding.get("category") or finding.get("principle")
                    or finding.get("class") or "AUDIT-FINDING"),
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


def evaluate_guard(name: str, command: Optional[List[str]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    result: Dict[str, Any] = {
        "status": "SKIPPED" if command is None else "ERROR",
        "applicable": command is not None,
        "exit_code": None,
        "stderr": "",
        "timed_out": False,
        "error": None,
        "command": redact_command(command) if command is not None else None,
        "findings_count": 0,
    }
    if command is None:
        return result, []
    if not Path(command[1]).is_file():
        result["error"] = f"Mandatory guard script missing: {command[1]}"
        return result, []

    process = run_command(command)
    result.update({key: process[key] for key in ("exit_code", "stderr", "timed_out", "error")})
    if result["error"]:
        return result, []
    if not process["stdout"].strip():
        result["error"] = "Missing JSON output from mandatory guard"
        return result, []
    try:
        report = json.loads(process["stdout"])
    except (ValueError, TypeError) as exc:
        result["error"] = f"Invalid JSON from guard: {exc}"
        result["stdout_excerpt"] = process["stdout"][:500]
        return result, []
    if not isinstance(report, dict) or not isinstance(report.get("findings"), list):
        result["error"] = "Invalid JSON report schema: required findings array"
        return result, []
    if any(not isinstance(item, dict) for item in report["findings"]):
        result["error"] = "Invalid JSON report schema: finding must be an object"
        return result, []
    known_severities = {
        "blocker", "block", "blocking", "error", "critical",
        "high", "medium", "low", "warning", "review",
    }
    for item in report["findings"]:
        raw_severity = item.get("severity", item.get("level"))
        if raw_severity is not None and str(raw_severity).lower() not in known_severities:
            result["error"] = f"Invalid JSON report schema: unknown severity {raw_severity!r}"
            return result, []
    if report.get("error"):
        result["error"] = f"Guard reported error: {report['error']}"
        return result, []

    findings = [normalize_finding(name, item, report) for item in report["findings"]]
    result["findings_count"] = len(findings)
    blockers = any(item["severity"] == "BLOCKER" for item in findings)
    code = process["exit_code"]
    valid_finding_exit = (
        (code == 2 and blockers)
        or (code == 1 and name in {"contrast_guard", "styleseed_guard"} and bool(findings))
    )
    if code != 0 and not valid_finding_exit:
        result["error"] = f"Guard exited with code {code} without a valid finding outcome"
        result["stdout_excerpt"] = process["stdout"][:500]
        return result, findings

    reported_status = str(report.get("status", "")).upper()
    reported_verdict = str(report.get("verdict", "")).upper()
    if (reported_status in {"FAIL", "BLOCKED"} or reported_verdict in {"FAIL", "REJECT"}) and not blockers:
        result["error"] = "Guard reported FAIL without matching blocker findings"
        return result, findings
    if reported_status in {"ERROR", "INCOMPLETE"} or reported_verdict in {"ERROR", "INCOMPLETE"}:
        result["error"] = f"Guard reported unsuccessful status: {reported_status or reported_verdict}"
        return result, findings

    result["status"] = "FINDINGS" if findings else "PASS"
    return result, findings


def collect_audit_findings(base: str = "HEAD") -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    guards: Dict[str, Dict[str, Any]] = {}
    for name, command in guard_commands(base):
        outcome, child_findings = evaluate_guard(name, command)
        guards[name] = outcome
        findings.extend(child_findings)
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"FINDING-{index:03d}"
    return findings, guards


def generate_audit_markdown(
    findings: List[Dict[str, Any]], audit_file: Path,
    status: Optional[str] = None, guards: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    today = datetime.date.today().isoformat()
    total = len(findings)
    blockers = sum(1 for f in findings if f.get("severity") == "BLOCKER")
    high = sum(1 for f in findings if f.get("severity") == "HIGH")
    medium = sum(1 for f in findings if f.get("severity") == "MEDIUM")
    low = sum(1 for f in findings if f.get("severity") == "LOW")

    lines = [
        f"# Anti-Slop Engineering Audit Report — {audit_file.stem}",
        "",
        f"> Generated on {today} by Anti-Slop Engineering Multi-Guard Audit Runner.",
        "",
        "## Summary",
        "",
        f"- **Total Findings:** {total}",
        f"- **Blockers:** {blockers}",
        f"- **High Severity:** {high}",
        f"- **Medium Severity:** {medium}",
        f"- **Low Severity:** {low}",
        f"- **Status:** {status or ('BLOCKED' if blockers > 0 else 'PASS')}",
        "",
        "## Findings Index",
        "",
        "| ID | Severity | Guard | Rule | Target | Message |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for f in findings:
        target = f"{f['file']}:{f['line']}" if f['file'] else "System"
        msg = f['message'].replace("|", "\\|")
        lines.append(f"| `{f['id']}` | **{f['severity']}** | `{f['guard']}` | `{f['rule']}` | `{target}` | {msg} |")

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Finding Dossiers",
        "",
    ])

    for name, result in (guards or {}).items():
        if result["status"] == "ERROR":
            lines.append(f"- **{name} execution error:** {result['error']}")
    if guards and any(result["status"] == "ERROR" for result in guards.values()):
        lines.append("")

    for f in findings:
        target = f"{f['file']}:{f['line']}" if f['file'] else "System"
        lines.extend([
            f"### [{f['id']}] {f['rule']}: {f['message']}",
            f"- **Target:** `{target}`",
            f"- **Severity:** {f['severity']}",
            f"- **Guard:** `{f['guard']}`",
            "",
            "```text",
            f.get("snippet", "(no snippet available)").strip(),
            "```",
            "",
            f"**Remediation:** {f['remediation']}",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Approval & Remediation Workflow",
        "",
        "In **AFTER Mode**, select finding IDs to approve remediation:",
        "```bash",
        "# Fix approved findings:",
        f"bunx anti-slop-engineering fix --findings={','.join(f['id'] for f in findings[:3]) if findings else 'ALL'}",
        "```",
    ])

    content = "\n".join(lines) + "\n"
    with open(audit_file, "w", encoding="utf-8") as out_f:
        out_f.write(content)
    return content


def run_audit(base: str = "HEAD", json_output: bool = False) -> int:
    findings, guards = collect_audit_findings(base)
    blockers = sum(1 for finding in findings if finding["severity"] == "BLOCKER")
    status = "ERROR" if any(result["status"] == "ERROR" for result in guards.values()) else (
        "BLOCKED" if blockers else "PASS"
    )
    audit_file = None
    audit_error = None
    try:
        audit_file = get_next_audit_file()
        generate_audit_markdown(findings, audit_file, status=status, guards=guards)
    except OSError as exc:
        status = "ERROR"
        audit_error = f"Unable to write audit report: {exc}"

    report = {
        "audit_file": str(audit_file) if audit_file is not None else None,
        "total_findings": len(findings),
        "blockers_count": blockers,
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
        print(f"   Dossier:  {audit_file or 'not written'}")
        print(f"   Findings: {len(findings)} total")
        print(f"   Status: {status} ({blockers} blockers)")
        for name, result in guards.items():
            if result["status"] == "ERROR":
                print(f"   ERROR {name}: {result['error']}", file=sys.stderr)
        if audit_error:
            print(f"   ERROR: {audit_error}", file=sys.stderr)
    return {"PASS": 0, "BLOCKED": 1, "ERROR": 2}[status]


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    command = args[0]
    if command == "mode":
        return handle_mode(args[1:])
    elif command in ("audit", "run"):
        json_mode = "--json" in args
        base = "HEAD"
        if "--base" in args:
            idx = args.index("--base")
            if idx + 1 < len(args):
                base = args[idx + 1]
        return run_audit(base, json_mode)
    else:
        print(f"Error: Unknown audit_runner command '{command}'", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
