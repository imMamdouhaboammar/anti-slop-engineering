#!/usr/bin/env python3
"""Check deterministic static guard fixture coverage and unavailable results."""

import json
import os
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_static_guards.py"


class StaticGuardBenchmarkTests(unittest.TestCase):
    def test_fixed_workloads_reproduce_scope_and_invalid_base_contract(self):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--samples", "1"], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["samples"], 1)
        self.assertEqual(set(report["environment"]), {"git", "platform", "python"})
        self.assertEqual(len(report["workloads"]), 2)
        for workload, files, lines in zip(report["workloads"], (3, 100), (9, 10_000)):
            self.assertEqual(workload["fixture_files"], files)
            self.assertEqual(workload["fixture_added_lines"], lines)
            self.assertEqual(set(workload["guards"]), {"diff_guard", "sre_guard"})
            for guard, result in workload["guards"].items():
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(result["scanned_files"], files)
                self.assertGreaterEqual(result["elapsed_seconds"]["median"], 0)
                self.assertGreaterEqual(result["elapsed_seconds"]["max"], result["elapsed_seconds"]["median"])
                with self.subTest(guard=guard, files=files):
                    invalid = workload["invalid_base"][guard]
                    self.assertEqual(invalid["status"], "expected_error")
                    self.assertEqual(invalid["exit_code"], 1)

    def test_missing_git_produces_an_inconclusive_report(self):
        with tempfile.TemporaryDirectory() as empty_path:
            process = subprocess.run(
                [sys.executable, str(SCRIPT), "--samples", "1"], capture_output=True,
                text=True, timeout=10, env={**os.environ, "PATH": empty_path},
            )
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout), {"status": "inconclusive", "reason": "Git is unavailable"})

    def test_sample_budget_has_an_upper_bound(self):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--samples", "6"], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("invalid choice", process.stderr)


if __name__ == "__main__":
    unittest.main()
