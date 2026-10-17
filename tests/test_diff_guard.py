# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Behavioral tests for the read-only diff guard. Uses disposable git repositories."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'diff_guard.py'


def git(path, *args):
    return subprocess.run(['git', *args], cwd=path, text=True, capture_output=True, check=True).stdout.strip()


class DiffGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        git(self.repo, 'init', '-q')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'src').mkdir()
        (self.repo / 'tests').mkdir()
        (self.repo / 'src' / 'calc.py').write_text('def value():\n    return 1\n')
        (self.repo / 'tests' / 'test_calc.py').write_text('def test_value():\n    assert value() == 1\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'baseline')

    def tearDown(self):
        self.temp.cleanup()

    def check(self, *extra):
        result = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.repo), '--base', 'HEAD', '--json', *extra], text=True, capture_output=True)
        return result, json.loads(result.stdout) if result.stdout.strip().startswith('{') else None

    def test_flags_existing_test_modification_without_blocking_it(self):
        (self.repo / 'tests' / 'test_calc.py').write_text('def test_value():\n    assert value() == 2\n')
        result, report = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertIn('TEST_CHANGE_REVIEW', [x['id'] for x in report['findings']])
        self.assertEqual(report['summary']['changed_test_files'], 1)

    def test_flags_weak_assertion_and_skipped_tests(self):
        (self.repo / 'tests' / 'test_calc.py').write_text('def test_value():\n    assert True\n\n@pytest.mark.skip\ndef test_other():\n    pass\n')
        result, report = self.check('--fail-on-blocker')
        self.assertEqual(result.returncode, 2)
        self.assertIn('SKIPPED_TEST', [x['id'] for x in report['findings']])
        self.assertIn('WEAK_ASSERTION', [x['id'] for x in report['findings']])

    def test_new_tests_are_not_mistaken_for_old_changed_tests(self):
        (self.repo / 'tests' / 'test_new.py').write_text('def test_new():\n    assert 1 == 2\n')
        _, report = self.check()
        self.assertEqual(report['summary']['changed_test_files'], 0)
        self.assertEqual(report['summary']['new_test_files'], 1)

    def test_reports_scope_and_flags_security_bypass_pattern_as_candidate(self):
        (self.repo / 'src' / 'calc.py').write_text('def value():\n    return 2\n# disable\nverify=False\n')
        _, report = self.check()
        self.assertEqual(report['summary']['changed_files'], 1)
        self.assertIn('SECURITY_BYPASS_CANDIDATE', [x['id'] for x in report['findings']])

    def test_no_changes_has_zero_findings(self):
        _, report = self.check()
        self.assertEqual(report['summary']['changed_files'], 0)
        self.assertEqual(report['findings'], [])

    def test_untracked_files_produce_explicit_scope_warning(self):
        (self.repo / 'src' / 'untracked.py').write_text('password="foo"\n')
        _, report = self.check()
        self.assertTrue(any('Untracked' in warning for warning in report['limitations']))
        self.assertEqual(report['summary']['changed_files'], 0)

    def test_documentation_files_are_excluded_from_code_pattern_matching(self):
        (self.repo / 'README.md').write_text('# Guide\nNever use verify=False or assert True in production.\n')
        git(self.repo, 'add', 'README.md')
        _, report = self.check()
        self.assertEqual(report['summary']['changed_files'], 1)
        self.assertEqual(report['findings'], [])


if __name__ == '__main__':
    unittest.main()
