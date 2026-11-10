# SPDX-License-Identifier: MIT
# Unit tests for scripts/verification_oracle_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verification_oracle_guard.py"
EXAMPLE = ROOT / "skills" / "verification-oracle-architect" / "examples" / "verification-oracle-record.json"
TS_EXAMPLE = ROOT / "skills" / "verification-oracle-architect" / "examples" / "verified-fake-property-chaos-oracle.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import verification_oracle_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class VerificationOracleGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_contract_parity_or_rollback_mechanic_fails(self):
        record = valid_record()
        record["verified_in_memory_fakes"]["contract_parity_verified"] = False
        record["verified_in_memory_fakes"]["enforced_fake_mechanics"] = [
            "unique_and_check_constraint_enforcement",
            "optimistic_concurrency_version_cas",
            "composite_tenant_isolation",
        ]
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("CONTRACT_PARITY_NOT_VERIFIED", codes)
        self.assertIn("MISSING_CORE_FAKE_ISOLATION_OR_ROLLBACK", codes)

    def test_low_property_runs_or_missing_shrinking_fails(self):
        record = valid_record()
        record["property_and_metamorphic_oracles"]["generated_runs_per_property"] = 10
        record["property_and_metamorphic_oracles"]["shrinking_enabled"] = False
        record["property_and_metamorphic_oracles"]["invariants_verified"] = [
            record["property_and_metamorphic_oracles"]["invariants_verified"][0]
        ]
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_GENERATED_PROPERTY_RUNS", codes)
        self.assertIn("SHRINKING_NOT_ENABLED", codes)
        self.assertIn("INSUFFICIENT_INVARIANTS_VERIFIED", codes)

    def test_missing_seeded_chaos_post_commit_or_mutation_falsification_fails(self):
        record = valid_record()
        record["deterministic_chaos_testing"]["reproduction_seeds"] = ["not-a-hex-seed"]
        record["deterministic_chaos_testing"]["injected_fault_modes"] = [
            "pre_commit_connection_drop",
            "transient_cas_version_conflict",
        ]
        record["mutation_falsification"]["red_green_falsification_verified"] = False
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_REPRODUCTION_SEEDS", codes)
        self.assertIn("MISSING_PRE_OR_POST_COMMIT_CHAOS_FAULTS", codes)
        self.assertIn("RED_GREEN_FALSIFICATION_NOT_VERIFIED", codes)

    def test_source_scanner_flags_banned_mocks_unseeded_random_sleep_and_weak_asserts(self):
        bad_test_source = """
        // oxlint-disable-next-line anti-slop/no-module-mocking
        vi.mock("../db/postgresLedgerStorage");
        test("weak flaky mock test", async () => {
          if (Math.random() < 0.5) {
            await new Promise((r) => setTimeout(r, 100));
          }
          expect(true).toBe(true);
          expect(result).toBeDefined();
        });
        """
        result = verification_oracle_guard.audit(valid_record(), source_text=bad_test_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_BANNED_MODULE_MOCK", codes)
        self.assertIn("SOURCE_UNSEEDED_RANDOM_IN_TEST", codes)
        self.assertIn("SOURCE_WALL_CLOCK_SLEEP_IN_TEST", codes)
        self.assertIn("SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION", codes)

    def test_source_scanner_accepts_clean_verified_fake_property_chaos_example(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = verification_oracle_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_rejecting_mock_slop_suite(self):
        record = {
            "schema_version": "1.0",
            "target_system": {
                "module_under_test": "MarketplaceEscrowSettlementEngine (src/ledger/settlementEngine.ts)",
                "domain_category": "financial_ledger_and_payments",
                "module_mocking_banned": True,
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing PR test suite that suppresses anti-slop/no-module-mocking with vi.mock(), tests only 1 static happy-path split, and uses setTimeout(200) instead of a Contract-Verified In-Memory Fake and Seeded Chaos Harness.",
                "revisit_triggers": [
                    "Replace vi.mock with InMemoryLedgerStorage verified by verifyLedgerStorageContract",
                    "Add >=100 property runs and Mulberry32 + VirtualClock chaos fault injection",
                ],
            },
        }
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")
        self.assertEqual(result["findings"], [])

    def test_cli_invocation_success(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(valid_record(), tmp)
            tmp_path = Path(tmp.name)
        try:
            res = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", str(tmp_path), "--source", str(TS_EXAMPLE), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)
            self.assertEqual(payload["record_status"], "complete")
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
