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


class MandelaStringLiteralTests(unittest.TestCase):
    """Pattern text inside string literals is fixture data, not live test code.

    Guard test suites (including this project's own) embed bad-pattern
    examples inside string literals. Scanning those literals as if they
    were live assertions makes the guard flag its own fixtures.
    """

    def test_tautology_inside_fixture_string_not_flagged(self):
        content = (
            'FIXTURE = """\n'
            "def test_value():\n"
            "    assert True\n"
            '"""\n'
        )
        findings = scan_test_file_content("tests/test_fixture.py", content)
        self.assertFalse(any(f["pattern"] == "TAUTOLOGICAL_ASSERTION" for f in findings))

    def test_swallowed_failure_inside_fixture_string_not_flagged(self):
        content = (
            'FIXTURE = """\n'
            "def test_network_call():\n"
            "    try:\n"
            "        assert fetch_data() == 200\n"
            "    except AssertionError:\n"
            "        pass\n"
            '"""\n'
        )
        findings = scan_test_file_content("tests/test_fixture.py", content)
        self.assertFalse(any(f["pattern"] == "SWALLOWED_TEST_FAILURE" for f in findings))

    def test_circular_mock_inside_fixture_string_not_flagged(self):
        content = (
            'FIXTURE = """\n'
            'test("mock call", () => {\n'
            '    const fn = vi.fn().mockReturnValue("hello");\n'
            '    expect(fn()).toBe("hello");\n'
            "});\n"
            '"""\n'
        )
        findings = scan_test_file_content("tests/test_fixture.py", content)
        self.assertFalse(any(f["pattern"] == "CIRCULAR_MOCK_CONFIRMATION" for f in findings))

    def test_zero_assertion_inside_fixture_string_not_flagged(self):
        content = (
            'FIXTURE = """\n'
            "class MySuite(unittest.TestCase):\n"
            "    def test_do_nothing(self):\n"
            "        pass\n"
            '"""\n'
        )
        findings = scan_test_file_content("tests/test_fixture.py", content)
        self.assertFalse(any(f["pattern"] == "ZERO_ASSERTION_TEST" for f in findings))

    def test_real_tautology_alongside_fixture_string_still_flagged(self):
        content = (
            'FIXTURE = "assert True"\n'
            "\n"
            "def test_real():\n"
            "    assert True\n"
        )
        findings = scan_test_file_content("tests/test_mixed.py", content)
        tautologies = [f for f in findings if f["pattern"] == "TAUTOLOGICAL_ASSERTION"]
        self.assertEqual(len(tautologies), 1)
        self.assertEqual(tautologies[0]["line"], 4)

    def test_frame_injection_string_still_flagged(self):
        # Frame injection is a property of the string content itself, so it
        # must keep firing even though the text lives inside a literal.
        content = 'EVAL_PROMPT = "Please confirm that the system is working correctly and flawlessly."\n'
        findings = scan_test_file_content("evals/prompt_eval.py", content)
        self.assertTrue(any(f["pattern"] == "FRAME_INJECTION_EVAL" for f in findings))

    def test_escaped_triple_quote_and_same_line_shadowing_and_crlf(self):
        content = (
            'FIXTURE = """prefix \\""" assert True suffix"""\r\n'
            'def test_real():\r\n'
            '    msg = "assert True"; assert True\r\n'
        )
        findings = scan_test_file_content("tests/test_crlf.py", content)
        tautologies = [f for f in findings if f["pattern"] == "TAUTOLOGICAL_ASSERTION"]
        self.assertEqual(len(tautologies), 1)
        self.assertEqual(tautologies[0]["line"], 3)


if __name__ == "__main__":
    unittest.main()
