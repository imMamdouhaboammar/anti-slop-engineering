# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Unit and behavioral tests for the AST and Type Slop Guard."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'ast_slop_guard.py'


class AstSlopGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_guard(self, *args):
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, text=True, capture_output=True)

    def test_detects_chained_type_assertion(self):
        file_path = self.repo / 'bad_cast.ts'
        file_path.write_text('const user = rawData as unknown as User;\n')
        res = self.run_guard(str(file_path), '--json')
        self.assertEqual(res.returncode, 0)
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_detects_conditional_empty_spread(self):
        file_path = self.repo / 'spread.ts'
        file_path.write_text('const opts = { ...(timeout ? { timeout } : {}) };\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CONDITIONAL_EMPTY_SPREAD', finding_ids)

    def test_detects_array_filter_map_chain(self):
        file_path = self.repo / 'chain.ts'
        file_path.write_text('const emails = users.filter(u => u.active).map(u => u.email);\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('ARRAY_FILTER_MAP_CHAIN', finding_ids)

    def test_detects_reduce_accumulator_copy(self):
        file_path = self.repo / 'reducer.ts'
        file_path.write_text('const out = items.reduce((acc, x) => Object.assign({}, acc, { [x.id]: x }), {});\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('REDUCE_ACCUMULATOR_COPY', finding_ids)

    def test_detects_module_mocking_in_tests(self):
        file_path = self.repo / 'test_service.spec.ts'
        file_path.write_text('import { vi } from "vitest";\nvi.mock("./user-store");\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('MODULE_MOCKING_ORACLE_EROSION', finding_ids)

    def test_detects_ad_hoc_runtime_typeof(self):
        file_path = self.repo / 'narrow.ts'
        file_path.write_text('if (typeof input === "object") { process(input); }\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('RUNTIME_TYPEOF_AD_HOC', finding_ids)

    def test_detects_metaname_shape_slop(self):
        file_path = self.repo / 'types.ts'
        file_path.write_text('export interface UserProfileShape { id: string; }\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('METANAME_SHAPE_SLOP', finding_ids)

    def test_detects_effect_manual_tag_slop(self):
        file_path = self.repo / 'effect_logic.ts'
        file_path.write_text('if (result._tag === "Ready") { handleReady(result); }\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('EFFECT_MANUAL_TAG_SLOP', finding_ids)

    def test_unjustified_type_assertion_requires_safety_comment(self):
        file_path = self.repo / 'unsafe_cast.ts'
        file_path.write_text('const id = rawId as UserId;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('UNJUSTIFIED_TYPE_ASSERTION', finding_ids)

    def test_justified_type_assertion_passes(self):
        file_path = self.repo / 'safe_cast.ts'
        file_path.write_text('// SAFETY: validated by schema upstream\nconst id = rawId as UserId;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('UNJUSTIFIED_TYPE_ASSERTION', finding_ids)

    def test_strict_exit_code_on_blocker(self):
        file_path = self.repo / 'blocker.ts'
        file_path.write_text('const x = val as any as Target;\n')
        res = self.run_guard(str(file_path), '--strict')
        self.assertEqual(res.returncode, 2)


if __name__ == '__main__':
    unittest.main()
