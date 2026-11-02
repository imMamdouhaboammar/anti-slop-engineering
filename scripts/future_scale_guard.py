#!/usr/bin/env python3
"""Check future-scale architectural decision records for structural completeness."""

import argparse
import json
import sys
from pathlib import Path


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def choice(value, values):
    return isinstance(value, str) and value in values


def check_scenarios(record, proceeding, require):
    scenarios = record.get("scenarios")
    require(isinstance(scenarios, list), "INVALID_SCENARIOS", "scenarios must be a list")
    if not isinstance(scenarios, list):
        return {}
    ids = {}
    for index, item in enumerate(scenarios):
        valid = (isinstance(item, dict) and filled(item.get("id"))
                 and filled(item.get("stress")) and filled(item.get("failure_if_unprepared"))
                 and choice(item.get("basis"), {"observed", "credible", "speculative"})
                 and filled(item.get("source")))
        require(valid, "INVALID_SCENARIO", "scenarios[%d] needs id, stress, basis, source and failure" % index)
        if valid:
            key = item["id"].strip().casefold()
            require(key not in ids, "DUPLICATE_SCENARIO", "Scenario ids must be distinct")
            ids[key] = item["basis"]
    if proceeding:
        require(bool(ids), "MISSING_FUTURE_ENVELOPE", "Name at least one source-backed future stress")
        require(any(basis in {"observed", "credible"} for basis in ids.values()),
                "SPECULATION_ONLY", "Do not harden foundations for speculative-only futures")
    return ids


def check_commitments(record, proceeding, require):
    commitments = record.get("commitments")
    require(isinstance(commitments, list), "INVALID_COMMITMENTS", "commitments must be a list")
    if not isinstance(commitments, list):
        return
    if proceeding:
        require(bool(commitments), "MISSING_COMMITMENTS", "Name costly-to-reverse decisions or explicit assumptions")
    for index, item in enumerate(commitments):
        valid = (isinstance(item, dict) and filled(item.get("decision"))
                 and filled(item.get("failure_cost"))
                 and choice(item.get("reversibility"), {"low", "medium", "high"}))
        require(valid, "INVALID_COMMITMENT", "commitments[%d] needs decision, failure_cost and reversibility" % index)
        if valid and item["reversibility"] in {"medium", "high"} and proceeding:
            require(filled(item.get("exit_path")), "MISSING_EXIT_PATH",
                    "Costly-to-reverse commitment needs a migration or recovery path")


def check_options(record, proceeding, require):
    options = record.get("options")
    require(isinstance(options, list), "INVALID_OPTIONS", "options must be a list")
    if not isinstance(options, list):
        return
    names = []
    chosen = 0
    for index, item in enumerate(options):
        valid = (isinstance(item, dict) and filled(item.get("name"))
                 and filled(item.get("now_cost")) and filled(item.get("future_cost"))
                 and type(item.get("selected")) is bool)
        require(valid, "INVALID_OPTION", "options[%d] needs name, both lifecycle costs and selected" % index)
        if valid:
            names.append(item["name"].strip().casefold())
            chosen += item["selected"]
    require(len(names) == len(set(names)), "DUPLICATE_OPTIONS", "Architecture options must be distinct")
    if proceeding:
        require(len(names) >= 2 or (len(names) == 1 and filled(record.get("sole_option_reason"))),
                "MISSING_ALTERNATIVES", "Compare designs or justify a single viable option")
        require(chosen == 1, "INVALID_SELECTION", "Select exactly one design")


def check_proofs(record, require):
    proofs = record.get("proofs")
    require(isinstance(proofs, list), "INVALID_PROOFS", "proofs must be a list")
    if not isinstance(proofs, list):
        return {}
    ids = {}
    for index, item in enumerate(proofs):
        valid = (isinstance(item, dict) and filled(item.get("id")) and filled(item.get("method"))
                 and choice(item.get("status"), {"passed", "failed", "not_run"})
                 and filled(item.get("evidence")))
        require(valid, "INVALID_PROOF", "proofs[%d] needs id, method, status and evidence" % index)
        if valid:
            key = item["id"].strip().casefold()
            require(key not in ids, "DUPLICATE_PROOF", "Proof ids must be distinct")
            ids[key] = item["status"]
    return ids


