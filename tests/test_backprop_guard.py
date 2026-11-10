#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import tempfile
import unittest

from scripts.backprop_guard import (
    backpropagate_finding,
    load_invariant_ledger,
    save_invariant_ledger,
)


class BackpropGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="backprop_test_")
        self.ledger_path = os.path.join(self.temp_dir, "invariant-ledger.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backpropagate_finding_generates_record(self):
        record = backpropagate_finding(
            trigger_error="DEMOCK_SILENT_FALLBACK",
            file_path="src/db/client.ts",
            line=55,
            excerpt="catch { return []; }",
            apply=False
        )
        self.assertEqual(record["trigger_error"], "DEMOCK_SILENT_FALLBACK")
        self.assertEqual(record["upstream_rule_implicated"], "RULE_FAIL_CLOSED_PERSISTENCE")
        self.assertIn("dummy fallback", record["elon_step_question"])
        self.assertEqual(record["ssot_owner"], "AGENTS.md")
        self.assertFalse(record["applied"])

    def test_backpropagate_unknown_error_fallback(self):
        record = backpropagate_finding(
            trigger_error="CUSTOM_API_TIMEOUT",
            file_path="src/api.ts",
            line=10,
            excerpt="timeout = 0",
            apply=False
        )
        self.assertEqual(record["trigger_error"], "CUSTOM_API_TIMEOUT")
        self.assertEqual(record["upstream_rule_implicated"], "RULE_PREVENT_CUSTOM_API_TIMEOUT")
        self.assertIn("Why was CUSTOM_API_TIMEOUT permitted", record["elon_step_question"])

    def test_backpropagate_apply_updates_invariant_ledger(self):
        # Initial empty ledger
        ledger = {"schema_version": "1.0.0", "invariants": []}
        save_invariant_ledger(ledger, self.ledger_path)

        # Patch the ledger path in backprop_guard for this test
        import scripts.backprop_guard as bg
        original_path = bg.INVARIANT_LEDGER_PATH
        bg.INVARIANT_LEDGER_PATH = self.ledger_path
        try:
            record = bg.backpropagate_finding(
                trigger_error="MANDELA_TAUTOLOGY",
                file_path="tests/test_x.py",
                line=20,
                excerpt="assert True",
                apply=True
            )
            self.assertTrue(record["applied"])

            updated_ledger = bg.load_invariant_ledger(self.ledger_path)
            self.assertEqual(len(updated_ledger["invariants"]), 1)
            self.assertEqual(updated_ledger["invariants"][0]["id"], "INV-MANDEL")
        finally:
            bg.INVARIANT_LEDGER_PATH = original_path


if __name__ == "__main__":
    unittest.main()
