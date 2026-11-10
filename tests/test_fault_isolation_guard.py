# SPDX-License-Identifier: MIT
# Unit tests for scripts/fault_isolation_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fault_isolation_guard.py"
EXAMPLE = ROOT / "skills" / "scientific-fault-isolation" / "examples" / "scientific-fault-isolation-record.json"
TS_EXAMPLE = ROOT / "skills" / "scientific-fault-isolation" / "examples" / "deterministic-race-reproducer.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import fault_isolation_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class FaultIsolationGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_shotgun_production_edit_before_probe_fails(self):
        record = valid_record()
        record["differential_diagnosis"]["zero_production_edits_before_probe"] = False
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SHOTGUN_PRODUCTION_EDIT_BEFORE_PROBE", codes)

    def test_fewer_than_three_hypotheses_fails(self):
        record = valid_record()
        record["differential_diagnosis"]["hypotheses"] = record["differential_diagnosis"]["hypotheses"][:2]
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_HYPOTHESES", codes)
        self.assertIn("FEWER_THAN_TWO_FALSIFIED_HYPOTHESES", codes)

    def test_fewer_than_two_falsified_hypotheses_fails(self):
        record = valid_record()
        record["differential_diagnosis"]["hypotheses"][2]["status"] = "pending"
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FEWER_THAN_TWO_FALSIFIED_HYPOTHESES", codes)
        self.assertIn("PROBE_KILLED_IDS_MISMATCH", codes)

    def test_probe_mismatch_with_confirmed_hypothesis_fails(self):
        record = valid_record()
        record["discriminating_probe"]["confirmed_hypothesis_id"] = "H99"
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("PROBE_CONFIRMED_ID_MISMATCH", codes)

    def test_invalid_binary_search_method_fails(self):
        record = valid_record()
        record["binary_search_isolation"]["method"] = "random_file_guessing"
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_BISECT_METHOD", codes)

    def test_sleep_timing_bandaid_or_flaky_reproducer_fails(self):
        record = valid_record()
        record["determinism_pinning"]["sleep_based_timing_absent"] = False
        record["determinism_pinning"]["reproduction_rate_after_pinning"] = "passes_9_of_10_runs"
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SLEEP_TIMING_BANDAID_PRESENT", codes)
        self.assertIn("FLAKY_REPRODUCER_NOT_PINNED", codes)

    def test_missing_revert_falsification_or_leftover_probes_fails(self):
        record = valid_record()
        record["red_green_verification"]["failed_again_on_fix_revert"] = False
        record["red_green_verification"]["diagnostic_probes_removed"] = False
        result = fault_isolation_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("REVERT_FALSIFICATION_MISSING", codes)
        self.assertIn("LEFTOVER_DIAGNOSTIC_PROBES", codes)

    def test_source_scanner_flags_sleep_leftover_probes_and_swallowed_exceptions(self):
        bad_source = """
        async function testRace() {
          console.log("DEBUG: entering race");
          await new Promise((r) => setTimeout(r, 250));
          try {
            await runCheckout();
          } catch (err) {}
        }
        """
        result = fault_isolation_guard.audit(valid_record(), source_text=bad_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_SLEEP_SYNCHRONIZATION_HACK", codes)
        self.assertIn("SOURCE_LEFTOVER_DEBUG_PROBE", codes)
        self.assertIn("SOURCE_SWALLOWED_EXCEPTION", codes)

    def test_source_scanner_accepts_clean_deterministic_reproducer(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = fault_isolation_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_blocking_shotgun_patch(self):
        record = {
            "schema_version": "1.0",
            "symptom": {
                "observable_failure": "Intermittent empty order list returned by GraphQL /orders resolver for enterprise tenants",
                "reproduction_frequency_before": "intermittent_flaky",
                "affected_boundary": "OrdersResolver.orders -> DataLoader -> RedisCache"
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing shotgun request to disable Redis, change SQL JOIN, and add empty catch in a single unverified commit without a discriminating probe.",
                "revisit_triggers": ["Complete 3-hypothesis differential diagnosis probe on tenant DataLoader keys"]
            }
        }
        result = fault_isolation_guard.audit(record)
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
