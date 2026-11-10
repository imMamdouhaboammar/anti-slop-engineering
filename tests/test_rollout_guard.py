# SPDX-License-Identifier: MIT
# Unit tests for scripts/rollout_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rollout_guard.py"
EXAMPLE = ROOT / "skills" / "safe-evolution-and-rollout-choreographer" / "examples" / "safe-evolution-record.json"

sys.path.insert(0, str(ROOT / "scripts"))
import rollout_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class RolloutGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_wire_compatibility_missing_tolerant_reader_fails_proceed(self):
        record = valid_record()
        record["wire_compatibility"]["tolerant_reader_enforced"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("TOLERANT_READER_NOT_ENFORCED", codes)

    def test_wire_compatibility_missing_additive_only_fails_proceed(self):
        record = valid_record()
        record["wire_compatibility"]["additive_only_verified"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("ADDITIVE_ONLY_NOT_VERIFIED", codes)

    def test_wire_compatibility_invalid_protocol_fails(self):
        record = valid_record()
        record["wire_compatibility"]["protocol"] = "custom_binary_hack"
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_WIRE_PROTOCOL", codes)

    def test_shadow_mode_unfenced_storage_mutations_fails(self):
        record = valid_record()
        record["dark_launch_and_shadow"]["side_effect_fencing"]["storage_mutations_blocked"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNFENCED_STORAGE_MUTATIONS", codes)

    def test_shadow_mode_unfenced_external_apis_fails(self):
        record = valid_record()
        record["dark_launch_and_shadow"]["side_effect_fencing"]["external_apis_mocked"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNFENCED_EXTERNAL_APIS", codes)

    def test_shadow_mode_excessive_mismatch_rate_fails(self):
        record = valid_record()
        record["dark_launch_and_shadow"]["parity_gate"]["measured_mismatch_rate"] = 0.05
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("EXCESSIVE_SHADOW_MISMATCH", codes)

    def test_shadow_mode_insufficient_samples_fails(self):
        record = valid_record()
        record["dark_launch_and_shadow"]["parity_gate"]["sample_size_evaluated"] = 500
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_SHADOW_SAMPLES", codes)

    def test_feature_flag_untested_kill_switch_fails(self):
        record = valid_record()
        record["feature_flag_governance"]["kill_switch_tested"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("KILL_SWITCH_NOT_TESTED", codes)

    def test_feature_flag_slow_kill_switch_fails(self):
        record = valid_record()
        record["feature_flag_governance"]["kill_switch_latency_ms"] = 3500
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SLOW_KILL_SWITCH_PROPAGATION", codes)

    def test_feature_flag_ttl_exceeds_90_days_fails(self):
        record = valid_record()
        record["feature_flag_governance"]["created_at"] = "2026-01-01T00:00:00Z"
        record["feature_flag_governance"]["expires_at"] = "2026-06-01T00:00:00Z"
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FLAG_TTL_EXCEEDS_90_DAYS", codes)

    def test_strangler_fig_missing_rollback_triggers_fails(self):
        record = valid_record()
        record["strangler_fig_protocol"]["automated_rollback_slo_triggers"] = []
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_ROLLBACK_TRIGGERS", codes)

    def test_pause_verdict_permits_incomplete_shadow_run(self):
        record = valid_record()
        record["verdict"]["status"] = "pause"
        record["dark_launch_and_shadow"]["parity_gate"]["sample_size_evaluated"] = 1200
        record["wire_compatibility"]["tolerant_reader_enforced"] = False
        result = rollout_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "pause")

    def test_source_scanner_flags_unfenced_shadow_billing_and_comms(self):
        bad_source = """
        async function runShadowMode(input) {
            const shadowExecution = true;
            await stripe.charges.create({ amount: 1000 });
            await twilio.messages.send({ to: "+1234567890" });
        }
        """
        findings = rollout_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("UNFENCED_SHADOW_BILLING", codes)
        self.assertIn("UNFENCED_SHADOW_COMMUNICATION", codes)

    def test_source_scanner_flags_missing_kill_switch_and_ttl(self):
        bad_source = """
        const checkoutFeatureFlag = {
            id: "checkout_v2",
            enabled: true
        };
        """
        findings = rollout_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("FLAG_MISSING_KILL_SWITCH", codes)
        self.assertIn("FLAG_MISSING_EXPIRATION", codes)

    def test_source_scanner_flags_big_bang_cutover(self):
        bad_source = "// We will switch 100% traffic directly at midnight without canary"
        findings = rollout_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("BIG_BANG_CUTOVER_DETECTED", codes)

    def test_cli_invocation_audit(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", str(EXAMPLE), "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["record_status"], "complete")
        self.assertEqual(data["verdict_action"], "proceed")

    def test_cli_invocation_scan(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as tf:
            tf.write("const cleanHelper = (x: number) => x * 2;\n")
            temp_path = tf.name
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "scan", "--files", temp_path, "--json"],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(proc.stdout)
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["findings"], [])
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
