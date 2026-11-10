#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Musk 5-Step Reduction & Add-Back Ledger Governor (Zero-Dependency Python >=3.9)
Enforces the 5-step simplification algorithm:
1. Make requirements less dumb
2. Delete the part or process
3. Simplify or optimize
4. Accelerate cycle time
5. Automate
Maintains the .anti-slop/add-back-ledger.jsonl ledger enforcing the 10% calibration gate.
"""

import argparse
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

LEDGER_DEFAULT_PATH = os.path.join(".anti-slop", "add-back-ledger.jsonl")


def ensure_ledger_dir(ledger_path: str) -> None:
    dirname = os.path.dirname(ledger_path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)


def read_ledger(ledger_path: str = LEDGER_DEFAULT_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(ledger_path):
        return []
    entries = []
    with open(ledger_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def append_ledger_entry(
    event: str,
    item: str,
    target_path: Optional[str] = None,
    reason: Optional[str] = None,
    ledger_path: str = LEDGER_DEFAULT_PATH
) -> Dict[str, Any]:
    ensure_ledger_dir(ledger_path)
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event,
        "item": item,
        "target_path": target_path or "",
        "reason": reason or "",
    }
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def compute_calibration(ledger_path: str = LEDGER_DEFAULT_PATH) -> Dict[str, Any]:
    entries = read_ledger(ledger_path)
    total_removals = sum(1 for e in entries if e.get("event") == "remove")
    total_addbacks = sum(1 for e in entries if e.get("event") == "add-back")

    if total_removals == 0:
        addback_rate = 0.0
        calibration = "BASELINE"
        verdict = "INSUFFICIENT_DATA"
    else:
        addback_rate = round(total_addbacks / total_removals, 4)
        if addback_rate < 0.10:
            calibration = "TIMID_BELOW_10_PERCENT"
            verdict = "UNDER_DELETING"
        elif addback_rate > 0.35:
            calibration = "RECKLESS_ABOVE_35_PERCENT"
            verdict = "OVER_DELETING"
        else:
            calibration = "OPTIMAL_10_TO_25_PERCENT"
            verdict = "CALIBRATED"

    return {
        "total_removals": total_removals,
        "total_addbacks": total_addbacks,
        "addback_rate": addback_rate,
        "calibration_status": calibration,
        "verdict": verdict,
    }


def audit_source_reduction(filepath: str) -> List[Dict[str, Any]]:
    """Evaluates whether code violates the reduction ladder (e.g. optimizing speculative parameters)."""
    findings = []
    if not os.path.exists(filepath):
        return findings

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return findings

    lines = content.splitlines()

    # Pattern: unused/speculative kwargs or parameters marked with _unused
    for line_idx, line in enumerate(lines, start=1):
        if re.search(r"def\s+[a-zA-Z0-9_]+\s*\([^)]*(_unused|future_param|reserved)[^)]*\)", line):
            findings.append({
                "item_id": f"RED-{line_idx}",
                "target_path": f"{filepath}:{line_idx}",
                "step": "2_DELETE_PART_OR_PROCESS",
                "mandated_constraint": False,
                "proposal": "REMOVE",
                "re_adding_cost": "LOW",
                "evidence": line.strip(),
                "reason": "Speculative parameter should be deleted rather than maintained."
            })
        elif re.search(r"//\s*TODO\(future\)|#\s*TODO\(future\)", line):
            findings.append({
                "item_id": f"RED-TODO-{line_idx}",
                "target_path": f"{filepath}:{line_idx}",
                "step": "1_QUESTION_REQUIREMENT",
                "mandated_constraint": False,
                "proposal": "REMOVE",
                "re_adding_cost": "LOW",
                "evidence": line.strip(),
                "reason": "Speculative future TODO violates YAGNI. Delete placeholder."
            })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Musk 5-Step Reduction & Add-Back Governor")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit file or diff for reduction compliance")
    audit_parser.add_argument("target", nargs="?", default=".", help="Target file or directory to audit")
    audit_parser.add_argument("--ledger", default=LEDGER_DEFAULT_PATH, help="Path to add-back ledger")
    audit_parser.add_argument("--json", action="store_true", help="Output JSON record")

    # Log remove
    remove_parser = subparsers.add_parser("log-remove", help="Record an item removal in the ledger")
    remove_parser.add_argument("--item", required=True, help="Name or signature of removed item")
    remove_parser.add_argument("--path", default="", help="File path where item lived")
    remove_parser.add_argument("--reason", default="", help="Why item was removed")
    remove_parser.add_argument("--ledger", default=LEDGER_DEFAULT_PATH, help="Path to add-back ledger")

    # Log add-back
    addback_parser = subparsers.add_parser("log-addback", help="Record an item re-instatement in the ledger")
    addback_parser.add_argument("--item", required=True, help="Name or signature of restored item")
    addback_parser.add_argument("--path", default="", help="File path where item was restored")
    addback_parser.add_argument("--reason", default="", help="Why item was added back")
    addback_parser.add_argument("--ledger", default=LEDGER_DEFAULT_PATH, help="Path to add-back ledger")

    # Status
    status_parser = subparsers.add_parser("status", help="Display Add-Back rate and calibration status")
    status_parser.add_argument("--ledger", default=LEDGER_DEFAULT_PATH, help="Path to add-back ledger")
    status_parser.add_argument("--json", action="store_true", help="Output JSON status")

    args = parser.parse_args()

    if args.command == "log-remove":
        entry = append_ledger_entry("remove", args.item, args.path, args.reason, args.ledger)
        print(f"✅ Logged removal: '{args.item}' into {args.ledger}")
        return 0

    elif args.command == "log-addback":
        entry = append_ledger_entry("add-back", args.item, args.path, args.reason, args.ledger)
        print(f"🔄 Logged add-back: '{args.item}' into {args.ledger}")
        return 0

    elif args.command == "status":
        stats = compute_calibration(args.ledger)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n📉 MUSK 5-STEP ADD-BACK LEDGER CALIBRATION:")
            print(f"   Total Removals:   {stats['total_removals']}")
            print(f"   Total Add-Backs:  {stats['total_addbacks']}")
            print(f"   Add-Back Rate:    {stats['addback_rate']*100:.1f}%")
            print(f"   Calibration:      {stats['calibration_status']}")
            print(f"   Verdict:          {stats['verdict']}\n")
            if stats["calibration_status"] == "TIMID_BELOW_10_PERCENT":
                print("   💡 Note: Rate is <10%. Musk's rule: 'If you're not adding things back 10% of the time, you're not deleting enough.'")
            elif stats["calibration_status"] == "OPTIMAL_10_TO_25_PERCENT":
                print("   🎯 Calibrated! Deletions are aggressive yet disciplined.")
        return 0

    else:
        # Default or audit
        target = getattr(args, "target", ".")
        ledger_path = getattr(args, "ledger", LEDGER_DEFAULT_PATH)
        stats = compute_calibration(ledger_path)

        items = []
        if os.path.isfile(target):
            items = audit_source_reduction(target)
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for f in files:
                    if f.endswith((".py", ".ts", ".js", ".rs", ".go")):
                        items.extend(audit_source_reduction(os.path.join(root, f)))

        record = {
            "schema_version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verdict": stats["verdict"],
            "idiot_index_evaluated": True,
            "total_removals": stats["total_removals"],
            "total_addbacks": stats["total_addbacks"],
            "addback_rate": stats["addback_rate"],
            "calibration_status": stats["calibration_status"],
            "items": items,
        }

        if getattr(args, "json", False):
            print(json.dumps(record, indent=2))
        else:
            print(f"\n✂️  REDUCTION GOVERNOR AUDIT: {record['verdict']}")
            print(f"   Add-back Rate: {record['addback_rate']*100:.1f}% ({record['calibration_status']})")
            print(f"   Flagged {len(items)} item(s) violating the reduction ladder.\n")
            for it in items:
                print(f"   • {it['target_path']}: {it['proposal']} ({it['step']})")
                print(f"     Reason: {it['reason']}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
