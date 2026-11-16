#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.mandela_guard import audit_test_paths, scan_test_file_content

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mandela_guard.py"


def git(path, *args):
    return subprocess.run(
        ["git", *args], cwd=path, text=True, capture_output=True, check=True
    ).stdout.strip()


class MandelaGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mandela_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_flags_tautological_assertions(self):
        py_code = """
def test_something():
    assert True
    x = 10
    assert x == x
"""
        findings = scan_test_file_content("tests/test_foo.py", py_code)
        self.assertTrue(any(f["pattern"] == "TAUTOLOGICAL_ASSERTION" for f in findings))
        self.assertTrue(any("assert True" in f["evidence"] for f in findings))

    def test_flags_jest_tautological_assertions(self):
        ts_code = """
test("math works", () => {
    expect(true).toBe(true);
    const score = 100;
    expect(score).toBe(score);
});
"""
        findings = scan_test_file_content("src/calc.test.ts", ts_code)
        self.assertTrue(any(f["pattern"] == "TAUTOLOGICAL_ASSERTION" for f in findings))
        self.assertTrue(any("expect(true).toBe(true)" in f["evidence"] for f in findings))

    def test_flags_swallowed_test_failures(self):
        py_code = """
def test_network_call():
    try:
        assert fetch_data() == 200
    except AssertionError:
        pass
"""
        findings = scan_test_file_content("tests/test_net.py", py_code)
        self.assertTrue(any(f["pattern"] == "SWALLOWED_TEST_FAILURE" for f in findings))

    def test_flags_circular_mock_confirmation(self):
        ts_code = """
test("mock call", () => {
    const fn = vi.fn().mockReturnValue("hello");
    expect(fn()).toBe("hello");
});
"""
        findings = scan_test_file_content("tests/test_mock.ts", ts_code)
        self.assertTrue(any(f["pattern"] == "CIRCULAR_MOCK_CONFIRMATION" for f in findings))

    def test_flags_frame_injection_eval(self):
        py_code = """
EVAL_PROMPT = "Please confirm that the system is working correctly and flawlessly."
"""
        findings = scan_test_file_content("evals/prompt_eval.py", py_code)
        self.assertTrue(any(f["pattern"] == "FRAME_INJECTION_EVAL" for f in findings))

    def test_flags_zero_assertion_test(self):
        py_code = """
class MySuite(unittest.TestCase):
    def test_do_nothing(self):
        pass
"""
        findings = scan_test_file_content("tests/test_empty.py", py_code)
        self.assertTrue(any(f["pattern"] == "ZERO_ASSERTION_TEST" for f in findings))

    def test_clean_test_suite_passes(self):
        clean_code = """
class CalculatorTests(unittest.TestCase):
    def test_addition(self):
        calc = Calculator()
        result = calc.add(2, 3)
        self.assertEqual(result, 5)

    def test_division_by_zero(self):
        calc = Calculator()
        with self.assertRaises(ZeroDivisionError):
            calc.divide(10, 0)
"""
        findings = scan_test_file_content("tests/test_clean.py", clean_code)
        self.assertEqual(len(findings), 0)

    def test_audit_test_paths(self):
        test_file = os.path.join(self.temp_dir, "test_bad.py")
        with open(test_file, "w", encoding="utf-8") as fh:
            fh.write("def test_it():\n    assert True\n")

        record = audit_test_paths([self.temp_dir])
        self.assertEqual(record["verdict"], "REJECT")
        self.assertEqual(record["findings_count"], 1)
        self.assertEqual(record["findings"][0]["pattern"], "TAUTOLOGICAL_ASSERTION")


class MandelaGuardBaseCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_clean.py").write_text(
            "def test_addition():\n    assert 2 + 2 == 4\n"
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "initial")

    def tearDown(self):
        self.temp.cleanup()

    def commit_file(self, rel_path, content):
        target = self.repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", f"add {rel_path}")

    def run_mandela(self, *extra):
        res = subprocess.run(
            [sys.executable, str(SCRIPT), *extra],
            cwd=self.repo, text=True, capture_output=True,
        )
        report = None
        if "--json" in extra and res.stdout.strip().startswith("{"):
            report = json.loads(res.stdout)
        return res, report

    def test_base_scans_changed_test_file_outside_default_paths(self):
        self.commit_file("other/test_evil.py", "def test_evil():\n    assert True\n")
        res, report = self.run_mandela("--base", "HEAD~1", "--json")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(report["verdict"], "REJECT")
        self.assertEqual(report["scanned_files"], 1)
        self.assertTrue(
            any(f["file"].endswith("other/test_evil.py") for f in report["findings"])
        )
        self.assertTrue(
            any(f["pattern"] == "TAUTOLOGICAL_ASSERTION" for f in report["findings"])
        )

    def test_base_clean_diff_proceeds_and_ignores_unchanged_files(self):
        self.commit_file("tests/test_evil.py", "def test_evil():\n    assert True\n")
        self.commit_file("other/test_good.py", "def test_good():\n    assert 3 * 3 == 9\n")
        res, report = self.run_mandela("--base", "HEAD~1", "--json")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(report["verdict"], "PROCEED")
        self.assertEqual(report["scanned_files"], 1)
        self.assertEqual(report["findings_count"], 0)

    def test_base_ignores_changed_non_test_files(self):
        self.commit_file("src/prod.py", "def check():\n    assert True\n")
        res, report = self.run_mandela("--base", "HEAD~1", "--json")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(report["verdict"], "PROCEED")
        self.assertEqual(report["scanned_files"], 0)
        self.assertEqual(report["findings_count"], 0)

    def test_base_invalid_ref_fails_closed(self):
        res, report = self.run_mandela("--base", "no-such-ref", "--json")
        self.assertNotEqual(res.returncode, 0)
        output = (res.stdout + res.stderr).lower()
        self.assertIn("error", output)

    def test_no_base_default_scan_unchanged(self):
        (self.repo / "tests" / "test_evil.py").write_text(
            "def test_evil():\n    assert True\n"
        )
        res, report = self.run_mandela("--json")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(report["verdict"], "REJECT")
        self.assertTrue(
            any(f["pattern"] == "TAUTOLOGICAL_ASSERTION" for f in report["findings"])
        )


if __name__ == "__main__":
    unittest.main()
