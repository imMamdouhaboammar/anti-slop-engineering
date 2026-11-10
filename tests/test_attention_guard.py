#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Unit Tests for Cognitive Bandwidth & Attention Economy Guard (scripts/attention_guard.py)
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import attention_guard  # noqa: E402


class AttentionGuardTests(unittest.TestCase):

    def test_scannability_metrics_clean(self):
        text = "**Result.** Deploy succeeded. All services active.\n\n→ Next: run smoke tests."
        m = attention_guard.calculate_scannability_metrics(text)
        self.assertEqual(m["words_to_emphasis"], 0)
        self.assertTrue(m["answer_first"])
        self.assertLessEqual(m["longest_wall_words"], 15)
        self.assertGreater(m["landing_per_100w"], 5.0)

    def test_scannability_flags_long_wall_of_text(self):
        # 85 words in one continuous paragraph without bold, anchors or headings
        wall = (
            "In modern software development when building microservices architectures teams often face "
            "multiple competing tradeoffs regarding operational reliability, observability pipelines, "
            "deployment frequencies, continuous integration workflows, container orchestration platforms, "
            "service mesh configurations, and database query optimization strategies across diverse distributed "
            "computing clusters and heterogeneous cloud environments where latency spikes and resource contention "
            "can create cascading outages and catastrophic cascading failure modes across interdependent upstream services "
            "leading to complete customer disruption and high MTTR."
        )
        record = attention_guard.audit_text(wall, max_wall_words=60)
        self.assertEqual(record["status"], 422)
        self.assertEqual(record["code"], "ERR_EXCESSIVE_WALL_OF_TEXT")
        self.assertTrue(any(f["category"] == "COGNITIVE-SCANNABILITY" for f in record["findings"]))

    def test_scannability_flags_time_to_point_delay(self):
        delayed = (
            "We have spent several hours investigating the distributed tracing logs from yesterday morning. "
            "There were several unexpected metrics in the queue worker pool, but after deeper analysis, "
            "**the root cause was connection exhaustion** in the Redis adapter."
        )
        record = attention_guard.audit_text(delayed, max_ttp=20)
        self.assertEqual(record["status"], 422)
        self.assertTrue(any(f["category"] == "COGNITIVE-TIME-TO-POINT" for f in record["findings"]))

    def test_deliverable_purity_flags_opener_wrapper(self):
        deliverable = "Here is the SQL migration for the users table:\n\nCREATE TABLE users (id UUID PRIMARY KEY);"
        pure, reasons = attention_guard.check_deliverable_purity(deliverable)
        self.assertFalse(pure)
        self.assertIn("opener-wrapper", reasons)

    def test_deliverable_purity_flags_closer_offer(self):
        deliverable = "git commit -m 'fix: race condition'\n\nHope this helps! Let me know if you need any adjustments!"
        pure, reasons = attention_guard.check_deliverable_purity(deliverable)
        self.assertFalse(pure)
        self.assertIn("closer-offer", reasons)

    def test_deliverable_purity_flags_lead_in_to_block(self):
        deliverable = "Here is the configuration:\n\n```json\n{\"active\": true}\n```"
        pure, reasons = attention_guard.check_deliverable_purity(deliverable)
        self.assertFalse(pure)
        self.assertTrue(any(r in ("opener-wrapper", "lead-in-to-block") for r in reasons))

    def test_blocking_placement_passes_clean_terminal(self):
        reply = (
            "Before I apply the migration, please review the plan.\n\n"
            "We will add 2 indexes to the orders table.\n\n"
            "Should I proceed with the schema migration?"
        )
        ok, meta = attention_guard.check_blocking_placement(reply)
        self.assertTrue(ok)
        self.assertTrue(meta["is_terminal"])
        self.assertTrue(meta["line_one_flagged"])

    def test_blocking_placement_waives_line_one_for_short_reply(self):
        # Short reply (< 40 words) does not require line 1 flag
        short_reply = "The test build passed.\n\nReady to push?"
        ok, meta = attention_guard.check_blocking_placement(short_reply)
        self.assertTrue(ok)
        self.assertTrue(meta["short_reply"])

    def test_blocking_placement_flags_buried_question(self):
        buried = (
            "Before I proceed, should I run the database reset now?\n\n"
            "Meanwhile, here are some notes on yesterday's benchmark results. "
            "Throughput increased by 15% across all endpoints, and p99 latency dropped "
            "from 120ms to 85ms on the authentication cluster. Everything is stable."
        )
        ok, meta = attention_guard.check_blocking_placement(buried)
        self.assertFalse(ok)
        self.assertFalse(meta["is_terminal"])

    def test_blocking_placement_allows_options_list_after_terminal_question(self):
        with_options = (
            "Confirm the destructive cleanup before I proceed.\n\n"
            "Are you ready to purge the expired test caches?\n"
            "- yes\n"
            "- no\n"
            "- cancel"
        )
        ok, meta = attention_guard.check_blocking_placement(with_options)
        self.assertTrue(ok)
        self.assertTrue(meta["is_terminal"])

    def test_blocking_placement_detects_imperative_ask(self):
        imperative = (
            "Confirm the branch merge before I push to production.\n\n"
            "All unit and integration tests are passing.\n\n"
            "Confirm before I proceed with the release."
        )
        ok, meta = attention_guard.check_blocking_placement(imperative)
        self.assertTrue(ok)
        self.assertTrue(meta["has_ask"])
        self.assertTrue(meta["is_terminal"])

    def test_blocking_placement_accepts_verdict_opener(self):
        verdict = (
            "No — do not deploy this commit.\n\n"
            "The memory leak in the connection pool has not been resolved.\n\n"
            "Should I roll back to v1.5.2?"
        )
        ok, meta = attention_guard.check_blocking_placement(verdict)
        self.assertTrue(ok)
        self.assertTrue(meta["line_one_flagged"])

    def test_working_memory_bounds_flags_list_over_5_items(self):
        long_list = (
            "**Tasks:**\n"
            "- Item 1\n"
            "- Item 2\n"
            "- Item 3\n"
            "- Item 4\n"
            "- Item 5\n"
            "- Item 6\n"
            "- Item 7\n"
        )
        max_len, violations = attention_guard.check_working_memory_bounds(long_list)
        self.assertEqual(max_len, 7)
        self.assertEqual(len(violations), 1)

    def test_cli_invocation_text_and_json(self):
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "attention_guard.py"),
            "--text",
            "**Verdict.** Clean deploy.\n\nAll tests green.",
            "--json",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["code"], "NO_ATTENTION_FINDINGS")
        self.assertEqual(data["remediation"]["action"], "NO_ACTION_REQUIRED")

    def test_cli_fail_on_blocker_exit_code(self):
        # A buried ask triggers blocker finding and exit code 2
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "attention_guard.py"),
            "--text",
            "Should we deploy now?\n\nHere are some extra notes about the server load and the weather.",
            "--fail-on-blocker",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
