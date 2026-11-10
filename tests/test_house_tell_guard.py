#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from house_tell_guard import (
    evaluate_commit_sheet,
    generate_template_commit_sheet,
    is_truism_or_generic,
)


class HouseTellGuardTests(unittest.TestCase):
    def test_is_truism_or_generic(self):
        self.assertTrue(is_truism_or_generic("clean modern"))
        self.assertTrue(is_truism_or_generic("beautiful animations throughout"))
        self.assertFalse(is_truism_or_generic("Hero: 300vh canvas disassembly of camera into 9 discrete floating optics"))

    def test_valid_template_passes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sheet_path = Path(tmp_dir) / "commit-sheet.json"
            tpl = generate_template_commit_sheet()
            sheet_path.write_text(json.dumps(tpl), encoding="utf-8")

            report = evaluate_commit_sheet(sheet_path)
            self.assertEqual(report["verdict"], "PROCEED")
            self.assertEqual(len(report["house_tells_broken"]), 2)

    def test_missing_sheet_rejects(self):
        fake_path = Path("/tmp/non_existent_sheet_12345.json")
        report = evaluate_commit_sheet(fake_path)
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(any(f["class"] == "MISSING_COMMIT_SHEET" for f in report["findings"]))

    def test_insufficient_house_tells_rejects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sheet_path = Path(tmp_dir) / "commit-sheet.json"
            tpl = generate_template_commit_sheet()
            tpl["house_tells_broken"] = [{"tell": "glow", "replacement": "shadow"}]  # Only 1
            sheet_path.write_text(json.dumps(tpl), encoding="utf-8")

            report = evaluate_commit_sheet(sheet_path)
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "INSUFFICIENT_HOUSE_TELLS_BROKEN" for f in report["findings"]))

    def test_motion_budget_overflow_rejects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sheet_path = Path(tmp_dir) / "commit-sheet.json"
            tpl = generate_template_commit_sheet()
            tpl["motion_budget"] = ["m1", "m2", "m3", "m4"]  # 4 patterns > 3 allowed
            sheet_path.write_text(json.dumps(tpl), encoding="utf-8")

            report = evaluate_commit_sheet(sheet_path)
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "MOTION_BUDGET_OVERFLOW" for f in report["findings"]))

    def test_cli_selftest(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "house_tell_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()
