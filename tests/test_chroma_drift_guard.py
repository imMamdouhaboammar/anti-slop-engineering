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

from chroma_drift_guard import (
    evaluate_chroma_drift,
    is_cream_reflex,
    is_purple_blue_gradient,
    parse_color_token,
    rgb_to_oklch,
)


class ChromaDriftGuardTests(unittest.TestCase):
    def test_rgb_to_oklch_black_and_white(self):
        l_black, c_black, _ = rgb_to_oklch(0, 0, 0)
        self.assertAlmostEqual(l_black, 0.0, places=2)
        self.assertAlmostEqual(c_black, 0.0, places=2)

        l_white, c_white, _ = rgb_to_oklch(255, 255, 255)
        self.assertAlmostEqual(l_white, 1.0, places=2)
        self.assertAlmostEqual(c_white, 0.0, places=2)

    def test_parse_color_token(self):
        c1 = parse_color_token("#1E293B")
        self.assertIsNotNone(c1)
        self.assertTrue(0.0 <= c1[0] <= 1.0)

        c2 = parse_color_token("oklch(0.55 0.12 45)")
        self.assertIsNotNone(c2)
        self.assertAlmostEqual(c2[0], 0.55, places=2)
        self.assertAlmostEqual(c2[1], 0.12, places=2)

    def test_cream_reflex_detection(self):
        # Warm cream sample
        cream = (0.92, 0.03, 60.0)
        self.assertTrue(is_cream_reflex(cream))

        # Distinct saturated color
        vibrant = (0.55, 0.18, 35.0)
        self.assertFalse(is_cream_reflex(vibrant))

    def test_purple_blue_gradient_detection(self):
        # AI default purple-blue
        stops_ai = [(0.5, 0.15, 260.0), (0.6, 0.18, 280.0)]
        self.assertTrue(is_purple_blue_gradient(stops_ai))

        # Non-AI gradient
        stops_clean = [(0.5, 0.15, 35.0), (0.6, 0.18, 45.0)]
        self.assertFalse(is_purple_blue_gradient(stops_clean))

    def test_flags_cheerful_drift(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "style.css"
            p.write_text("body { background-color: #3b82f6; }", encoding="utf-8")

            report = evaluate_chroma_drift(
                Path(tmp_dir),
                target_l=None,
                target_c=0.02,
                max_delta=0.03,
            )
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "CHEERFUL_DRIFT" for f in report["findings"]))

    def test_cli_invocation_selftest(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "chroma_drift_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()
