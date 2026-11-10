#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import tempfile
import unittest

from scripts.reduction_guard import (
    append_ledger_entry,
    audit_source_reduction,
    compute_calibration,
    read_ledger,
)


class ReductionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="reduction_test_")
        self.ledger_path = os.path.join(self.temp_dir, "add-back-ledger.jsonl")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_remove_and_addback(self):
        append_ledger_entry("remove", "legacy_auth_v1", "src/auth.ts", "Deprecated", self.ledger_path)
        append_ledger_entry("add-back", "legacy_auth_v1", "src/auth.ts", "Downstream client needed it", self.ledger_path)

        entries = read_ledger(self.ledger_path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["event"], "remove")
        self.assertEqual(entries[1]["event"], "add-back")

    def test_compute_calibration_rates(self):
        # 1. Baseline
        stats = compute_calibration(self.ledger_path)
        self.assertEqual(stats["calibration_status"], "BASELINE")
        self.assertEqual(stats["verdict"], "INSUFFICIENT_DATA")

        # 2. Timid (< 10%)
        for i in range(20):
            append_ledger_entry("remove", f"item_{i}", ledger_path=self.ledger_path)
        append_ledger_entry("add-back", "item_0", ledger_path=self.ledger_path) # 1 / 20 = 5%

        stats = compute_calibration(self.ledger_path)
        self.assertEqual(stats["calibration_status"], "TIMID_BELOW_10_PERCENT")
        self.assertEqual(stats["verdict"], "UNDER_DELETING")
        self.assertAlmostEqual(stats["addback_rate"], 0.05)

        # 3. Optimal (10% - 25%)
        append_ledger_entry("add-back", "item_1", ledger_path=self.ledger_path)
        append_ledger_entry("add-back", "item_2", ledger_path=self.ledger_path) # 3 / 20 = 15%

        stats = compute_calibration(self.ledger_path)
        self.assertEqual(stats["calibration_status"], "OPTIMAL_10_TO_25_PERCENT")
        self.assertEqual(stats["verdict"], "CALIBRATED")
        self.assertAlmostEqual(stats["addback_rate"], 0.15)

        # 4. Reckless (> 35%)
        for i in range(3, 10):
            append_ledger_entry("add-back", f"item_{i}", ledger_path=self.ledger_path) # 10 / 20 = 50%

        stats = compute_calibration(self.ledger_path)
        self.assertEqual(stats["calibration_status"], "RECKLESS_ABOVE_35_PERCENT")
        self.assertEqual(stats["verdict"], "OVER_DELETING")

    def test_audit_source_flags_speculative_params_and_todos(self):
        code_file = os.path.join(self.temp_dir, "bad_code.py")
        with open(code_file, "w", encoding="utf-8") as fh:
            fh.write("""
def calculate_quote(amount, _unused=None):
    # TODO(future): support multiple currencies
    return amount * 1.2
""")

        findings = audit_source_reduction(code_file)
        self.assertEqual(len(findings), 2)
        steps = [f["step"] for f in findings]
        self.assertIn("2_DELETE_PART_OR_PROCESS", steps)
        self.assertIn("1_QUESTION_REQUIREMENT", steps)

    def test_audit_source_clean_code_passes(self):
        clean_file = os.path.join(self.temp_dir, "clean_code.py")
        with open(clean_file, "w", encoding="utf-8") as fh:
            fh.write("""
def calculate_quote(amount: float) -> float:
    return amount * 1.2
""")

        findings = audit_source_reduction(clean_file)
        self.assertEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
