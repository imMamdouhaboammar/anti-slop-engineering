#!/usr/bin/env python3
"""Check Verification Oracle Architect records and test/source files for Contract-Verified In-Memory Fakes, Property-Based & Metamorphic Oracles, Seeded Deterministic Chaos Testing, and Red-Green Mutation Falsification."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_DOMAIN_CATEGORIES = {
    "financial_ledger_and_payments",
    "parser_serializer_codec",
    "state_machine_and_workflow",
    "distributed_storage_and_sync",
    "authorization_and_policy_engine",
}
VALID_FAKE_MECHANICS = {
    "structured_clone_boundary_isolation",
    "unique_and_check_constraint_enforcement",
    "optimistic_concurrency_version_cas",
    "transactional_snapshot_rollback",
    "composite_tenant_isolation",
    "deterministic_cursor_pagination",
}
VALID_PROPERTY_FRAMEWORKS = {
    "fast-check",
    "hypothesis",
    "proptest",
    "rapid",
    "deterministic_seeded_property_engine",
}
VALID_INVARIANT_CATEGORIES = {
    "conservation_law",
    "roundtrip_invertibility",
    "idempotency_law",
    "metamorphic_relation",
    "state_machine_safety",
}
VALID_PRNG_ALGORITHMS = {
    "mulberry32",
    "xorshift32",
    "pcg32",
    "chacha8_rng",
}
VALID_CHAOS_FAULT_MODES = {
    "pre_commit_connection_drop",
    "post_commit_ack_drop",
    "transient_cas_version_conflict",
    "duplicate_out_of_order_delivery",
    "virtual_clock_lease_skew",
}
HEX_SEED_RE = re.compile(r"^0x[0-9a-fA-F]{4,16}$")


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
    require(isinstance(target, dict), "INVALID_TARGET_SYSTEM",
            "target_system must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("module_under_test"), 10),
            "MISSING_MODULE_UNDER_TEST",
            "target_system.module_under_test must be at least 10 characters")
    require(choice(target.get("domain_category"), VALID_DOMAIN_CATEGORIES),
            "INVALID_DOMAIN_CATEGORY",
            "target_system.domain_category must be one of: %s"
            % ", ".join(sorted(VALID_DOMAIN_CATEGORIES)))
    require(target.get("module_mocking_banned") is True,
            "MODULE_MOCKING_NOT_BANNED",
            "target_system.module_mocking_banned must be true")


def check_verified_fakes(record, require):
    fakes = record.get("verified_in_memory_fakes")
    require(isinstance(fakes, dict), "INVALID_VERIFIED_IN_MEMORY_FAKES",
            "verified_in_memory_fakes must be a dictionary")
    if not isinstance(fakes, dict):
        return
    require(filled(fakes.get("port_interface"), 5),
            "MISSING_PORT_INTERFACE",
            "verified_in_memory_fakes.port_interface must name the domain Port")
    require(filled(fakes.get("fake_adapter_name"), 5),
            "MISSING_FAKE_ADAPTER_NAME",
            "verified_in_memory_fakes.fake_adapter_name must name the In-Memory Fake")
    require(filled(fakes.get("real_adapter_name"), 5),
            "MISSING_REAL_ADAPTER_NAME",
            "verified_in_memory_fakes.real_adapter_name must name the Real production adapter")
    require(filled(fakes.get("shared_contract_suite"), 10),
            "MISSING_SHARED_CONTRACT_SUITE",
            "verified_in_memory_fakes.shared_contract_suite must specify the shared contract suite")
    require(fakes.get("contract_parity_verified") is True,
            "CONTRACT_PARITY_NOT_VERIFIED",
            "verified_in_memory_fakes.contract_parity_verified must be true")

    mechanics = fakes.get("enforced_fake_mechanics")
    valid_list = (
        isinstance(mechanics, list)
        and len(mechanics) >= 3
        and all(isinstance(m, str) and m in VALID_FAKE_MECHANICS for m in mechanics)
    )
    require(valid_list, "INSUFFICIENT_ENFORCED_FAKE_MECHANICS",
            "verified_in_memory_fakes.enforced_fake_mechanics must list at least 3 valid mechanics")
    if isinstance(mechanics, list):
        require("transactional_snapshot_rollback" in mechanics
                and "structured_clone_boundary_isolation" in mechanics,
                "MISSING_CORE_FAKE_ISOLATION_OR_ROLLBACK",
                "enforced_fake_mechanics must include 'structured_clone_boundary_isolation' and 'transactional_snapshot_rollback'")


def check_property_oracles(record, require):
    prop = record.get("property_and_metamorphic_oracles")
    require(isinstance(prop, dict), "INVALID_PROPERTY_AND_METAMORPHIC_ORACLES",
            "property_and_metamorphic_oracles must be a dictionary")
    if not isinstance(prop, dict):
        return
    require(choice(prop.get("framework"), VALID_PROPERTY_FRAMEWORKS),
            "INVALID_PROPERTY_FRAMEWORK",
            "property_and_metamorphic_oracles.framework must be a supported property engine")
    runs = prop.get("generated_runs_per_property")
    require(isinstance(runs, int) and runs >= 100,
            "INSUFFICIENT_GENERATED_PROPERTY_RUNS",
            "property_and_metamorphic_oracles.generated_runs_per_property must be an integer >= 100")
    require(prop.get("shrinking_enabled") is True,
            "SHRINKING_NOT_ENABLED",
            "property_and_metamorphic_oracles.shrinking_enabled must be true")

    invariants = prop.get("invariants_verified")
    require(isinstance(invariants, list) and len(invariants) >= 2,
            "INSUFFICIENT_INVARIANTS_VERIFIED",
            "property_and_metamorphic_oracles.invariants_verified must contain at least 2 invariants")
    if not isinstance(invariants, list):
        return
    for idx, inv in enumerate(invariants):
        ok_item = (
            isinstance(inv, dict)
            and filled(inv.get("name"), 5)
            and choice(inv.get("category"), VALID_INVARIANT_CATEGORIES)
            and filled(inv.get("assertion_formula"), 15)
        )
        require(ok_item, "INVALID_PROPERTY_INVARIANT_%d" % idx,
                "invariants_verified[%d] must specify valid name, category, and assertion_formula" % idx)


def check_chaos_and_mutation(record, require):
    chaos = record.get("deterministic_chaos_testing")
    require(isinstance(chaos, dict), "INVALID_DETERMINISTIC_CHAOS_TESTING",
            "deterministic_chaos_testing must be a dictionary")
    if isinstance(chaos, dict):
        require(choice(chaos.get("seeded_prng_algorithm"), VALID_PRNG_ALGORITHMS),
                "INVALID_SEEDED_PRNG_ALGORITHM",
                "deterministic_chaos_testing.seeded_prng_algorithm must be a valid deterministic PRNG")
        seeds = chaos.get("reproduction_seeds")
        seeds_ok = (
            isinstance(seeds, list)
            and len(seeds) >= 2
            and all(isinstance(s, str) and bool(HEX_SEED_RE.match(s)) for s in seeds)
        )
        require(seeds_ok, "INVALID_REPRODUCTION_SEEDS",
                "deterministic_chaos_testing.reproduction_seeds must contain at least 2 hex seeds (0x...)")
        require(chaos.get("virtual_clock_injected") is True,
                "VIRTUAL_CLOCK_NOT_INJECTED",
                "deterministic_chaos_testing.virtual_clock_injected must be true")
        require(chaos.get("zero_wall_clock_sleeps") is True,
                "WALL_CLOCK_SLEEPS_PRESENT",
                "deterministic_chaos_testing.zero_wall_clock_sleeps must be true")
        faults = chaos.get("injected_fault_modes")
        faults_ok = (
            isinstance(faults, list)
            and len(faults) >= 2
            and all(isinstance(f, str) and f in VALID_CHAOS_FAULT_MODES for f in faults)
            and "pre_commit_connection_drop" in faults
            and "post_commit_ack_drop" in faults
        )
        require(faults_ok, "MISSING_PRE_OR_POST_COMMIT_CHAOS_FAULTS",
                "injected_fault_modes must include both 'pre_commit_connection_drop' and 'post_commit_ack_drop'")
        require(chaos.get("idempotency_and_rollback_proven") is True,
                "IDEMPOTENCY_AND_ROLLBACK_NOT_PROVEN",
                "deterministic_chaos_testing.idempotency_and_rollback_proven must be true")

    mut = record.get("mutation_falsification")
    require(isinstance(mut, dict), "INVALID_MUTATION_FALSIFICATION",
            "mutation_falsification must be a dictionary")
    if isinstance(mut, dict):
        require(mut.get("red_green_falsification_verified") is True,
                "RED_GREEN_FALSIFICATION_NOT_VERIFIED",
                "mutation_falsification.red_green_falsification_verified must be true")
        require(filled(mut.get("mutated_production_invariant"), 20),
                "MISSING_MUTATED_PRODUCTION_INVARIANT",
                "mutation_falsification.mutated_production_invariant must describe the deliberate mutation")
        require(filled(mut.get("observed_red_failure_signal"), 20),
                "MISSING_OBSERVED_RED_FAILURE_SIGNAL",
                "mutation_falsification.observed_red_failure_signal must record the failing counterexample/seed")


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

    has_banned_mock = bool(
        re.search(
            r"\b(?:vi\.mock|jest\.mock|sinon\.stub|unittest\.mock\.patch|mock\.module)\s*\("
            r"|no-module-mocking",
            source_text,
        )
    )
    require(not has_banned_mock, "SOURCE_BANNED_MODULE_MOCK",
            "Detected banned module mocking (vi.mock/jest.mock/sinon.stub/unittest.mock.patch) or rule suppression; use a Contract-Verified In-Memory Fake")

    has_unseeded_random = bool(re.search(r"\b(?:Math\.random|random\.random)\s*\(", source_text))
    require(not has_unseeded_random, "SOURCE_UNSEEDED_RANDOM_IN_TEST",
            "Detected unseeded Math.random()/random.random(); use an explicit seeded PRNG (e.g. Mulberry32) for deterministic replay")

    has_wall_clock_sleep = bool(re.search(r"\b(?:setTimeout|time\.sleep)\s*\(", source_text))
    require(not has_wall_clock_sleep, "SOURCE_WALL_CLOCK_SLEEP_IN_TEST",
            "Detected wall-clock sleep (setTimeout/time.sleep); inject a DeterministicVirtualClock instead")

    has_tautological_assert = bool(
        re.search(r"expect\s*\(\s*true\s*\)\s*\.toBe\s*\(\s*true\s*\)|\.toBeDefined\s*\(\s*\)", source_text)
    )
    require(not has_tautological_assert, "SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION",
            "Detected tautological or weak assertion (expect(true).toBe(true) or .toBeDefined()); assert concrete domain invariants")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_system(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_verified_fakes(record, require)
        check_property_oracles(record, require)
        check_chaos_and_mutation(record, require)

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
                        help="Optional test/source file to scan for banned module mocks, unseeded Math.random(), setTimeout sleeps, or weak assertions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Verification Oracle record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Verification Oracle record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: Shared Contract Suites, Property Generators, and Deterministic Chaos seeds must be executed in the test runner.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
