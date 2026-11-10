#!/usr/bin/env python3
"""Tests for scripts/simulation_guard.py (Deterministic Simulation & Property Testing Guard)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import simulation_guard


def make_valid_record():
    return {
        "schema_version": "1.0",
        "target_system": {
            "module_under_test": "distributed_raft_consensus_engine",
            "system_archetype": "distributed_consensus_and_replication",
            "example_based_tests_only_banned": True,
        },
        "property_testing": {
            "framework": "fast-check",
            "min_test_cases": 1000,
            "shrinking_enabled": True,
            "invariants": [
                {
                    "id": "INV-01",
                    "category": "round_trip_invertibility",
                    "description": "Log entry serialization and deserialization is perfectly lossless and canonical.",
                    "shrink_counterexample_verified": True,
                },
                {
                    "id": "INV-02",
                    "category": "state_model_equivalence",
                    "description": "State transition outcome matches formal TLA+ state machine oracle across 10,000 steps.",
                    "shrink_counterexample_verified": True,
                },
            ],
        },
        "deterministic_simulation": {
            "virtual_clock_enabled": True,
            "prng_algorithm": "mulberry32",
            "seed": "0xCAFE_BABE",
            "reproducibility_verified": True,
            "fault_injection_matrix": [
                {
                    "fault_type": "network_packet_loss",
                    "probability_or_cadence": 0.05,
                    "mitigation_or_invariant": "Heartbeat quorum ensures leader election completes within 3 simulated ticks.",
                },
                {
                    "fault_type": "clock_skew_drift",
                    "probability_or_cadence": "+/-500ms jitter",
                    "mitigation_or_invariant": "Logical Lamport clocks prevent split-brain under severe monotonic skew.",
                },
                {
                    "fault_type": "message_reordering",
                    "probability_or_cadence": 0.10,
                    "mitigation_or_invariant": "Strict sequence numbers reject stale RPC frames and duplicate votes.",
                },
            ],
        },
        "state_machine_modeling": {
            "model_name": "RaftNodeStateMachine",
            "type_level_impossible_states_prevented": True,
            "states": ["Follower", "Candidate", "Leader", "Terminated"],
            "transitions": [
                {
                    "from_state": "Follower",
                    "event": "ElectionTimeout",
                    "to_state": "Candidate",
                    "guard_or_effect": "Increment term, vote for self, broadcast RequestVote RPC.",
                },
                {
                    "from_state": "Candidate",
                    "event": "QuorumVotesReceived",
                    "to_state": "Leader",
                    "guard_or_effect": "Initialize nextIndex/matchIndex, broadcast initial AppendEntries heartbeat.",
                },
                {
                    "from_state": "Leader",
                    "event": "HigherTermDiscovered",
                    "to_state": "Follower",
                    "guard_or_effect": "Update currentTerm, step down to Follower immediately.",
                },
            ],
            "generative_model_test_executed": True,
        },
        "structure_aware_fuzzing": {
            "target_boundary": "raft_rpc_frame_decoder",
            "fuzz_engine": "libfuzzer",
            "corpus_strategy": "Grammar-based RPC seed corpus mutated across malformed headers, negative terms, and payload sizes.",
            "crash_freedom_verified": True,
            "bounded_recursion_and_memory": True,
            "max_payload_bytes": 1048576,
        },
        "mutation_falsification": {
            "red_green_falsification_verified": True,
            "mutated_invariant": "Invert term comparison from strictly greater to greater-or-equal in RequestVote.",
            "observed_failure_seed_or_counterexample": "Seed 0xCAFE_BABE failed at tick 412: candidate granted vote to lower term.",
        },
        "verdict": {
            "action": "proceed",
            "rationale": "All invariants, seeded DST simulation with virtual clock, state machine model, and structure-aware fuzzing are verified.",
            "revisit_triggers": [
                "Addition of new consensus RPC message types",
                "Modification of election timeout intervals or clock drift models",
            ],
        },
    }


class SimulationGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = make_valid_record()
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_pause_verdict_permits_incomplete_simulation_plan(self):
        record = {
            "target_system": {
                "module_under_test": "distributed_raft_consensus_engine",
                "system_archetype": "distributed_consensus_and_replication",
                "example_based_tests_only_banned": True,
            },
            "verdict": {
                "action": "pause",
                "rationale": "Holding execution while formulating TLA+ state transition matrix and seed PRNG harness.",
                "revisit_triggers": ["Completion of state machine transition definitions"],
            },
        }
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "pause")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_rejecting_example_based_tests(self):
        record = {
            "target_system": {
                "module_under_test": "distributed_raft_consensus_engine",
                "system_archetype": "distributed_consensus_and_replication",
                "example_based_tests_only_banned": True,
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing pull request because critical consensus engine relies exclusively on static example tests.",
                "revisit_triggers": ["Authoring property-based tests with fast-check and seeded DST simulator"],
            },
        }
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")
        self.assertEqual(result["findings"], [])

    def test_example_based_tests_only_fails(self):
        record = make_valid_record()
        record["target_system"]["example_based_tests_only_banned"] = False
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("EXAMPLE_BASED_TESTS_ONLY_NOT_BANNED", codes)

    def test_low_property_runs_or_missing_shrinking_fails(self):
        record = make_valid_record()
        record["property_testing"]["min_test_cases"] = 50
        record["property_testing"]["shrinking_enabled"] = False
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_PROPERTY_RUNS", codes)
        self.assertIn("SHRINKING_DISABLED", codes)

    def test_invalid_or_missing_virtual_clock_fails(self):
        record = make_valid_record()
        record["deterministic_simulation"]["virtual_clock_enabled"] = False
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("VIRTUAL_CLOCK_DISABLED", codes)

    def test_invalid_seed_format_fails(self):
        record = make_valid_record()
        record["deterministic_simulation"]["seed"] = "invalid_non_hex_random_seed"
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_SIMULATION_SEED", codes)

    def test_insufficient_fault_modes_or_duplicate_faults_fails(self):
        record = make_valid_record()
        record["deterministic_simulation"]["fault_injection_matrix"] = [
            {
                "fault_type": "network_packet_loss",
                "probability_or_cadence": 0.05,
                "mitigation_or_invariant": "Quorum election handles loss.",
            },
            {
                "fault_type": "network_packet_loss",
                "probability_or_cadence": 0.10,
                "mitigation_or_invariant": "Duplicate fault type.",
            },
        ]
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_FAULT_INJECTION_MODES", codes)
        self.assertIn("DUPLICATE_FAULT_TYPE", codes)

    def test_impossible_states_not_prevented_fails(self):
        record = make_valid_record()
        record["state_machine_modeling"]["type_level_impossible_states_prevented"] = False
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("IMPOSSIBLE_STATES_NOT_PREVENTED", codes)

    def test_unbounded_fuzz_recursion_or_payload_fails(self):
        record = make_valid_record()
        record["structure_aware_fuzzing"]["bounded_recursion_and_memory"] = False
        record["structure_aware_fuzzing"]["max_payload_bytes"] = 50_000_000
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNBOUNDED_RECURSION_OR_MEMORY", codes)
        self.assertIn("INVALID_MAX_PAYLOAD_BYTES", codes)

    def test_missing_mutation_falsification_fails(self):
        record = make_valid_record()
        record["mutation_falsification"]["red_green_falsification_verified"] = False
        result = simulation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("RED_GREEN_FALSIFICATION_NOT_VERIFIED", codes)

    def test_source_scanner_flags_unseeded_random(self):
        source = """
        function generateJitter() {
            return Math.random() * 100;
        }
        """
        findings = simulation_guard.scan_source_hazards(source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_UNSEEDED_RANDOM_IN_SIMULATION", codes)

    def test_source_scanner_flags_wall_clock_sleep(self):
        source = """
        async function waitElection() {
            await new Promise(r => setTimeout(r, 150));
        }
        """
        findings = simulation_guard.scan_source_hazards(source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_WALL_CLOCK_SLEEP_IN_SIMULATION", codes)

    def test_source_scanner_flags_impossible_state_booleans(self):
        source = """
        interface RequestState {
            isLoading: boolean;
            isError: boolean;
            data: unknown;
        }
        """
        findings = simulation_guard.scan_source_hazards(source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_IMPOSSIBLE_STATE_BOOLEANS", codes)

    def test_source_scanner_flags_tautological_assertions(self):
        source = """
        test("weak assertion test", () => {
            expect(true).toBe(true);
        });
        """
        findings = simulation_guard.scan_source_hazards(source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION", codes)

    def test_source_scanner_accepts_clean_simulation_runner(self):
        source = """
        class DeterministicVirtualClock {
            private currentTime = 0;
            public advance(ms: number): void {
                this.currentTime += ms;
            }
            public now(): number {
                return this.currentTime;
            }
        }
        type State = { type: 'Idle' } | { type: 'Active'; payload: string };
        """
        findings = simulation_guard.scan_source_hazards(source)
        self.assertEqual(findings, [])

    def test_cli_invocation_success_and_failure(self):
        record = make_valid_record()
        repo_root = Path(__file__).resolve().parent.parent
        script_path = repo_root / "scripts" / "simulation_guard.py"
        tmp_record = repo_root / "tests" / "_temp_sim_record.json"

        try:
            tmp_record.write_text(json.dumps(record, indent=2), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script_path), "audit", str(tmp_record), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["record_status"], "complete")

            # Corrupt record and expect exit code 2
            record["property_testing"]["shrinking_enabled"] = False
            tmp_record.write_text(json.dumps(record, indent=2), encoding="utf-8")
            proc_fail = subprocess.run(
                [sys.executable, str(script_path), "audit", str(tmp_record), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_fail.returncode, 2)
            data_fail = json.loads(proc_fail.stdout)
            self.assertEqual(data_fail["record_status"], "incomplete")
        finally:
            if tmp_record.exists():
                tmp_record.unlink()


if __name__ == "__main__":
    unittest.main()
