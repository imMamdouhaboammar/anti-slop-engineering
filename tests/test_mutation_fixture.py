import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mutation_fixture.py"


class MutationFixtureTests(unittest.TestCase):
    def run_fixture(self, *flags):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *flags], capture_output=True,
            text=True, check=False, timeout=15,
        )

    def test_replays_real_mutants_from_a_seed(self):
        command = ["--seed", "42"]
        first = self.run_fixture(*command)
        second = self.run_fixture(*command)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        result = json.loads(first.stdout)
        self.assertEqual(result, json.loads(second.stdout))
        self.assertEqual(result["baseline"], "passed")
        self.assertEqual(result["score"], {"killed": 1, "evaluated": 2})
        states = {item["mutant"]: item["status"] for item in result["results"]}
        self.assertEqual(states, {
            "condition": "killed", "return": "survived", "invalid_ast": "invalid",
            "unavailable": "inconclusive", "timeout": "inconclusive",
        })

    def test_arguments_cannot_select_a_script_or_workspace(self):
        command = self.run_fixture("--source", "user_project.py")
        self.assertEqual(command.returncode, 2)
        self.assertEqual(command.stdout, "")
        self.assertIn("unrecognized arguments", command.stderr)

    def test_invalid_baseline_stops_the_suite(self):
        spec = importlib.util.spec_from_file_location("mutation_fixture_test", SCRIPT)
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        observed = []

        def runner(case):
            observed.append(case)
            return "failed"

        result = fixture.evaluate(42, runner)
        self.assertEqual(observed, ["baseline"])
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["score"], {"killed": 0, "evaluated": 0})
