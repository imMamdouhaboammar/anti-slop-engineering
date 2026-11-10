#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Anti-Slop Honeypot Trap & Prompt Canary Guard (Zero-Dependency Python >=3.9)
Detects automated AI slop through active prompt canary traps, decoy issue references,
and decoy template checkboxes while preventing self-blocking on template maintenance.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Default decoy patterns that indicate ungrounded LLM ingestion
DEFAULT_DECOY_ISSUES = {"#9999", "#8888", "#99999", "GH-9999"}
DEFAULT_DECOY_PHRASES = {
    "quantum teleportation algorithm",
    "verified-autonomous-agent-bypass",
    "synthetic-canary-ack",
}

# Regex to detect active canary echo directives in text
CANARY_ECHO_REGEX = re.compile(r"anti-slop-canary:([a-zA-Z0-9_-]+)", re.IGNORECASE)

# Decoy checkbox pattern: e.g. - [x] I confirm this PR contains quantum teleportation
DECOY_CHECKBOX_REGEX = re.compile(
    r"^\s*-\s+\[([xX])\]\s+.*(?:quantum teleportation|synthetic canary|autonomous bot marker).*",
    re.IGNORECASE | re.MULTILINE,
)

# Paths exempt from honeypot triggers (template maintenance by maintainers)
EXEMPT_TEMPLATE_PATH_PATTERNS = [
    re.compile(r"^\.github/.*template.*\.md$", re.IGNORECASE),
    re.compile(r"^\.github/workflows/", re.IGNORECASE),
    re.compile(r"^templates?/", re.IGNORECASE),
    re.compile(r"^schemas/.*honeypot.*\.json$", re.IGNORECASE),
    re.compile(r"^tests/test_honeypot", re.IGNORECASE),
]


