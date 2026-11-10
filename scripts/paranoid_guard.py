#!/usr/bin/env python3
"""Check paranoid principal architect records for zero-trust and 10M-scale compliance."""

import argparse
import json
import sys
from pathlib import Path

VALID_THREAT_CLASSES = {
    "race_condition",
    "hot_key_contention",
    "unbounded_concurrency",
    "injection",
    "timing_attack",
    "edos",
    "toctou",
    "memory_leak",
    "network_stall",
}

VALID_LOCKING_STRATEGIES = {
    "optimistic_occ",
    "sharded_counters",
    "event_ledger",
    "partitioned_lock",
}


def filled(value, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and bool(value.strip())


def choice(value, values):
    return isinstance(value, str) and value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_scale_profile(record, require):
    scale = record.get("scale_profile")
    require(isinstance(scale, dict), "INVALID_SCALE_PROFILE", "scale_profile must be a dictionary")
    if not isinstance(scale, dict):
        return

    ceiling = scale.get("architectural_ceiling_target")
    concurrency = scale.get("target_concurrency")
    require(ceiling is not None or concurrency is not None,
            "INVALID_CONCURRENCY", "scale_profile requires architectural_ceiling_target or target_concurrency >= 10,000,000")
    if ceiling is not None:
        require(isinstance(ceiling, int) and ceiling >= 10_000_000,
                "INVALID_CONCURRENCY", "architectural_ceiling_target must be an integer >= 10,000,000")
    if concurrency is not None:
        require(isinstance(concurrency, int) and concurrency >= 10_000_000,
                "INVALID_CONCURRENCY", "target_concurrency must be an integer >= 10,000,000")

    day_one = scale.get("day_one_active_load")
    throughput = scale.get("throughput_rps")
    require(day_one is not None or throughput is not None,
            "INVALID_THROUGHPUT", "scale_profile requires day_one_active_load or throughput_rps")

    if day_one is not None:
        require(isinstance(day_one, dict), "INVALID_DAY_ONE_LOAD", "day_one_active_load must be a dictionary")
        if isinstance(day_one, dict):
            c = day_one.get("concurrency")
            require(isinstance(c, int) and c >= 1,
                    "INVALID_DAY_ONE_CONCURRENCY", "day_one_active_load.concurrency must be an integer >= 1")
            r = day_one.get("throughput_rps")
            require(isinstance(r, int) and r >= 1,
                    "INVALID_DAY_ONE_THROUGHPUT", "day_one_active_load.throughput_rps must be an integer >= 1")

    if throughput is not None:
        require(isinstance(throughput, int) and throughput >= 1_000,
                "INVALID_THROUGHPUT", "throughput_rps must be an integer >= 1,000")

    latency = scale.get("latency_budget_ms")
    require(isinstance(latency, int) and 0 < latency <= 500,
            "INVALID_LATENCY_BUDGET", "latency_budget_ms must be an integer between 1 and 500")


def check_threat_pre_mortem(record, require):
    threats = record.get("threat_pre_mortem")
    require(isinstance(threats, list), "INVALID_THREATS", "threat_pre_mortem must be a list")
    if not isinstance(threats, list):
        return
    require(len(threats) >= 3, "INSUFFICIENT_THREATS", "threat_pre_mortem must identify at least 3 failure modes")
    ids = set()
    for index, item in enumerate(threats):
        valid = (isinstance(item, dict) and filled(item.get("id"))
                 and choice(item.get("threat_class"), VALID_THREAT_CLASSES)
                 and isinstance(item.get("description"), str) and len(item.get("description", "").strip()) >= 15
                 and isinstance(item.get("mitigation"), str) and len(item.get("mitigation", "").strip()) >= 15)
        require(valid, "INVALID_THREAT_ITEM",
                "threat_pre_mortem[%d] needs valid id, threat_class, description and mitigation" % index)
        if valid:
            key = item["id"].strip().casefold()
            require(key not in ids, "DUPLICATE_THREAT_ID", "Threat IDs must be distinct")
            ids.add(key)


def check_trust_boundaries(record, require):
    boundaries = record.get("trust_boundaries")
    require(isinstance(boundaries, list), "INVALID_BOUNDARIES", "trust_boundaries must be a list")
    if not isinstance(boundaries, list):
        return
    require(len(boundaries) >= 1, "MISSING_TRUST_BOUNDARY", "Name at least one trust boundary")
    for index, item in enumerate(boundaries):
        valid = (isinstance(item, dict) and filled(item.get("name"))
                 and filled(item.get("schema_validation"))
                 and filled(item.get("data_layer_ownership")))
        require(valid, "INVALID_BOUNDARY_ITEM",
                "trust_boundaries[%d] needs name, schema_validation and data_layer_ownership" % index)


def check_concurrency_controls(record, require):
    controls = record.get("concurrency_controls")
    require(isinstance(controls, dict), "INVALID_CONCURRENCY_CONTROLS", "concurrency_controls must be a dictionary")
    if not isinstance(controls, dict):
        return
    idempotency = controls.get("idempotency")
    require(isinstance(idempotency, dict), "INVALID_IDEMPOTENCY", "idempotency must be a dictionary")
    if isinstance(idempotency, dict):
        require(idempotency.get("enabled") is True, "IDEMPOTENCY_DISABLED",
                "State mutations must enforce idempotency: enabled must be true")
        require(filled(idempotency.get("key_header")), "MISSING_IDEMPOTENCY_HEADER",
                "Idempotency must declare key_header (e.g. Idempotency-Key)")
        require(filled(idempotency.get("storage")), "MISSING_IDEMPOTENCY_STORAGE",
                "Idempotency must declare storage deduplication mechanism")

    locking = controls.get("locking_strategy")
    require(choice(locking, VALID_LOCKING_STRATEGIES), "INVALID_LOCKING_STRATEGY",
            "locking_strategy must be one of: %s" % ", ".join(sorted(VALID_LOCKING_STRATEGIES)))


def check_bounded_limits(record, require):
    limits = record.get("bounded_limits")
    require(isinstance(limits, dict), "INVALID_BOUNDED_LIMITS", "bounded_limits must be a dictionary")
    if not isinstance(limits, dict):
        return
    read_limit = limits.get("max_read_limit")
    require(isinstance(read_limit, int) and 0 < read_limit <= 100,
            "UNBOUNDED_READ_LIMIT", "max_read_limit must be an integer <= 100")
    payload = limits.get("max_payload_bytes")
    require(isinstance(payload, int) and 0 < payload <= 10_485_760,
            "UNBOUNDED_PAYLOAD_LIMIT", "max_payload_bytes must be an integer <= 10,485,760 (10MB)")
    timeout = limits.get("network_timeout_ms")
    require(isinstance(timeout, int) and 0 < timeout <= 10_000,
            "UNBOUNDED_TIMEOUT", "network_timeout_ms must be an integer <= 10,000")
    require(limits.get("backoff_algorithm") == "exponential_full_jitter",
            "INVALID_BACKOFF_ALGORITHM", "backoff_algorithm must be 'exponential_full_jitter'")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(isinstance(verdict.get("rationale"), str) and len(verdict.get("rationale", "").strip()) >= 20,
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def audit(record):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    require(filled(record.get("goal")), "MISSING_GOAL", "Record must specify the architectural goal")
    action = check_verdict(record, require)

    proceeding = action == "proceed"
    if proceeding or action == "pause":
        check_scale_profile(record, require)
        check_threat_pre_mortem(record, require)
        check_trust_boundaries(record, require)
        check_concurrency_controls(record, require)
        check_bounded_limits(record, require)

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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        result = audit(record)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid paranoid architect record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Paranoid Architect record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: domain security and live load testing must be verified independently.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
