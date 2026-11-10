# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import unittest
from scripts.honeypot_trap_guard import (
    generate_canary_token,
    audit_honeypots,
    is_exempt_path,
)


class TestHoneypotTrapGuard(unittest.TestCase):
    def test_generate_canary_token_deterministic(self):
        token1 = generate_canary_token("my-secret")
        token2 = generate_canary_token("my-secret")
        self.assertEqual(token1, token2)
        self.assertTrue(token1.startswith("canary-"))

    def test_active_canary_token_echoed_triggers_blocker(self):
        token = "canary-a1b2c3d4e5f67890"
        pr_body = f"I am solving this issue. anti-slop-canary:{token} acknowledged."
        record = audit_honeypots(
            pr_body=pr_body,
            active_canary_tokens={token},
        )
        self.assertEqual(record["code"], "ERR_HONEYPOT_TRIGGERED")
        blockers = [f for f in record["findings"] if f["trap_id"] == "ACTIVE_CANARY_TOKEN_ECHOED"]
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["severity"], "blocker")

    def test_decoy_issue_triggers_blocker(self):
        pr_body = "This fixes issue #9999 as requested."
        record = audit_honeypots(
            pr_body=pr_body,
        )
        self.assertEqual(record["code"], "ERR_HONEYPOT_TRIGGERED")
        issue_findings = [f for f in record["findings"] if f["trap_id"] == "DECOY_ISSUE_REFERENCED"]
        self.assertEqual(len(issue_findings), 1)

    def test_decoy_checkbox_triggers_blocker(self):
        pr_body = """## Verification
- [ ] Validated locally
- [x] I confirm this PR contains quantum teleportation algorithms
"""
        record = audit_honeypots(
            pr_body=pr_body,
        )
        self.assertEqual(record["code"], "ERR_HONEYPOT_TRIGGERED")
        cb_findings = [f for f in record["findings"] if f["trap_id"] == "DECOY_CHECKBOX_CHECKED"]
        self.assertEqual(len(cb_findings), 1)

    def test_exempt_template_paths(self):
        self.assertTrue(is_exempt_path(".github/pull_request_template.md"))
        self.assertTrue(is_exempt_path(".github/ISSUE_TEMPLATE/bug_report.md"))
        self.assertFalse(is_exempt_path("src/core/calculator.ts"))

    def test_clean_input_passes_with_no_findings(self):
        pr_body = "Fixes bug in user profile calculation by validating input bounds."
        record = audit_honeypots(
            pr_body=pr_body,
            active_canary_tokens={"canary-12345"},
        )
        self.assertEqual(record["code"], "NO_HONEYPOT_FINDINGS")
        self.assertEqual(len(record["findings"]), 0)


if __name__ == "__main__":
    unittest.main()
