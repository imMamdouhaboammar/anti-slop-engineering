#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for versioned rule registry and engine-to-catalog-to-skill feedback loop."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import rule_registry
from rule_registry import (
    RULE_REGISTRY_VERSION,
    explain_rule,
    export_rule_catalog_mapping,
    get_all_rule_mappings,
    resolve_rule_mapping,
)


class RuleRegistryTests(unittest.TestCase):
    def setUp(self):
        self.catalog_path = ROOT_DIR / "references" / "anti-pattern-catalog.md"
        self.assertTrue(self.catalog_path.is_file(), "references/anti-pattern-catalog.md must exist")
        catalog_text = self.catalog_path.read_text(encoding="utf-8")
        self.catalog_ids = set(re.findall(r"^\- \*\*([A-Z]+-[0-9]+)", catalog_text, re.MULTILINE))
        self.assertTrue(len(self.catalog_ids) >= 200, "Catalog must define at least 200 patterns")

    def test_version_string(self):
        """Rule registry must declare a semantic version."""
        self.assertRegex(RULE_REGISTRY_VERSION, r"^\d+\.\d+\.\d+$")

    def test_every_mapped_catalog_id_exists_in_markdown_catalog(self):
        """Every mapped catalog ID in the registry must exist in references/anti-pattern-catalog.md."""
        mappings = get_all_rule_mappings()
        self.assertTrue(len(mappings) >= 40, "Registry must map at least 40 canonical engine codes")
        for key, entry in mappings.items():
            catalog_id = entry.get("catalog_id")
            if catalog_id:
                self.assertIn(
                    catalog_id,
                    self.catalog_ids,
                    f"Rule {key} references catalog ID {catalog_id} which does not exist in anti-pattern-catalog.md",
                )

    def test_every_mapped_skill_path_exists_on_disk(self):
        """Every mapped skill_path in the registry must point to an existing SKILL.md."""
        mappings = get_all_rule_mappings()
        for key, entry in mappings.items():
            skill_path_rel = entry.get("skill_path")
            if skill_path_rel:
                abs_path = ROOT_DIR / skill_path_rel
                self.assertTrue(
                    abs_path.is_file(),
                    f"Rule {key} references skill path '{skill_path_rel}' which does not exist on disk",
                )

    def test_native_rust_codes_resolution(self):
        """Native Rust engine codes (BORING-*, DEMOCK-*, ATTENTION-*, TAGORE-*, STYLESEED-*) resolve accurately."""
        sample_codes = [
            ("BORING-KISS-01", "SIM-08", "anti-slop-engineering"),
            ("BORING-DRY-01", "SIM-01", "anti-slop-engineering"),
            ("DEMOCK-001", "TST-01", "demock-guard"),
            ("ATTENTION-WRAPPER-01", "AGT-01", "cognitive-load-and-attention-governor"),
            ("TAGORE-INFLATION-01", "REV-01", "tagore-guard"),
            ("STYLESEED-001", "UI-01", "styleseed-guard"),
            ("COMMENT-NARRATION-01", "SIM-08", "comment-budget-guard"),
        ]
        for code, expected_cat, expected_skill in sample_codes:
            resolved = resolve_rule_mapping(code)
            self.assertTrue(resolved["mapped"], f"Code {code} must be mapped")
            self.assertEqual(resolved["catalog_id"], expected_cat)
            self.assertEqual(resolved["skill"], expected_skill)
            self.assertTrue(resolved["remediation"])
            self.assertTrue((ROOT_DIR / resolved["skill_path"]).is_file())

    def test_native_go_codes_resolution(self):
        """Native Go engine codes (SRE-KISS-*, SRE-DRY-*, SRE-SCALE-*) resolve accurately."""
        sample_codes = [
            ("SRE-KISS-FUNC-LEN", "SRE-01", "anti-slop-engineering"),
            ("SRE-KISS-NESTING", "SRE-01", "anti-slop-engineering"),
            ("SRE-DRY-DUPLICATE", "SRE-03", "anti-slop-engineering"),
            ("SRE-SCALE-FLAT-RETRY", "SRE-08", "anti-slop-engineering"),
            ("SRE-SCALE-SWALLOWED-EXCEPTION", "SRE-10", "anti-slop-engineering"),
        ]
        for code, expected_cat, expected_skill in sample_codes:
            resolved = resolve_rule_mapping(code)
            self.assertTrue(resolved["mapped"], f"Code {code} must be mapped")
            self.assertEqual(resolved["catalog_id"], expected_cat)
            self.assertEqual(resolved["skill"], expected_skill)

    def test_python_guard_rules_resolution(self):
        """Python guard rules across diff, SRE, AST, and record gates resolve accurately."""
        sample_rules = [
            ("KISS_FUNCTION_BLOAT", "SRE-01", "anti-slop-engineering"),
            ("CHAINED_TYPE_ASSERTION", "ARC-10", "type-level-and-ast-slop-gate"),
            ("WCAG_CONTRAST_FAIL", "UI-04", "ui-and-copy-discipline"),
            ("BLOCKING_ASK_PLACEMENT", "AGT-01", "cognitive-load-and-attention-governor"),
            ("CCR_BUDGET_EXCEEDED", "SIM-08", "comment-budget-guard"),
            ("PY-04", "SEC-05", "paranoid-principal-architect"),
        ]
        for rule, expected_cat, expected_skill in sample_rules:
            resolved = resolve_rule_mapping(rule)
            self.assertTrue(resolved["mapped"], f"Rule {rule} must be mapped")
            self.assertEqual(resolved["catalog_id"], expected_cat)
            self.assertEqual(resolved["skill"], expected_skill)

    def test_unmapped_finding_fallback(self):
        """Unmapped finding gracefully returns mapped=False and explicit fallback without hallucination."""
        resolved = resolve_rule_mapping("COMPLETELY_UNKNOWN_CUSTOM_RULE_999")
        self.assertFalse(resolved["mapped"])
        self.assertIsNone(resolved["catalog_id"])
        self.assertIn("Unmapped", resolved["remediation"])

        # With fallback guard supplied
        resolved_guard = resolve_rule_mapping(
            "COMPLETELY_UNKNOWN_RULE_IN_DIFF",
            fallback_guard="diff_guard",
            fallback_severity="BLOCKER",
        )
        self.assertFalse(resolved_guard["mapped"])
        self.assertIsNone(resolved_guard["catalog_id"])
        self.assertEqual(resolved_guard["skill"], "anti-slop-engineering")
        self.assertEqual(resolved_guard["severity"], "BLOCKER")

    def test_explain_rule_function(self):
        """explain_rule produces diagnostic dossier with catalog and skill details."""
        explained = explain_rule("SRE-KISS-FUNC-LEN")
        self.assertTrue(explained["mapped"])
        self.assertEqual(explained["engine_code"], "SRE-KISS-FUNC-LEN")
        self.assertEqual(explained["catalog_id"], "SRE-01")
        self.assertEqual(explained["skill"], "anti-slop-engineering")
        self.assertIn("Decompose", explained["remediation"])
        self.assertTrue(len(explained["catalog_entry"]) > 0)

    def test_audit_runner_normalize_finding_enriches_catalog_and_skill(self):
        """audit_runner normalize_finding enriches findings with catalog_id, skill, and skill_path."""
        import audit_runner
        raw_finding = {
            "rule": "KISS_FUNCTION_BLOAT",
            "file": "src/utils.ts",
            "line": 15,
            "snippet": "function big() { ... }",
        }
        normalized = audit_runner.normalize_finding("sre_guard", raw_finding, {})
        self.assertEqual(normalized["rule"], "KISS_FUNCTION_BLOAT")
        self.assertEqual(normalized["catalog_id"], "SRE-01")
        self.assertEqual(normalized["skill"], "anti-slop-engineering")
        self.assertEqual(normalized["skill_path"], "skills/anti-slop-engineering/SKILL.md")
        self.assertTrue(normalized["mapped"])

    def test_cli_explain_command(self):
        """audit_runner explain CLI command outputs structured JSON and text."""
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "explain", "SRE-KISS-FUNC-LEN", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["catalog_id"], "SRE-01")
        self.assertEqual(data["skill"], "anti-slop-engineering")

        res_text = subprocess.run([sys.executable, script, "explain", "CHAINED_TYPE_ASSERTION"], capture_output=True, text=True)
        self.assertEqual(res_text.returncode, 0)
        self.assertIn("Catalog ID:", res_text.stdout)
        self.assertIn("Skill:", res_text.stdout)


if __name__ == "__main__":
    unittest.main()
