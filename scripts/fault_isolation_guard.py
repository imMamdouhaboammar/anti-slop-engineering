#!/usr/bin/env python3
"""Check scientific fault isolation records and source/test files for 3-hypothesis differential diagnosis, binary search isolation, determinism pinning, and shotgun-debugging hazards."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_FREQUENCIES = {
    "intermittent_flaky",
    "deterministic_regression",
    "load_dependent_race",
    "environment_specific",
}
VALID_HYPOTHESIS_STATUSES = {"confirmed", "falsified", "pending"}
VALID_PROBE_TYPES = {
    "minimal_reproducer",
    "structured_boundary_log",
    "state_invariant_assertion",
    "git_bisect_script",
    "packet_or_query_capture",
}
VALID_BISECT_METHODS = {
    "git_bisect",
    "layer_boundary_halving",
    "delta_debugging_input",
    "call_graph_midpoint",
}
VALID_DETERMINISM_CONTROLS = {
    "pinned_prng_seed",
    "frozen_monotonic_clock",
    "concurrency_barrier_latch",
    "deterministic_task_scheduler",
    "hermetic_fixture_isolation",
    "fixed_chunk_boundary",
}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return isinstance(value, str) and value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_symptom(record, require):
    symptom = record.get("symptom")
    require(isinstance(symptom, dict), "INVALID_SYMPTOM", "symptom must be a dictionary")
    if not isinstance(symptom, dict):
        return
    require(filled(symptom.get("observable_failure"), 15),
            "MISSING_OBSERVABLE_FAILURE",
            "symptom.observable_failure must be at least 15 characters")
    require(choice(symptom.get("reproduction_frequency_before"), VALID_FREQUENCIES),
            "INVALID_REPRODUCTION_FREQUENCY",
            "symptom.reproduction_frequency_before must be one of: %s"
            % ", ".join(sorted(VALID_FREQUENCIES)))
    require(filled(symptom.get("affected_boundary"), 5),
            "MISSING_AFFECTED_BOUNDARY",
            "symptom.affected_boundary must identify the failing boundary")


def check_differential_diagnosis(record, require):
    diag = record.get("differential_diagnosis")
    require(isinstance(diag, dict), "INVALID_DIFFERENTIAL_DIAGNOSIS",
            "differential_diagnosis must be a dictionary")
    if not isinstance(diag, dict):
        return set(), set()

    require(diag.get("zero_production_edits_before_probe") is True,
            "SHOTGUN_PRODUCTION_EDIT_BEFORE_PROBE",
            "differential_diagnosis.zero_production_edits_before_probe must be true")

    hypotheses = diag.get("hypotheses")
    require(isinstance(hypotheses, list) and len(hypotheses) >= 3,
            "INSUFFICIENT_HYPOTHESES",
            "differential_diagnosis.hypotheses must contain at least 3 falsifiable hypotheses")
    if not isinstance(hypotheses, list):
        return set(), set()

    confirmed_ids = set()
    falsified_ids = set()
    for idx, item in enumerate(hypotheses):
        if not isinstance(item, dict):
            require(False, "INVALID_HYPOTHESIS_ITEM",
                    "Hypothesis at index %d must be an object" % idx)
            continue
        hid = item.get("id")
        status = item.get("status")
        ok = (
            filled(hid, 2)
            and filled(item.get("mechanism"), 15)
            and filled(item.get("prediction"), 10)
            and filled(item.get("falsified_if"), 10)
            and choice(status, VALID_HYPOTHESIS_STATUSES)
            and filled(item.get("evidence"), 10)
        )
        require(ok, "INCOMPLETE_HYPOTHESIS",
                "Each hypothesis needs id, mechanism (>=15 chars), prediction, falsified_if, valid status, and evidence")
        if filled(hid, 2):
            if status == "confirmed":
                confirmed_ids.add(hid)
            elif status == "falsified":
                falsified_ids.add(hid)

    require(len(falsified_ids) >= 2,
            "FEWER_THAN_TWO_FALSIFIED_HYPOTHESES",
            "At least 2 hypotheses must be falsified by empirical evidence before editing production code")
    require(len(confirmed_ids) == 1,
            "MISSING_SINGLE_CONFIRMED_HYPOTHESIS",
            "Exactly 1 surviving hypothesis must be confirmed before proceeding to a production fix")
    return confirmed_ids, falsified_ids


def check_discriminating_probe(record, confirmed_ids, falsified_ids, require):
    probe = record.get("discriminating_probe")
    require(isinstance(probe, dict), "INVALID_DISCRIMINATING_PROBE",
            "discriminating_probe must be a dictionary")
    if not isinstance(probe, dict):
        return

    require(choice(probe.get("probe_type"), VALID_PROBE_TYPES),
            "INVALID_PROBE_TYPE",
            "discriminating_probe.probe_type must be one of: %s"
            % ", ".join(sorted(VALID_PROBE_TYPES)))
    require(filled(probe.get("design"), 15),
            "MISSING_PROBE_DESIGN",
            "discriminating_probe.design must be at least 15 characters")
    require(filled(probe.get("observed_outcome"), 15),
            "MISSING_PROBE_OUTCOME",
            "discriminating_probe.observed_outcome must be at least 15 characters")

    killed = probe.get("killed_hypothesis_ids")
    require(isinstance(killed, list) and len(killed) >= 2
            and all(isinstance(k, str) and k in falsified_ids for k in killed),
            "PROBE_KILLED_IDS_MISMATCH",
            "discriminating_probe.killed_hypothesis_ids must list at least 2 falsified hypothesis IDs")

    confirmed = probe.get("confirmed_hypothesis_id")
    require(isinstance(confirmed, str) and confirmed in confirmed_ids,
            "PROBE_CONFIRMED_ID_MISMATCH",
            "discriminating_probe.confirmed_hypothesis_id must match the confirmed hypothesis ID")


def check_binary_search_isolation(record, require):
    bisect = record.get("binary_search_isolation")
    require(isinstance(bisect, dict), "INVALID_BINARY_SEARCH_ISOLATION",
            "binary_search_isolation must be a dictionary")
    if not isinstance(bisect, dict):
        return

    require(choice(bisect.get("method"), VALID_BISECT_METHODS),
            "INVALID_BISECT_METHOD",
            "binary_search_isolation.method must be one of: %s"
            % ", ".join(sorted(VALID_BISECT_METHODS)))
    require(filled(bisect.get("initial_fault_space"), 10),
            "MISSING_INITIAL_FAULT_SPACE",
            "binary_search_isolation.initial_fault_space must describe the starting search range")
    require(filled(bisect.get("isolated_boundary"), 10),
            "MISSING_ISOLATED_BOUNDARY",
            "binary_search_isolation.isolated_boundary must describe the narrowed fault seam")
    steps = bisect.get("steps_taken")
    require(isinstance(steps, int) and 1 <= steps <= 30,
            "INVALID_BISECT_STEPS",
            "binary_search_isolation.steps_taken must be an integer between 1 and 30")


def check_determinism_pinning(record, require):
    pinning = record.get("determinism_pinning")
    require(isinstance(pinning, dict), "INVALID_DETERMINISM_PINNING",
            "determinism_pinning must be a dictionary")
    if not isinstance(pinning, dict):
        return

    controls = pinning.get("controls_applied")
    require(isinstance(controls, list) and bool(controls)
            and all(choice(c, VALID_DETERMINISM_CONTROLS) for c in controls),
            "INVALID_DETERMINISM_CONTROLS",
            "determinism_pinning.controls_applied must be a non-empty list of valid determinism controls")
    require(pinning.get("sleep_based_timing_absent") is True,
            "SLEEP_TIMING_BANDAID_PRESENT",
            "determinism_pinning.sleep_based_timing_absent must be true (ban sleep/setTimeout race hacks)")
    require(filled(pinning.get("deterministic_red_test_command"), 5),
            "MISSING_RED_TEST_COMMAND",
            "determinism_pinning.deterministic_red_test_command must specify the reproducer command")
    require(pinning.get("reproduction_rate_after_pinning") == "100_percent_deterministic",
            "FLAKY_REPRODUCER_NOT_PINNED",
            "determinism_pinning.reproduction_rate_after_pinning must be '100_percent_deterministic'")


def check_red_green_verification(record, require):
    verify = record.get("red_green_verification")
    require(isinstance(verify, dict), "INVALID_RED_GREEN_VERIFICATION",
            "red_green_verification must be a dictionary")
    if not isinstance(verify, dict):
        return

    require(verify.get("failed_before_fix") is True,
            "RED_TEST_NOT_PROVEN",
            "red_green_verification.failed_before_fix must be true")
    require(verify.get("passed_after_fix") is True,
            "GREEN_FIX_NOT_PROVEN",
            "red_green_verification.passed_after_fix must be true")
    require(verify.get("failed_again_on_fix_revert") is True,
            "REVERT_FALSIFICATION_MISSING",
            "red_green_verification.failed_again_on_fix_revert must be true (Red-Green-Revert law)")
    require(verify.get("diagnostic_probes_removed") is True,
            "LEFTOVER_DIAGNOSTIC_PROBES",
            "red_green_verification.diagnostic_probes_removed must be true")
    require(filled(verify.get("root_fix_owner_layer"), 5),
            "MISSING_ROOT_FIX_OWNER_LAYER",
            "red_green_verification.root_fix_owner_layer must specify the owning boundary")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    has_sleep_hack = bool(
        re.search(
            r"\b(setTimeout\s*\(|time\.sleep\s*\(|asyncio\.sleep\s*\(|thread::sleep\s*\()",
            source_text,
        )
    )
    require(not has_sleep_hack, "SOURCE_SLEEP_SYNCHRONIZATION_HACK",
            "Detected wall-clock sleep/setTimeout synchronization band-aid; use deterministic barriers or virtual clocks")

    has_debug_probe = bool(
        re.search(
            r"""(console\.(log|debug)\s*\(\s*["'`]\s*(DEBUG|HERE|PROBE|WTF)|print\s*\(\s*["']\s*(DEBUG|HERE|PROBE)|\bdebugger\s*;)""",
            source_text,
            re.IGNORECASE,
        )
    )
    require(not has_debug_probe, "SOURCE_LEFTOVER_DEBUG_PROBE",
            "Detected leftover diagnostic debug print/debugger statement in source or test")

    has_empty_catch = bool(
        re.search(
            r"(\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}|\bexcept(?:\s+\w+)?\s*:\s*pass\b)",
            source_text,
        )
    )
    require(not has_empty_catch, "SOURCE_SWALLOWED_EXCEPTION",
            "Detected silent exception swallowing (empty catch / except: pass) masking underlying fault")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_symptom(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        confirmed_ids, falsified_ids = check_differential_diagnosis(record, require)
        check_discriminating_probe(record, confirmed_ids, falsified_ids, require)
        check_binary_search_isolation(record, require)
        check_determinism_pinning(record, require)
        check_red_green_verification(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    return {
        "record_status": "incomplete" if findings else "complete",
        "verdict_action": action,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--source", type=Path, default=None,
                        help="Optional source or test file to scan for sleep() hacks, leftover probes, or swallowed exceptions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid scientific fault isolation record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Scientific Fault Isolation record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: deterministic test execution and Red-Green-Revert falsification must be verified independently.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
