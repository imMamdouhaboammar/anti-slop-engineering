#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Demock & Silent-Fallback Guard (Zero-Dependency Python >=3.9)
Inspects production code for test doubles on real paths, swallowed failures,
dummy fallbacks (e.g. SQLite fallback in Supabase apps), fail-open auth gates,
and unimplemented placeholders.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Patterns to identify test directories and files that are exempt from demock checks
TEST_PATH_PATTERNS = [
    re.compile(r"(^|[/\\])(tests?|__tests__|testing|fixtures|testdata)([/\\]|$)"),
    re.compile(r"(\.|_)(test|spec)\.(py|ts|js|tsx|jsx|go|rs|mjs|cjs)$"),
]

# Patterns for Test Doubles in Production paths
TEST_DOUBLE_PATTERNS = [
    (re.compile(r"(from\s+unittest\.mock\s+import|import\s+unittest\.mock)"), "Python unittest.mock imported in production code"),
    (re.compile(r"\b(MagicMock|Mock|AsyncMock)\s*\("), "unittest.mock object instantiated in production path"),
    (re.compile(r"(from\s+vitest\s+import\s*\{[^}]*\bmock\b|import\s*\{[^}]*\bmock\b\s*from\s*['\"]vitest['\"])"), "Vitest mock imported in production file"),
    (re.compile(r"(import\s*\{[^}]*\bjst\b|jest\.fn\s*\()"), "Jest mock utility referenced in production code"),
    (re.compile(r"\b(new\s+FakeDatabase|new\s+DummyStorage|new\s+MockService)\s*\("), "Explicit fake/mock service instantiated in production path"),
]

# Patterns for Silent Fallbacks & False Successes
SILENT_FALLBACK_PATTERNS = [
    (re.compile(r"except\s+Exception\s*:\s*\n\s+return\s+(\[\]|\{\}|None|True|False|['\"][^'\"]*['\"])"), "Exception swallowed returning dummy default"),
    (re.compile(r"except\s*:\s*\n\s+return\s+(\[\]|\{\}|None|True|False|['\"][^'\"]*['\"])"), "Bare except returning dummy fallback"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*return\s+(\[\]|\{\}|null|true|false|['\"][^'\"]*['\"]);?\s*\}"), "Catch block swallowed returning dummy fallback"),
    (re.compile(r"catch\s*\{\s*return\s+(\[\]|\{\}|null|true|false|['\"][^'\"]*['\"]);?\s*\}"), "Catch block without param swallowed returning dummy fallback"),
    (re.compile(r"(//?\s*fallback\s+to\s+sqlite|fallback_to_sqlite|local_sqlite_fallback|new\s+LocalSqliteDb)", re.IGNORECASE), "Forbidden local SQLite fallback detected in database layer"),
]

# Patterns for Fail-Open Authorization Gates
FAIL_OPEN_PATTERNS = [
    (re.compile(r"if\s*\(!?(token|apiKey|api_key|auth|secret|credential)\)\s*\{\s*(?:\n\s*)?return\s+true;?", re.DOTALL), "Missing auth credential fails open (returns true)"),
    (re.compile(r"if\s+not\s+(token|apiKey|api_key|auth|secret|credential)\s*:\s*\n\s+return\s+True"), "Missing auth credential fails open in Python"),
    (re.compile(r"//\s*(bypass|skip)\s+auth.*return\s+true"), "Explicit dev auth bypass returning true in production path"),
]

# Patterns for Unimplemented Placeholders in active exports
PLACEHOLDER_PATTERNS = [
    (re.compile(r"raise\s+NotImplementedError\b"), "raise NotImplementedError in reachable production path"),
    (re.compile(r"\b(todo!|unimplemented!)\s*\("), "Rust todo!/unimplemented! macro in production path"),
    (re.compile(r"throw\s+new\s+Error\s*\(\s*['\"](TODO|not implemented|unimplemented)['\"]\s*\)"), "TODO error thrown on production path"),
]


def is_test_file(path: str) -> bool:
    norm_path = path.replace("\\", "/")
    for pattern in TEST_PATH_PATTERNS:
        if pattern.search(norm_path):
            return True
    return False


def get_git_diff_files(base_ref: str = "HEAD") -> List[Tuple[str, str]]:
    """Returns list of (filepath, status) modified relative to base_ref."""
    try:
        res = subprocess.run(
            ["git", "diff", "--name-status", base_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        files = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                status, path = parts[0], parts[1]
                if status != "D":  # Exclude deleted files
                    files.append((path, status))
        return files
    except Exception:
        return []


def scan_file_content(path: str, content: str) -> List[Dict[str, Any]]:
    findings = []
    lines = content.splitlines()

    # 1. Test doubles
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in TEST_DOUBLE_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "id": f"DEMOCK-TD-{len(findings)+1:03d}",
                    "file": path,
                    "line": line_idx,
                    "class": "TEST_DOUBLE_IN_PROD",
                    "severity": "BLOCKING",
                    "evidence": line.strip(),
                    "recommendation": f"Remove test double from production runtime ({desc}). Inject real dependency via constructor or container."
                })

    # 2. Silent fallbacks (multi-line regex support)
    for pattern, desc in SILENT_FALLBACK_PATTERNS:
        for match in pattern.finditer(content):
            # Calculate line number from character offset
            start_pos = match.start()
            line_idx = content.count("\n", 0, start_pos) + 1
            matched_text = match.group(0).strip().replace("\n", " ")
            findings.append({
                "id": f"DEMOCK-FB-{len(findings)+1:03d}",
                "file": path,
                "line": line_idx,
                "class": "SILENT_FALLBACK",
                "severity": "BLOCKING",
                "evidence": matched_text[:120],
                "recommendation": f"Eliminate silent dummy fallback ({desc}). Let error propagate, fail closed, or return explicit typed failure."
            })

    # 3. Fail-open gates
    for pattern, desc in FAIL_OPEN_PATTERNS:
        for match in pattern.finditer(content):
            start_pos = match.start()
            line_idx = content.count("\n", 0, start_pos) + 1
            matched_text = match.group(0).strip().replace("\n", " ")
            findings.append({
                "id": f"DEMOCK-FO-{len(findings)+1:03d}",
                "file": path,
                "line": line_idx,
                "class": "FAIL_OPEN_GATE",
                "severity": "BLOCKING",
                "evidence": matched_text[:120],
                "recommendation": f"Security check fails open ({desc}). Gate must fail closed: return false, 401 Unauthorized, or raise AuthenticationError."
            })

    # 4. Placeholders
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in PLACEHOLDER_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "id": f"DEMOCK-PH-{len(findings)+1:03d}",
                    "file": path,
                    "line": line_idx,
                    "class": "UNIMPLEMENTED_PLACEHOLDER",
                    "severity": "WARNING",
                    "evidence": line.strip(),
                    "recommendation": f"Unimplemented placeholder on production path ({desc}). Fully implement logic or decouple from active export."
                })

    return findings


