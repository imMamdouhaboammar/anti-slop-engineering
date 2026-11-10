#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Comment Budget & Syntactic Obviousness Guard (Zero-Dependency Python >=3.9)
Enforces the Zero-Obviousness & Anti-Truism Doctrine by calculating Comment-to-Code
Ratios (CCR) and detecting banned syntax narration slop while strictly preserving
formal docstrings, license headers, and // SAFETY: invariants.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Comment prefixes across supported polyglot languages
LINE_COMMENT_PREFIXES: Dict[str, Tuple[str, ...]] = {
    ".py": ("#",),
    ".sh": ("#",),
    ".bash": ("#",),
    ".zsh": ("#",),
    ".rb": ("#",),
    ".js": ("//",),
    ".jsx": ("//",),
    ".ts": ("//",),
    ".tsx": ("//",),
    ".mjs": ("//",),
    ".cjs": ("//",),
    ".rs": ("//",),
    ".go": ("//",),
    ".c": ("//",),
    ".cpp": ("//",),
    ".h": ("//",),
    ".hpp": ("//",),
    ".java": ("//",),
    ".kt": ("//",),
    ".swift": ("//",),
    ".php": ("//", "#"),
    ".sql": ("--",),
}

# Exempt file extensions (documentation, pure data, configuration, migrations)
EXEMPT_EXTENSIONS = {
    ".md", ".markdown", ".rst", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".sql", ".csv", ".tsv", ".svg", ".lock",
}

