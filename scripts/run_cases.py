#!/usr/bin/env python3
"""
Anti-Slop Evaluation Case Runner (scripts/run_cases.py).
Evaluates declarative Bad/Good test case pairs against the execution guard.
Complies with Python 3.9+ standard library without external dependencies.
"""

import json
import os
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exec_guard


def run_case(case_path):
    """Run an individual test case file and return (passed, details)."""
    try:
        with open(case_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as ex:
        return False, f"Failed to parse JSON in {case_path}: {ex}"

    case_id = data.get("id", case_path.name)
    title = data.get("title", "")
    inp = data.get("input", {})
    contract = inp.get("contract", {})
    action = inp.get("action", {})
    state = inp.get("state", {})
    expected = data.get("expected", {})

    actual = exec_guard.decide(contract, action, state)

    mismatches = []
    if actual.get("outcome") != expected.get("outcome"):
        mismatches.append(f"outcome: expected '{expected.get('outcome')}', got '{actual.get('outcome')}'")

    if actual.get("family") != expected.get("family"):
        mismatches.append(f"family: expected '{expected.get('family')}', got '{actual.get('family')}'")

    if actual.get("reason_code") != expected.get("reason_code"):
        mismatches.append(f"reason_code: expected '{expected.get('reason_code')}', got '{actual.get('reason_code')}'")

    if mismatches:
        return False, f"[{case_id}] {title} -> FAILED: {'; '.join(mismatches)}"

    return True, f"[{case_id}] {title} -> PASSED"


def main():
    repo_root = Path(__file__).resolve().parent.parent
    cases_dir = repo_root / "cases"

    if not cases_dir.exists():
        print(f"Error: Cases directory {cases_dir} does not exist.")
        sys.exit(1)

    case_files = sorted(cases_dir.glob("*.json"))
    if not case_files:
        print(f"Error: No test case files found in {cases_dir}.")
        sys.exit(1)

    print(f"Running {len(case_files)} Anti-Slop evaluation cases from {cases_dir}...\n")

    passed_count = 0
    failed_count = 0
    failures = []

    for path in case_files:
        passed, msg = run_case(path)
        if passed:
            passed_count += 1
            print(f"  OK   {msg}")
        else:
            failed_count += 1
            failures.append(msg)
            print(f"  FAIL {msg}")

    print("\n" + "=" * 60)
    print(f"Cases evaluated: {len(case_files)} | Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 60)

    if failed_count > 0:
        print("\nSummary of failures:")
        for fail in failures:
            print(f"  - {fail}")
        sys.exit(1)

    print("\nAll Anti-Slop evaluation cases passed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
