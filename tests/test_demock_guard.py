#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import tempfile
import unittest

from scripts.demock_guard import audit_paths, is_test_file, scan_file_content


class DemockGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demock_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_test_file(self):
        self.assertTrue(is_test_file("tests/test_foo.py"))
        self.assertTrue(is_test_file("src/__tests__/app.test.ts"))
        self.assertTrue(is_test_file("services/auth_test.go"))
        self.assertTrue(is_test_file("tests/fixtures/sample.json"))
        self.assertFalse(is_test_file("src/controllers/auth.ts"))
        self.assertFalse(is_test_file("services/payment_service.py"))

    def test_flags_test_double_in_production(self):
        py_code = """
from unittest.mock import MagicMock

def process_payment(amount):
    client = MagicMock()
    return client.charge(amount)
"""
        findings = scan_file_content("src/payment.py", py_code)
        self.assertTrue(any(f["class"] == "TEST_DOUBLE_IN_PROD" for f in findings))
        self.assertTrue(any(f["severity"] == "BLOCKING" for f in findings))

    def test_flags_silent_fallback_in_production(self):
        py_code = """
def fetch_users():
    try:
        return db.query("SELECT * FROM users")
    except Exception:
        return []
"""
        findings = scan_file_content("src/users.py", py_code)
        self.assertTrue(any(f["class"] == "SILENT_FALLBACK" for f in findings))
        self.assertTrue(any("dummy default" in f["recommendation"] for f in findings))

    def test_flags_forbidden_sqlite_fallback(self):
        ts_code = """
export async function getClient() {
    if (!supabaseClient) {
        // fallback to sqlite
        return new LocalSqliteDb();
    }
    return supabaseClient;
}
"""
        findings = scan_file_content("src/db.ts", ts_code)
        self.assertTrue(any(f["class"] == "SILENT_FALLBACK" for f in findings))
        self.assertTrue(any("SQLite fallback" in f["recommendation"] for f in findings))

    def test_flags_fail_open_security_gate(self):
        ts_code = """
export function requireAuth(req: Request) {
    const token = req.headers.get("Authorization");
    if (!token) {
        return true;
    }
    return verifyJwt(token);
}
"""
        findings = scan_file_content("src/auth.ts", ts_code)
        self.assertTrue(any(f["class"] == "FAIL_OPEN_GATE" for f in findings))
        self.assertTrue(any("fail closed" in f["recommendation"] for f in findings))

    def test_flags_unimplemented_placeholder(self):
        py_code = """
def export_dataset(dataset_id: str):
    raise NotImplementedError("TODO: implement export")
"""
        findings = scan_file_content("src/exporter.py", py_code)
        self.assertTrue(any(f["class"] == "UNIMPLEMENTED_PLACEHOLDER" for f in findings))

    def test_clean_production_code_passes(self):
        clean_code = """
export async function authenticate(req: Request): Promise<UserSession> {
    const token = req.headers.get("Authorization");
    if (!token) {
        throw new AuthenticationError("Missing Authorization token");
    }
    try {
        const decoded = await verifyJwt(token);
        return decoded;
    } catch (err) {
        logger.error("JWT verification failed", { error: err });
        throw new AuthenticationError("Invalid Authorization token");
    }
}
"""
        findings = scan_file_content("src/auth_clean.ts", clean_code)
        self.assertEqual(len(findings), 0)

    def test_audit_paths_directory_scan(self):
        prod_file = os.path.join(self.temp_dir, "service.ts")
        with open(prod_file, "w", encoding="utf-8") as fh:
            fh.write("const mock = new FakeDatabase();\n")

        record = audit_paths([self.temp_dir])
        self.assertEqual(record["verdict"], "REJECT")
        self.assertEqual(record["findings_count"], 1)
        self.assertEqual(record["findings"][0]["class"], "TEST_DOUBLE_IN_PROD")


class DemockStringLiteralTests(unittest.TestCase):
    """Pattern text inside string literals or comments is not live code.

    The guard's own catalog (and any documentation of banned patterns)
    contains the forbidden identifiers as data; scanning that text as
    code makes the guard flag itself.
    """

    def test_pattern_text_inside_strings_not_flagged(self):
        py_code = (
            'PATTERN_NAME = "local_sqlite_fallback"\n'
            'EXAMPLE_SNIPPET = "client = MagicMock()"\n'
        )
        findings = scan_file_content("src/catalog.py", py_code)
        self.assertEqual(findings, [])

    def test_pattern_text_inside_comment_not_flagged(self):
        py_code = (
            "# never fall back to local_sqlite_fallback in this layer\n"
            "value = compute()\n"
        )
        findings = scan_file_content("src/service.py", py_code)
        self.assertEqual(findings, [])

    def test_escaped_triple_quote_and_same_line_shadowing_and_crlf(self):
        py_code = (
            'DOC = """prefix \\""" client = MagicMock() suffix"""\r\n'
            'MSG = "MagicMock("; client = MagicMock()\r\n'
        )
        findings = scan_file_content("src/service.py", py_code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["class"], "TEST_DOUBLE_IN_PROD")
        self.assertEqual(findings[0]["line"], 2)


class DemockBaseModeTests(unittest.TestCase):
    """An explicit --base with an empty diff means "nothing changed",
    not "scan the whole repository"."""

    def test_explicit_base_with_empty_diff_scans_nothing(self):
        import subprocess
        import sys
        from pathlib import Path

        repo = tempfile.mkdtemp(prefix="demock_base_")
        try:
            def git(*args):
                subprocess.run(["git", "-C", repo, *args], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@t.t")
            git("config", "user.name", "t")
            src = Path(repo) / "src"
            src.mkdir()
            # Real test-double code that a full-repository scan would flag.
            (src / "service.py").write_text("client = MagicMock()\n")
            git("add", "-A")
            git("commit", "-qm", "base")

            script = Path(__file__).resolve().parent.parent / "scripts" / "demock_guard.py"
            proc = subprocess.run(
                [sys.executable, str(script), "--base", "HEAD", "--json"],
                cwd=repo, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            record = json.loads(proc.stdout)
            self.assertEqual(record["scanned_files"], 0)
            self.assertEqual(record["findings_count"], 0)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
