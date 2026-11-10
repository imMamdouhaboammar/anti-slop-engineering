#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import tempfile
import unittest

from scripts.mandela_guard import audit_test_paths, scan_test_file_content


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


if __name__ == "__main__":
    unittest.main()
