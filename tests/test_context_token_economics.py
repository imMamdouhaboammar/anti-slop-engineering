# SPDX-License-Identifier: MIT
"""Verification of the offline context and token economics example."""
import pathlib
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = runpy.run_path(str(
    ROOT / "skills" / "context-window-and-token-economics-architect" / "examples" / "refund_workflow.py"
))
retrieve = EXAMPLE["retrieve"]
render_context = EXAMPLE["render_context"]


class ContextTokenEconomicsTests(unittest.TestCase):
    def setUp(self):
        self.cache = {}

    def test_warm_result_keeps_source_and_expected_answer(self):
        args = ("tenant-a", "r1", "refund:read", "refund-v1", self.cache)
        self.assertEqual(retrieve(*args), {"status": "ok", "days": 30, "source": "refund-policy:r1"})
        self.assertIs(retrieve(*args), self.cache[args[:4]])

    def test_revision_and_access_changes_require_new_evidence(self):
        retrieve("tenant-a", "r1", "refund:read", "refund-v1", self.cache)
        revised = retrieve("tenant-a", "r2", "refund:read", "refund-v1", self.cache)
        self.assertEqual(revised, {"status": "ok", "days": 14, "source": "refund-policy:r2"})
        self.assertEqual(retrieve("tenant-a", "r1", "revoked", "refund-v1", self.cache),
                         {"status": "no_evidence"})
        self.assertEqual(retrieve("tenant-b", "r1", "refund:read", "refund-v1", self.cache),
                         {"status": "no_evidence"})

    def test_schema_revision_never_reuses_previous_cache_entry(self):
        first = retrieve("tenant-a", "r2", "refund:read", "refund-v1", self.cache)
        second = retrieve("tenant-a", "r2", "refund:read", "refund-v2", self.cache)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_narrowed_context_fits_budget_and_carries_required_evidence(self):
        source = EXAMPLE["POLICIES"][("tenant-a", "r2")]
        full = render_context(source, include_full_policy=True)
        narrow = render_context(source, include_full_policy=False)
        self.assertGreater(len(full.split()), 20)
        self.assertLessEqual(len(narrow.split()), 20)
        self.assertIn("refund-policy:r2", narrow)
        self.assertIn("14 days", narrow)
