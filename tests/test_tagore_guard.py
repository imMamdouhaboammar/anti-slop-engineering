#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Unit Tests for Tagore Engineering Discourse & Substance Guard (scripts/tagore_guard.py)
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import tagore_guard  # noqa: E402


class TagoreGuardTests(unittest.TestCase):

    def test_clean_engineering_prose_passes(self):
        clean_text = (
            "We isolated the race condition in the outbox publisher to un-fenced Postgres transactions. "
            "Under 5,000 msg/s throughput, duplicate events spiked by 8.4% when worker pods crashed. "
            "We added distributed idempotency keys via Redis and enforced strict generation fencing. "
            "Benchmark in tests/outbox_test.rs shows duplicate events dropped to 0.00% across 500k messages. "
            "Trade-off: write latency increased by 1.2ms per message due to Redis key acquisition."
        )
        record = tagore_guard.evaluate_tagore_prose(clean_text, "clean_pr.md")
        self.assertEqual(record["status"], 200)
        self.assertEqual(record["metrics"]["verdict"], "PROCEED")
        self.assertGreaterEqual(record["metrics"]["total_score"], 56)
        self.assertGreaterEqual(record["metrics"]["mechanics_subtotal"], 35)
        self.assertGreaterEqual(record["metrics"]["substance_subtotal"], 21)
        self.assertEqual(record["metrics"]["discourse_vector"], "clean")
        self.assertEqual(record["metrics"]["catalog_tells_count"], 0)

    def test_inflated_slop_detected(self):
        inflated_text = (
            "Great question! Here is an overview. I hope this helps!\n"
            "This architectural overhaul serves as an enduring testament to the transformative power "
            "of our groundbreaking microservices suite, marking a pivotal milestone in our evolving landscape. "
            "It streamlines workflows, enhancing performance while fostering developer joy and cultivating collaboration. "
            "At its core, it's not just about speed, it's about unlocking creativity. "
            "- **Resilience:** Reliability is maximized.\n"
            "- **Scalability:** Throughput is enhanced.\n"
            "The future looks bright as we continue our journey toward excellence."
        )
        record = tagore_guard.evaluate_tagore_prose(inflated_text, "inflated.md")
        self.assertIn(record["metrics"]["verdict"], ("REVISE_MECHANICS", "REVISE_SUBSTANCE", "REFUSE"))
        self.assertGreaterEqual(record["metrics"]["catalog_tells_count"], 5)
        pattern_ids = {f["pattern_id"] for f in record["findings"]}
        self.assertIn("T01_SIGNIFICANCE_INFLATION", pattern_ids)
        self.assertIn("T04_PROMOTIONAL_VOCABULARY", pattern_ids)
        self.assertIn("T20_COLLABORATIVE_COMMUNICATION", pattern_ids)

    def test_flattened_soulless_slop_fails_substance_floor(self):
        # Clean grammar and syntax, but passive, subjectless, zero empirical numbers, zero technical stakes
        flattened_text = (
            "The components were updated in the repository. "
            "The configuration files were reviewed by the team. "
            "The functions were tested across multiple environments. "
            "The documentation was written to explain the implementation. "
            "The system is expected to operate as intended."
        )
        record = tagore_guard.evaluate_tagore_prose(flattened_text, "flattened.md")
        # Substance floor is 21/30. This text has zero empirical tokens and zero stakes.
        self.assertLess(record["metrics"]["substance_subtotal"], 21)
        self.assertEqual(record["metrics"]["verdict"], "REVISE_SUBSTANCE")
        self.assertEqual(record["remediation"]["action"], "INJECT_ENGINEERING_SUBSTANCE")

    def test_subtotal_floors_enforce_dual_direction_attack(self):
        # Text with some metrics but heavy slop mechanics
        mixed_text = (
            "This PR serves as an enduring testament to our groundbreaking architecture. "
            "Under 10k req/s load, latency in tests/perf.rs was 12ms. "
            "At its core, it's not just about caching, it's about unlocking developer joy. "
            "In order to achieve this, we delve into the intricate interplay of services."
        )
        record = tagore_guard.evaluate_tagore_prose(mixed_text, "mixed.md")
        self.assertNotEqual(record["metrics"]["verdict"], "PROCEED")
        self.assertTrue(record["metrics"]["catalog_tells_count"] >= 3)

    def test_voice_calibration_profile_computation(self):
        sample = (
            "We run 10,000 simulated iterations in tests/sim.rs with seed 0xDEADBEEF. "
            "Packet loss rates varied from 0.1% to 5.0%. "
            "Under high jitter, p99 latency spiked to 45ms; however, consensus was maintained. "
            "The primary trade-off is memory overhead in the Raft state log."
        )
        profile = tagore_guard.profile_voice(sample)
        self.assertGreater(profile["word_count"], 25)
        self.assertGreater(profile["mean_sentence_length"], 5.0)
        self.assertGreater(profile["empirical_token_ratio"], 0.05)
        self.assertIn("type_token_ratio", profile)

    def test_cli_selftest(self):
        res = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "tagore_guard.py"), "--selftest"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Self-test passed", res.stdout)

    def test_cli_json_and_toon_invocation(self):
        clean_input = (
            "Fixed deadlock in worker pool by acquiring mutexes in strict canonical order. "
            "Benchmark in tests/pool_test.rs shows 0 timeouts over 100k tasks. "
            "Latency is 4.2ms. Trade-off: lock contention increased CPU by 1.8%."
        )
        # JSON test
        res_json = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "tagore_guard.py"), "--text", clean_input, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_json.returncode, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(data["metrics"]["verdict"], "PROCEED")
        self.assertIn("dimensions", data["metrics"])

        # TOON test
        res_toon = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "tagore_guard.py"), "--text", clean_input, "--toon"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res_toon.returncode, 0)
        self.assertIn("```toon [TagoreDiscourseRecord]", res_toon.stdout)


if __name__ == "__main__":
    unittest.main()