# Banned syntax play-by-play comment patterns (Zero-Obviousness & Anti-Truism Doctrine)
SYNTAX_NARRATION_PATTERNS = [
    re.compile(r"^\s*(?://|#)\s*(?:increment|decrement)\s+\w+", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*return\s+(?:the\s+)?(?:result|value|response|data|true|false|null|none)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*check\s+if\s+(?:\w+\s+)?(?:is\s+)?(?:null|none|empty|valid|defined|exists)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*(?:initialize|declare|assign)\s+(?:variable|state|object|array|counter|constant)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*(?:loop|iterate)\s+(?:through|over)\s+(?:all\s+)?(?:items|elements|list|array)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*parse\s+(?:the\s+)?(?:json|string|input|data)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*call\s+(?:\w+\s+)?(?:function|method|api)\b", re.IGNORECASE),
    re.compile(r"^\s*(?://|#)\s*print\s+(?:the\s+)?(?:message|error|output|log)\b", re.IGNORECASE),
]

# Explicitly protected comment patterns that are encouraged and never flagged as slop
PROTECTED_COMMENT_PATTERNS = [
    re.compile(r"//\s*SAFETY:", re.IGNORECASE),
    re.compile(r"//\s*SPDX-License-Identifier:", re.IGNORECASE),
    re.compile(r"//\s*Copyright\s+\(c\)", re.IGNORECASE),
    re.compile(r"#\s*SPDX-License-Identifier:", re.IGNORECASE),
    re.compile(r"#\s*Copyright\s+\(c\)", re.IGNORECASE),
    re.compile(r"^\s*///", re.IGNORECASE),  # Rust doc comment
    re.compile(r"^\s*/\*\*", re.IGNORECASE), # JSDoc / TSDoc block start
    re.compile(r"^\s*\*", re.IGNORECASE),   # JSDoc / TSDoc continuation
]


def is_exempt_file(filename: str) -> bool:
    """Check if file should be exempted from comment budget calculations."""
    base = os.path.basename(filename).lower()
    if base in {"license", "notice", "readme.md", "security.md", "code_of_conduct.md"}:
        return True
    ext = os.path.splitext(filename)[1].lower()
    return ext in EXEMPT_EXTENSIONS


def is_protected_comment(line: str) -> bool:
    """Verify if a comment line matches formal safety invariants or docstrings."""
    return any(p.search(line) is not None for p in PROTECTED_COMMENT_PATTERNS)


def is_syntax_narration(line: str) -> bool:
    """Verify if a comment line matches banned trivial syntax play-by-play."""
    return any(p.search(line) is not None for p in SYNTAX_NARRATION_PATTERNS)


def is_line_comment(line: str, ext: str) -> bool:
    """Check if a trimmed line is a single-line comment for the given extension."""
    prefixes = LINE_COMMENT_PREFIXES.get(ext)
    if not prefixes:
        return False
    trimmed = line.lstrip()
    return any(trimmed.startswith(p) for p in prefixes)


def audit_diff_comments(
    diff_text: str,
    density_threshold: float = 0.35,
    min_comment_floor: int = 20,
) -> Dict[str, Any]:
    """Audit unified diff for comment density and syntax narration slop."""
    findings: List[Dict[str, Any]] = []
    current_file = ""
    current_ext = ""
    line_number = 0
    in_hunk = False
    is_exempt = False

    added_comment_lines = 0
    added_code_lines = 0
    narration_slop_count = 0
    slop_target_lines: List[int] = []

    file_added_comments: Dict[str, int] = {}
    file_added_code: Dict[str, int] = {}

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git"):
            parts = raw_line.split()
            if len(parts) >= 4:
                current_file = parts[3].lstrip("b/")
                current_ext = os.path.splitext(current_file)[1].lower()
                is_exempt = is_exempt_file(current_file)
                file_added_comments[current_file] = 0
                file_added_code[current_file] = 0
            in_hunk = False
            continue

        if is_exempt:
            continue

        if raw_line.startswith("@@"):
            # Extract target line number: @@ -l,s +L,s @@
            match = re.search(r"\+(\d+)", raw_line)
            if match:
                line_number = int(match.group(1))
            in_hunk = True
            continue

        if not in_hunk:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            code_line = raw_line[1:]
            trimmed = code_line.strip()

            if not trimmed:
                line_number += 1
                continue

            # License header stripping: skip comment lines in first 25 lines of new files
            if line_number <= 25 and (
                "spdx-license" in trimmed.lower() or "copyright" in trimmed.lower()
            ):
                line_number += 1
                continue

            # Check if this line is a comment
            if is_line_comment(trimmed, current_ext):
                added_comment_lines += 1
                file_added_comments[current_file] = file_added_comments.get(current_file, 0) + 1

                # Check for syntax narration slop
                if not is_protected_comment(trimmed) and is_syntax_narration(trimmed):
                    narration_slop_count += 1
                    slop_target_lines.append(line_number)
                    findings.append({
                        "file": current_file,
                        "line": line_number,
                        "severity": "blocker",
                        "category": "SYNTAX_NARRATION_SLOP",
                        "evidence": trimmed,
                    })
            else:
                added_code_lines += 1
                file_added_code[current_file] = file_added_code.get(current_file, 0) + 1

            line_number += 1
        elif raw_line.startswith(" "):
            line_number += 1

    # Calculate global Comment-to-Code Ratio (CCR)
    total_effective_code = max(1, added_code_lines)
    ccr = round(added_comment_lines / total_effective_code, 3)

    # Check if comment budget exceeded
    if added_comment_lines >= min_comment_floor and ccr > density_threshold:
        severity = "blocker" if narration_slop_count > 0 else "review"
        findings.append({
            "file": "DIFF_TOTAL",
            "line": 1,
            "severity": severity,
            "category": "COMMENT_BUDGET_EXCEEDED",
            "evidence": f"CCR={ccr} ({added_comment_lines} comments / {added_code_lines} code lines) exceeds {density_threshold}",
        })

    has_blockers = any(f["severity"] == "blocker" for f in findings)
    status_code = 400 if has_blockers else (200 if not findings else 200)
    problem_code = (
        "ERR_SYNTAX_NARRATION_SLOP" if narration_slop_count > 0
        else ("ERR_COMMENT_BUDGET_EXCEEDED" if has_blockers else "NO_COMMENT_FINDINGS")
    )

    remediation_action = (
        "STRIP_SYNTAX_NARRATION" if narration_slop_count > 0
        else ("REDUCE_COMMENT_DENSITY" if findings else "NO_ACTION_REQUIRED")
    )

    return {
        "type": "https://anti-slop.org/problem/comment-budget",
        "title": "Comment Budget & Syntactic Obviousness Evaluation",
        "status": status_code,
        "code": problem_code,
        "detail": (
            f"Evaluated {added_comment_lines} added comment lines across {added_code_lines} code lines (CCR={ccr}). "
            f"Found {len(findings)} finding(s)."
        ),
        "metrics": {
            "added_comment_lines": added_comment_lines,
            "added_code_lines": added_code_lines,
            "comment_density_ratio": ccr,
            "threshold": density_threshold,
        },
        "findings": findings,
        "remediation": {
            "action": remediation_action,
            "target_lines": slop_target_lines,
            "guidance": (
                "Strip tautological and obvious syntax play-by-play comments. Let self-explanatory code speak for itself."
                if findings else "Comment density and obviousness invariants are satisfied."
            ),
        },
    }


def audit_git_diff(
    base: str = "HEAD",
    repo_root: Optional[str] = None,
    density_threshold: float = 0.35,
    min_comment_floor: int = 20,
) -> Dict[str, Any]:
    """Run comment budget audit against git diff."""
    cmd = ["git", "diff", base]
    try:
        proc = subprocess.run(
            cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        if proc.returncode != 0:
            # Fallback to inspecting staged or uncommitted diff
            proc = subprocess.run(
                ["git", "diff", "HEAD"], cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
        diff_text = proc.stdout
    except Exception as exc:
        diff_text = ""

    return audit_diff_comments(
        diff_text,
        density_threshold=density_threshold,
        min_comment_floor=min_comment_floor,
    )


def main():
    parser = argparse.ArgumentParser(description="Comment Budget & Obviousness Guard")
    parser.add_argument("--base", default="HEAD", help="Base commit or branch to compare against")
    parser.add_argument("--repo", default=None, help="Path to Git repository")
    parser.add_argument("--diff-file", default=None, help="Unified git diff file to audit directly")
    parser.add_argument("--threshold", type=float, default=0.35, help="Maximum Comment-to-Code Ratio (CCR)")
    parser.add_argument("--min-floor", type=int, default=20, help="Minimum comment lines to activate ratio check")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--fail-on-blocker", action="store_true", help="Exit code 2 if blocker findings exist")

    args = parser.parse_args()

    if args.diff_file and os.path.exists(args.diff_file):
        with open(args.diff_file, "r", encoding="utf-8") as f:
            diff_text = f.read()
        record = audit_diff_comments(
            diff_text,
            density_threshold=args.threshold,
            min_comment_floor=args.min_floor,
        )
    else:
        record = audit_git_diff(
            base=args.base,
            repo_root=args.repo,
            density_threshold=args.threshold,
            min_comment_floor=args.min_floor,
        )

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n💬  Anti-Slop Comment Budget Guard — Result: {record['code']}")
        print(f"Metrics: comments={record['metrics']['added_comment_lines']} code={record['metrics']['added_code_lines']} CCR={record['metrics']['comment_density_ratio']} (limit: {record['metrics']['threshold']})")
        if record["findings"]:
            print(f"Findings ({len(record['findings'])}):")
            for f in record["findings"]:
                print(f"  [{f['severity'].upper()}] {f['category']} in {f['file']}:{f['line']}")
                print(f"    Evidence: {f['evidence']}")
        else:
            print("  ✅ Comment density and syntax narration checks passed clean.")

    if args.fail_on_blocker and any(f["severity"] == "blocker" for f in record["findings"]):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
