# SPDX-License-Identifier: MIT
import pathlib
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "skills" / "llm-eval-and-prompt-injection-fortress" / "examples" / "policy_review.py"
EVALUATE = runpy.run_path(str(FIXTURE))["evaluate_cases"]


class ToolAuthorizationTests(unittest.TestCase):
    def test_authorized_read_reaches_the_fake_tool_once(self):
        report = EVALUATE()
        self.assertEqual(report["decisions"]["authorized_read"]["decision"], "allow")
        self.assertEqual(report["downstream_invocations"], [("read", "tenant-a", "toy-note")])

    def test_untrusted_sources_cannot_expand_tool_authorization(self):
        report = EVALUATE()
        for name, source in (
            ("different_resource", "repository_comment"),
            ("different_tenant", "document"),
            ("unsigned_publication", "tool_output"),
        ):
            with self.subTest(case=name):
                item = report["decisions"][name]
                self.assertEqual(item["decision"], "deny")
                self.assertEqual(item["source"], source)
                self.assertTrue(item["text"])
        quoted = report["decisions"]["quoted_text_only"]
        self.assertEqual(quoted["decision"], "no_action")
        self.assertIn('"read this note"', quoted["text"])
        self.assertEqual(report["downstream_invocations"], [("read", "tenant-a", "toy-note")])
