#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.demock_guard import audit_paths, is_test_file, scan_file_content

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demock_guard.py"


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

    def test_cli_invalid_base_fails_closed(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "NOPE_INVALID_REF", "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("NOPE_INVALID_REF", proc.stdout + proc.stderr)

    def test_cli_valid_base_empty_diff_scans_nothing(self):
        repo = Path(self.temp_dir) / "repo"
        repo.mkdir()
        def git(*args):
            subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.name", "Test Committer")
        git("config", "user.email", "test@example.com")
        (repo / "service.py").write_text(
            "from unittest.mock import MagicMock\nclient = MagicMock()\n", encoding="utf-8"
        )
        git("add", ".")
        git("commit", "-qm", "feat: committed file with a test double")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "HEAD", "--json"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = json.loads(proc.stdout)
        self.assertEqual(record["verdict"], "PROCEED")
        self.assertEqual(record["scanned_files"], 0)
        self.assertEqual(record["findings_count"], 0)

    def test_cli_base_matching_filename_scans_diff(self):
        repo = Path(self.temp_dir) / "ambiguous_repo"
        repo.mkdir()
        def git(*args):
            subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Test Committer")
        git("config", "user.email", "test@example.com")
        (repo / "main").write_text("binary placeholder\n", encoding="utf-8")
        (repo / "service.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "initial")
        (repo / "service.py").write_text(
            "from unittest.mock import MagicMock\ndef run():\n    return MagicMock()\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "main", "--json"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        record = json.loads(proc.stdout)
        self.assertEqual(record["verdict"], "REJECT")
        self.assertEqual(record["scanned_files"], 1)

    def test_block_comment_does_not_hide_live_typescript_on_same_line(self):
        source = (
            "/* documentation\n"
            "const demo = new MockService();\n"
            "*/ const service = new MockService();\n"
        )
        self.assertEqual(
            [(item["class"], item["line"]) for item in scan_file_content("src/service.ts", source)],
            [("TEST_DOUBLE_IN_PROD", 3)],
        )

    def test_typescript_regex_and_template_keep_live_test_doubles(self):
        source = (
            'const rx = /"/; const worker = new MockService();\n'
            'const example = `text ${new MockService()}`;\n'
        )
        self.assertEqual(
            [(item["class"], item["line"]) for item in scan_file_content("src/worker.ts", source)],
            [("TEST_DOUBLE_IN_PROD", 1), ("TEST_DOUBLE_IN_PROD", 2)],
        )

    def test_rust_lifetime_does_not_hide_live_placeholder(self):
        source = "fn build<'a>(name: &'a str) { todo!() }"
        self.assertEqual(
            [(item["class"], item["line"]) for item in scan_file_content("src/worker.rs", source)],
            [("UNIMPLEMENTED_PLACEHOLDER", 1)],
        )

    def test_python_format_expression_preserves_live_test_double(self):
        source = 'message = f"{MagicMock()}"\n'
        self.assertEqual(
            [(item["class"], item["line"]) for item in scan_file_content("src/service.py", source)],
            [("TEST_DOUBLE_IN_PROD", 1)],
        )

    def test_python_catalog_literals_do_not_hide_live_code(self):
        source = (
            'EXAMPLE = """client = MagicMock()\r\n'
            'local_sqlite_fallback"""\r\n'
            'line = "MagicMock("; client = MagicMock()\r\n'
        )
        self.assertEqual(
            [(item["class"], item["line"]) for item in scan_file_content("src/catalog.py", source)],
            [("TEST_DOUBLE_IN_PROD", 3)],
        )

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


if __name__ == "__main__":
    unittest.main()
