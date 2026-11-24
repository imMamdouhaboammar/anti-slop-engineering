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

    def test_escaped_line_break_keeps_string_context_without_masking_code(self):
        path = self.repo / 'continued.ts'
        path.write_text(
            'const message = "start ' + chr(92) + '\n'
            'val as unknown as T";\n'
            'const real = val as unknown as T;\n'
        )
        result = self.run_guard(str(path), '--json')
        findings = json.loads(result.stdout)['findings']
        self.assertEqual([f['line'] for f in findings if f['id'] == 'CHAINED_TYPE_ASSERTION'], [3])

    def test_chained_assertion_inside_double_quoted_string_not_flagged(self):
        file_path = self.repo / 'msg_double.ts'
        file_path.write_text('const msg = "never use as unknown as here";\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CHAINED_TYPE_ASSERTION', finding_ids)
        self.assertEqual(report['verdict'], 'PASS')

    def test_chained_assertion_inside_single_quoted_string_not_flagged(self):
        file_path = self.repo / 'msg_single.ts'
        file_path.write_text("const msg = 'never use as unknown as here';\n")
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CHAINED_TYPE_ASSERTION', finding_ids)
        self.assertEqual(report['verdict'], 'PASS')

    def test_chained_assertion_inside_template_literal_not_flagged(self):
        file_path = self.repo / 'msg_template.ts'
        file_path.write_text('const msg = `never use as unknown as here`;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CHAINED_TYPE_ASSERTION', finding_ids)
        self.assertEqual(report['verdict'], 'PASS')

    def test_chained_assertion_with_escaped_quote_inside_string_not_flagged(self):
        file_path = self.repo / 'msg_escaped.ts'
        file_path.write_text('const msg = "a \\" as unknown as b";\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_chained_assertion_in_code_still_flagged(self):
        file_path = self.repo / 'real_cast.ts'
        file_path.write_text('const x = v as unknown as T;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_chained_assertion_after_string_literal_still_flagged(self):
        file_path = self.repo / 'after_string.ts'
        file_path.write_text('const msg = "hello"; const x = v as unknown as T;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_regex_after_control_condition_preserves_following_code(self):
        code = (
            "if (ready(check())) /[`]/.test(value);\n"
            "const invalid = raw as unknown as User;\n"
        )
        file_path = self.repo / 'conditional_regex.ts'
        file_path.write_text(code)
        result = self.run_guard(str(file_path), '--json')
        hits = [
            item['line'] for item in json.loads(result.stdout)['findings']
            if item['id'] == 'CHAINED_TYPE_ASSERTION'
        ]
        self.assertEqual(hits, [2])

    def test_regex_after_arrow_does_not_desync_masking(self):
        file_path = self.repo / 'arrow_regex.ts'
        file_path.write_text(
            'const hasBacktick = (s: string) => /`/.test(s);\n'
            'const hasQuote = (s: string) => /"/.test(s); const y = v as unknown as T;\n'
            'const hasCast = (s: string) => /v as unknown as T/.test(s);\n'
            'const x = w as unknown as U;\n'
        )
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        chained_lines = [f['line'] for f in report['findings'] if f['id'] == 'CHAINED_TYPE_ASSERTION']
        self.assertEqual(chained_lines, [2, 4])

    def test_regex_after_default_does_not_desync_masking(self):
        file_path = self.repo / 'default_regex.ts'
        file_path.write_text('export default /"/.source;\nconst x = v as unknown as T;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        chained_lines = [f['line'] for f in report['findings'] if f['id'] == 'CHAINED_TYPE_ASSERTION']
        self.assertEqual(chained_lines, [2])

    def test_chained_assertion_inside_template_interpolation_still_flagged(self):
        file_path = self.repo / 'interp.ts'
        file_path.write_text('const s = `text ${v as unknown as T} end`;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('CHAINED_TYPE_ASSERTION', finding_ids)

    def test_chained_assertion_inside_multiline_template_not_flagged(self):
        file_path = self.repo / 'multiline_template.ts'
        file_path.write_text(
            'const s = `start\n'
            'as unknown as\n'
            'end`;\n'
            'const x = v as unknown as T;\n'
        )
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        chained_lines = [f['line'] for f in report['findings'] if f['id'] == 'CHAINED_TYPE_ASSERTION']
        self.assertEqual(chained_lines, [4])

    def test_typeof_inside_string_not_flagged_but_real_typeof_flagged(self):
        file_path = self.repo / 'typeof_mask.ts'
        file_path.write_text(
            'const msg = \'typeof a === "object"\'; if (typeof b === "object") { run(); }\n'
        )
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        typeof_hits = [f for f in report['findings'] if f['id'] == 'RUNTIME_TYPEOF_AD_HOC']
        self.assertEqual(len(typeof_hits), 1)

    def test_chained_assertion_inside_comment_not_flagged(self):
        file_path = self.repo / 'comment_mask.ts'
        file_path.write_text('const y = 1; // avoid "v as unknown as T"\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('CHAINED_TYPE_ASSERTION', finding_ids)
        self.assertEqual(report['verdict'], 'PASS')

    def test_regex_with_backtick_does_not_desync_masking(self):
        file_path = self.repo / 'regex_backtick.ts'
        file_path.write_text('const re = /`/;\nconst x = v as unknown as T;\n')
        res = self.run_guard(str(file_path), '--json')
        report = json.loads(res.stdout)
        chained_lines = [f['line'] for f in report['findings'] if f['id'] == 'CHAINED_TYPE_ASSERTION']
        self.assertEqual(chained_lines, [2])

    def test_committed_index_and_worktree_use_their_own_full_literal_context(self):
        def git(*args):
            return subprocess.run(
                ['git', *args], cwd=self.repo, text=True, capture_output=True, check=True
            ).stdout.strip()

        git('init', '-q')
        git('config', 'user.name', 'AST guard fixture')
        git('config', 'user.email', 'ast-guard@example.invalid')
        paths = [self.repo / name for name in ('committed.ts', 'staged.ts', 'worktree.ts')]
        content = 'const message = ' + chr(96) + '\n' + 'sample text\n' * 5 + 'sample only\n' + chr(96) + ';\n'
        for path in paths:
            path.write_text(content)
        git('add', '.')
        git('commit', '-qm', 'long template baseline')
        baseline = git('rev-parse', 'HEAD')
        for index, path in enumerate(paths):
            path.write_text(content.replace('sample only', 'val as unknown as T'))
            if index < 2:
                git('add', path.name)
            if index == 0:
                git('commit', '-qm', 'mention a cast inside a template')
        result = self.run_guard('--repo', str(self.repo), '--base', baseline, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['findings'], [])

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


class AstCliSurfaceTests(unittest.TestCase):
    """User-facing CLI surface: prog name and common file selection."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_guard(self, *args):
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, text=True, capture_output=True)

    def _write(self, name):
        target = self.repo / name
        target.write_text('export const value: number = 1;\n', encoding='utf-8')
        return target

    def test_help_uses_user_facing_prog_name(self):
        result = self.run_guard('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('usage: anti-slop-engineering ast', result.stdout)
        self.assertNotIn('ast_slop_guard.py', result.stdout)

    def test_multiple_positional_files_are_scanned(self):
        first = self._write('a.ts')
        second = self._write('b.ts')
        result = self.run_guard(str(first), str(second), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['mode'], 'files')
        self.assertIn('a.ts', report['target'])
        self.assertIn('b.ts', report['target'])

    def test_files_flag_matches_positional_surface(self):
        first = self._write('a.ts')
        second = self._write('b.ts')
        result = self.run_guard('--files', str(first), str(second), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['mode'], 'files')
        self.assertIn('a.ts', report['target'])
        self.assertIn('b.ts', report['target'])

    def test_single_positional_file_behavior_unchanged(self):
        only = self._write('a.ts')
        result = self.run_guard(str(only), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['mode'], 'file')


if __name__ == '__main__':
    unittest.main()
