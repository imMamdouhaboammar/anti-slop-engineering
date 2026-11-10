#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Design System Drift & Variant-Budget Guard.

Audits multi-surface applications and component libraries for cross-route design
system drift, unpoliced component variant explosions, orphaned single-route tokens,
and keyboard focus-ring accessibility suppression.

Usage:
    python3 scripts/system_drift_guard.py --scan src/
    python3 scripts/system_drift_guard.py --file record.json --json
    python3 scripts/system_drift_guard.py --max-variants button=4,select=1,card=3
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_MAX_VARIANTS = 4
DEFAULT_KIND_BUDGETS: Dict[str, int] = {
    "button": 4,
    "select": 2,
    "input": 3,
    "card": 4,
    "badge": 3,
}

SCAN_EXTENSIONS = {".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte", ".html", ".js", ".ts"}
SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".next", "out"}


def parse_variant_budget_arg(raw: str) -> Dict[str, int]:
    """Parse budget argument: e.g. '4' or 'button=4,select=1,card=3'."""
    budgets = dict(DEFAULT_KIND_BUDGETS)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        m = re.match(r"^([a-z]+)\s*=\s*(\d+)$", p, re.I)
        if m:
            budgets[m.group(1).lower()] = int(m.group(2))
        elif p.isdigit():
            default_val = int(p)
            for k in list(budgets.keys()):
                budgets[k] = default_val
    return budgets


