# SPDX-License-Identifier: MIT
# Unit tests for scripts/migration_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "migration_guard.py"
EXAMPLE = ROOT / "skills" / "zero-downtime-migration-gate" / "examples" / "zero-downtime-migration-record.json"

sys.path.insert(0, str(ROOT / "scripts"))
import migration_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class MigrationGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_goal_is_flagged(self):
        record = valid_record()
        record["goal"] = "short"
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_GOAL", codes)

    def test_invalid_evolution_pattern_fails(self):
        record = valid_record()
        record["evolution_strategy"]["pattern"] = "single_shot_destructive"
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_EVOLUTION_PATTERN", codes)

    def test_expand_phase_incompatible_with_n_minus_1_fails(self):
        record = valid_record()
        record["evolution_strategy"]["phases"]["expand"]["n_minus_1_compatible"] = False
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_EXPAND_PHASE", codes)

    def test_excessive_lock_timeout_fails(self):
        record = valid_record()
        record["ddl_safety"]["lock_timeout_ms"] = 60000
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNSAFE_LOCK_TIMEOUT", codes)

    def test_blocking_index_creation_fails(self):
        record = valid_record()
        record["ddl_safety"]["concurrent_index_creation"] = False
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("BLOCKING_INDEX_CREATION", codes)

    def test_coupled_ddl_backfill_fails(self):
        record = valid_record()
        record["backfill_plan"]["decoupled_from_ddl"] = False
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("COUPLED_DDL_BACKFILL", codes)

    def test_unbounded_backfill_batch_size_fails(self):
        record = valid_record()
        record["backfill_plan"]["batch_size"] = 500000
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNBOUNDED_BACKFILL_BATCH", codes)

    def test_wire_incompatibility_fails(self):
        record = valid_record()
        record["wire_compatibility"]["forward_compatible_n_minus_1_reads_n"] = False
        record["wire_compatibility"]["protobuf_reserved_enforced"] = False
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FORWARD_WIRE_INCOMPATIBLE", codes)
        self.assertIn("PROTOBUF_RESERVED_MISSING", codes)

    def test_unsafe_binary_rollback_fails(self):
        record = valid_record()
        record["rollback_safety"]["n_minus_1_binary_safe_without_db_rollback"] = False
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNSAFE_BINARY_ROLLBACK", codes)

    def test_sql_scanner_flags_blocking_ddl_patterns(self):
        unsafe_sql = """
        BEGIN;
        ALTER TABLE users RENAME COLUMN phone TO mobile;
        CREATE INDEX idx_users_mobile ON users (mobile);
        ALTER TABLE users ADD CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES orgs(id);
        COMMIT;
        """
        result = migration_guard.audit(valid_record(), sql_text=unsafe_sql)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SQL_MISSING_LOCK_TIMEOUT", codes)
        self.assertIn("SQL_DIRECT_RENAME", codes)
        self.assertIn("SQL_BLOCKING_CREATE_INDEX", codes)
        self.assertIn("SQL_UNVALIDATED_CONSTRAINT_LOCK", codes)

    def test_sql_scanner_flags_concurrent_index_inside_transaction(self):
        bad_tx_sql = """
        BEGIN;
        SET LOCAL lock_timeout = '2s';
        CREATE INDEX CONCURRENTLY idx_users_email ON users (email);
        COMMIT;
        """
        result = migration_guard.audit(valid_record(), sql_text=bad_tx_sql)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SQL_CONCURRENT_INDEX_IN_TX", codes)

    def test_sql_scanner_accepts_lock_free_ddl(self):
        safe_sql = """
        SET lock_timeout = '2s';
        SET statement_timeout = '10s';
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users (email);
        ALTER TABLE users ADD CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES orgs(id) NOT VALID;
        ALTER TABLE users VALIDATE CONSTRAINT fk_org;
        """
        result = migration_guard.audit(valid_record(), sql_text=safe_sql)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_stopping_unsafe_migration(self):
        record = {
            "schema_version": "1.0",
            "goal": "Reject single-PR column drop and unbatched 50M row rewrite",
            "verdict": {
                "action": "refuse",
                "rationale": "Dropping legacy column in the same deployment crashes N-1 pods and prevents binary rollback.",
                "revisit_triggers": ["Decompose into 3-phase Expand-Migrate-Contract PRs"]
            }
        }
        result = migration_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")
        self.assertEqual(result["findings"], [])

    def test_cli_invocation_success(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(valid_record(), tmp)
            tmp_path = Path(tmp.name)
        try:
            res = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", str(tmp_path), "--json"],
                capture_output=True,
                text=True,
                check=False
            )
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)
            self.assertEqual(payload["record_status"], "complete")
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
