#!/usr/bin/env python3
"""Tests for scripts/privacy_guard.py (Privacy & Data Lineage Gate Guard)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import privacy_guard


def make_valid_record():
    return {
        "schema_version": "1.0",
        "system_id": "customer-identity-service",
        "target_system": {
            "module_under_test": "services/identity-service",
            "system_archetype": "event_driven_data_lakehouse",
            "regulatory_regimes": ["gdpr", "ccpa", "apple_privacy_policy"],
        },
        "tainted_pii_types": {
            "branded_types_enabled": True,
            "redaction_wrapper": "Redacted<T>",
            "log_leakage_prevented": True,
            "unredacted_serialization_banned": True,
            "audited_pii_fields": [
                {
                    "field_name": "user_email",
                    "sensitivity": "restricted_pii",
                    "type_brand": "Redacted<UserEmail>",
                    "serialization_policy": "sha256_salted_pseudonym",
                },
                {
                    "field_name": "phone_number",
                    "sensitivity": "restricted_pii",
                    "type_brand": "Redacted<E164Phone>",
                    "serialization_policy": "e164_masked_trailing4",
                },
            ],
        },
        "cryptographic_erasure": {
            "mechanism": "crypto_shredding_key_per_subject",
            "kms_provider": "aws_kms",
            "key_derivation_algorithm": "AES-256-GCM",
            "immutable_ledger_coverage": ["kafka_event_stream", "iceberg_data_lake"],
            "revocation_latency_ms": 150,
            "confirmation_receipt_verified": True,
        },
        "data_minimization_and_ttl": {
            "purpose_binding_declared": True,
            "retention_ttl_enforced": True,
            "max_retention_days": 90,
            "automated_gc_pipeline": "partition_drop_cron",
            "differential_privacy_or_anonymization": "laplace_dp_epsilon_1_0",
        },
        "data_lineage_and_flow": {
            "lineage_dag_modeled": True,
            "forbidden_sinks_guarded": True,
            "telemetry_egress_allowlist": ["internal_aggregated_metrics"],
            "third_party_sharing_fenced": True,
        },
        "verdict": {
            "action": "proceed",
            "rationale": "Comprehensive privacy boundary enforcement with crypto-shredding and automated retention TTL.",
            "revisit_triggers": ["Adding third party analytics"],
        },
    }


class TestPrivacyGuard(unittest.TestCase):
    def test_valid_record_passes(self):
        record = make_valid_record()
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(len(result["findings"]), 0)

    def test_canonical_example_file_passes(self):
        repo_root = Path(__file__).resolve().parent.parent
        example_path = repo_root / "skills" / "privacy-and-data-lineage-gate" / "examples" / "privacy-lineage-record.json"
        record = json.loads(example_path.read_text(encoding="utf-8"))
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(len(result["findings"]), 0)

    def test_invalid_target_system_fails(self):
        record = make_valid_record()
        record["target_system"]["system_archetype"] = "unsupported_archetype"
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_SYSTEM_ARCHETYPE", codes)

    def test_disabled_branded_types_fails(self):
        record = make_valid_record()
        record["tainted_pii_types"]["branded_types_enabled"] = False
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("BRANDED_TYPES_DISABLED", codes)

    def test_insufficient_or_duplicate_pii_fields_fails(self):
        record = make_valid_record()
        record["tainted_pii_types"]["audited_pii_fields"] = [
            {
                "field_name": "email",
                "sensitivity": "restricted_pii",
                "type_brand": "Redacted<Email>",
                "serialization_policy": "masked",
            },
            {
                "field_name": "email",  # Duplicate name
                "sensitivity": "restricted_pii",
                "type_brand": "Redacted<Email>",
                "serialization_policy": "masked",
            },
        ]
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("DUPLICATE_PII_FIELD", codes)

    def test_invalid_erasure_mechanism_fails(self):
        record = make_valid_record()
        record["cryptographic_erasure"]["mechanism"] = "soft_delete_flag"
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_ERASURE_MECHANISM", codes)

    def test_excessive_revocation_latency_fails(self):
        record = make_valid_record()
        record["cryptographic_erasure"]["revocation_latency_ms"] = 10000  # Exceeds 5000ms bound
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_REVOCATION_LATENCY", codes)

    def test_missing_retention_ttl_fails(self):
        record = make_valid_record()
        record["data_minimization_and_ttl"]["retention_ttl_enforced"] = False
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("RETENTION_TTL_NOT_ENFORCED", codes)

    def test_missing_lineage_dag_fails(self):
        record = make_valid_record()
        record["data_lineage_and_flow"]["lineage_dag_modeled"] = False
        result = privacy_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("LINEAGE_DAG_NOT_MODELED", codes)

    def test_verdict_pause_or_refuse_skips_deep_checks(self):
        record = make_valid_record()
        record["verdict"]["action"] = "pause"
        record["tainted_pii_types"] = {}  # Empty sub-dict would normally fail on proceed
        result = privacy_guard.audit(record)
        self.assertEqual(result["verdict_action"], "pause")
        self.assertEqual(result["record_status"], "complete")

    def test_source_scan_detects_raw_pii_logging(self):
        bad_code = """
        function logUser(user: User) {
            console.log("Registered user email:", user.email);
        }
        """
        findings = privacy_guard.scan_source_hazards(bad_code)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_RAW_PII_LOGGING", codes)

    def test_source_scan_detects_telemetry_pii_leak(self):
        bad_code = """
        function trackEvent(user: User) {
            analytics.track("purchase", { email: user.email, total: 100 });
        }
        """
        findings = privacy_guard.scan_source_hazards(bad_code)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_TELEMETRY_PII_LEAK", codes)

    def test_source_scan_detects_naive_soft_delete(self):
        bad_code = """
        async function deleteAccount(userId: string) {
            await db.execute("UPDATE users SET is_deleted = true WHERE id = ?", [userId]);
        }
        """
        findings = privacy_guard.scan_source_hazards(bad_code)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_NAIVE_SOFT_DELETE", codes)

    def test_source_scan_detects_unbounded_retention_table(self):
        bad_code = """
        CREATE TABLE user_activity_log (
            user_id UUID,
            ip_address VARCHAR(45),
            event_name VARCHAR(100),
            recorded_at TIMESTAMP
        );
        """
        findings = privacy_guard.scan_source_hazards(bad_code)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_UNBOUNDED_RETENTION_TABLE", codes)

    def test_source_scan_detects_unredacted_tostring(self):
        bad_code = """
        class UserCredentials {
            email: string;
            toString() {
                return `Credentials for ${this.email}`;
            }
        }
        """
        findings = privacy_guard.scan_source_hazards(bad_code)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_UNREDACTED_TOSTRING", codes)

    def test_clean_source_code_has_zero_findings(self):
        clean_code = """
        class UserCredentials {
            email: Redacted<UserEmail>;
            toString() {
                return "[REDACTED:UserCredentials]";
            }
        }
        """
        findings = privacy_guard.scan_source_hazards(clean_code)
        self.assertEqual(len(findings), 0)

    def test_cli_execution_via_subprocess(self):
        repo_root = Path(__file__).resolve().parent.parent
        example_path = repo_root / "skills" / "privacy-and-data-lineage-gate" / "examples" / "privacy-lineage-record.json"
        proc = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "privacy_guard.py"), "audit", str(example_path), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["record_status"], "complete")
        self.assertEqual(data["verdict_action"], "proceed")


if __name__ == "__main__":
    unittest.main()
