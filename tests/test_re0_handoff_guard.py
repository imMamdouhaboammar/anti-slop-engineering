#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import tempfile
import unittest

from scripts.re0_handoff_guard import (
    estimate_token_count,
    run_shower_test,
)


class Re0HandoffGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="re0_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_shower_test_passes_clean_note(self):
        clean_note = {
            "schema_version": "1.0.0",
            "goal": "Verify all unit tests in tests/ pass with exit code 0",
            "proven_invariants": [
                {
                    "id": "INV-001",
                    "statement": "381 unit tests passing",
                    "evidence_command": "python3 -m unittest discover -s tests -v",
                    "verification_digest": "verified-green"
                }
            ],
            "negative_corpus": [
                {
                    "discarded_approach": "Ad-hoc regex without AST parser",
                    "cause_of_death": "Failed on nested function blocks",
                    "archive_reference": ".fable/archive/regex-v0"
                }
            ],
            "next_single_action": {
                "action": "Run cargo test in services/anti-slop-rust",
                "target_file": "services/anti-slop-rust/Cargo.toml",
                "verification_command": "cargo test --manifest-path services/anti-slop-rust/Cargo.toml"
            }
        }
        passed, issues = run_shower_test(clean_note)
        self.assertTrue(passed)
        self.assertEqual(len(issues), 0)

    def test_shower_test_fails_excessive_token_count(self):
        bloated_note = {
            "goal": "Test goal",
            "proven_invariants": [{"id": "1", "statement": "a", "evidence_command": "b"}],
            "negative_corpus": [],
            "next_single_action": {"action": "do it", "target_file": "foo.py"},
            "filler": "x" * 8000 # ~2000 tokens > 1500
        }
        passed, issues = run_shower_test(bloated_note)
        self.assertFalse(passed)
        self.assertTrue(any("exceeds NVIDIA 1,500 token budget" in iss for iss in issues))

    def test_shower_test_fails_ungrounded_pronouns(self):
        bad_note = {
            "goal": "Fix the bug in it",
            "proven_invariants": [{"id": "1", "statement": "a", "evidence_command": "b"}],
            "negative_corpus": [],
            "next_single_action": {
                "action": "fix this file",
                "target_file": "unknown"
            }
        }
        passed, issues = run_shower_test(bad_note)
        self.assertFalse(passed)
        self.assertTrue(any("ungrounded pronoun" in iss for iss in issues))

    def test_shower_test_fails_empty_invariants(self):
        missing_inv_note = {
            "goal": "Verify system",
            "proven_invariants": [],
            "negative_corpus": [],
            "next_single_action": {"action": "run test", "target_file": "test.py"}
        }
        passed, issues = run_shower_test(missing_inv_note)
        self.assertFalse(passed)
        self.assertTrue(any("invariants list is empty" in iss for iss in issues))


if __name__ == "__main__":
    unittest.main()
