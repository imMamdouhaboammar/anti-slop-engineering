#!/usr/bin/env python3
"""Validate the unified audit report and publish composite-action outputs."""

import argparse
import json
import sys
from pathlib import Path

from audit_runner import guard_commands


def evaluate_report(report, audit_exit, canary_present=False):
    if not isinstance(report, dict):
        raise ValueError("Audit report must be a JSON object")
    if report.get("status") not in {"PASS", "BLOCKED", "ERROR"}:
        raise ValueError("Audit report has an unknown status")
    if audit_exit != {"PASS": 0, "BLOCKED": 1, "ERROR": 2}[report["status"]]:
        raise ValueError("Audit process exit does not match its JSON status")

    expected = dict(guard_commands("HEAD", canary_token="present" if canary_present else ""))
    guards = report.get("guards")
    if not isinstance(guards, dict) or set(guards) != set(expected):
        raise ValueError("Audit report is missing mandatory guard results")
    for name, command in expected.items():
        result = guards[name]
        if not isinstance(result, dict):
            raise ValueError(f"Invalid result for {name}")
        status = result.get("status")
        if command is None:
            if (status != "SKIPPED" or result.get("applicable") is not False
                    or result.get("exit_code") is not None):
                raise ValueError(f"Optional guard {name} has an invalid skip record")
        elif status not in {"PASS", "FINDINGS", "ERROR"} or result.get("applicable") is not True:
            raise ValueError(f"Mandatory guard {name} is incomplete")
        if command is not None and status in {"PASS", "FINDINGS"}:
            if (type(result.get("exit_code")) is not int
                    or result["exit_code"] not in {0, 1, 2}
                    or (status == "PASS" and result["exit_code"] != 0)
                    or result.get("error") or result.get("timed_out")):
                raise ValueError(f"Guard {name} did not finish successfully")

    findings = report.get("findings")
    total = report.get("total_findings")
    blockers = report.get("blockers_count")
    if not isinstance(findings, list) or any(
        not isinstance(finding, dict) or finding.get("severity") not in {"BLOCKER", "HIGH", "MEDIUM", "LOW"}
        for finding in findings
    ):
        raise ValueError("Audit findings have an invalid schema")
    if type(total) is not int or type(blockers) is not int or total < 0 or blockers < 0:
        raise ValueError("Audit counts must be nonnegative integers")
    if total != len(findings) or blockers != sum(f["severity"] == "BLOCKER" for f in findings):
        raise ValueError("Audit counts disagree with the findings list")
    if any(finding.get("guard") not in expected for finding in findings):
        raise ValueError("Audit finding came from an unknown guard")
    for name, result in guards.items():
        count = sum(finding["guard"] == name for finding in findings)
        if type(result.get("findings_count")) is not int or result["findings_count"] != count:
            raise ValueError(f"Guard {name} finding count does not match the report")
        if (result["status"] == "PASS" and count) or (result["status"] == "FINDINGS" and not count):
            raise ValueError(f"Guard {name} status disagrees with its findings")
    if (report["status"] == "PASS" and (blockers or any(
        item["status"] == "ERROR" for item in guards.values()
    ))) or (report["status"] == "BLOCKED" and not blockers):
        raise ValueError("Audit status contradicts its findings or execution results")
    if report["status"] != "ERROR" and any(item["status"] == "ERROR" for item in guards.values()):
        raise ValueError("Audit execution errors cannot be ignored")

    return ("PASSED" if report["status"] == "PASS" else report["status"], total, blockers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit-exit", type=int, required=True)
    parser.add_argument("--fail-on-blocker", choices=("true", "false"), required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--canary-present", action="store_true")
    args = parser.parse_args()

    report = None
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        status, findings, blockers = evaluate_report(report, args.audit_exit, args.canary_present)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Anti-Slop audit result invalid: {exc}", file=sys.stderr)
        status, findings, blockers = "ERROR", 0, 0

    if status == "ERROR" and isinstance(report, dict):
        guards = report.get("guards")
        if isinstance(guards, dict):
            for name, outcome in guards.items():
                if isinstance(outcome, dict) and outcome.get("status") == "ERROR":
                    print(f"{name}: {outcome.get('error') or 'guard execution failed'}", file=sys.stderr)

    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f"status={status}\nfindings-count={findings}\nblockers-count={blockers}\n")
    if status == "ERROR":
        return 2
    return 2 if status == "BLOCKED" and args.fail_on_blocker == "true" else 0


if __name__ == "__main__":
    sys.exit(main())