def check_foundations(record, proceeding, scenarios, proofs, require):
    foundations = record.get("foundations")
    require(isinstance(foundations, list), "INVALID_FOUNDATIONS", "foundations must be a list")
    if not isinstance(foundations, list):
        return
    if proceeding:
        require(bool(foundations), "MISSING_FOUNDATION", "Name the minimal boundary to establish now")
    for index, item in enumerate(foundations):
        valid = (isinstance(item, dict) and filled(item.get("boundary"))
                 and filled(item.get("choice_now")) and filled(item.get("future_capacity"))
                 and filled(item.get("proof_ref")) and isinstance(item.get("scenario_refs"), list)
                 and bool(item["scenario_refs"]))
        require(valid, "INVALID_FOUNDATION", "foundations[%d] needs boundary, choice, capacity and references" % index)
        if not valid:
            continue
        refs = item["scenario_refs"]
        known = [scenarios.get(ref.strip().casefold()) for ref in refs if filled(ref)]
        require(len(known) == len(refs) and all(known), "UNKNOWN_SCENARIO_REF",
                "Foundation must reference existing scenarios")
        if proceeding:
            require(any(value in {"observed", "credible"} for value in known),
                    "SPECULATIVE_FOUNDATION", "Foundation needs a credible non-speculative scenario")
        proof_id = item["proof_ref"].strip().casefold()
        require(proof_id in proofs, "UNKNOWN_PROOF_REF", "Foundation must reference a declared proof")
        if proceeding:
            require(proofs.get(proof_id) == "passed", "UNPROVEN_EVOLUTION_PATH",
                    "Do not commit to a foundation whose evolution test failed or was not run")


def check_deferred(record, require):
    deferred = record.get("deferred")
    require(isinstance(deferred, list), "INVALID_DEFERRED", "deferred must be a list")
    if not isinstance(deferred, list):
        return
    for index, item in enumerate(deferred):
        valid = (isinstance(item, dict) and filled(item.get("capability"))
                 and filled(item.get("trigger")) and filled(item.get("pathway")))
        require(valid, "INVALID_DEFERRAL", "deferred[%d] needs capability, trigger and pathway" % index)


def audit(record):
    findings = []

    def require(ok, code, message):
        if not ok:
            findings.append({"severity": "block", "code": code, "message": message})

    require(filled(record.get("goal")), "MISSING_GOAL", "Name the long-lived product goal")
    decision = record.get("decision")
    action = decision.get("action") if isinstance(decision, dict) else None
    require(choice(action, {"proceed", "pause", "stop"}), "INVALID_DECISION", "Choose proceed, pause or stop")
    if isinstance(decision, dict):
        require(filled(decision.get("reason")) and filled(decision.get("revisit_when")),
                "MISSING_DECISION_RATIONALE", "Record reason and revisit trigger")
    proceeding = action == "proceed"
    if proceeding:
        require(filled(record.get("horizon")), "MISSING_HORIZON", "State the lifetime, not only today's workload")
        scenarios = check_scenarios(record, True, require)
        check_commitments(record, True, require)
        check_options(record, True, require)
        proofs = check_proofs(record, require)
        check_foundations(record, True, scenarios, proofs, require)
        check_deferred(record, require)
    return {"record_status": "incomplete" if findings else "complete",
            "decision_action": action if choice(action, {"proceed", "pause", "stop"}) else None,
            "machine_check_only": True, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("record must be a JSON object")
        result = audit(record)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid future-scale record: %s" % error, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Future-Scale record: %s (%s)" % (result["record_status"], result["decision_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: evidence and architecture must be checked independently.")
    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
