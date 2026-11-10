# SPDX-License-Identifier: MIT
# Unit tests for scripts/observability_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "observability_guard.py"
EXAMPLE = (
    ROOT
    / "skills"
    / "observability-and-slo-architect"
    / "examples"
    / "observability-slo-record.json"
)
EXAMPLE_SOURCE = (
    ROOT
    / "skills"
    / "observability-and-slo-architect"
    / "examples"
    / "dapper-monarch-telemetry-pipeline.ts"
)

sys.path.insert(0, str(ROOT / "scripts"))
import observability_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class ObservabilityGuardTests(unittest.TestCase):
    def test_canonical_record_is_complete_and_proceed(self):
        record = valid_record()
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_service_name_fails(self):
        record = valid_record()
        record["target_service"]["service_name"] = "abc"
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_SERVICE_NAME", codes)

    def test_invalid_telemetry_standard_fails(self):
        record = valid_record()
        record["target_service"]["telemetry_standard"] = "statsd_unsupported"
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_TELEMETRY_STANDARD", codes)

    def test_insufficient_execution_boundaries_fails(self):
        record = valid_record()
        record["target_service"]["execution_boundaries"] = ["http_or_grpc_service"]
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_EXECUTION_BOUNDARIES", codes)

    def test_dynamic_ids_not_banned_fails(self):
        record = valid_record()
        record["metric_cardinality_governance"]["dynamic_ids_banned_in_metric_labels"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("DYNAMIC_IDS_NOT_BANNED", codes)

    def test_unmatched_routes_not_collapsed_fails(self):
        record = valid_record()
        record["metric_cardinality_governance"]["unmatched_routes_collapsed_to_constant"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("UNMATCHED_ROUTES_NOT_COLLAPSED", codes)

    def test_high_cardinality_label_in_approved_metric_labels_fails(self):
        record = valid_record()
        record["metric_cardinality_governance"]["approved_low_cardinality_labels"].append("user_id")
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("HIGH_CARDINALITY_LABEL_IN_METRIC", codes)

    def test_cardinality_product_exceeds_thousand_fails(self):
        record = valid_record()
        record["metric_cardinality_governance"]["max_label_cardinality_product"] = 5000
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_CARDINALITY_PRODUCT", codes)

    def test_gauge_latency_not_banned_fails(self):
        record = valid_record()
        record["latency_histograms_and_quantiles"]["gauge_or_average_latency_banned"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("GAUGE_LATENCY_NOT_BANNED", codes)

    def test_insufficient_histogram_buckets_fails(self):
        record = valid_record()
        record["latency_histograms_and_quantiles"]["explicit_buckets_ms"] = [10, 50, 100]
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_HISTOGRAM_BUCKETS", codes)

    def test_non_monotonic_buckets_fail(self):
        record = valid_record()
        record["latency_histograms_and_quantiles"]["explicit_buckets_ms"] = [10, 50, 25, 100, 200]
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NON_MONOTONIC_BUCKETS", codes)

    def test_missing_mandatory_quantiles_fail(self):
        record = valid_record()
        record["latency_histograms_and_quantiles"]["tracked_quantiles"] = ["p50", "p95"]
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_MANDATORY_QUANTILES", codes)

    def test_exemplars_not_attached_fails(self):
        record = valid_record()
        record["latency_histograms_and_quantiles"]["trace_exemplars_attached"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("EXEMPLARS_NOT_ATTACHED", codes)

    def test_disabled_red_or_use_metrics_fail(self):
        record = valid_record()
        record["red_and_use_metrics"]["red_endpoint_metrics_enabled"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("RED_METRICS_DISABLED", codes)

        record2 = valid_record()
        record2["red_and_use_metrics"]["use_resource_metrics_enabled"] = False
        result2 = observability_guard.audit(record2)
        self.assertEqual(result2["record_status"], "incomplete")
        codes2 = [f["code"] for f in result2["findings"]]
        self.assertIn("USE_METRICS_DISABLED", codes2)

    def test_w3c_propagation_missing_fields_fail(self):
        record = valid_record()
        record["w3c_context_propagation"]["correlation_id_enforced"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("CORRELATION_ID_NOT_ENFORCED", codes)

    def test_raw_console_log_not_banned_fails(self):
        record = valid_record()
        record["structured_logging_and_redaction"]["raw_console_log_banned"] = False
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("RAW_CONSOLE_LOG_NOT_BANNED", codes)

    def test_insufficient_redacted_keys_fails(self):
        record = valid_record()
        record["structured_logging_and_redaction"]["redacted_sensitive_keys"] = ["password"]
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_REDACTED_KEYS", codes)

    def test_burn_rate_too_low_fails(self):
        record = valid_record()
        record["slo_and_burn_rate_alerts"]["fast_burn_multi_window"]["burn_rate_multiplier"] = 5.0
        result = observability_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("LOW_FAST_BURN_MULTIPLIER", codes)

        record2 = valid_record()
        record2["slo_and_burn_rate_alerts"]["slow_burn_multi_window"]["burn_rate_multiplier"] = 0.5
        result2 = observability_guard.audit(record2)
        self.assertEqual(result2["record_status"], "incomplete")
        codes2 = [f["code"] for f in result2["findings"]]
        self.assertIn("LOW_SLOW_BURN_MULTIPLIER", codes2)

    def test_pause_and_refuse_verdicts(self):
        record_pause = valid_record()
        record_pause["verdict"]["action"] = "pause"
        result_pause = observability_guard.audit(record_pause)
        self.assertEqual(result_pause["record_status"], "complete")
        self.assertEqual(result_pause["verdict_action"], "pause")

        record_refuse = valid_record()
        record_refuse["verdict"]["action"] = "refuse"
        result_refuse = observability_guard.audit(record_refuse)
        self.assertEqual(result_refuse["record_status"], "complete")
        self.assertEqual(result_refuse["verdict_action"], "refuse")

    def test_source_scanner_accepts_clean_pipeline(self):
        findings = observability_guard.scan_source_code(EXAMPLE_SOURCE)
        self.assertEqual(findings, [])

    def test_source_scanner_flags_high_cardinality_label(self):
        code = 'counter.add(1, { user_id: req.user.id });'
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as tf:
            tf.write(code)
            tf_path = Path(tf.name)
        try:
            findings = observability_guard.scan_source_code(tf_path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "HIGH_CARDINALITY_METRIC_CALL")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_source_scanner_flags_gauge_averaged_latency(self):
        code = 'gauge.set(avg_latency);'
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as tf:
            tf.write(code)
            tf_path = Path(tf.name)
        try:
            findings = observability_guard.scan_source_code(tf_path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "GAUGE_AVERAGED_LATENCY")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_source_scanner_flags_raw_console_log(self):
        code = 'console.log("User signed in");'
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as tf:
            tf.write(code)
            tf_path = Path(tf.name)
        try:
            findings = observability_guard.scan_source_code(tf_path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "RAW_CONSOLE_LOGGING")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_source_scanner_flags_unstructured_logger_error(self):
        code = 'logger.error("Something went wrong " + err);'
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as tf:
            tf.write(code)
            tf_path = Path(tf.name)
        try:
            findings = observability_guard.scan_source_code(tf_path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "UNSTRUCTURED_LOGGER_ERROR")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_source_scanner_flags_noisy_threshold_alert(self):
        code = 'alert: HighCpuRule cpu > 80% for 5m'
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(code)
            tf_path = Path(tf.name)
        try:
            findings = observability_guard.scan_source_code(tf_path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "NON_IMPACT_RESOURCE_ALERT")
        finally:
            tf_path.unlink(missing_ok=True)

    def test_cli_invocation_success_and_failure(self):
        proc_ok = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", str(EXAMPLE), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_ok.returncode, 0)
        out = json.loads(proc_ok.stdout)
        self.assertEqual(out["record_status"], "complete")

        proc_missing = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", "nonexistent.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_missing.returncode, 1)


if __name__ == "__main__":
    unittest.main()
