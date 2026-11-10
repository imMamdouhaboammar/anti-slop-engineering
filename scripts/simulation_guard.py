#!/usr/bin/env python3
"""Check Deterministic Simulation and Property Testing records and source code for Microsoft Research & AWS rigor."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_SYSTEM_ARCHETYPES = {
    "distributed_consensus_and_replication",
    "event_driven_actor_system",
    "financial_transaction_pipeline",
    "parser_codec_deserializer",
    "stateful_workflow_engine",
}

VALID_PROPERTY_FRAMEWORKS = {
    "fast-check",
    "hypothesis",
    "proptest",
    "rapid",
    "custom_deterministic_pbt",
}

VALID_INVARIANT_CATEGORIES = {
    "round_trip_invertibility",
    "idempotency",
    "metamorphic_relation",
    "state_model_equivalence",
    "conservation_law",
}

VALID_PRNG_ALGORITHMS = {
    "mulberry32",
    "xorshift128p",
    "pcg32",
    "splitmix64",
    "chacha8_rng",
}

VALID_FAULT_TYPES = {
    "network_packet_loss",
    "clock_skew_drift",
    "message_reordering",
    "partition_split_brain",
    "storage_write_corruption",
    "node_crash_restart",
}

VALID_FUZZ_ENGINES = {
    "libfuzzer",
    "atheris",
    "jazzer",
    "cargo-fuzz",
    "native_go_fuzz",
    "structure_aware_generator",
}

HEX_SEED_RE = re.compile(r"^0x[0-9a-fA-F_]{4,20}$")


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_target_system(record, require):
    target = record.get("target_system")
    require(isinstance(target, dict), "INVALID_TARGET_SYSTEM", "target_system must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("module_under_test"), 10),
            "MISSING_MODULE_UNDER_TEST",
            "target_system.module_under_test must be at least 10 characters")
    require(choice(target.get("system_archetype"), VALID_SYSTEM_ARCHETYPES),
            "INVALID_SYSTEM_ARCHETYPE",
            "target_system.system_archetype must be one of: %s" % ", ".join(sorted(VALID_SYSTEM_ARCHETYPES)))
    require(target.get("example_based_tests_only_banned") is True,
            "EXAMPLE_BASED_TESTS_ONLY_NOT_BANNED",
            "target_system.example_based_tests_only_banned must be true; example-based tests alone are insufficient")


def check_property_testing(record, require):
    pbt = record.get("property_testing")
    require(isinstance(pbt, dict), "INVALID_PROPERTY_TESTING", "property_testing must be a dictionary")
    if not isinstance(pbt, dict):
        return
    require(choice(pbt.get("framework"), VALID_PROPERTY_FRAMEWORKS),
            "INVALID_PROPERTY_FRAMEWORK",
            "property_testing.framework must be one of: %s" % ", ".join(sorted(VALID_PROPERTY_FRAMEWORKS)))
    min_cases = pbt.get("min_test_cases")
    require(isinstance(min_cases, int) and min_cases >= 100,
            "INSUFFICIENT_PROPERTY_RUNS",
            "property_testing.min_test_cases must be an integer >= 100")
    require(pbt.get("shrinking_enabled") is True,
            "SHRINKING_DISABLED",
            "property_testing.shrinking_enabled must be true; shrinking to minimal failing counterexamples is mandatory")

    invariants = pbt.get("invariants")
    require(isinstance(invariants, list) and len(invariants) >= 2,
            "INSUFFICIENT_INVARIANTS",
            "property_testing.invariants must declare at least 2 distinct invariants")
    if isinstance(invariants, list):
        ids = set()
        for idx, inv in enumerate(invariants):
            valid = (
                isinstance(inv, dict)
                and filled(inv.get("id"), 3)
                and choice(inv.get("category"), VALID_INVARIANT_CATEGORIES)
                and filled(inv.get("description"), 15)
                and inv.get("shrink_counterexample_verified") is True
            )
            require(valid, "INVALID_INVARIANT_SPEC",
                    "property_testing.invariants[%d] requires id, valid category, description (>=15 chars), and shrink_counterexample_verified=true" % idx)
            if isinstance(inv, dict) and filled(inv.get("id")):
                key = inv["id"].strip().casefold()
                require(key not in ids, "DUPLICATE_INVARIANT_ID", "Invariant IDs must be distinct")
                ids.add(key)


def check_deterministic_simulation(record, require):
    dst = record.get("deterministic_simulation")
    require(isinstance(dst, dict), "INVALID_DETERMINISTIC_SIMULATION",
            "deterministic_simulation must be a dictionary")
    if not isinstance(dst, dict):
        return
    require(dst.get("virtual_clock_enabled") is True,
            "VIRTUAL_CLOCK_DISABLED",
            "deterministic_simulation.virtual_clock_enabled must be true; wall-clock sleeps and unscheduled delays are banned")
    require(choice(dst.get("prng_algorithm"), VALID_PRNG_ALGORITHMS),
            "INVALID_PRNG_ALGORITHM",
            "deterministic_simulation.prng_algorithm must be one of: %s" % ", ".join(sorted(VALID_PRNG_ALGORITHMS)))

    seed = dst.get("seed")
    valid_seed = (isinstance(seed, int) and seed >= 0) or (isinstance(seed, str) and bool(HEX_SEED_RE.match(seed)))
    require(valid_seed, "INVALID_SIMULATION_SEED",
            "deterministic_simulation.seed must be an integer >= 0 or hex string (e.g. '0xCAFE_BABE')")

    require(dst.get("reproducibility_verified") is True,
            "REPRODUCIBILITY_NOT_VERIFIED",
            "deterministic_simulation.reproducibility_verified must be true; rerun with identical seed must yield identical trace")

    faults = dst.get("fault_injection_matrix")
    require(isinstance(faults, list) and len(faults) >= 3,
            "INSUFFICIENT_FAULT_INJECTION_MODES",
            "deterministic_simulation.fault_injection_matrix must declare at least 3 distinct fault modes")
    if isinstance(faults, list):
        seen_types = set()
        for idx, item in enumerate(faults):
            valid = (
                isinstance(item, dict)
                and choice(item.get("fault_type"), VALID_FAULT_TYPES)
                and (filled(item.get("probability_or_cadence")) or isinstance(item.get("probability_or_cadence"), (int, float)))
                and filled(item.get("mitigation_or_invariant"), 15)
            )
            require(valid, "INVALID_FAULT_SPEC",
                    "fault_injection_matrix[%d] requires valid fault_type, probability_or_cadence, and mitigation_or_invariant (>=15 chars)" % idx)
            if isinstance(item, dict) and item.get("fault_type") in VALID_FAULT_TYPES:
                ft = item["fault_type"]
                require(ft not in seen_types, "DUPLICATE_FAULT_TYPE", "Fault types in matrix must be distinct")
                seen_types.add(ft)


def check_state_machine_modeling(record, require):
    smm = record.get("state_machine_modeling")
    require(isinstance(smm, dict), "INVALID_STATE_MACHINE_MODELING",
            "state_machine_modeling must be a dictionary")
    if not isinstance(smm, dict):
        return
    require(filled(smm.get("model_name"), 5),
            "MISSING_MODEL_NAME",
            "state_machine_modeling.model_name must be at least 5 characters")
    require(smm.get("type_level_impossible_states_prevented") is True,
            "IMPOSSIBLE_STATES_NOT_PREVENTED",
            "state_machine_modeling.type_level_impossible_states_prevented must be true; use tagged unions or ADTs")

    states = smm.get("states")
    require(isinstance(states, list) and len(states) >= 3 and all(filled(s) for s in states),
            "INSUFFICIENT_STATES",
            "state_machine_modeling.states must list at least 3 valid states")

    transitions = smm.get("transitions")
    require(isinstance(transitions, list) and len(transitions) >= 3,
            "INSUFFICIENT_TRANSITIONS",
            "state_machine_modeling.transitions must define at least 3 state transitions")
    if isinstance(transitions, list):
        for idx, trans in enumerate(transitions):
            valid = (
                isinstance(trans, dict)
                and filled(trans.get("from_state"))
                and filled(trans.get("event"))
                and filled(trans.get("to_state"))
                and filled(trans.get("guard_or_effect"))
            )
            require(valid, "INVALID_TRANSITION_SPEC",
                    "state_machine_modeling.transitions[%d] requires from_state, event, to_state, and guard_or_effect" % idx)

    require(smm.get("generative_model_test_executed") is True,
            "GENERATIVE_MODEL_TEST_NOT_EXECUTED",
            "state_machine_modeling.generative_model_test_executed must be true")


def check_structure_aware_fuzzing(record, require):
    saf = record.get("structure_aware_fuzzing")
    require(isinstance(saf, dict), "INVALID_STRUCTURE_AWARE_FUZZING",
            "structure_aware_fuzzing must be a dictionary")
    if not isinstance(saf, dict):
        return
    require(filled(saf.get("target_boundary"), 5),
            "MISSING_FUZZ_TARGET_BOUNDARY",
            "structure_aware_fuzzing.target_boundary must specify the parser, deserializer, or untrusted boundary")
    require(choice(saf.get("fuzz_engine"), VALID_FUZZ_ENGINES),
            "INVALID_FUZZ_ENGINE",
            "structure_aware_fuzzing.fuzz_engine must be one of: %s" % ", ".join(sorted(VALID_FUZZ_ENGINES)))
    require(filled(saf.get("corpus_strategy"), 10),
            "MISSING_CORPUS_STRATEGY",
            "structure_aware_fuzzing.corpus_strategy must describe the seed corpus and grammar generator (>=10 chars)")
    require(saf.get("crash_freedom_verified") is True,
            "CRASH_FREEDOM_NOT_VERIFIED",
            "structure_aware_fuzzing.crash_freedom_verified must be true")
    require(saf.get("bounded_recursion_and_memory") is True,
            "UNBOUNDED_RECURSION_OR_MEMORY",
            "structure_aware_fuzzing.bounded_recursion_and_memory must be true to prevent allocation and call-stack bombs")

    max_payload = saf.get("max_payload_bytes")
    require(isinstance(max_payload, int) and 0 < max_payload <= 10_485_760,
            "INVALID_MAX_PAYLOAD_BYTES",
            "structure_aware_fuzzing.max_payload_bytes must be an integer between 1 and 10,485,760 bytes (10MB)")


def check_mutation_falsification(record, require):
    mut = record.get("mutation_falsification")
    require(isinstance(mut, dict), "INVALID_MUTATION_FALSIFICATION",
            "mutation_falsification must be a dictionary")
    if not isinstance(mut, dict):
        return
    require(mut.get("red_green_falsification_verified") is True,
            "RED_GREEN_FALSIFICATION_NOT_VERIFIED",
            "mutation_falsification.red_green_falsification_verified must be true")
    require(filled(mut.get("mutated_invariant"), 20),
            "MISSING_MUTATED_INVARIANT",
            "mutation_falsification.mutated_invariant must describe the deliberate mutation (>=20 chars)")
    require(filled(mut.get("observed_failure_seed_or_counterexample"), 10),
            "MISSING_FAILURE_SEED_OR_COUNTEREXAMPLE",
            "mutation_falsification.observed_failure_seed_or_counterexample must record the failing seed or shrunk input")


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

    # Anti-Pattern 1: Unseeded randomness in test or simulation code
    has_unseeded_random = bool(
        re.search(r"\b(?:Math\.random|random\.random|rand\.Int|rand\.Float)\s*\(", source_text)
    )
    require(not has_unseeded_random, "SOURCE_UNSEEDED_RANDOM_IN_SIMULATION",
            "Detected unseeded randomness (Math.random/random.random); all simulation and property generation must use an explicit seeded PRNG (e.g. Mulberry32/PCG32) for deterministic replay")

    # Anti-Pattern 2: Real wall-clock sleep in simulation code
    has_wall_clock_sleep = bool(
        re.search(r"\b(?:setTimeout|time\.sleep|time\.Sleep|SystemClock\.sleep)\s*\(", source_text)
    )
    require(not has_wall_clock_sleep, "SOURCE_WALL_CLOCK_SLEEP_IN_SIMULATION",
            "Detected wall-clock sleep (setTimeout/time.sleep); inject a DeterministicVirtualClock / DiscreteEventSimulator instead of real wall-clock delays")

    # Anti-Pattern 3: Loose boolean flags representing impossible states
    has_impossible_state_booleans = bool(
        re.search(r"(?:isLoading|loading):\s*boolean[\s\S]*?(?:isError|error):\s*boolean[\s\S]*?(?:data|result):\s*", source_text)
    )
    require(not has_impossible_state_booleans, "SOURCE_IMPOSSIBLE_STATE_BOOLEANS",
            "Detected anti-pattern boolean bag (isLoading + isError + data); make impossible states unrepresentable via tagged unions or algebraic data types")

    # Anti-Pattern 4: Tautological or weak assertions
    has_tautological_assert = bool(
        re.search(r"expect\s*\(\s*true\s*\)\s*\.toBe\s*\(\s*true\s*\)|\.toBeDefined\s*\(\s*\)", source_text)
    )
    require(not has_tautological_assert, "SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION",
            "Detected tautological or weak assertion; assert formal invariant properties and state invariants directly")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_system(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_property_testing(record, require)
        check_deterministic_simulation(record, require)
        check_state_machine_modeling(record, require)
        check_structure_aware_fuzzing(record, require)
        check_mutation_falsification(record, require)

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
                        help="Optional test/source file to scan for unseeded random, wall-clock sleeps, impossible state booleans, or weak assertions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Deterministic Simulation & Property Testing record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Deterministic Simulation & Property Testing record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: Invariants, Seeded DST simulations, and Fuzz harnesses must be executed in test runners.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
