#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import subprocess
import sys
import unittest
from pathlib import Path

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from contrast_guard import (
    calculate_contrast_ratio,
    evaluate_contrast,
    parse_color,
    relative_luminance,
    run_selftest,
    scan_file_for_contrast,
)


class ContrastGuardTests(unittest.TestCase):
    def test_parse_color_hex_and_named(self):
        self.assertEqual(parse_color("#FFFFFF"), (255, 255, 255))
        self.assertEqual(parse_color("FFF"), (255, 255, 255))
        self.assertEqual(parse_color("black"), (0, 0, 0))
        self.assertEqual(parse_color("slate-900"), (15, 23, 42))

    def test_parse_color_invalid(self):
        with self.assertRaises(ValueError):
            parse_color("not-a-color")
        with self.assertRaises(ValueError):
            parse_color("#12345")

    def test_relative_luminance_extremes(self):
        self.assertAlmostEqual(relative_luminance((0, 0, 0)), 0.0, places=4)
        self.assertAlmostEqual(relative_luminance((255, 255, 255)), 1.0, places=4)

    def test_contrast_ratio_black_white(self):
        ratio = calculate_contrast_ratio((0, 0, 0), (255, 255, 255))
        self.assertAlmostEqual(ratio, 21.0, places=2)

    def test_evaluate_contrast_pass_and_fail(self):
        pass_res = evaluate_contrast("#FFFFFF", "#1E293B")
        self.assertTrue(pass_res["wcag_aa_normal"])
        self.assertEqual(pass_res["overall_status"], "PASS")

        fail_res = evaluate_contrast("#555555", "#000000")
        self.assertFalse(fail_res["wcag_aa_normal"])
        self.assertFalse(fail_res["wcag_aa_large"])
        self.assertEqual(fail_res["overall_status"], "FAIL")

        large_only = evaluate_contrast("#777777", "#FFFFFF")
        self.assertFalse(large_only["wcag_aa_normal"])
        self.assertTrue(large_only["wcag_aa_large"])
        self.assertEqual(large_only["overall_status"], "PASS_LARGE_ONLY")

    def test_selftest_passes(self):
        self.assertTrue(run_selftest())

    def test_cli_invocation(self):
        script = str(SCRIPTS_DIR / "contrast_guard.py")
        # Direct CLI execution
        res = subprocess.run([sys.executable, script, "#FFFFFF", "#1E293B", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn('"overall_status": "PASS"', res.stdout)

        # Selftest CLI execution
        res_selftest = subprocess.run([sys.executable, script, "--selftest"], capture_output=True, text=True)
        self.assertEqual(res_selftest.returncode, 0)


if __name__ == "__main__":
    unittest.main()
