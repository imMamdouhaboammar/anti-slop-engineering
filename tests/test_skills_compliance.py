#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for Universal Skills Invariant Extraction and Compliance Engine."""

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_skill_rules import extract_all_skills
from skills_compliance_engine import SkillsComplianceEngine, Finding


class TestSkillsCompliance(unittest.TestCase):
    def setUp(self):
        self.ledger = extract_all_skills()

    def test_extract_all_46_skills(self):
        """Verify all 46 skills are parsed with non-empty axioms."""
        self.assertGreaterEqual(self.ledger["total_skills"], 46)
        self.assertGreater(self.ledger["total_rules"], 50)

        skills = self.ledger["skills"]
        self.assertIn("type-level-and-ast-slop-gate", skills)
        self.assertIn("paranoid-principal-architect", skills)
        self.assertIn("apple-craft-and-interaction-physics", skills)
        self.assertIn("mandela-guard", skills)

        ast_skill = skills["type-level-and-ast-slop-gate"]
        self.assertEqual(ast_skill["category"], "code_hygiene")
        self.assertEqual(ast_skill["execution_tier"], "DETERMINISTIC")
        self.assertGreaterEqual(len(ast_skill["axioms"]), 1)

    def test_clean_code_passes_gate(self):
        """Clean code should produce a 100/100 score and PASS decision."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_file = tmp_path / "clean_service.ts"
            clean_file.write_text("""
import { z } from "zod";

export const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
});

export type User = z.infer<typeof UserSchema>;

export function getUserDisplayName(user: User): string {
  return user.name.trim();
}
""", encoding="utf-8")

            engine = SkillsComplianceEngine(ledger=self.ledger)
            result = engine.evaluate(target_path=str(tmp_path))

            self.assertEqual(result["overall_score"], 100)
            self.assertEqual(result["decision"], "PASS")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["violations_summary"]["critical"], 0)

    def test_chained_cast_triggers_critical_block(self):
        """Violating AST chained cast rule must fail the gate with exit code 1."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dirty_file = tmp_path / "dirty_service.ts"
            dirty_file.write_text("""
export function unsafeCast(payload: any) {
  const result = payload as unknown as MyCustomType;
  return result;
}
""", encoding="utf-8")

            engine = SkillsComplianceEngine(ledger=self.ledger)
            result = engine.evaluate(target_path=str(tmp_path))

            self.assertLess(result["overall_score"], 100)
            self.assertEqual(result["decision"], "BLOCK_CRITICAL_VIOLATION")
            self.assertEqual(result["exit_code"], 1)
            self.assertGreaterEqual(result["violations_summary"]["critical"], 1)

            ast_res = result["skills"]["type-level-and-ast-slop-gate"]
            self.assertEqual(ast_res["status"], "FAILED")
            self.assertTrue(any(f["rule_id"] == "AST-CHAINED-CAST" for f in ast_res["findings"]))

    def test_dummy_db_triggers_critical_block(self):
        """Violating Demock rule (dummy database in service) must fail the gate."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_file = tmp_path / "storage_client.ts"
            db_file.write_text("""
export function getDbConnection() {
  if (process.env.NODE_ENV === "test") {
    return sqlite3.connect(":memory:");
  }
  return realDbPool();
}
""", encoding="utf-8")

            engine = SkillsComplianceEngine(ledger=self.ledger)
            result = engine.evaluate(target_path=str(tmp_path))

            self.assertEqual(result["decision"], "BLOCK_CRITICAL_VIOLATION")
            self.assertEqual(result["exit_code"], 1)
            demock_res = result["skills"]["demock-guard"]
            self.assertEqual(demock_res["status"], "FAILED")

    def test_timing_attack_triggers_paranoid_block(self):
        """Direct string comparison on security tokens must fail Paranoid rule."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            auth_file = tmp_path / "webhook_auth.ts"
            auth_file.write_text("""
export function verifyWebhook(signature: string, expected: string) {
  return signature === expected;
}
""", encoding="utf-8")

            engine = SkillsComplianceEngine(ledger=self.ledger)
            result = engine.evaluate(target_path=str(tmp_path))

            self.assertEqual(result["exit_code"], 1)
            paranoid_res = result["skills"]["paranoid-principal-architect"]
            self.assertEqual(paranoid_res["status"], "FAILED")
            self.assertTrue(any(f["rule_id"] == "SEC-TIMING-ATTACK" for f in paranoid_res["findings"]))


if __name__ == "__main__":
    unittest.main()
