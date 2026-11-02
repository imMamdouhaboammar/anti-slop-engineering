import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "future_scale_guard.py"


def example_packet():
    return {
        "goal": "Keep the simulation language viable as programs and users grow",
        "horizon": "Multiple product generations and heterogeneous simulation workloads",
        "scenarios": [
            {"id": "large-runs", "stress": "Millions of deterministic events in some programs",
             "basis": "credible", "source": "Product direction: user-authored large simulations",
             "failure_if_unprepared": "Runtime details leak into public language semantics"},
            {"id": "alternate-runtime", "stress": "A second execution engine must consume programs",
             "basis": "credible", "source": "Planned support for heterogeneous runtimes",
             "failure_if_unprepared": "Compiler and runtime become inseparable"},
        ],
        "commitments": [
            {"decision": "Stable semantic IR boundary", "reversibility": "high",
             "failure_cost": "Existing programs require incompatible rewrites",
             "exit_path": "Versioned IR translation and compatibility tests"},
        ],
        "options": [
            {"name": "Couple language semantics to CPython", "now_cost": "Simplest interpreter",
             "future_cost": "Rewrite parser and semantics for another runtime", "selected": False},
            {"name": "Define an independent semantic IR", "now_cost": "Contract and adapter tests",
             "future_cost": "Maintain IR compatibility across engines", "selected": True},
        ],
        "foundations": [
            {"boundary": "Compiler to execution engine", "choice_now": "Versioned semantic IR",
             "future_capacity": "Alternative engine can execute the same semantics",
             "scenario_refs": ["alternate-runtime"], "proof_ref": "engine-spike"},
        ],
        "proofs": [
            {"id": "engine-spike", "method": "Execute golden program through second minimal backend",
             "status": "passed", "evidence": "Synthetic prototype trace and compared results"},
        ],
        "deferred": [
            {"capability": "Distributed execution", "trigger": "Workloads exceed single-host bounds",
             "pathway": "Add scheduler above independent engine boundary"},
        ],
        "decision": {"action": "proceed", "reason": "Preserve execution portability without building a cluster",
                     "revisit_when": "IR prototype diverges or workload constraints change"},
    }


def audit(packet):
    with tempfile.TemporaryDirectory() as directory:
        record = Path(directory) / "record.json"
        record.write_text(json.dumps(packet), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "audit", str(record), "--json"],
                                cwd=ROOT, capture_output=True, text=True, check=False)
        return result, json.loads(result.stdout) if result.stdout else None


def codes(packet):
    result, output = audit(packet)
    return result, {item["code"] for item in output["findings"]} if output else set()


class FutureScaleGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        result, output = audit(example_packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")
        self.assertEqual(output["decision_action"], "proceed")
        self.assertTrue(output["machine_check_only"])

    def test_pause_can_record_unknown_future_without_fabricating_proofs(self):
        packet = {"goal": "Assess unknown regulation", "decision": {
            "action": "pause", "reason": "Authority not accessible", "revisit_when": "Policy published"}}
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["decision_action"], "pause")

    def test_proceed_needs_credible_future_envelope(self):
        packet = example_packet()
        packet["scenarios"] = []
        self.assertIn("MISSING_FUTURE_ENVELOPE", codes(packet)[1])
        packet["scenarios"] = [{**example_packet()["scenarios"][0], "basis": "speculative"}]
        self.assertIn("SPECULATION_ONLY", codes(packet)[1])

    def test_one_verified_irreversible_future_is_enough_without_inventing_more(self):
        packet = example_packet()
        packet["scenarios"] = [packet["scenarios"][1]]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")

    def test_duplicate_scenario_ids_and_broken_references_are_blocked(self):
        packet = example_packet()
        packet["scenarios"][1]["id"] = "large-runs"
        found = codes(packet)[1]
        self.assertIn("DUPLICATE_SCENARIO", found)
        self.assertIn("UNKNOWN_SCENARIO_REF", found)

    def test_irreversible_commitment_needs_exit_path(self):
        packet = example_packet()
        packet["commitments"][0]["exit_path"] = " "
        self.assertIn("MISSING_EXIT_PATH", codes(packet)[1])

    def test_options_need_distinct_alternatives_and_one_selection(self):
        packet = example_packet()
        packet["options"][1]["name"] = "  COUPLE LANGUAGE SEMANTICS TO CPYTHON "
        self.assertIn("DUPLICATE_OPTIONS", codes(packet)[1])
        packet = example_packet()
        packet["options"][0]["selected"] = True
        self.assertIn("INVALID_SELECTION", codes(packet)[1])

    def test_one_viable_option_can_be_explained_by_a_hard_constraint(self):
        packet = example_packet()
        packet["options"] = [packet["options"][1]]
        self.assertIn("MISSING_ALTERNATIVES", codes(packet)[1])
        packet["sole_option_reason"] = "Signed compatibility requirement rules out coupling semantics to one interpreter"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")

    def test_future_proof_cannot_be_only_a_promise(self):
        packet = example_packet()
        packet["proofs"][0]["status"] = "not_run"
        self.assertIn("UNPROVEN_EVOLUTION_PATH", codes(packet)[1])
        packet["proofs"][0]["status"] = "failed"
        self.assertIn("UNPROVEN_EVOLUTION_PATH", codes(packet)[1])

    def test_foundation_requires_known_proof_and_grounded_scenario(self):
        packet = example_packet()
        packet["foundations"][0]["proof_ref"] = "missing"
        self.assertIn("UNKNOWN_PROOF_REF", codes(packet)[1])
        packet = example_packet()
        packet["foundations"][0]["scenario_refs"] = ["not-a-scenario"]
        self.assertIn("UNKNOWN_SCENARIO_REF", codes(packet)[1])

    def test_deferred_work_requires_a_revisit_trigger_and_evolution_path(self):
        packet = example_packet()
        packet["deferred"][0]["trigger"] = ""
        self.assertIn("INVALID_DEFERRAL", codes(packet)[1])

    def test_unexpected_input_types_return_findings_without_crashing(self):
        for field, value in (("scenarios", {}), ("commitments", None), ("options", "no"),
                             ("foundations", [42]), ("proofs", [{"id": []}]),
                             ("deferred", [{"trigger": []}])):
            with self.subTest(field=field):
                packet = example_packet()
                packet[field] = value
                result, output = audit(packet)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIsNotNone(output)

    def test_invalid_json_is_not_a_clean_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{oops", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "audit", str(path), "--json"],
                                    cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(result.stdout)


if __name__ == "__main__":
    unittest.main()
