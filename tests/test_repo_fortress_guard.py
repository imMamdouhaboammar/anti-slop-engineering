# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.repo_fortress_guard import audit_repository, FORBIDDEN_SUPPRESSIONS


class TestRepoFortressGuard(unittest.TestCase):
    def test_forbidden_suppression_regex_matches_anti_patterns(self):
        samples = [
            "+// @ts-ignore",
            "+// @ts-expect-error",
            "+// eslint-disable-next-line",
            "+// oxlint-disable no-floating-promises",
            "+# noqa: E501",
            "+# type: ignore",
            "+const x = y as unknown as User;",
        ]
        for s in samples:
            self.assertTrue(FORBIDDEN_SUPPRESSIONS.search(s), f"Should have matched: {s}")

    def test_forbidden_suppression_regex_ignores_legitimate_code(self):
        legitimate = [
            "// This is a normal comment",
            "const x = y as User;",
            "function test() {}",
            "# regular python comment",
        ]
        for s in legitimate:
            self.assertFalse(FORBIDDEN_SUPPRESSIONS.search(s), f"Should not match: {s}")

    def test_audit_repository_in_empty_tempdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            res = audit_repository(Path(tmpdir))
            self.assertEqual(res["status"], "REWORK")
            self.assertEqual(res["tier1_local_hooks"]["status"], "MISSING")
            self.assertEqual(res["tier2_ci_gate"]["status"], "MISSING")
            self.assertEqual(res["tier3_release_engine"]["status"], "PARTIAL/MISSING")

    def test_audit_repository_fully_fortified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # Tier 1
            (p / "lefthook.yml").write_text("pre-commit:\n", encoding="utf-8")
            (p / "commitlint.config.mjs").write_text("export default {};\n", encoding="utf-8")
            # Tier 2
            workflows_dir = p / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)
            (workflows_dir / "lint-gate.yml").write_text("name: Lint Gate\n", encoding="utf-8")
            # Tier 3
            (p / "release-please-config.json").write_text("{}\n", encoding="utf-8")
            (p / ".release-please-manifest.json").write_text("{}\n", encoding="utf-8")
            (workflows_dir / "release-please.yml").write_text("name: Release\n", encoding="utf-8")

            with patch("scripts.repo_fortress_guard.get_git_diff", return_value=""):
                res = audit_repository(p)
                self.assertEqual(res["status"], "PASS")
                self.assertEqual(res["tier1_local_hooks"]["status"], "HEALTHY")
                self.assertEqual(res["tier2_ci_gate"]["status"], "HEALTHY")
                self.assertEqual(res["tier3_release_engine"]["status"], "HEALTHY")
                self.assertTrue(res["anti_suppression_guard"]["clean_diff"])


if __name__ == "__main__":
    unittest.main()
