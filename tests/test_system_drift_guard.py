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

from system_drift_guard import (
    evaluate_system_drift,
    parse_variant_budget_arg,
    validate_drift_record,
)


class SystemDriftGuardTests(unittest.TestCase):
    def test_parse_variant_budget_arg(self):
        budgets = parse_variant_budget_arg("button=5,select=1,card=2")
        self.assertEqual(budgets["button"], 5)
        self.assertEqual(budgets["select"], 1)
        self.assertEqual(budgets["card"], 2)

        global_budget = parse_variant_budget_arg("3")
        self.assertEqual(global_budget["button"], 3)
        self.assertEqual(global_budget["card"], 3)

    def test_clean_component_passes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "button.tsx"
            p.write_text("""
                export const Button = ({ variant = "primary" }) => {
                    return <button className="btn-primary focus-visible:ring-2">Click</button>;
                };
            """, encoding="utf-8")

            report = evaluate_system_drift(Path(tmp_dir), {"button": 4})
            self.assertEqual(report["verdict"], "PROCEED")
            self.assertEqual(report["entropy_index"], 0.0)

    def test_flags_focus_ring_suppression(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "input.css"
            p.write_text("""
                input.bad {
                    outline: none;
                    border: 1px solid #ccc;
                }
            """, encoding="utf-8")

            report = evaluate_system_drift(Path(tmp_dir), {"button": 4, "input": 3})
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "FOCUS_RING_SUPPRESSED" for f in report["findings"]))

    def test_flags_variant_budget_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "buttons.tsx"
            p.write_text("""
                const b1 = "button-primary";
                const b2 = "button-secondary";
                const b3 = "button-outline";
                const b4 = "button-ghost";
            """, encoding="utf-8")

            report = evaluate_system_drift(Path(tmp_dir), {"button": 2})
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "VARIANT_BUDGET_EXCEEDED" for f in report["findings"]))

    def test_cli_invocation_json(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "system_drift_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()
