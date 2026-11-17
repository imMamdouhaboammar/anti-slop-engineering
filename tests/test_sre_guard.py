# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Behavioral tests for the Google SRE Guard."""
import contextlib
import io
import json
import pathlib
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'sre_guard.py'


def git(path, *args):
    return subprocess.run(['git', *args], cwd=path, text=True, capture_output=True, check=True).stdout.strip()


class SreGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        git(self.repo, 'init', '-q')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'src').mkdir()
        (self.repo / 'tests').mkdir()
        (self.repo / 'src' / 'worker.py').write_text('def execute():\n    return 42\n')
        (self.repo / 'tests' / 'test_worker.py').write_text('def test_execute():\n    assert 42 == 42\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'initial')

    def tearDown(self):
        self.temp.cleanup()

    def run_sre(self, *extra):
        cmd = [sys.executable, str(SCRIPT), '--repo', str(self.repo), *extra]
        res = subprocess.run(cmd, text=True, capture_output=True)
        report = None
        if '--json' in extra and res.stdout.strip().startswith('{'):
            report = json.loads(res.stdout)
        return res, report

    def test_flags_kiss_deep_nesting(self):
        code = (
            "def deeply_nested(a, b, c, d, e):\n"
            "    if a:\n"
            "        for item in b:\n"
            "            while c:\n"
            "                try:\n"
            "                    if d:\n"
            "                        return e\n"
            "                except Exception:\n"
            "                    pass\n"
        )
        (self.repo / 'src' / 'nested.py').write_text(code)
        git(self.repo, 'add', 'src/nested.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        self.assertEqual(res.returncode, 0)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('KISS_DEEP_NESTING', finding_ids)

    def test_flags_kiss_function_bloat(self):
        long_func = "def long_routine():\n" + "\n".join(f"    x{i} = {i}" for i in range(90)) + "\n    return x89\n"
        (self.repo / 'src' / 'bloated.py').write_text(long_func)
        git(self.repo, 'add', 'src/bloated.py')
        res, report = self.run_sre('--base', 'HEAD', '--json', '--max-function-lines', '80')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('KISS_FUNCTION_BLOAT', finding_ids)

    def test_flags_dry_code_duplication_across_files(self):
        dup_block = (
            "    val = sanitize(raw_input)\n"
            "    record = db.query(val)\n"
            "    audit_log(record.id)\n"
            "    return record.serialize()\n"
        )
        (self.repo / 'src' / 'service_a.py').write_text(f"def handler_a(raw_input):\n{dup_block}")
        (self.repo / 'src' / 'service_b.py').write_text(f"def handler_b(raw_input):\n{dup_block}")
        git(self.repo, 'add', 'src/service_a.py', 'src/service_b.py')
        res, report = self.run_sre('--base', 'HEAD', '--json', '--min-dup-lines', '4')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('DRY_CODE_DUPLICATION', finding_ids)

    def test_permits_damp_duplication_in_test_files(self):
        dup_block = (
            "    user = create_mock_user()\n"
            "    token = generate_test_token(user)\n"
            "    client = create_test_client(token)\n"
            "    assert client is not None\n"
        )
        (self.repo / 'tests' / 'test_auth.py').write_text(f"def test_one():\n{dup_block}")
        (self.repo / 'tests' / 'test_api.py').write_text(f"def test_two():\n{dup_block}")
        git(self.repo, 'add', 'tests/test_auth.py', 'tests/test_api.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('DRY_CODE_DUPLICATION', finding_ids)

    def test_flags_yagni_speculative_comment(self):
        (self.repo / 'src' / 'future.py').write_text(
            "def connect():\n"
            "    # TODO(future): support Redis cluster\n"
            "    return True\n"
        )
        git(self.repo, 'add', 'src/future.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('YAGNI_SPECULATIVE_COMMENT', finding_ids)

    def test_flags_yagni_dead_speculative_flag(self):
        (self.repo / 'src' / 'dead.py').write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
        )
        git(self.repo, 'add', 'src/dead.py')
        res, report = self.run_sre('--base', 'HEAD', '--json', '--strict')
        self.assertEqual(res.returncode, 2)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('YAGNI_DEAD_SPECULATIVE_FLAG', finding_ids)

    def test_strict_diff_does_not_block_on_pre_existing_dead_flag(self):
        dead = self.repo / 'src' / 'dead.py'
        dead.write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
        )
        git(self.repo, 'add', 'src/dead.py')
        git(self.repo, 'commit', '-qm', 'add dead flag')
        dead.write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
            "# comment only\n"
        )
        res, report = self.run_sre('--base', 'HEAD', '--json', '--strict')
        self.assertEqual(res.returncode, 0)
        matches = [f for f in report['findings'] if f['id'] == 'YAGNI_DEAD_SPECULATIVE_FLAG']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['severity'], 'blocker')
        self.assertIs(matches[0]['in_active_diff'], False)
        self.assertEqual(report['summary']['blockers'], 1)
        self.assertGreaterEqual(report['summary']['total_findings'], 1)
        res, report = self.run_sre('--base', 'HEAD', '--json')
        self.assertEqual(res.returncode, 0)
        self.assertIn(
            'YAGNI_DEAD_SPECULATIVE_FLAG',
            [f['id'] for f in report['findings']],
        )

    def test_strict_implicit_head_diff_does_not_block_on_pre_existing_dead_flag(self):
        dead = self.repo / 'src' / 'dead.py'
        dead.write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
        )
        git(self.repo, 'add', 'src/dead.py')
        git(self.repo, 'commit', '-qm', 'add dead flag')
        dead.write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
            "# comment only\n"
        )
        res, report = self.run_sre('--json', '--strict')
        self.assertEqual(res.returncode, 0)
        self.assertEqual(report['base'], 'HEAD')
        matches = [f for f in report['findings'] if f['id'] == 'YAGNI_DEAD_SPECULATIVE_FLAG']
        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0]['in_active_diff'], False)
        self.assertEqual(report['summary']['blockers'], 1)
        text_res, _ = self.run_sre('--strict')
        self.assertEqual(text_res.returncode, 0)
        self.assertIn('non-blocking in diff mode', text_res.stdout)

    def test_strict_diff_blocks_on_dead_flag_added_in_diff(self):
        (self.repo / 'src' / 'worker.py').write_text(
            "def execute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 42\n"
        )
        res, report = self.run_sre('--base', 'HEAD', '--json', '--strict')
        self.assertEqual(res.returncode, 2)
        matches = [f for f in report['findings'] if f['id'] == 'YAGNI_DEAD_SPECULATIVE_FLAG']
        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0]['in_active_diff'], True)

    def test_strict_files_scan_blocks_on_dead_flag(self):
        file_path = self.repo / 'src' / 'direct_dead.py'
        file_path.write_text(
            "def compute():\n"
            "    if False:\n"
            "        return 999\n"
            "    return 1\n"
        )
        res, report = self.run_sre('--files', str(file_path), '--json', '--strict')
        self.assertEqual(res.returncode, 2)
        self.assertIn(
            'YAGNI_DEAD_SPECULATIVE_FLAG',
            [f['id'] for f in report['findings']],
        )

    def test_flags_yagni_speculative_parameter(self):
        (self.repo / 'src' / 'params.py').write_text(
            "def execute_task(task_id, future_kwargs=None):\n"
            "    return task_id\n"
        )
        git(self.repo, 'add', 'src/params.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('YAGNI_SPECULATIVE_PARAMETER', finding_ids)

    def test_flags_scale_flat_retry(self):
        (self.repo / 'src' / 'retry.py').write_text(
            "def fetch():\n"
            "    for attempt in range(5): sleep(2)\n"
        )
        git(self.repo, 'add', 'src/retry.py')
        res, report = self.run_sre('--base', 'HEAD', '--json', '--strict')
        self.assertEqual(res.returncode, 2)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_UNBOUNDED_OR_FLAT_RETRY', finding_ids)

    def test_flags_scale_sleep_band_aid(self):
        (self.repo / 'src' / 'sync.py').write_text(
            "def wait_for_event():\n"
            "    time.sleep(2)\n"
            "    return True\n"
        )
        git(self.repo, 'add', 'src/sync.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_SLEEP_BAND_AID', finding_ids)

    def test_flags_scale_unbounded_concurrency(self):
        (self.repo / 'src' / 'batch.ts').write_text(
            "export async function processAll(items: any[]) {\n"
            "  return Promise.all(items.map(async (i) => upload(i)));\n"
            "}\n"
        )
        git(self.repo, 'add', 'src/batch.ts')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_UNBOUNDED_CONCURRENCY', finding_ids)

    def test_flags_scale_unbounded_concurrency_gather_star_tasks(self):
        (self.repo / 'src' / 'fanout.py').write_text(
            "import asyncio\n"
            "\n"
            "async def run_all(tasks):\n"
            "    return await asyncio.gather(*tasks)\n"
        )
        git(self.repo, 'add', 'src/fanout.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_UNBOUNDED_CONCURRENCY', finding_ids)

    def test_does_not_flag_gather_with_fixed_arguments(self):
        (self.repo / 'src' / 'fanout.py').write_text(
            "import asyncio\n"
            "\n"
            "async def run_pair(first, second):\n"
            "    return await asyncio.gather(first(), second())\n"
        )
        git(self.repo, 'add', 'src/fanout.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertNotIn('SCALE_UNBOUNDED_CONCURRENCY', finding_ids)

    def test_flags_scale_toil_error_swallow(self):
        (self.repo / 'src' / 'toil.py').write_text(
            "def run_job():\n"
            "    try:\n"
            "        do_work()\n"
            "    except Exception:\n"
            "        pass\n"
        )
        git(self.repo, 'add', 'src/toil.py')
        res, report = self.run_sre('--base', 'HEAD', '--json', '--strict')
        self.assertEqual(res.returncode, 2)
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_TOIL_ERROR_SWALLOW', finding_ids)

    def test_flags_scale_misleading_health_check(self):
        (self.repo / 'src' / 'probe.py').write_text(
            "def healthz():\n"
            "    return {'status': 'ok'}\n"
        )
        git(self.repo, 'add', 'src/probe.py')
        res, report = self.run_sre('--base', 'HEAD', '--json')
        finding_ids = [f['id'] for f in report['findings']]
        self.assertIn('SCALE_MISLEADING_HEALTH_CHECK', finding_ids)

    def test_git_diff_marks_findings_for_quoted_and_spaced_paths(self):
        git(self.repo, 'config', 'diff.noprefix', 'true')
        sources = ['src/café.py', 'src/wait for job.py', 'src/job\tname.py']
        for name in sources:
            (self.repo / name).write_text('import time\ntime.sleep(1)\n', encoding='utf-8')
        git(self.repo, 'add', '--', *sources)
        git(self.repo, 'commit', '-qm', 'existing callers')

        for name in sources:
            (self.repo / name).write_text(
                'import time\ntime.sleep(1)\nready = True\ntime.sleep(2)\n', encoding='utf-8'
            )

        res, report = self.run_sre('--base', 'HEAD', '--json')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(report['summary']['scanned_files'], 3)
        self.assertEqual(
            {(f['file'], f['line'], f['in_active_diff']) for f in report['findings']
             if f['id'] == 'SCALE_SLEEP_BAND_AID'},
            {(name, line, active) for name in sources for line, active in [(2, False), (4, True)]},
        )

    def test_git_diff_preserves_rename_and_deletion_line_attribution(self):
        files = {
            'src/previous.py': 'import time\n' + ''.join(f'entry_{i} = {i}\n' for i in range(12)),
            'src/removal.py': 'import time\nobsolete = None\ntime.sleep(3)\n',
            'src/metadata.py': 'import time\ntime.sleep(4)\n',
        }
        for name, source in files.items():
            (self.repo / name).write_text(source, encoding='utf-8')
        git(self.repo, 'add', '--', *files)
        git(self.repo, 'commit', '-qm', 'tracked inputs')
        git(self.repo, 'mv', 'src/previous.py', 'src/renamed task.py')
        (self.repo / 'src/renamed task.py').write_text(
            files['src/previous.py'] + 'time.sleep(2)\n', encoding='utf-8'
        )
        (self.repo / 'src/removal.py').write_text('import time\ntime.sleep(3)\n', encoding='utf-8')
        git(self.repo, 'update-index', '--chmod=+x', 'src/metadata.py')
        (self.repo / 'src/metadata.py').chmod(0o755)

        res, report = self.run_sre('--base', 'HEAD', '--json')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(
            {(f['file'], f['line'], f['in_active_diff']) for f in report['findings']
             if f['id'] == 'SCALE_SLEEP_BAND_AID'},
            {('src/metadata.py', 2, False), ('src/removal.py', 2, False), ('src/renamed task.py', 14, True)},
        )

    def test_git_diff_does_not_mark_unchanged_lines_between_hunks(self):
        git(self.repo, 'config', 'diff.interHunkContext', '2')
        source = self.repo / 'src/worker.py'
        source.write_text('import time\nfirst = 1\ntime.sleep(2)\nlast = 3\n', encoding='utf-8')
        git(self.repo, 'add', 'src/worker.py')
        git(self.repo, 'commit', '-qm', 'with existing delay')
        source.write_text('import time\nfirst = 2\ntime.sleep(2)\nlast = 4\n', encoding='utf-8')

        res, report = self.run_sre('--base', 'HEAD', '--json')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(
            [(f['line'], f['in_active_diff']) for f in report['findings'] if f['id'] == 'SCALE_SLEEP_BAND_AID'],
            [(3, False)],
        )

    def test_git_diff_reports_unreadable_path_encoding_and_checks_other_files(self):
        source = self.repo / 'src' / 'worker.py'
        source.write_text('import time\ntime.sleep(2)\n', encoding='utf-8')
        git(self.repo, 'add', 'src/worker.py')
        scan = runpy.run_path(str(SCRIPT))['scan_git_diff']
        collect_changes = scan.__globals__['collect_changes']

        def with_non_utf8_record(repo, base, *args, **kwargs):
            evidence = collect_changes(repo, base, *args, **kwargs)
            evidence['files'].append({
                'new_path': {'text': None, 'raw_hex': 'ff'},
                'old_path': None,
                'binary': False,
                'new_mode': '100644',
                'hunks': [],
            })
            return evidence

        stderr = io.StringIO()
        with mock.patch.dict(scan.__globals__, collect_changes=with_non_utf8_record), \
                contextlib.redirect_stderr(stderr):
            report = scan(self.repo)
        self.assertIn('skipped a non-UTF-8 Git path', stderr.getvalue())
        self.assertEqual(report['summary']['scanned_files'], 1)
        self.assertEqual(
            [(f['file'], f['line'], f['in_active_diff']) for f in report['findings']
             if f['id'] == 'SCALE_SLEEP_BAND_AID'],
            [('src/worker.py', 2, True)],
        )

    def test_scan_paths_direct(self):
        file_path = self.repo / 'src' / 'direct.py'
        file_path.write_text("def run():\n    # TODO(future): implement\n    return 0\n")
        res, report = self.run_sre('--files', str(file_path), '--json')
        self.assertEqual(res.returncode, 0)
        self.assertEqual(report['summary']['scanned_files'], 1)
        self.assertIn('YAGNI_SPECULATIVE_COMMENT', [f['id'] for f in report['findings']])


if __name__ == '__main__':
    unittest.main()
