#!/usr/bin/env python3
"""Audit root-cause ownership records and optionally inspect a Git change surface."""

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def choice(value, allowed):
    return isinstance(value, str) and value in allowed


def valid_path(value):
    return (filled(value) and not value.startswith("/") and "\\" not in value
            and ".." not in PurePosixPath(value).parts and str(PurePosixPath(value)) == value
            and value != ".")


def check_options(record, proceeding, require):
    options = record.get("options")
    require(isinstance(options, list), "INVALID_OPTIONS", "options must be a list")
    if not isinstance(options, list):
        return
    names = []
    selected_count = 0
    for index, item in enumerate(options):
        valid = (isinstance(item, dict) and filled(item.get("approach"))
                 and filled(item.get("tradeoff")) and type(item.get("selected")) is bool)
        require(valid, "INVALID_OPTION", "options[%d] requires approach, tradeoff and boolean selected" % index)
        if valid:
            names.append(item["approach"].strip().casefold())
            selected_count += item["selected"] is True
    require(len(names) == len(set(names)), "DUPLICATE_OPTIONS", "Options must be genuinely distinct")
    if proceeding:
        require(len(options) >= 2 or (len(options) == 1 and filled(record.get("sole_option_reason"))),
                "MISSING_COMPARISON", "Compare different causal fixes or justify one viable approach")
        require(selected_count == 1, "INVALID_SELECTION", "Select exactly one proposed approach")


def check_surface(record, proceeding, require):
    plan = record.get("planned_changes")
    require(isinstance(plan, list), "INVALID_CHANGE_PLAN", "planned_changes must be a list")
    if not isinstance(plan, list):
        return {}
    paths = {}
    has_owner = False
    valid_count = 0
    for index, item in enumerate(plan):
        valid = (isinstance(item, dict) and valid_path(item.get("path"))
                 and choice(item.get("role"), {"owner", "consumer", "test", "migration", "integration"})
                 and filled(item.get("reason")))
        require(valid, "INVALID_PLANNED_CHANGE", "planned_changes[%d] needs safe path, role and reason" % index)
        if valid:
            paths[item["path"]] = item["role"]
            has_owner |= item["role"] == "owner"
            valid_count += 1
    require(len(paths) == valid_count,
            "DUPLICATE_PLANNED_PATH", "Each planned path should be declared once")
    if proceeding:
        require(has_owner, "NO_OWNER_CHANGE", "Proceed must identify a change at the responsible boundary")
    return paths


def check_safety(record, proceeding, require):
    invariants = record.get("invariants")
    require(isinstance(invariants, list), "INVALID_INVARIANTS", "invariants must be a list")
    if isinstance(invariants, list):
        for index, item in enumerate(invariants):
            require(isinstance(item, dict) and filled(item.get("rule")) and filled(item.get("proof")),
                    "INVALID_INVARIANT", "invariants[%d] needs rule and independent verification" % index)
    if proceeding:
        require(isinstance(invariants, list) and len(invariants) > 0, "MISSING_PROOF", "Name an invariant and its proof")

    impact = record.get("data_impact")
    valid_impact = isinstance(impact, dict) and choice(impact.get("mode"), {"none", "additive", "destructive"})
    require(valid_impact, "INVALID_DATA_IMPACT", "Set data_impact.mode to none, additive or destructive")
    if valid_impact and impact["mode"] == "destructive" and proceeding:
        require(filled(impact.get("approval_ref")) and filled(impact.get("recovery")),
                "DESTRUCTIVE_CHANGE_UNAUTHORIZED", "Record explicit user authority and tested recovery evidence")
        require(False, "MANUAL_AUTHORITY_CHECK", "Review approval and restore evidence independently", "review")


