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

from motion_runtime_guard import (
    evaluate_motion_metrics,
    evaluate_motion_record_file,
)


class MotionRuntimeGuardTests(unittest.TestCase):
    def test_clean_production_metrics_proceed(self):
        report = evaluate_motion_metrics(
            fps=58.5,
            dpr=2.0,
            max_longtask_ms=22.0,
            audio_silent=True,
            reduced_motion_present=True,
            is_dev_server=False,
        )
        self.assertEqual(report["verdict"], "PROCEED")
        self.assertEqual(report["findings_count"], 0)

    def test_low_fps_at_dpr2_rejects(self):
        report = evaluate_motion_metrics(
            fps=38.0,
            dpr=2.0,
            max_longtask_ms=20.0,
            audio_silent=True,
            reduced_motion_present=True,
        )
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(any(f["class"] == "SUBPAR_FPS_AT_DPR2" for f in report["findings"]))

    def test_longtask_budget_exceeded_rejects(self):
        report = evaluate_motion_metrics(
            fps=60.0,
            dpr=2.0,
            max_longtask_ms=75.0,  # > 50ms
            audio_silent=True,
            reduced_motion_present=True,
        )
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(any(f["class"] == "LONGTASK_BUDGET_EXCEEDED" for f in report["findings"]))

    def test_unmuted_autoplay_rejects(self):
        report = evaluate_motion_metrics(
            fps=60.0,
            dpr=2.0,
            max_longtask_ms=15.0,
            audio_silent=False,
            reduced_motion_present=True,
        )
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(any(f["class"] == "AUTOPLAY_SOUND_UNMUTED" for f in report["findings"]))

    def test_missing_reduced_motion_rejects(self):
        report = evaluate_motion_metrics(
            fps=60.0,
            dpr=2.0,
            max_longtask_ms=15.0,
            audio_silent=True,
            reduced_motion_present=False,
        )
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(any(f["class"] == "REDUCED_MOTION_COLLAPSE" for f in report["findings"]))

    def test_dev_server_measurement_warns_without_blocking(self):
        report = evaluate_motion_metrics(
            fps=55.0,
            dpr=2.0,
            max_longtask_ms=20.0,
            audio_silent=True,
            reduced_motion_present=True,
            is_dev_server=True,
        )
        self.assertEqual(report["verdict"], "WARNING")
        self.assertTrue(any(f["class"] == "DEV_SERVER_MEASUREMENT_INVALID" for f in report["findings"]))

    def test_cli_selftest(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "motion_runtime_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()
