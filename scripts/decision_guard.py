#!/usr/bin/env python3
"""Check decision-record completeness; never certify the truth of its evidence."""

import argparse
import json
import sys
from pathlib import Path


def filled(value):
    """Check whether value is a non-empty string after stripping whitespace."""
    return isinstance(value, str) and bool(value.strip())


def one_of(value, allowed):
    """Check whether value is a string belonging to the allowed collection."""
    return isinstance(value, str) and value in allowed


def _audit_architecture(packet, require):
    """Validate architecture-specific decision axes, alternatives, and horizon stress scenarios."""
    axes = packet.get("decision_axes")
    require(isinstance(axes, list) and len(axes) > 0, "MISSING_DECISION_AXES", "Compare independent decision axes instead of assuming a bundled stack")
    if isinstance(axes, list):
        for index, axis in enumerate(axes):
            if not isinstance(axis, dict):
                require(False, "INVALID_DECISION_AXIS", f"decision_axes[{index}] must be an object")
                continue
            name = axis.get("name")
            considered = axis.get("considered")
            selected = axis.get("selected")
            eliminated = axis.get("eliminated") if isinstance(axis.get("eliminated"), list) else []
            eliminated_set = set(map(str, eliminated))
            active_considered = [c for c in considered if str(c) not in eliminated_set] if isinstance(considered, list) else []
            constraint_rationale = axis.get("constraint_rationale")
            single_candidate = axis.get("single_candidate") is True or bool(constraint_rationale)

            if single_candidate:
                valid = (filled(name) and isinstance(considered, list)
                         and len(active_considered) >= 1
                         and all(filled(v) for v in active_considered)
                         and filled(selected) and selected in active_considered
                         and filled(constraint_rationale))
            else:
                valid = (filled(name) and isinstance(considered, list)
                         and len(set(map(str, active_considered))) >= 2
                         and all(filled(v) for v in active_considered)
                         and filled(selected) and selected in active_considered)
            require(valid, "INVALID_DECISION_AXIS", f"decision_axes[{index}] must compare >=2 distinct candidates or provide constraint_rationale for single candidate")

    alternatives = packet.get("alternatives")
    has_alts_list = isinstance(alternatives, list)
    alt_names = [item.get("name").strip() for item in alternatives if isinstance(item, dict) and filled(item.get("name"))] if has_alts_list else []
    distinct_alt_names = set(alt_names)
    is_single_alt = packet.get("single_candidate") is True or filled(packet.get("constraint_rationale"))
    min_alts = 1 if is_single_alt else 2

    require(
        has_alts_list and len(alternatives) >= min_alts and len(distinct_alt_names) >= min_alts and len(alt_names) == len(alternatives),
        "MISSING_ALTERNATIVES",
        "Compare at least two distinct architectural alternatives" if not is_single_alt else "Record at least one architectural alternative with constraint rationale"
    )
    if is_single_alt:
        require(filled(packet.get("constraint_rationale")), "MISSING_CONSTRAINT_RATIONALE", "Single candidate requires constraint_rationale explaining eliminated alternatives")
    if has_alts_list:
        for index, item in enumerate(alternatives):
            valid = isinstance(item, dict) and all(filled(item.get(key)) for key in ("name", "benefit", "risk", "reversal"))
            require(valid, "INVALID_ALTERNATIVE", f"alternatives[{index}] needs benefit, risk and reversal path")

    horizons = packet.get("horizons")
    valid_horizons = isinstance(horizons, list) and all(
        isinstance(item, dict) and one_of(item.get("stage"), {"now", "later"})
        and filled(item.get("scenario")) and filled(item.get("consequence"))
        for item in horizons
    )
    require(valid_horizons, "INVALID_HORIZONS", "horizons requires stage (now/later), scenario and consequence")
    if isinstance(horizons, list):
        require(any(isinstance(item, dict) and item.get("stage") == "later" for item in horizons),
                "MISSING_FUTURE_SCENARIO", "Test at least one credible future growth, failure or migration scenario")
        require(any(isinstance(item, dict) and item.get("stage") == "now" for item in horizons),
                "MISSING_CURRENT_SCENARIO", "Evaluate the near-term operational reality")


