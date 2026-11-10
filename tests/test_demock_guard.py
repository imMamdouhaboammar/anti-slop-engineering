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


if __name__ == "__main__":
    unittest.main()
