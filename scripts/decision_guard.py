#!/usr/bin/env python3
"""Check decision-record completeness; never certify the truth of its evidence."""

import argparse
import json
import sys
from pathlib import Path


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def audit(packet):
    findings = []

    def require(condition, code, message):
        if not condition:
            findings.append({"code": code, "message": message})

    kind = packet.get("kind")
    require(kind in {"investigation", "architecture"}, "INVALID_KIND", "kind must be investigation or architecture")
    for key in ("goal", "proposal"):
        require(filled(packet.get(key)), "MISSING_" + key.upper(), key + " must be nonempty")

    evidence = packet.get("evidence")
    require(isinstance(evidence, list) and len(evidence) > 0, "MISSING_EVIDENCE", "List at least one traceable source and finding")
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            valid = (isinstance(item, dict) and filled(item.get("source"))
                     and filled(item.get("finding"))
                     and item.get("level") in {"observed", "derived", "inferred"})
            require(valid, "INVALID_EVIDENCE", "evidence[%d] requires source, finding and valid level" % index)

    direct = packet.get("direct_check")
    valid_direct = (isinstance(direct, dict)
                    and direct.get("status") in {"found", "not_found", "unknown", "not_applicable"}
                    and filled(direct.get("source")) and filled(direct.get("finding")))
    require(valid_direct, "MISSING_DIRECT_CHECK", "Record direct-answer/source search, including unknown or unavailable evidence")
    if valid_direct and kind == "investigation":
        require(direct["status"] != "not_applicable", "DIRECT_CHECK_SKIPPED", "Investigations must inspect or explicitly mark the direct source unknown")

    assumptions = packet.get("assumptions", [])
    require(isinstance(assumptions, list), "INVALID_ASSUMPTIONS", "assumptions must be a list")
    if isinstance(assumptions, list):
        for index, item in enumerate(assumptions):
            valid = (isinstance(item, dict) and filled(item.get("claim"))
                     and item.get("state") in {"verified", "unverified"}
                     and filled(item.get("basis")))
            require(valid, "INVALID_ASSUMPTION", "assumptions[%d] must distinguish verified from unverified" % index)

    decision = packet.get("decision")
    valid_decision = isinstance(decision, dict) and decision.get("action") in {"proceed", "pause", "stop"}
    require(valid_decision, "MISSING_DECISION", "decision.action must be proceed, pause or stop")
    if isinstance(decision, dict):
        for key in ("choice", "reason", "invalidated_by"):
            require(filled(decision.get(key)), "MISSING_DECISION_FIELD", "decision.%s is required" % key)

    if kind == "architecture":
        axes = packet.get("decision_axes")
        require(isinstance(axes, list) and len(axes) > 0, "MISSING_DECISION_AXES", "Compare independent decision axes instead of assuming a bundled stack")
        if isinstance(axes, list):
            for index, axis in enumerate(axes):
                considered = axis.get("considered") if isinstance(axis, dict) else None
                selected = axis.get("selected") if isinstance(axis, dict) else None
                valid = (isinstance(axis, dict) and filled(axis.get("name"))
                         and isinstance(considered, list) and len(set(map(str, considered))) >= 2
                         and all(filled(value) for value in considered)
                         and filled(selected) and selected in considered)
                require(valid, "INVALID_DECISION_AXIS", "decision_axes[%d] must compare >=2 distinct candidates and select one" % index)

        alternatives = packet.get("alternatives")
        require(isinstance(alternatives, list) and len(alternatives) >= 2, "MISSING_ALTERNATIVES", "Compare at least two serious architectural alternatives")
        if isinstance(alternatives, list):
            for index, item in enumerate(alternatives):
                valid = isinstance(item, dict) and all(filled(item.get(key)) for key in ("name", "benefit", "risk", "reversal"))
                require(valid, "INVALID_ALTERNATIVE", "alternatives[%d] needs benefit, risk and reversal path" % index)

        horizons = packet.get("horizons")
        valid_horizons = isinstance(horizons, list) and all(
            isinstance(item, dict) and item.get("stage") in {"now", "later"}
            and filled(item.get("scenario")) and filled(item.get("consequence"))
            for item in horizons
        )
        require(valid_horizons, "INVALID_HORIZONS", "horizons requires stage (now/later), scenario and consequence")
        if isinstance(horizons, list):
            require(any(isinstance(item, dict) and item.get("stage") == "later" for item in horizons),
                    "MISSING_FUTURE_SCENARIO", "Test at least one credible future growth, failure or migration scenario")
            require(any(isinstance(item, dict) and item.get("stage") == "now" for item in horizons),
                    "MISSING_CURRENT_SCENARIO", "Evaluate the near-term operational reality")

    if valid_direct and valid_decision and decision["action"] == "proceed":
        grounded = isinstance(evidence, list) and any(
            isinstance(item, dict) and item.get("level") in {"observed", "derived"}
            for item in evidence
        )
        require(grounded, "NO_GROUNDED_EVIDENCE", "Proceed requires at least one observed or derived source; inference alone is insufficient")
        if direct["status"] == "unknown":
            require(False, "DIRECT_PATH_UNRESOLVED", "Investigate direct path or pause before committing")
        if direct["status"] == "found":
            handling = decision.get("direct_path_handling")
            require(handling in {"use", "bypass"}, "DIRECT_PATH_OVERRIDE_REQUIRED", "Explicitly use the direct path or justify bypassing it")
            if handling == "bypass":
                require(filled(decision.get("direct_override_reason")), "DIRECT_PATH_OVERRIDE_REQUIRED", "Explain why an indirect approach beats the observed direct answer")

    return {
        "record_status": "complete" if not findings else "incomplete",
        "decision_action": decision.get("action") if isinstance(decision, dict) else None,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        packet = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid JSON or unreadable decision record: %s" % error, file=sys.stderr)
        return 1
    if not isinstance(packet, dict):
        print("Invalid JSON: decision record must be an object", file=sys.stderr)
        return 1
    result = audit(packet)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Decision record: %s (%s)" % (result["record_status"], result["decision_action"]))
        for finding in result["findings"]:
            print("  %s: %s" % (finding["code"], finding["message"]))
        print("Structural check only; sources and reasoning require independent verification.")
    return 2 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