def _audit_proceed(packet, direct, valid_direct, decision, valid_decision, evidence, require):
    """Validate conditions required when a decision concludes with a proceed action."""
    if not (valid_direct and valid_decision and decision.get("action") == "proceed"):
        return
    grounded = isinstance(evidence, list) and any(
        isinstance(item, dict) and one_of(item.get("level"), {"observed", "derived"})
        for item in evidence
    )
    require(grounded, "NO_GROUNDED_EVIDENCE", "Proceed requires at least one observed or derived source; inference alone is insufficient")
    if direct.get("status") == "unknown":
        require(False, "DIRECT_PATH_UNRESOLVED", "Investigate direct path or pause before committing")
    if direct.get("status") == "found":
        handling = decision.get("direct_path_handling")
        require(one_of(handling, {"use", "bypass"}), "DIRECT_PATH_OVERRIDE_REQUIRED", "Explicitly use the direct path or justify bypassing it")
        if handling == "bypass":
            require(filled(decision.get("direct_override_reason")), "DIRECT_PATH_OVERRIDE_REQUIRED", "Explain why an indirect approach beats the observed direct answer")


def audit(packet):
    """Audit a decision packet against structural completeness requirements."""
    findings = []

    def require(condition, code, message):
        if not condition:
            findings.append({"code": code, "message": message})

    kind = packet.get("kind")
    require(one_of(kind, {"investigation", "architecture"}), "INVALID_KIND", "kind must be investigation or architecture")
    for key in ("goal", "proposal"):
        require(filled(packet.get(key)), "MISSING_" + key.upper(), key + " must be nonempty")

    evidence = packet.get("evidence")
    require(isinstance(evidence, list) and len(evidence) > 0, "MISSING_EVIDENCE", "List at least one traceable source and finding")
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            valid = (isinstance(item, dict) and filled(item.get("source"))
                     and filled(item.get("finding"))
                     and one_of(item.get("level"), {"observed", "derived", "inferred"}))
            require(valid, "INVALID_EVIDENCE", f"evidence[{index}] requires source, finding and valid level")

    direct = packet.get("direct_check")
    valid_direct = (isinstance(direct, dict)
                    and one_of(direct.get("status"), {"found", "not_found", "unknown", "not_applicable"})
                    and filled(direct.get("source")) and filled(direct.get("finding")))
    require(valid_direct, "MISSING_DIRECT_CHECK", "Record direct-answer/source search, including unknown or unavailable evidence")
    if valid_direct and kind == "investigation":
        require(direct["status"] != "not_applicable", "DIRECT_CHECK_SKIPPED", "Investigations must inspect or explicitly mark the direct source unknown")

    assumptions = packet.get("assumptions", [])
    require(isinstance(assumptions, list), "INVALID_ASSUMPTIONS", "assumptions must be a list")
    if isinstance(assumptions, list):
        for index, item in enumerate(assumptions):
            valid = (isinstance(item, dict) and filled(item.get("claim"))
                     and one_of(item.get("state"), {"verified", "unverified"})
                     and filled(item.get("basis")))
            require(valid, "INVALID_ASSUMPTION", f"assumptions[{index}] must distinguish verified from unverified")

    decision = packet.get("decision")
    valid_decision = isinstance(decision, dict) and one_of(decision.get("action"), {"proceed", "pause", "stop"})
    require(valid_decision, "MISSING_DECISION", "decision.action must be proceed, pause or stop")
    if isinstance(decision, dict):
        for key in ("choice", "reason", "invalidated_by"):
            require(filled(decision.get(key)), "MISSING_DECISION_FIELD", f"decision.{key} is required")

    if kind == "architecture":
        _audit_architecture(packet, require)

    _audit_proceed(packet, direct, valid_direct, decision, valid_decision, evidence, require)

    return {
        "record_status": "complete" if not findings else "incomplete",
        "decision_action": decision.get("action") if isinstance(decision, dict) and isinstance(decision.get("action"), str) else None,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    """Parse command-line arguments and run the decision-record audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        packet = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Invalid JSON or unreadable decision record: {error}", file=sys.stderr)
        return 1
    if not isinstance(packet, dict):
        print("Invalid JSON: decision record must be an object", file=sys.stderr)
        return 1
    result = audit(packet)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Decision record: {result['record_status']} ({result['decision_action']})")
        for finding in result["findings"]:
            print(f"  {finding['code']}: {finding['message']}")
        print("Structural check only; sources and reasoning require independent verification.")
    return 2 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
