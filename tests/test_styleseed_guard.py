"""Unit tests for StyleSeed Cognitive Grammar, Token Canon DAG & Spatial Rhythm Guard."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(REPO_ROOT))

from scripts.styleseed_guard import (
    StyleSeedAuditor,
    calculate_contrast_ratio,
    color_euclidean_distance,
    evaluate_styleseed,
    generate_toon_payload,
)


class StyleSeedGuardTests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_contrast_ratio_calculation(self):
        # Black on white: 21:1
        ratio_bw = calculate_contrast_ratio("#000000", "#FFFFFF")
        self.assertAlmostEqual(ratio_bw, 21.0, delta=0.5)

        # White on green 700: >= 4.5
        ratio_green = calculate_contrast_ratio("#FFFFFF", "#15803D")
        self.assertGreaterEqual(ratio_green, 4.5)

        # White on yellow: fail WCAG AA
        ratio_yellow = calculate_contrast_ratio("#FFFFFF", "#FACC15")
        self.assertLess(ratio_yellow, 4.5)

    def test_clean_token_layers_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            clean_tokens = {
                "primitive": {
                    "slate": {"900": "#0F172A", "500": "#64748B"},
                    "blue": {"600": "#2563EB"},
                },
                "semantic": {
                    "background": "#FFFFFF",
                    "surface": "#F8FAFC",
                    "chrome": "#E2E8F0",
                    "foreground": "#0F172A",
                    "mutedForeground": "#64748B",
                    "chromeForeground": "#0F172A",
                    "border": "#CBD5E1",
                    "primary": "#2563EB",
                    "primaryForeground": "#FFFFFF",
                    "accent": "#2563EB",
                    "accentForeground": "#FFFFFF",
                    "focus": "#2563EB",
                    "success": "#15803D",
                    "successForeground": "#FFFFFF",
                    "warning": "#B45309",
                    "warningForeground": "#FFFFFF",
                    "danger": "#DC2626",
                    "dangerForeground": "#FFFFFF",
                },
            }
            summary, findings = auditor.audit_token_layers(clean_tokens, scan_sources=False)
            self.assertEqual(summary["contrast_gate_violations_count"], 0)
            self.assertEqual(summary["circular_alias_violations_count"], 0)
            blocking_findings = [f for f in findings if f["severity"] == "BLOCKING"]
            self.assertEqual(len(blocking_findings), 0)

    def test_primitive_token_leakage_in_component_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            comp_file = root / "Button.tsx"
            comp_file.write_text(
                "export const Button = () => <button style={{ backgroundColor: '#2563EB' }}>Click</button>;",
                encoding="utf-8",
            )
            auditor = StyleSeedAuditor(root)
            summary, findings = auditor.audit_token_layers({}, scan_sources=True)
            self.assertGreaterEqual(summary["primitive_leakage_violations_count"], 1)
            self.assertTrue(any(f["class"] == "PRIMITIVE_TOKEN_LEAKAGE" for f in findings))

    def test_upward_and_circular_aliases_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            circular_tokens = {
                "primitive": {
                    "colorA": "{primitive.colorB}",
                    "colorB": "{primitive.colorA}",
                },
                "semantic": {
                    "bg": "{component.card.bg}",  # Upward aliasing!
                },
                "component": {
                    "card": {"bg": "#ffffff"},
                },
            }
            summary, findings = auditor.audit_token_layers(circular_tokens, scan_sources=False)
            self.assertGreaterEqual(summary["circular_alias_violations_count"], 2)
            self.assertTrue(any(f["class"] == "UPWARD_CIRCULAR_ALIAS" for f in findings))

    def test_pairwise_contrast_gate_deficit_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            tokens = {
                "semantic": {
                    "background": "#FFFFFF",
                    "foreground": "#CBD5E1",  # Light grey on white: fail!
                }
            }
            summary, findings = auditor.audit_token_layers(tokens, scan_sources=False)
            self.assertGreaterEqual(summary["contrast_gate_violations_count"], 1)
            self.assertTrue(any(f["class"] == "PAIRWISE_CONTRAST_DEFICIT" for f in findings))

    def test_spatial_inversion_anomaly_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            inverted_spacing = {
                "roles": {
                    "pageInset": 24,
                    "sectionGap": 16,
                    "stackGap": 32,  # stackGap > sectionGap!
                }
            }
            summary, findings = auditor.audit_spatial_rhythm(inverted_spacing, scan_sources=False)
            self.assertEqual(summary["inversion_anomalies_count"], 1)
            self.assertTrue(any(f["class"] == "SPATIAL_INVERSION_ANOMALY" for f in findings))

    def test_ad_hoc_spatial_slop_in_source_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            card_file = root / "Card.tsx"
            card_file.write_text(
                "export const Card = () => <div className='p-[19px] mt-[13px]'>Card Content</div>;",
                encoding="utf-8",
            )
            auditor = StyleSeedAuditor(root)
            summary, findings = auditor.audit_spatial_rhythm({}, scan_sources=True)
            self.assertGreaterEqual(summary["ad_hoc_spacing_violations_count"], 1)
            self.assertTrue(any(f["class"] == "AD_HOC_SPATIAL_SLOP" for f in findings))

    def test_cognitive_grammar_height_and_radius_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            # In operations-console, control heights must be [28, 32, 36], max radius <= 6
            metrics = {
                "observed_control_heights": [56],  # Cartoon oversized button
                "observed_border_radius": 24,  # Pill radius violates console density
            }
            profile, findings = auditor.audit_cognitive_grammar("operations-console", metrics)
            self.assertEqual(profile["grammar"], "operations-console")
            self.assertGreaterEqual(len(findings), 2)
            self.assertTrue(all(f["class"] == "COGNITIVE_GRAMMAR_MISMATCH" for f in findings))

    def test_s1_longitudinal_drift_metric(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            probes = [
                {"id": "screen-1-dashboard", "accent_color": "#2563EB", "border_radius": 8, "font_family": "Inter", "control_height": 40},
                {"id": "screen-2-users", "accent_color": "#2563EB", "border_radius": 8, "font_family": "Inter", "control_height": 40},
                {"id": "screen-5-billing", "accent_color": "#EC4899", "border_radius": 28, "font_family": "Papyrus", "control_height": 64},
            ]
            summary, findings = auditor.audit_s1_drift(probes, max_drift_threshold=0.20)
            self.assertEqual(summary["status"], "DRIFTING")
            self.assertGreater(summary["max_s1_drift_distance"], 0.20)
            self.assertTrue(any(f["class"] == "S1_LONGITUDINAL_DRIFT_EXCEEDED" for f in findings))

    def test_decisions_ledger_illegal_invariant_waiver_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            ledger = {
                "decisions": [
                    {
                        "id": "D-001",
                        "kind": "exception",
                        "rule": "INV-02-status-not-color-only",
                        "statement": "Allowing color-only indicators in status badge",
                        "scope": {"screens": ["dashboard"]},
                    }
                ]
            }
            summary, findings = auditor.audit_decisions_ledger(ledger)
            self.assertEqual(summary["invariant_waive_attempts_count"], 1)
            self.assertTrue(any(f["class"] == "ILLEGAL_INVARIANT_WAIVER" for f in findings))

    def test_decisions_ledger_unscoped_exception_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auditor = StyleSeedAuditor(root)
            ledger = {
                "decisions": [
                    {
                        "id": "D-002",
                        "kind": "exception",
                        "rule": "CRAFT-control-heights",
                        "statement": "Allowing 32px controls",
                        "scope": {},  # Empty scope!
                    }
                ]
            }
            summary, findings = auditor.audit_decisions_ledger(ledger)
            self.assertEqual(summary["invalid_exceptions_count"], 1)
            self.assertTrue(any(f["class"] == "UNSCOPED_DECISION_EXCEPTION" for f in findings))

    def test_toon_payload_generation(self):
        report = {
            "schema_version": "1.0.0",
            "verdict": "PROCEED",
            "grammar_profile": {"grammar": "operations-console", "density": "compact"},
            "token_layers_summary": {
                "primitive_tokens_count": 20,
                "semantic_tokens_count": 18,
                "contrast_gate_violations_count": 0,
                "primitive_leakage_violations_count": 0,
            },
            "spatial_rhythm_summary": {
                "roles_defined": ["pageInset", "sectionGap"],
                "inversion_anomalies_count": 0,
                "ad_hoc_spacing_violations_count": 0,
            },
            "s1_drift_summary": {
                "status": "ANCHORED",
                "max_s1_drift_distance": 0.02,
            },
            "decisions_ledger_summary": {
                "decisions_count": 2,
                "approved_exceptions_count": 1,
                "invalid_exceptions_count": 0,
            },
            "findings_count": 0,
            "findings": [],
        }
        toon_text = generate_toon_payload(report)
        self.assertIn("styleseed-audit[v1.0.0]:", toon_text)
        self.assertIn("verdict: PROCEED", toon_text)
        self.assertIn("grammar: operations-console", toon_text)

    def test_cli_selftest(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "styleseed_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS: StyleSeed guard selftest green.", res.stdout)


if __name__ == "__main__":
    unittest.main()