def generate_canary_token(secret: str, salt: str = "anti-slop-canary") -> str:
    """Generate a deterministic HMAC-SHA256 canary token from a secret key."""
    digest = hmac.new(secret.encode("utf-8"), salt.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"canary-{digest[:16]}"


def is_exempt_path(path: str) -> bool:
    """Check if file path is exempt from honeypot trigger evaluation."""
    norm_path = path.replace("\\", "/")
    if norm_path.startswith("./"):
        norm_path = norm_path[2:]
    return any(pattern.search(norm_path) is not None for pattern in EXEMPT_TEMPLATE_PATH_PATTERNS)


def scan_text_for_honeypots(
    text: str,
    active_canary_tokens: Optional[Set[str]] = None,
    decoy_issues: Optional[Set[str]] = None,
    decoy_phrases: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Scan arbitrary text (PR description, commit message, code hunk) for honeypot triggers."""
    if not text:
        return []

    findings: List[Dict[str, Any]] = []
    if active_canary_tokens is None:
        active_canary_tokens = set()
    if decoy_issues is None:
        decoy_issues = DEFAULT_DECOY_ISSUES
    if decoy_phrases is None:
        decoy_phrases = DEFAULT_DECOY_PHRASES

    # 1. Check for Active Canary Tokens echoed by an LLM
    for match in CANARY_ECHO_REGEX.finditer(text):
        token_val = match.group(1).lower()
        if token_val in {t.lower() for t in active_canary_tokens}:
            findings.append({
                "trap_id": "ACTIVE_CANARY_TOKEN_ECHOED",
                "severity": "blocker",
                "message": f"PR text echoes secret active prompt canary token '{token_val}'. LLM ingestion confirmed.",
                "matched_text": match.group(0),
            })

    # 2. Check for Decoy Issue References
    for issue in decoy_issues:
        pattern = re.compile(r"(?<!\w)" + re.escape(issue) + r"(?!\w)", re.IGNORECASE)
        if pattern.search(text):
            findings.append({
                "trap_id": "DECOY_ISSUE_REFERENCED",
                "severity": "blocker",
                "message": f"PR references decoy honeypot issue '{issue}'. Unverified bot activity detected.",
                "matched_text": issue,
            })

    # 3. Check for Decoy Phrases
    for phrase in decoy_phrases:
        if phrase.lower() in text.lower():
            findings.append({
                "trap_id": "DECOY_PHRASE_DETECTED",
                "severity": "blocker",
                "message": f"PR contains decoy honeypot phrase '{phrase}'. Hallucination confirmed.",
                "matched_text": phrase,
            })

    # 4. Check for Decoy Checkboxes checked in Markdown
    for cb_match in DECOY_CHECKBOX_REGEX.finditer(text):
        findings.append({
            "trap_id": "DECOY_CHECKBOX_CHECKED",
            "severity": "blocker",
            "message": "PR checked a decoy trap checkbox intended solely to catch unguided automated bots.",
            "matched_text": cb_match.group(0).strip(),
        })

    return findings


def audit_diff_for_honeypots(
    diff_text: str,
    active_canary_tokens: Optional[Set[str]] = None,
    decoy_issues: Optional[Set[str]] = None,
    decoy_phrases: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Audit added lines in a unified git diff, respecting exempt template paths."""
    findings: List[Dict[str, Any]] = []
    current_file = ""
    is_exempt = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[3].lstrip("b/")
                is_exempt = is_exempt_path(current_file)
            continue

        if is_exempt:
            continue

        # Only audit newly added code lines (not removals or context)
        if line.startswith("+") and not line.startswith("+++"):
            added_content = line[1:].strip()
            line_findings = scan_text_for_honeypots(
                added_content,
                active_canary_tokens=active_canary_tokens,
                decoy_issues=decoy_issues,
                decoy_phrases=decoy_phrases,
            )
            for f in line_findings:
                f["file"] = current_file
                findings.append(f)

    return findings


def audit_honeypots(
    pr_body: Optional[str] = None,
    pr_title: Optional[str] = None,
    commit_messages: Optional[List[str]] = None,
    diff_text: Optional[str] = None,
    active_canary_tokens: Optional[Set[str]] = None,
    decoy_issues: Optional[Set[str]] = None,
    decoy_phrases: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Execute complete multi-target honeypot audit."""
    findings: List[Dict[str, Any]] = []
    targets_scanned = 0

    # Scan PR Title
    if pr_title:
        targets_scanned += 1
        findings.extend(
            scan_text_for_honeypots(
                pr_title,
                active_canary_tokens=active_canary_tokens,
                decoy_issues=decoy_issues,
                decoy_phrases=decoy_phrases,
            )
        )

    # Scan PR Body
    if pr_body:
        targets_scanned += 1
        findings.extend(
            scan_text_for_honeypots(
                pr_body,
                active_canary_tokens=active_canary_tokens,
                decoy_issues=decoy_issues,
                decoy_phrases=decoy_phrases,
            )
        )

    # Scan Commit Messages
    if commit_messages:
        targets_scanned += len(commit_messages)
        for msg in commit_messages:
            findings.extend(
                scan_text_for_honeypots(
                    msg,
                    active_canary_tokens=active_canary_tokens,
                    decoy_issues=decoy_issues,
                    decoy_phrases=decoy_phrases,
                )
            )

    # Scan Git Diff additions
    if diff_text:
        targets_scanned += 1
        findings.extend(
            audit_diff_for_honeypots(
                diff_text,
                active_canary_tokens=active_canary_tokens,
                decoy_issues=decoy_issues,
                decoy_phrases=decoy_phrases,
            )
        )

    traps_count = len(DEFAULT_DECOY_ISSUES) + len(DEFAULT_DECOY_PHRASES) + (
        len(active_canary_tokens) if active_canary_tokens else 0
    )
    canary_found = len(findings)
    has_blockers = any(f["severity"] == "blocker" for f in findings)
    status_code = 400 if has_blockers else 200
    problem_code = "ERR_HONEYPOT_TRIGGERED" if has_blockers else "NO_HONEYPOT_FINDINGS"

    return {
        "type": "https://anti-slop.org/problem/honeypot-trap",
        "title": "Honeypot Trap & Prompt Canary Evaluation",
        "status": status_code,
        "code": problem_code,
        "detail": (
            f"Triggered {canary_found} honeypot traps in scanned targets."
            if canary_found
            else "Clean scan. Zero prompt honeypot or canary traps triggered."
        ),
        "canary_scan": {
            "targets_scanned": targets_scanned,
            "traps_configured": traps_count,
            "canary_tokens_found": canary_found,
        },
        "findings": findings,
        "remediation": {
            "action": "PURGE_CANARY_ECHOES" if has_blockers else "NO_ACTION_REQUIRED",
            "guidance": (
                "Remove decoy issue references, uncheck decoy checkboxes, or strip hallucinated canary phrases."
                if has_blockers
                else "No honeypot action required."
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Anti-Slop Honeypot Trap Guard")
    parser.add_argument("--generate-canary", action="store_true", help="Generate a new HMAC canary token")
    parser.add_argument("--secret", default="anti-slop-default-secret", help="Secret key for canary token generation")
    parser.add_argument("--pr-body-file", default=None, help="File containing PR body markdown to audit")
    parser.add_argument("--pr-title", default=None, help="PR title to audit")
    parser.add_argument("--canary-token", action="append", default=[], help="Active canary token(s) to verify")
    parser.add_argument("--diff-file", default=None, help="Unified git diff file to audit")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--fail-on-blocker", action="store_true", help="Exit code 2 if blocker findings exist")

    args = parser.parse_args()

    if args.generate_canary:
        token = generate_canary_token(args.secret)
        print(f"Generated Canary Token: {token}")
        print(f"Embed in markdown template as: <!-- anti-slop-canary:{token} -->")
        sys.exit(0)

    pr_body = None
    if args.pr_body_file and os.path.exists(args.pr_body_file):
        with open(args.pr_body_file, "r", encoding="utf-8") as f:
            pr_body = f.read()

    diff_text = None
    if args.diff_file and os.path.exists(args.diff_file):
        with open(args.diff_file, "r", encoding="utf-8") as f:
            diff_text = f.read()

    canaries = set(args.canary_token) if args.canary_token else None

    record = audit_honeypots(
        pr_body=pr_body,
        pr_title=args.pr_title,
        diff_text=diff_text,
        active_canary_tokens=canaries,
    )

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n🍯  Anti-Slop Honeypot Guard — Result: {record['code']}")
        print(f"Scan Summary: targets={record['canary_scan']['targets_scanned']} traps={record['canary_scan']['traps_configured']} triggered={record['canary_scan']['canary_tokens_found']}")
        if record["findings"]:
            print(f"Findings ({len(record['findings'])}):")
            for f in record["findings"]:
                print(f"  [{f['severity'].upper()}] {f['trap_id']}: {f['message']}")
                print(f"    Evidence: {f['matched_text']}")
        else:
            print("  ✅ All honeypot checks passed clean.")

    if args.fail_on_blocker and any(f["severity"] == "blocker" for f in record["findings"]):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