def audit_paths(paths: List[str], strict: bool = False) -> Dict[str, Any]:
    all_findings = []
    scanned_count = 0

    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs"]:
                        fpath = os.path.join(root, f)
                        if not is_test_file(fpath):
                            try:
                                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                                    findings = scan_file_content(fpath, fh.read())
                                    all_findings.extend(findings)
                                    scanned_count += 1
                            except Exception:
                                pass
        else:
            if not is_test_file(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as fh:
                        findings = scan_file_content(p, fh.read())
                        all_findings.extend(findings)
                        scanned_count += 1
                except Exception:
                    pass

    blocking_count = sum(1 for f in all_findings if f["severity"] == "BLOCKING")
    if blocking_count > 0 or (strict and len(all_findings) > 0):
        verdict = "REJECT"
    elif len(all_findings) > 0:
        verdict = "WARNING"
    else:
        verdict = "PROCEED"

    record = {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "scanned_files": scanned_count,
        "findings_count": len(all_findings),
        "findings": all_findings,
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Demock & Silent-Fallback Guard")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan")
    parser.add_argument("--base", default=None, help="Scan git diff against base ref (e.g. HEAD or main)")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as blocking failures")
    args = parser.parse_args()

    targets = list(args.paths)
    if args.base is not None or not targets:
        base_ref = args.base if args.base is not None else "HEAD"
        diff_files = get_git_diff_files(base_ref)
        targets.extend([f for f, _ in diff_files])

    if not targets:
        # Default to scanning src/ or current dir
        if os.path.isdir("src"):
            targets = ["src"]
        elif os.path.isdir("lib"):
            targets = ["lib"]
        else:
            targets = ["."]

    record = audit_paths(targets, strict=args.strict)

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n🎭 DEMOCK GUARD AUDIT: {record['verdict']}")
        print(f"Scanned {record['scanned_files']} production files, found {record['findings_count']} finding(s).\n")
        for f in record["findings"]:
            sev_badge = "🚨 [BLOCKING]" if f["severity"] == "BLOCKING" else "⚠️  [WARNING]"
            print(f"{sev_badge} {f['file']}:{f['line']} ({f['class']})")
            print(f"   Evidence: {f['evidence']}")
            print(f"   Fix:      {f['recommendation']}\n")

    return 1 if record["verdict"] == "REJECT" else 0


if __name__ == "__main__":
    sys.exit(main())
