#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_runner import (
    generate_audit_markdown,
    get_next_audit_file,
    handle_mode,
    load_settings,
    save_settings,
)


class AuditRunnerTests(unittest.TestCase):
    def test_mode_management(self):
        # Setting mode to during
        ret = handle_mode(["during"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "during")

        # Setting mode to after
        ret = handle_mode(["after"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "after")

        # Invalid mode returns 2
        ret = handle_mode(["invalid_mode"])
        self.assertEqual(ret, 2)

    def test_generate_audit_markdown(self):
        findings = [
            {
                "id": "FINDING-001",
                "guard": "diff_guard",
                "rule": "SEVEN-GATES",
                "severity": "BLOCKER",
                "file": "src/index.ts",
                "line": 10,
                "message": "Direct modification without contract",
                "snippet": "const a = 1;",
                "remediation": "Follow Gate 1 contract",
            },
            {
                "id": "FINDING-002",
                "guard": "contrast_guard",
                "rule": "WCAG-2.2",
                "severity": "MEDIUM",
                "file": "src/App.tsx",
                "line": 42,
                "message": "Low contrast: #777 on white",
                "snippet": "<div className='text-[#777] bg-white'>",
                "remediation": "Increase contrast",
            }
        ]
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_test.md"
        try:
            content = generate_audit_markdown(findings, tmp_file)
            self.assertIn("# Anti-Slop Engineering Audit Report", content)
            self.assertIn("FINDING-001", content)
            self.assertIn("BLOCKER", content)
            self.assertIn("WCAG-2.2", content)
            self.assertTrue(tmp_file.exists())
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_cli_invocation(self):
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "mode"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Current anti-slop-engineering mode:", res.stdout)


if __name__ == "__main__":
    unittest.main()