def scan_file_for_system_drift(
    file_path: Path,
    kind_variants: Dict[str, Set[str]],
    token_usage: Dict[str, Set[str]],
    focus_violations: List[Dict[str, Any]],
    route_name: str,
) -> List[Dict[str, Any]]:
    """Scan a single source or style file for focus ring suppression and variant patterns."""
    findings: List[Dict[str, Any]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    lines = content.splitlines()

    # 1. Focus ring suppression detection: outline: none or focus:outline-none without visible replacement
    for idx, line in enumerate(lines, 1):
        # Ignore comments
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Check for bare outline suppression
        if re.search(r"outline\s*:\s*(?:none|0)\b", line, re.I) and not re.search(
            r":focus-visible|focus-visible|box-shadow|ring-", line, re.I
        ):
            # Check nearby lines for replacement (excluding bare outline: none / 0)
            window_lines = [lines[j] for j in range(max(0, idx - 4), min(len(lines), idx + 4)) if j != idx - 1]
            window = "\n".join(window_lines)
            if not re.search(r":focus-visible|focus-visible|box-shadow|ring|outline\s*:\s*(?:[1-9]|solid|dashed|dotted)", window, re.I):
                focus_violations.append({
                    "element": "interactive-control",
                    "file": str(file_path),
                    "line": idx,
                })
                findings.append({
                    "id": f"SYS-FOCUS-{idx}",
                    "file": str(file_path),
                    "line": idx,
                    "class": "FOCUS_RING_SUPPRESSED",
                    "severity": "BLOCKING",
                    "evidence": line.strip()[:100],
                    "recommendation": "Provide a high-contrast :focus-visible ring or Tailwind focus-visible:ring-2.",
                })

        # Tailwind bare focus:outline-none without focus:ring or focus-visible:ring
        if "focus:outline-none" in line and not re.search(r"focus(?:-visible)?:ring", line):
            focus_violations.append({
                "element": "tailwind-control",
                "file": str(file_path),
                "line": idx,
            })
            findings.append({
                "id": f"SYS-FOCUS-TW-{idx}",
                "file": str(file_path),
                "line": idx,
                "class": "FOCUS_RING_SUPPRESSED",
                "severity": "BLOCKING",
                "evidence": line.strip()[:100],
                "recommendation": "Pair focus:outline-none with explicit focus-visible:ring-2.",
            })

    # 2. Extract variants for button, input, card, badge, select
    for kind in ("button", "input", "select", "card", "badge"):
        pattern = rf"(?:{kind}[-_]?(?:variant|type|style)?|variant)\s*[:=]\s*['\"]([a-zA-Z0-9_-]+)['\"]"
        for m in re.finditer(pattern, content, re.I):
            variant_val = m.group(1).lower()
            kind_variants.setdefault(kind, set()).add(variant_val)

        # CVA / Class variance authority or prop types: variant: { primary: ..., secondary: ... }
        cva_pattern = rf"(?:cva|\bvariant)\s*\(\s*\{{.*?variants\s*:\s*\{{\s*{kind}\s*:\s*\{{([^}}]+)\}}"
        for m in re.finditer(cva_pattern, content, re.I | re.DOTALL):
            body = m.group(1)
            for v_match in re.finditer(r"['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:", body):
                kind_variants.setdefault(kind, set()).add(v_match.group(1).lower())

        # CSS class patterns or string tokens: .btn-primary, .button--outline, "button-ghost", "btn_danger"
        cls_pattern = rf"(?:\.|\b)(?:btn|button|card|badge|select)[-_]+([a-zA-Z0-9_-]+)"
        for m in re.finditer(cls_pattern, content, re.I):
            variant_val = m.group(1).lower()
            kind_variants.setdefault(kind, set()).add(variant_val)

    # 3. Track design tokens to detect single-route orphans
    token_pattern = r"(?:var\(--[a-zA-Z0-9_-]+\)|--color-[a-zA-Z0-9_-]+|--spacing-[a-zA-Z0-9_-]+)"
    for m in re.finditer(token_pattern, content):
        token_name = m.group(0)
        token_usage.setdefault(token_name, set()).add(route_name)

    return findings


def evaluate_system_drift(
    scanned_path: Path,
    budgets: Dict[str, int],
) -> Dict[str, Any]:
    """Execute complete design system drift audit over repository path."""
    kind_variants: Dict[str, Set[str]] = {k: set() for k in budgets}
    token_usage: Dict[str, Set[str]] = {}
    focus_violations: List[Dict[str, Any]] = []
    all_findings: List[Dict[str, Any]] = []
    scanned_files_count = 0

    if scanned_path.is_file():
        # Single record file mode
        try:
            record_data = json.loads(scanned_path.read_text(encoding="utf-8"))
            if isinstance(record_data, dict) and "variant_budgets" in record_data:
                return validate_drift_record(record_data)
        except Exception:
            pass
        files_to_scan = [scanned_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(scanned_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in SCAN_EXTENSIONS:
                    files_to_scan.append(Path(root) / f)

    scanned_files_count = len(files_to_scan)

    for fpath in files_to_scan:
        route_name = fpath.parent.name or "root"
        file_findings = scan_file_for_system_drift(
            fpath, kind_variants, token_usage, focus_violations, route_name
        )
        all_findings.extend(file_findings)

    # Check variant budgets
    variant_budgets_result: Dict[str, Dict[str, Any]] = {}
    entropy_score = 0.0

    for kind, declared_budget in budgets.items():
        actual_variants = kind_variants.get(kind, set())
        actual_count = len(actual_variants)
        exceeded = actual_count > declared_budget
        if exceeded:
            overage = (actual_count - declared_budget) / float(declared_budget)
            entropy_score += overage
            all_findings.append({
                "id": f"SYS-BUDGET-{kind.upper()}",
                "file": str(scanned_path),
                "line": 1,
                "class": "VARIANT_BUDGET_EXCEEDED",
                "severity": "BLOCKING",
                "evidence": f"Kind '{kind}' declared budget {declared_budget}, found {actual_count} variants: {sorted(list(actual_variants))}",
                "recommendation": f"Prune redundant {kind} variants back to declared budget of {declared_budget}.",
            })
        variant_budgets_result[kind] = {
            "budget": declared_budget,
            "actual": actual_count,
            "exceeded": exceeded,
        }

    # Focus violations add to entropy
    entropy_score += 0.25 * len(focus_violations)

    # Detect orphaned tokens (used in exactly one route when >=3 routes scanned)
    all_routes = {r for routes in token_usage.values() for r in routes}
    orphaned_tokens: List[str] = []
    if len(all_routes) >= 3:
        for token, routes in token_usage.items():
            if len(routes) == 1:
                orphaned_tokens.append(token)
                if len(orphaned_tokens) <= 10:
                    all_findings.append({
                        "id": f"SYS-ORPHAN-{len(orphaned_tokens)}",
                        "file": str(scanned_path),
                        "line": 1,
                        "class": "ORPHANED_ROUTE_TOKEN",
                        "severity": "WARNING",
                        "evidence": f"Token '{token}' is used on exactly one route ({list(routes)[0]}).",
                        "recommendation": "Promote token to global theme or replace with canonical system token.",
                    })
        entropy_score += 0.05 * len(orphaned_tokens)

    verdict = "PROCEED"
    if any(f["severity"] == "BLOCKING" for f in all_findings):
        verdict = "REJECT"
    elif all_findings:
        verdict = "WARNING"

    return {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "scanned_routes_or_files": scanned_files_count,
        "entropy_index": round(entropy_score, 4),
        "variant_budgets": variant_budgets_result,
        "orphaned_tokens": orphaned_tokens,
        "focus_ring_violations": focus_violations,
        "findings_count": len(all_findings),
        "findings": all_findings,
    }


def validate_drift_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a pre-existing drift record JSON."""
    findings = data.get("findings", [])
    has_blocking = any(f.get("severity") == "BLOCKING" for f in findings)
    verdict = "REJECT" if has_blocking else ("WARNING" if findings else "PROCEED")
    data["verdict"] = verdict
    data["findings_count"] = len(findings)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Design System Drift & Variant-Budget Guard for multi-screen applications."
    )
    parser.add_argument("--scan", type=str, default=".", help="Directory or file to scan")
    parser.add_argument("--file", type=str, help="Validate pre-existing system drift record JSON")
    parser.add_argument(
        "--max-variants",
        type=str,
        default="4",
        help="Variant budget per kind (e.g. 4 or button=4,select=1,card=3)",
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail with code 2 on warnings")
    parser.add_argument("--selftest", action="store_true", help="Execute built-in self-test assertions")
    args = parser.parse_args()

    if args.selftest:
        budgets = parse_variant_budget_arg("button=2,select=1")
        assert budgets["button"] == 2
        assert budgets["select"] == 1
        print("PASS: System drift guard selftest green.")
        return 0

    budgets = parse_variant_budget_arg(args.max_variants)
    target_path = Path(args.file if args.file else args.scan).resolve()

    if not target_path.exists():
        print(f"Error: Target path does not exist: {target_path}", file=sys.stderr)
        return 1

    report = evaluate_system_drift(target_path, budgets)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"System Drift Guard Verdict: {report['verdict']}")
        print(f"Design System Entropy Index (DSEI): {report['entropy_index']}")
        print(f"Scanned Files/Routes: {report['scanned_routes_or_files']}")
        print(f"Focus Violations: {len(report['focus_ring_violations'])}")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"][:10]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")
            print(f"      Fix: {f['recommendation']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
