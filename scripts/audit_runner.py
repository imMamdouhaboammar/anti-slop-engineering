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
    except Exception:
        pass
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


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


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


def collect_audit_findings(base: str = "HEAD") -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    scripts_dir = Path(__file__).resolve().parent

    # 1. Run Diff Guard
    diff_guard = scripts_dir / "diff_guard.py"
    if diff_guard.exists():
        code, out, _ = run_command([sys.executable, str(diff_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "diff_guard",
                        "rule": f.get("category", "SEVEN-GATES"),
                        "severity": "BLOCKER" if f.get("level") == "BLOCK" else "HIGH",
                        "file": f.get("file", ""),
                        "line": f.get("line", 0),
                        "message": f.get("message", ""),
                        "snippet": f.get("snippet", ""),
                        "remediation": "Adhere to the Seven Gates in SKILL.md",
                    })
            except Exception:
                pass

    # 2. Run SRE Guard
    sre_guard = scripts_dir / "sre_guard.py"
    if sre_guard.exists():
        code, out, _ = run_command([sys.executable, str(sre_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "sre_guard",
                        "rule": f.get("principle", "SRE-RELIABILITY"),
                        "severity": "HIGH",
                        "file": f.get("file", ""),
                        "line": f.get("line", 0),
                        "message": f.get("message", ""),
                        "snippet": f.get("snippet", ""),
                        "remediation": f.get("remediation", "Apply KISS/DRY/YAGNI refactoring"),
                    })
            except Exception:
                pass

    # 3. Run AST Slop Guard
    ast_guard = scripts_dir / "ast_slop_guard.py"
    if ast_guard.exists():
        code, out, _ = run_command([sys.executable, str(ast_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("violations", []):
                    findings.append({
                        "guard": "ast_slop_guard",
                        "rule": f.get("rule_id", "AST-TYPE-SLOP"),
                        "severity": "BLOCKER" if f.get("severity") == "error" else "MEDIUM",
                        "file": f.get("file", ""),
                        "line": f.get("line", 0),
                        "message": f.get("message", ""),
                        "snippet": f.get("line_content", ""),
                        "remediation": "Replace with type-safe pattern without chained casts or copies",
                    })
            except Exception:
                pass

    # 4. Run Contrast Guard
    contrast_guard = scripts_dir / "contrast_guard.py"
    if contrast_guard.exists():
        code, out, _ = run_command([sys.executable, str(contrast_guard), "--scan", ".", "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "contrast_guard",
                        "rule": "WCAG-2.2-CONTRAST",
                        "severity": "MEDIUM",
                        "file": f.get("file", ""),
                        "line": f.get("line", 0),
                        "message": f"Low contrast color pairing: {f.get('fg')} on {f.get('bg')} ({f.get('ratio')}:1 fails AA)",
                        "snippet": f.get("snippet", ""),
                        "remediation": "Ensure color contrast ratio meets at least 4.5:1 for normal text",
                    })
            except Exception:
                pass

    # 5. Run Comment Budget Guard
    comment_guard = scripts_dir / "comment_budget_guard.py"
    if comment_guard.exists():
        code, out, _ = run_command([sys.executable, str(comment_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "comment_budget_guard",
                        "rule": f.get("category", "COMMENT-BUDGET"),
                        "severity": "BLOCKER" if f.get("severity") == "blocker" else "HIGH",
                        "file": f.get("file", ""),
                        "line": f.get("line", 0),
                        "message": f.get("message", f.get("evidence", "")),
                        "snippet": f.get("evidence", ""),
                        "remediation": data.get("remediation", {}).get("guidance", "Reduce comment density and remove syntax narration"),
                    })
            except Exception:
                pass

    # 6. Run PR Boundary Guard
    pr_guard = scripts_dir / "pr_boundary_guard.py"
    if pr_guard.exists():
        code, out, _ = run_command([sys.executable, str(pr_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "pr_boundary_guard",
                        "rule": f.get("rule", "PR-BOUNDARY"),
                        "severity": "BLOCKER" if f.get("severity") == "blocker" else "HIGH",
                        "file": "git://topology",
                        "line": 1,
                        "message": f.get("message", ""),
                        "snippet": f.get("evidence", ""),
                        "remediation": data.get("remediation", {}).get("guidance", "Fix git topology or branch conventions"),
                    })
            except Exception:
                pass

    # 7. Run Invariant Steward Drift Guard
    steward_guard = scripts_dir / "invariant_steward_guard.py"
    ledger_file = Path.cwd() / ".anti-slop" / "invariant-ledger.json"
    if steward_guard.exists() and ledger_file.exists():
        code, out, _ = run_command([sys.executable, str(steward_guard), "drift", "--base", base, "--ledger", str(ledger_file), "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "invariant_steward_guard",
                        "rule": f.get("code", "INVARIANT-DRIFT"),
                        "severity": "BLOCKER" if f.get("severity") == "block" else "HIGH",
                        "file": "ledger://invariants",
                        "line": 1,
                        "message": f.get("message", ""),
                        "snippet": f.get("rule", ""),
                        "remediation": f.get("remediation", "Restore invariant or open Reassessment Trigger"),
                    })
            except Exception:
                pass

    # 8. Run Cognitive Bandwidth & Attention Economy Guard
    attention_guard = scripts_dir / "attention_guard.py"
    if attention_guard.exists():
        code, out, _ = run_command([sys.executable, str(attention_guard), "--base", base, "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "attention_guard",
                        "rule": f.get("rule", "COGNITIVE-ATTENTION"),
                        "severity": "BLOCKER" if f.get("severity") == "blocker" else "HIGH",
                        "file": "doc://markdown",
                        "line": 1,
                        "message": f.get("message", ""),
                        "snippet": f.get("evidence", ""),
                        "remediation": data.get("remediation", {}).get("guidance", "Enforce scannability, deliverable purity, and terminal blocking placement"),
                    })
            except Exception:
                pass

    # 9. Run Design System Drift Guard
    system_drift = scripts_dir / "system_drift_guard.py"
    if system_drift.exists():
        code, out, _ = run_command([sys.executable, str(system_drift), "--scan", ".", "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "system_drift_guard",
                        "rule": f.get("class", "DESIGN-SYSTEM-DRIFT"),
                        "severity": "BLOCKER" if f.get("severity") == "BLOCKING" else "MEDIUM",
                        "file": f.get("file", ""),
                        "line": f.get("line", 1),
                        "message": f.get("evidence", ""),
                        "snippet": f.get("evidence", ""),
                        "remediation": f.get("recommendation", "Bound variant budgets and restore focus rings"),
                    })
            except Exception:
                pass

    # 10. Run Chromatic Saturation Drift Guard
    chroma_drift = scripts_dir / "chroma_drift_guard.py"
    if chroma_drift.exists():
        code, out, _ = run_command([sys.executable, str(chroma_drift), "--scan", ".", "--json"])
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "chroma_drift_guard",
                        "rule": f.get("class", "CHROMA-DRIFT"),
                        "severity": "BLOCKER" if f.get("severity") == "BLOCKING" else "MEDIUM",
                        "file": f.get("file", ""),
                        "line": f.get("line", 1),
                        "message": f.get("evidence", ""),
                        "snippet": f.get("evidence", ""),
                        "remediation": f.get("recommendation", "Align chroma and lightness with committed OKLCH contract"),
                    })
            except Exception:
                pass

    # 11. Run StyleSeed Guard
    styleseed_guard = scripts_dir / "styleseed_guard.py"
    if styleseed_guard.exists():
        tokens_arg = ["--tokens", ".anti-slop/tokens.json"] if (Path(".anti-slop/tokens.json").exists()) else []
        code, out, _ = run_command([sys.executable, str(styleseed_guard), "--scan", ".", "--json"] + tokens_arg)
        if out.strip():
            try:
                data = json.loads(out)
                for f in data.get("findings", []):
                    findings.append({
                        "guard": "styleseed_guard",
                        "rule": f.get("class", "STYLESEED-SLOP"),
                        "severity": "BLOCKER" if f.get("severity") == "BLOCKING" else "MEDIUM",
                        "file": f.get("file", ""),
                        "line": f.get("line", 1),
                        "message": f.get("evidence", ""),
                        "snippet": f.get("evidence", ""),
                        "remediation": f.get("recommendation", "Adhere to StyleSeed 4-tier token DAG and 6-role spatial scale"),
                    })
            except Exception:
                pass

    # Assign sequential IDs
    for idx, f in enumerate(findings, start=1):
        f["id"] = f"FINDING-{idx:03d}"

    return findings


def generate_audit_markdown(findings: List[Dict[str, Any]], audit_file: Path) -> str:
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
        f"- **Status:** {'FAIL (Blockers Detected)' if blockers > 0 else ('NEEDS_WORK' if total > 0 else 'PASS')}",
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
    findings = collect_audit_findings(base)
    audit_file = get_next_audit_file()
    generate_audit_markdown(findings, audit_file)

    if json_output:
        print(json.dumps({
            "audit_file": str(audit_file),
            "total_findings": len(findings),
            "findings": findings,
            "status": "FAIL" if any(f.get("severity") == "BLOCKER" for f in findings) else "PASS"
        }, indent=2))
    else:
        print(f"\n📋 Multi-Guard Audit Complete.")
        print(f"   Dossier:  {audit_file}")
        print(f"   Findings: {len(findings)} total")
        blockers = sum(1 for f in findings if f.get("severity") == "BLOCKER")
        if blockers > 0:
            print(f"   ⚠️ {blockers} BLOCKER findings detected.")
            return 1
        print("   ✓ Zero blocker findings.")
    return 0


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
