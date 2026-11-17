#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Mandela Test-Oracle & Evaluation Leakage Guard (Zero-Dependency Python >=3.9)
Audits test suites, benchmarks, and evaluation fixtures for the 8 Mandela leakage
patterns where tests confirm themselves, verifiers judge their own designs,
or assertions are tautological.
"""

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

if not __package__:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.git_changeset import collect_changes, repository_root
from scripts.source_trivia import source_trivia

TEST_FILE_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs"}

TEST_PATH_RE = re.compile(
    r"(?i)(?:^|/)(?:tests?|__tests__|specs?|evals?)(?:/|$)"
    r"|(?:^|/)(?:test_[^/]+|[^/]+[._](?:test|spec)\.[a-z0-9]+)$"
)

# Patterns for Tautological Assertions
TAUTOLOGY_PATTERNS = [
    (re.compile(r"\bassert\s+(True|1\s*==\s*1)\b"), "Python tautological assert True or 1==1"),
    (re.compile(r"self\.assert(True|Equal)\s*\(\s*True\s*\)"), "unittest assertTrue(True)"),
    (re.compile(r"self\.assertEqual\s*\(\s*([a-zA-Z_0-9]+)\s*,\s*\1\s*\)"), "unittest self.assertEqual(x, x) self-comparison"),
    (re.compile(r"assert\s+([a-zA-Z_0-9]+)\s*==\s*\1\b"), "Python assert x == x self-comparison"),
    (re.compile(r"expect\s*\(\s*true\s*\)\.to(Be|Equal)\s*\(\s*true\s*\)"), "Jest/Vitest expect(true).toBe(true)"),
    (re.compile(r"expect\s*\(\s*([a-zA-Z_0-9]+)\s*\)\.to(Be|Equal)\s*\(\s*\1\s*\)"), "Jest/Vitest expect(x).toBe(x) self-comparison"),
    (re.compile(r"expect\s*\(\s*1\s*\)\.to(Be|Equal)\s*\(\s*1\s*\)"), "Jest/Vitest expect(1).toBe(1)"),
]

# Patterns for Swallowed Test Failures
SWALLOWED_TEST_PATTERNS = [
    (re.compile(r"except\s+AssertionError\s*:\s*\n\s+pass"), "Swallowed AssertionError in test"),
    (re.compile(r"try\s*:\s*\n\s+[^#\n]+assert[^\n]+\n\s+except\s+Exception\s*:\s*\n\s+pass"), "Assertion swallowed by general except: pass"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*//?\s*ignore\s+error\s*\}"), "Empty catch block in test ignoring assertion failure"),
]

# Patterns for Circular Mock Confirmation
CIRCULAR_MOCK_PATTERNS = [
    (re.compile(r"\.mockReturnValue\s*\(\s*([^)]+)\s*\)[^\n]*\n\s*expect\s*\(.*?\)\.to(?:Be|Equal)\s*\(\s*\1\s*\)"), "Circular mock: asserting mock returns what mock was configured to return"),
    (re.compile(r"\breturn_value\s*=\s*([^,\n]+)[^\n]*\n\s*assert\s+.*?==\s*\1"), "Python circular mock return_value assertion"),
]

# Patterns for Frame Injection in Evals
FRAME_INJECTION_PATTERNS = [
    (re.compile(r"['\"][^'\"]*confirm\s+that\s+the\s+system\s+is\s+working\s+correctly[^'\"]*['\"]", re.IGNORECASE), "Frame injection: leading eval prompt instructing model to confirm success"),
    (re.compile(r"['\"][^'\"]*verify\s+that\s+this\s+output\s+is\s+flawless[^'\"]*['\"]", re.IGNORECASE), "Frame injection: biased prompt pre-supposing perfection"),
]


def scan_test_file_content(path: str, content: str) -> List[Dict[str, Any]]:
    findings = []
    lines = content.splitlines()
    in_trivia = source_trivia(path, content)
    line_offsets: List[int] = []
    _pos = 0
    for _raw_line in content.splitlines(keepends=True):
        line_offsets.append(_pos)
        _pos += len(_raw_line)

    # 1. Tautological assertions
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in TAUTOLOGY_PATTERNS:
            for match in pattern.finditer(line):
                if not in_trivia(line_offsets[line_idx - 1] + match.start()):
                    findings.append({
                        "id": f"MANDELA-TAUT-{len(findings)+1:03d}",
                        "file": path,
                        "line": line_idx,
                        "pattern": "TAUTOLOGICAL_ASSERTION",
                        "severity": "BLOCKING",
                        "evidence": line.strip(),
                        "independence_fix": f"Replace tautological assertion ({desc}) with validation against external ground truth or real computed result."
                    })
                    break

    # 2. Swallowed failures
    for pattern, desc in SWALLOWED_TEST_PATTERNS:
        for match in pattern.finditer(content):
            if in_trivia(match.start()):
                continue
            start_pos = match.start()
            line_idx = content.count("\n", 0, start_pos) + 1
            findings.append({
                "id": f"MANDELA-SWAL-{len(findings)+1:03d}",
                "file": path,
                "line": line_idx,
                "pattern": "SWALLOWED_TEST_FAILURE",
                "severity": "BLOCKING",
                "evidence": match.group(0).strip().replace("\n", " ")[:120],
                "independence_fix": f"Remove swallowed test failure ({desc}). Assert expected exceptions using assertRaises / expect().toThrow()."
            })

    # 3. Circular Mock confirmation
    for pattern, desc in CIRCULAR_MOCK_PATTERNS:
        for match in pattern.finditer(content):
            if in_trivia(match.start()):
                continue
            start_pos = match.start()
            line_idx = content.count("\n", 0, start_pos) + 1
            findings.append({
                "id": f"MANDELA-CIRC-{len(findings)+1:03d}",
                "file": path,
                "line": line_idx,
                "pattern": "CIRCULAR_MOCK_CONFIRMATION",
                "severity": "BLOCKING",
                "evidence": match.group(0).strip().replace("\n", " ")[:120],
                "independence_fix": f"Eliminate circular mock testing ({desc}). Exercise actual production business logic rather than testing the mock configuration."
            })

    # 4. Frame Injection
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in FRAME_INJECTION_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "id": f"MANDELA-FRAM-{len(findings)+1:03d}",
                    "file": path,
                    "line": line_idx,
                    "pattern": "FRAME_INJECTION_EVAL",
                    "severity": "WARNING",
                    "evidence": line.strip(),
                    "independence_fix": f"Neutralize prompt framing ({desc}). Use blind neutral prompts without steering the evaluator towards a predetermined verdict."
                })

    # 5. Check for empty tests in Python (def test_... with only pass or docstring)
    py_test_func = re.compile(r"def\s+(test_[a-zA-Z0-9_]+)\s*\([^)]*\)\s*:(?:\s*['\"].*?['\"])?\s*\n(\s+)(pass|return)\s*$", re.MULTILINE)
    for match in py_test_func.finditer(content):
        if in_trivia(match.start()):
            continue
        start_pos = match.start()
        line_idx = content.count("\n", 0, start_pos) + 1
        func_name = match.group(1)
        findings.append({
            "id": f"MANDELA-ZERO-{len(findings)+1:03d}",
            "file": path,
            "line": line_idx,
            "pattern": "ZERO_ASSERTION_TEST",
            "severity": "BLOCKING",
            "evidence": f"def {func_name} contains only pass/return with zero assertions",
            "independence_fix": f"Add substantive assertions verifying behavior of {func_name}, or remove the empty test stub."
        })

    return findings


def build_record(
    all_findings: List[Dict[str, Any]], scanned_count: int, strict: bool = False
) -> Dict[str, Any]:
    blocking_count = sum(1 for f in all_findings if f["severity"] == "BLOCKING")
    if blocking_count > 0 or (strict and len(all_findings) > 0):
        verdict = "REJECT"
    elif len(all_findings) > 0:
        verdict = "WARNING"
    else:
        verdict = "PROCEED"

    return {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "scanned_files": scanned_count,
        "findings_count": len(all_findings),
        "findings": all_findings,
    }


def audit_test_paths(paths: List[str], strict: bool = False) -> Dict[str, Any]:
    all_findings = []
    scanned_count = 0

    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in TEST_FILE_EXTENSIONS:
                        fpath = os.path.join(root, f)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                                findings = scan_test_file_content(fpath, fh.read())
                                all_findings.extend(findings)
                                scanned_count += 1
                        except Exception:
                            pass
        else:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    findings = scan_test_file_content(p, fh.read())
                    all_findings.extend(findings)
                    scanned_count += 1
            except Exception:
                pass

    return build_record(all_findings, scanned_count, strict=strict)


def audit_git_diff(base: str, strict: bool = False) -> Dict[str, Any]:
    """Scan only test files changed against base, via git_changeset evidence."""
    repo = pathlib.Path(repository_root(".")).resolve()
    all_findings = []
    scanned_count = 0

    for change in collect_changes(repo, base)["files"]:
        path = change["new_path"]
        if path is None or change["binary"] or change["new_mode"] not in {"100644", "100755"}:
            continue
        name = path["text"]
        if name is None:
            print("[mandela-guard] Warning: skipped a non-UTF-8 Git path.", file=sys.stderr)
            continue
        if os.path.splitext(name)[1].lower() not in TEST_FILE_EXTENSIONS:
            continue
        if not TEST_PATH_RE.search(name):
            continue
        full_path = repo / name
        if full_path.is_symlink() or not full_path.is_file():
            continue
        if not full_path.resolve().is_relative_to(repo):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception:
            continue
        all_findings.extend(scan_test_file_content(name, content))
        scanned_count += 1

    return build_record(all_findings, scanned_count, strict=strict)


def audit_default_paths(paths: List[str], strict: bool = False) -> Dict[str, Any]:
    targets = list(paths)
    if not targets:
        # Default to tests/ and evals/
        for candidate in ["tests", "test", "__tests__", "evals"]:
            if os.path.isdir(candidate):
                targets.append(candidate)
        if not targets:
            targets = ["."]

    return audit_test_paths(targets, strict=strict)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mandela Test-Oracle & Leakage Guard")
    parser.add_argument("paths", nargs="*", help="Test files or directories to scan")
    parser.add_argument("--base", default=None, help="Scan git diff test files against base ref")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as blocking failures")
    args = parser.parse_args()

    if args.base is not None:
        try:
            record = audit_git_diff(args.base, strict=args.strict)
        except (RuntimeError, ValueError) as exc:
            if args.json:
                print(json.dumps({"error": str(exc)}))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    else:
        record = audit_default_paths(args.paths, strict=args.strict)

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n🧪 MANDELA LEAKAGE AUDIT: {record['verdict']}")
        print(f"Scanned {record['scanned_files']} test files, found {record['findings_count']} leakage finding(s).\n")
        for f in record["findings"]:
            sev_badge = "🚨 [BLOCKING]" if f["severity"] == "BLOCKING" else "⚠️  [WARNING]"
            print(f"{sev_badge} {f['file']}:{f['line']} ({f['pattern']})")
            print(f"   Evidence: {f['evidence']}")
            print(f"   Fix:      {f['independence_fix']}\n")

    return 1 if record["verdict"] == "REJECT" else 0


if __name__ == "__main__":
    sys.exit(main())
