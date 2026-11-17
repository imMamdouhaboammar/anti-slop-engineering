# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Unit and behavioral tests for the AST and Type Slop Guard."""
import json
import pathlib
import re
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

    def git(self, *args):
        return subprocess.run(
            ['git', '-c', 'commit.gpgSign=false', '-c', 'core.hooksPath=/dev/null',
             '-C', str(self.repo), *args],
            text=True, capture_output=True, check=True,
        )

    def init_git_repo(self):
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'AST Guard Fixture')
        clean = self.repo / 'clean.ts'
        clean.write_text('export const answer: number = 42;\n')
        self.git('add', 'clean.ts')
        self.git('commit', '-qm', 'initial clean commit')

    def run_diff_guard(self, base):
        return self.run_guard('--repo', str(self.repo), '--base', base, '--json')

    def test_scan_diff_detects_staged_blocker_with_base_head(self):
        self.init_git_repo()
        bad = self.repo / 'bad.ts'
        bad.write_text('export const user = rawData as unknown as User;\n')
        self.git('add', 'bad.ts')
        res = self.run_diff_guard('HEAD')
        self.assertEqual(res.returncode, 0, res.stdout)
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_scan_diff_detects_unstaged_blocker_with_base_head(self):
        self.init_git_repo()
        tracked = self.repo / 'clean.ts'
        tracked.write_text('export const user = rawData as unknown as User;\n')
        res = self.run_diff_guard('HEAD')
        self.assertEqual(res.returncode, 0, res.stdout)
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_scan_diff_detects_committed_blocker_against_parent(self):
        self.init_git_repo()
        bad = self.repo / 'bad.ts'
        bad.write_text('export const user = rawData as unknown as User;\n')
        self.git('add', 'bad.ts')
        self.git('commit', '-qm', 'add chained assertion')
        res = self.run_diff_guard('HEAD~1')
        self.assertEqual(res.returncode, 0, res.stdout)
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_scan_diff_preserves_committed_and_local_findings_with_named_base(self):
        self.init_git_repo()
        self.git('branch', 'scan-base')
        committed = self.repo / 'committed.ts'
        committed.write_text('export const committed = rawData as unknown as User;\n')
        self.git('add', 'committed.ts')
        self.git('commit', '-qm', 'add committed assertion')
        staged = self.repo / 'staged.ts'
        staged.write_text('export const staged = rawData as unknown as User;\n')
        self.git('add', 'staged.ts')
        (self.repo / 'clean.ts').write_text('export const unstaged = rawData as unknown as User;\n')
        (self.repo / 'untracked.ts').write_text('export const untracked = rawData as unknown as User;\n')

        committed.write_text('export const committed = rawData;\n')

        for base, expected in (
            ('scan-base', {'clean.ts', 'committed.ts', 'staged.ts'}),
            ('HEAD', {'clean.ts', 'staged.ts'}),
        ):
            with self.subTest(base=base):
                result = self.run_diff_guard(base)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(
                    {finding['file'] for finding in report['findings']
                     if finding['id'] == 'CHAINED_TYPE_ASSERTION'},
                    expected,
                )

    def test_scan_diff_checks_staged_content_shadowed_by_worktree(self):
        self.init_git_repo()
        path = self.repo / 'clean.ts'
        baseline = path.read_text()
        path.write_text('export const answer = rawData as unknown as number;\n')
        self.git('add', 'clean.ts')
        path.write_text(baseline)

        result = self.run_diff_guard('HEAD')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(
            [(finding['file'], finding['line']) for finding in report['findings']
             if finding['id'] == 'CHAINED_TYPE_ASSERTION'],
            [('clean.ts', 1)],
        )

    def test_scan_diff_clean_tree_passes_with_base_head(self):
        self.init_git_repo()
        res = self.run_diff_guard('HEAD')
        self.assertEqual(res.returncode, 0, res.stdout)
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'PASS')
        self.assertEqual(report['summary']['total_findings'], 0)

    def test_scan_diff_invalid_base_fails_closed(self):
        self.init_git_repo()
        res = self.run_diff_guard('nonexistent-ref-xyz')
        self.assertEqual(res.returncode, 1)
        report = json.loads(res.stdout)
        self.assertIn('error', report)
        self.assertIn('nonexistent-ref-xyz', report['error'])

    def test_version_matches_project_version(self):
        pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
        self.assertIsNotNone(match)
        res = self.run_guard('--version')
        self.assertEqual(res.returncode, 0)
        tokens = res.stdout.strip().split()
        self.assertTrue(tokens, f"Empty --version output: {res.stdout!r}")
        self.assertEqual(
            tokens[-1],
            match.group(1),
            f"ast_slop_guard --version {res.stdout.strip()!r} does not match pyproject.toml version {match.group(1)!r}",
        )

    def test_strict_exit_code_on_blocker(self):
        file_path = self.repo / 'blocker.ts'
        file_path.write_text('const x = val as any as Target;\n')
        res = self.run_guard(str(file_path), '--strict')
        self.assertEqual(res.returncode, 2)

    def test_permits_conditional_spread_with_fallback(self):
        file_path = self.repo / 'spread_fallback.ts'
        file_path.write_text(
            'const a = { ...(condition ? { x: 1 } : fallback) };\n'
            'const b = { ...(condition ? { x: 1 } : { x: 0 }) };\n'
            'const c = { ...(condition ? { timeout: 100 } : { timeout: DEFAULT_TIMEOUT }) };\n'
            'const d = { ...(condition ? customProps : defaultProps) };\n'
            'const e = { ...(condition ? { ...props } : fallback) };\n'
            'const f = { ...(condition ? { a: 1 } : fallback ?? {}) };\n'
            'const g = { ...(condition ? { a: 1 } : (fallback || {})) };\n'
            'const h = { ...(condition ? { x: 1 } : fallback), meta: {} };\n'
            'const i = { ...(condition ? primary : fallback) };\n'
        )
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CONDITIONAL_EMPTY_SPREAD', finding_ids)

    def test_detects_conditional_empty_spread_with_colon_property(self):
        file_path = self.repo / 'spread_colon.ts'
        file_path.write_text('const opts = { ...(timeout ? { timeout: 1000 } : {}) };\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CONDITIONAL_EMPTY_SPREAD', finding_ids)

    def test_permits_exhaustive_switch_guards(self):
        file_path = self.repo / 'exhaustive_switch.ts'
        file_path.write_text(
            'switch (action.type) {\n'
            '  case "add":\n'
            '    return state + action.payload;\n'
            '  default:\n'
            '    const _exhaustive: never = action;\n'
            '    throw new UnhandledActionError(action as UnhandledAction);\n'
            '}\n'
            'function handleShape(shape: Shape) {\n'
            '  switch (shape.kind) {\n'
            '    case "circle": return Math.PI * shape.radius ** 2;\n'
            '    default:\n'
            '      return assertNever(shape as never);\n'
            '  }\n'
            '}\n'
        )
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('UNJUSTIFIED_TYPE_ASSERTION', finding_ids)


    def test_conditional_empty_spread_uses_outer_object_branches(self):
        file_path = self.write_shared_fixture()
        result = self.run_guard(str(file_path), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.finding_lines(result, 'CONDITIONAL_EMPTY_SPREAD'), [1, 2, 3, 4, 5])

    def test_parenthesized_empty_spread_branches(self):
        file_path = self.repo / 'branches.ts'
        file_path.write_text(
            'const opts = { ...(ready ? props : (({}))) };\n'
            'const other = { ...(ready ? ({}) : props) };\n'
            'const safe = { ...(ready ? ({ item: 1 }) : props) };\n'
        )
        result = self.run_guard(str(file_path), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.finding_lines(result, 'CONDITIONAL_EMPTY_SPREAD'), [1, 2])

    def test_default_and_explicit_head_scan_tracked_working_tree(self):
        file_path = self.repo / 'review.ts'
        file_path.write_text('const value = 1;\n')
        subprocess.run(['git', 'init', '-q'], cwd=self.repo, check=True)
        self.commit_fixture()
        file_path.write_text('const value = raw as unknown as User;\n')
        for args in ((), ('--base', 'HEAD')):
            with self.subTest(args=args):
                result = self.run_guard('--repo', str(self.repo), '--strict', '--json', *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.finding_lines(result, 'CHAINED_TYPE_ASSERTION'), [1])

    def test_spread_after_a_multiline_call_closer(self):
        file_path = self.repo / 'continuation.ts'
        file_path.write_text(
            'consume(\n'
            '  1\n'
            '); const options = { ...(ready ? pair : {}) };\n'
        )
        result = self.run_guard(str(file_path), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.finding_lines(result, 'CONDITIONAL_EMPTY_SPREAD'), [3])

    def test_cast_exemption_requires_adjacent_never_proof_for_same_value(self):
        file_path = self.write_shared_fixture()
        result = self.run_guard(str(file_path), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.finding_lines(result, 'UNJUSTIFIED_TYPE_ASSERTION'), [13, 15, 17, 36, 40, 53])

    def test_diff_preserves_source_adjacency_and_absolute_lines(self):
        file_path = self.repo / 'review.ts'
        lines = ['// unchanged'] * 100
        lines[89] = '// SAFETY: the upstream parser validated the user'
        lines[94] = 'switch (action.type) {'
        lines[95] = '  default:'
        lines[96] = '    const verified: never = action;'
        lines[98] = '}'
        file_path.write_text('\n'.join(lines) + '\n')
        subprocess.run(['git', 'init', '-q'], cwd=self.repo, check=True)
        self.commit_fixture()

        lines[9] = 'const _exhaustive: never = raw;'
        lines[79] = 'throw new UnhandledActionError(raw as User);'
        lines[90] = 'const safe = raw as User;'
        lines[97] = '    throw new AuditError(action as User);'
        file_path.write_text('\n'.join(lines) + '\n')
        self.commit_fixture()

        result = self.run_guard('--repo', str(self.repo), '--base', 'HEAD^', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.finding_lines(result, 'UNJUSTIFIED_TYPE_ASSERTION'), [80])

    def write_shared_fixture(self):
        fixture = ROOT / 'tests' / 'fixtures' / 'ast-slop.source.txt'
        file_path = self.repo / 'spread-and-casts.ts'
        file_path.write_bytes(fixture.read_bytes())
        return file_path

    def finding_lines(self, result, finding_id):
        return [f['line'] for f in json.loads(result.stdout)['findings'] if f['id'] == finding_id]

    def commit_fixture(self):
        subprocess.run(['git', 'add', 'review.ts'], cwd=self.repo, check=True)
        subprocess.run(
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
             '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
             'commit', '-qm', 'fixture'],
            cwd=self.repo, check=True,
        )


if __name__ == '__main__':
    unittest.main()
