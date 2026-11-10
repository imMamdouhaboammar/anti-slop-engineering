#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Upstream Invariant & Rule Backpropagation Guard (Zero-Dependency Python >=3.9)
When downstream code fails or slop is flagged, backpropagates the finding into
the upstream sources that allowed it: AGENTS.md, .anti-slop/invariant-ledger.json,
and skill rule definitions.
"""

import argparse
import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional

INVARIANT_LEDGER_PATH = os.path.join(".anti-slop", "invariant-ledger.json")

RULE_MAPPINGS = {
    "DEMOCK_TEST_DOUBLE": {
        "rule": "RULE_NO_TEST_DOUBLES_IN_PROD",
        "question": "Why was a test double imported into production runtime instead of using dependency injection?",
        "owner": "AGENTS.md",
        "action": "ADD_INVARIANT",
        "text": "Never import or instantiate test doubles (Mock*, Fake*, Stub*) in production code. Use dependency injection.",
    },
    "DEMOCK_SILENT_FALLBACK": {
        "rule": "RULE_FAIL_CLOSED_PERSISTENCE",
        "question": "Why did a catch block return dummy fallback data or fake SQLite instead of propagating the failure?",
        "owner": "AGENTS.md",
        "action": "ADD_INVARIANT",
        "text": "All database and external service failures must fail closed; silent dummy fallbacks and local SQLite fallbacks are strictly banned.",
    },
    "MANDELA_TAUTOLOGY": {
        "rule": "RULE_EXTERNAL_GROUND_TRUTH_TESTS",
        "question": "Why did a test assert a self-referential tautology rather than outside ground truth?",
        "owner": "AGENTS.md",
        "action": "ADD_INVARIANT",
        "text": "Test assertions must evaluate actual behavior against external ground truth; expect(true).toBe(true) and self-comparisons are prohibited.",
    },
    "REDUCTION_SPECULATIVE_PARAM": {
        "rule": "RULE_YAGNI_NO_SPECULATIVE_PARAMS",
        "question": "Why was an unexercised speculative parameter added before a concrete caller needed it?",
        "owner": "AGENTS.md",
        "action": "ADD_INVARIANT",
        "text": "Delete speculative parameters and unused kwargs. Add parameters only when accompanied by real caller call-sites.",
    },
}


def load_invariant_ledger(path: str = INVARIANT_LEDGER_PATH) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "invariants": []
    }


def save_invariant_ledger(data: Dict[str, Any], path: str = INVARIANT_LEDGER_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def backpropagate_finding(
    trigger_error: str,
    file_path: str,
    line: int,
    excerpt: str,
    apply: bool = False
) -> Dict[str, Any]:
    mapping = RULE_MAPPINGS.get(trigger_error, {
        "rule": f"RULE_PREVENT_{trigger_error.upper()}",
        "question": f"Why was {trigger_error} permitted to reach code review without an upstream invariant?",
        "owner": "AGENTS.md",
        "action": "ADD_INVARIANT",
        "text": f"Enforce strict prevention of {trigger_error} across all pull requests.",
    })

    record = {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trigger_error": trigger_error,
        "symptom_location": {
            "file": file_path,
            "line": line,
            "excerpt": excerpt
        },
        "upstream_rule_implicated": mapping["rule"],
        "elon_step_question": mapping["question"],
        "ssot_owner": mapping["owner"],
        "action": mapping["action"],
        "applied": apply,
        "resulting_diff_snippet": f"+ [INVARIANT {mapping['rule']}] {mapping['text']}"
    }

    if apply:
        ledger = load_invariant_ledger(INVARIANT_LEDGER_PATH)
        existing_ids = {inv.get("id") for inv in ledger.get("invariants", [])}
        inv_id = f"INV-{trigger_error[:6].upper()}"
        if inv_id not in existing_ids:
            ledger["invariants"].append({
                "id": inv_id,
                "statement": mapping["text"],
                "originating_error": trigger_error,
                "source_file": file_path,
                "date_added": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            save_invariant_ledger(ledger, INVARIANT_LEDGER_PATH)

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstream Invariant & Rule Backpropagation Guard")
    parser.add_argument("--finding", required=True, help="Finding error type (e.g. DEMOCK_SILENT_FALLBACK)")
    parser.add_argument("--file", default="unknown", help="Source file where symptom surfaced")
    parser.add_argument("--line", type=int, default=1, help="Line number of symptom")
    parser.add_argument("--excerpt", default="", help="Code excerpt showing symptom")
    parser.add_argument("--apply", action="store_true", help="Atomically apply new invariant into ledger")
    parser.add_argument("--json", action="store_true", help="Output JSON record")
    args = parser.parse_args()

    record = backpropagate_finding(
        trigger_error=args.finding,
        file_path=args.file,
        line=args.line,
        excerpt=args.excerpt,
        apply=args.apply
    )

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print("\n🔁 UPSTREAM BACKPROPAGATION RECORD:")
        print(f"   Trigger:  {record['trigger_error']}")
        print(f"   Symptom:  {record['symptom_location']['file']}:{record['symptom_location']['line']}")
        print(f"   Question: {record['elon_step_question']}")
        print(f"   Owner:    {record['ssot_owner']} -> {record['upstream_rule_implicated']}")
        print(f"   Status:   {'APPLIED TO LEDGER' if record['applied'] else 'PROPOSED (run with --apply to commit)'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