def audit(record):
    findings = []

    def require(ok, code, message, severity="block"):
        if not ok:
            findings.append({"code": code, "severity": severity, "message": message})

    for field in ("problem", "symptom"):
        require(filled(record.get(field)), "MISSING_" + field.upper(), field + " must be nonempty")
    decision = record.get("decision")
    action = decision.get("action") if isinstance(decision, dict) else None
    require(choice(action, {"proceed", "pause", "stop"}), "INVALID_DECISION", "Choose proceed, pause or stop")
    if isinstance(decision, dict):
        for field in ("reason", "invalidated_by"):
            require(filled(decision.get(field)), "MISSING_DECISION_FIELD", "decision.%s is required" % field)
    proceeding = action == "proceed"
    cause = record.get("root_cause")
    require(isinstance(cause, dict) and filled(cause.get("cause")) and filled(cause.get("owner")),
            "MISSING_ROOT_CAUSE", "Identify a causal hypothesis and responsible owner, or explicitly mark unknown")
    evidence = cause.get("evidence") if isinstance(cause, dict) else None
    require(isinstance(evidence, list), "INVALID_OWNER_EVIDENCE", "root_cause.evidence must be a list")
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            require(isinstance(item, dict) and filled(item.get("source")) and filled(item.get("finding"))
                    and choice(item.get("level"), {"observed", "derived", "inferred"}),
                    "INVALID_OWNER_EVIDENCE", "root_cause.evidence[%d] needs source, finding and level" % index)
    if proceeding:
        grounded = isinstance(evidence, list) and any(
            isinstance(item, dict) and filled(item.get("source")) and filled(item.get("finding"))
            and choice(item.get("level"), {"observed", "derived"}) for item in evidence
        )
        require(grounded, "OWNER_UNGROUNDED", "Do not proceed on inferred-only ownership claims")
    check_options(record, proceeding, require)
    planned = check_surface(record, proceeding, require)
    check_safety(record, proceeding, require)
    return {
        "record_status": "incomplete" if any(item["severity"] == "block" for item in findings) else "complete",
        "decision_action": action if choice(action, {"proceed", "pause", "stop"}) else None,
        "machine_check_only": True,
        "diff_status": "not_run",
        "changed_files": None,
        "findings": findings,
    }, planned


def inspect_git_diff(repo, base):
    if base.startswith("-"):
        raise ValueError("Git base must be a revision, not a flag")
    changed = []
    for git_args in (["diff", "--no-renames", "--name-only", "-z", base, "--"],
                     ["ls-files", "--others", "--exclude-standard", "-z", "--"]):
        result = subprocess.run(["git", "-C", str(repo), *git_args], capture_output=True, check=False)
        if result.returncode != 0:
            raise ValueError("Git inspection failed: " + result.stderr.decode("utf-8", "replace").strip())
        changed.extend(path.decode("utf-8", "replace") for path in result.stdout.split(b"\0") if path)
    return set(changed)


def attach_git_diff(result, planned, changed):
    result["diff_status"] = "checked"
    result["changed_files"] = len(changed)
    unexpected = sorted(changed - set(planned))
    if unexpected:
        sample = ", ".join(unexpected[:8])
        result["findings"].append({"code": "UNPLANNED_CHANGE", "severity": "review",
                                   "message": "%d paths absent from the plan: %s" % (len(unexpected), sample)})
    owner_paths = sorted(path for path, role in planned.items() if role == "owner")
    if result["decision_action"] == "proceed" and owner_paths and not changed.intersection(owner_paths):
        result["findings"].append({"code": "OWNER_CHANGE_NOT_OBSERVED", "severity": "review",
                                   "message": "No planned owner path changed: %s" % ", ".join(owner_paths[:8])})
    if len(changed) > 8:
        result["findings"].append({"code": "WIDE_CHANGE_SURFACE", "severity": "review",
                                   "message": "%d changed paths require a causal ownership review, not an automatic rejection" % len(changed)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("decision record must be a JSON object")
        result, planned = audit(record)
        if args.base:
            attach_git_diff(result, planned, inspect_git_diff(args.repo, args.base))
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid input or Git inspection: %s" % error, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Root-Fix record: %s (%s)" % (result["record_status"], result["decision_action"]))
        for finding in result["findings"]:
            print("  [%s] %s: %s" % (finding["severity"], finding["code"], finding["message"]))
        print("Structural and change-surface review only; ownership and authority need independent proof.")
    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
