# SPDX-License-Identifier: MIT
# Unit tests for scripts/paranoid_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "paranoid_guard.py"
EXAMPLE = ROOT / "skills" / "paranoid-principal-architect" / "examples" / "paranoid-architecture-record.json"

sys.path.insert(0, str(ROOT / "scripts"))
import paranoid_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class ParanoidGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_goal_is_flagged(self):
        record = valid_record()
        record["goal"] = ""
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_GOAL", codes)

    def test_concurrency_below_ten_million_fails(self):
        record = valid_record()
        record["scale_profile"]["target_concurrency"] = 500_000
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_CONCURRENCY", codes)

    def test_throughput_below_thousand_rps_fails(self):
        record = valid_record()
        record["scale_profile"]["throughput_rps"] = 50
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_THROUGHPUT", codes)

    def test_insufficient_threat_pre_mortem_fails(self):
        record = valid_record()
        record["threat_pre_mortem"] = record["threat_pre_mortem"][:2]
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_THREATS", codes)

    def test_invalid_threat_class_fails(self):
        record = valid_record()
        record["threat_pre_mortem"][0]["threat_class"] = "vague_complaint"
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_THREAT_ITEM", codes)

    def test_duplicate_threat_ids_fail(self):
        record = valid_record()
        record["threat_pre_mortem"][1]["id"] = record["threat_pre_mortem"][0]["id"]
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("DUPLICATE_THREAT_ID", codes)

    def test_disabled_idempotency_fails(self):
        record = valid_record()
        record["concurrency_controls"]["idempotency"]["enabled"] = False
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("IDEMPOTENCY_DISABLED", codes)

    def test_invalid_locking_strategy_fails(self):
        record = valid_record()
        record["concurrency_controls"]["locking_strategy"] = "sync_in_memory_mutex"
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_LOCKING_STRATEGY", codes)

    def test_unbounded_read_limit_fails(self):
        record = valid_record()
        record["bounded_limits"]["max_read_limit"] = 1000
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNBOUNDED_READ_LIMIT", codes)

    def test_unbounded_network_timeout_fails(self):
        record = valid_record()
        record["bounded_limits"]["network_timeout_ms"] = 60000
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNBOUNDED_TIMEOUT", codes)

    def test_invalid_backoff_algorithm_fails(self):
        record = valid_record()
        record["bounded_limits"]["backoff_algorithm"] = "fixed_sleep_100ms"
        result = paranoid_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_BACKOFF_ALGORITHM", codes)

    def test_refuse_verdict_permits_stopping_work(self):
        record = {
            "schema_version": "1.0",
            "goal": "Evaluate high-risk insecure microservice",
            "verdict": {
                "action": "refuse",
                "rationale": "Client dictating role elevation without authentication cannot proceed.",
                "revisit_triggers": ["Complete overhaul of authentication boundary"]
            }
        }
        result = paranoid_guard.audit(record)
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

    def test_cli_invocation_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write("{ invalid json")
            tmp_path = Path(tmp.name)
        try:
            res = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", str(tmp_path)],
                capture_output=True,
                text=True,
                check=False
            )
            self.assertEqual(res.returncode, 1)
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
