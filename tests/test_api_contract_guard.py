#!/usr/bin/env python3
"""Tests for scripts/api_contract_guard.py (API Ergonomics & Contract Governor Guard)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import api_contract_guard


def make_valid_record():
    return {
        "schema_version": "1.0",
        "contract_id": "stripe-style-billing-sdk",
        "target_interface": {
            "module_path": "services/billing/sdk/client.ts",
            "interface_type": "public_sdk",
            "language": "typescript",
        },
        "pit_of_success_defaults": {
            "enabled": True,
            "default_timeout_ms": 10000,
            "auto_retry_max_attempts": 3,
            "backoff_strategy": "exponential_full_jitter",
            "default_page_limit": 20,
            "max_page_limit_ceiling": 100,
            "safe_tls_enforced": True,
        },
        "illegal_states_unrepresentable": {
            "discriminated_unions_enforced": True,
            "discriminator_field": "status",
            "branded_types_enforced": True,
            "branded_type_identifiers": [
                "CustomerId",
                "PaymentIntentId",
                "IdempotencyKey",
                "CurrencyCode",
            ],
            "exhaustive_match_enforced": True,
            "zero_boolean_traps_verified": True,
        },
        "progressive_disclosure": {
            "tier_1_one_liner_facade": "client.paymentIntents.create({ amount: 5000, currency: 'usd' }) provides instantaneous payment initialization",
            "tier_2_options_bag_supported": True,
            "tier_3_power_escape_hatch": "client.raw.request() and ClientBuilder allow custom transport pipelines, custom fetchers, and byte streaming",
            "namespace_pollution_prevented": True,
        },
        "rfc9457_problem_details": {
            "standard_compliance": "RFC_9457",
            "error_type_uri_prefix": "https://api.billing.example.com/errors/",
            "deterministic_machine_codes": [
                "card_declined",
                "insufficient_funds",
                "idempotency_key_reused",
                "rate_limit_exceeded",
            ],
            "invalid_params_breakdown_supported": True,
            "remediation_action_supported": True,
            "retryability_metadata_exposed": True,
        },
        "verdict": {
            "action": "proceed",
            "rationale": "Exemplary contract design adhering to Microsoft TypeScript compiler rigor and Stripe world-class developer experience.",
            "revisit_triggers": [
                "Adding non-HTTP transport protocol (e.g. gRPC or WebSocket)",
                "Modifying payment intent lifecycle state variants",
            ],
        },
    }


class ApiContractGuardTests(unittest.TestCase):
    def test_valid_record_passes(self):
        record = make_valid_record()
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(len(result["findings"]), 0)

    def test_canonical_example_file_passes(self):
        repo_root = Path(__file__).resolve().parent.parent
        example_path = (
            repo_root
            / "skills"
            / "api-ergonomics-and-contract-governor"
            / "examples"
            / "api-contract-record.json"
        )
        record = json.loads(example_path.read_text(encoding="utf-8"))
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(len(result["findings"]), 0)

    def test_invalid_target_interface_fails(self):
        record = make_valid_record()
        record["target_interface"]["interface_type"] = "unsupported_type"
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_INTERFACE_TYPE", codes)

    def test_pit_of_success_disabled_fails(self):
        record = make_valid_record()
        record["pit_of_success_defaults"]["enabled"] = False
        record["pit_of_success_defaults"]["default_timeout_ms"] = 999999
        record["pit_of_success_defaults"]["backoff_strategy"] = "flat_retry"
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("PIT_OF_SUCCESS_DISABLED", codes)
        self.assertIn("INVALID_DEFAULT_TIMEOUT", codes)
        self.assertIn("INVALID_BACKOFF_STRATEGY", codes)

    def test_illegal_states_disabled_fails(self):
        record = make_valid_record()
        record["illegal_states_unrepresentable"]["discriminated_unions_enforced"] = False
        record["illegal_states_unrepresentable"]["branded_types_enforced"] = False
        record["illegal_states_unrepresentable"]["branded_type_identifiers"] = ["OnlyOne"]
        record["illegal_states_unrepresentable"]["exhaustive_match_enforced"] = False
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("DISCRIMINATED_UNIONS_DISABLED", codes)
        self.assertIn("BRANDED_TYPES_DISABLED", codes)
        self.assertIn("INSUFFICIENT_BRANDED_IDENTIFIERS", codes)
        self.assertIn("EXHAUSTIVE_MATCH_NOT_ENFORCED", codes)

    def test_progressive_disclosure_disabled_fails(self):
        record = make_valid_record()
        record["progressive_disclosure"]["tier_2_options_bag_supported"] = False
        record["progressive_disclosure"]["namespace_pollution_prevented"] = False
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("TIER_2_OPTIONS_NOT_SUPPORTED", codes)
        self.assertIn("NAMESPACE_POLLUTION_NOT_PREVENTED", codes)

    def test_invalid_rfc9457_error_model_fails(self):
        record = make_valid_record()
        record["rfc9457_problem_details"]["standard_compliance"] = "CUSTOM_JSON"
        record["rfc9457_problem_details"]["deterministic_machine_codes"] = ["single_code"]
        record["rfc9457_problem_details"]["retryability_metadata_exposed"] = False
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_RFC_COMPLIANCE", codes)
        self.assertIn("INSUFFICIENT_MACHINE_CODES", codes)
        self.assertIn("RETRYABILITY_NOT_EXPOSED", codes)

    def test_pause_and_refuse_verdicts(self):
        record = make_valid_record()
        record["verdict"]["action"] = "pause"
        record["verdict"]["rationale"] = "Contract review is paused pending RFC 9457 schema finalization."
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "pause")

        record["verdict"]["action"] = "refuse"
        record["verdict"]["rationale"] = "Contract is refused due to pervasive boolean traps and unbranded IDs."
        result = api_contract_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")

    def test_source_scanner_flags_boolean_traps(self):
        bad_sig = "export function processUser(id: string, isGuest: boolean, autoRenew: boolean): void;"
        findings = api_contract_guard.scan_source_hazards(bad_sig)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_BOOLEAN_PARAMETER_TRAP", codes)

        bad_call = "client.updateAccount(accountId, true, false);"
        findings_call = api_contract_guard.scan_source_hazards(bad_call)
        codes_call = [f["code"] for f in findings_call]
        self.assertIn("SOURCE_BOOLEAN_CALL_TRAP", codes_call)

    def test_source_scanner_flags_bare_error_throws(self):
        bad_source = "if (!token) throw new Error('Unauthorized access');"
        findings = api_contract_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_BARE_ERROR_THROW", codes)

    def test_source_scanner_flags_stringly_typed_ids(self):
        bad_source = "export class CustomerService { async retrieve(customerId: string): Promise<Customer> {} }"
        findings = api_contract_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_STRINGLY_TYPED_IDENTIFIER", codes)

    def test_source_scanner_flags_hanging_fetch(self):
        bad_source = "const res = await fetch('https://api.example.com/v1/data');"
        findings = api_contract_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_HANGING_NETWORK_FETCH", codes)

    def test_source_scanner_accepts_clean_sdk(self):
        repo_root = Path(__file__).resolve().parent.parent
        example_ts = (
            repo_root
            / "skills"
            / "api-ergonomics-and-contract-governor"
            / "examples"
            / "hardened-sdk-contract.ts"
        )
        source_text = example_ts.read_text(encoding="utf-8")
        findings = api_contract_guard.scan_source_hazards(source_text)
        self.assertEqual(len(findings), 0)

    def test_cli_invocation_success_and_failure(self):
        repo_root = Path(__file__).resolve().parent.parent
        script = repo_root / "scripts" / "api_contract_guard.py"
        record_file = (
            repo_root
            / "skills"
            / "api-ergonomics-and-contract-governor"
            / "examples"
            / "api-contract-record.json"
        )
        proc = subprocess.run(
            [sys.executable, str(script), "audit", str(record_file), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["record_status"], "complete")

        # Invalid file invocation
        invalid_record = repo_root / "skills" / "api-ergonomics-and-contract-governor" / "evals" / "scenarios.json"
        proc_invalid = subprocess.run(
            [sys.executable, str(script), "audit", str(invalid_record), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
