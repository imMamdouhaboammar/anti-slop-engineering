# SPDX-License-Identifier: MIT
# Unit tests for scripts/profiler_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "profiler_guard.py"
EXAMPLE = ROOT / "skills" / "mechanical-sympathy-profiler" / "examples" / "mechanical-sympathy-profiler-record.json"
TS_EXAMPLE = ROOT / "skills" / "mechanical-sympathy-profiler" / "examples" / "batched-streaming-hot-path.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import profiler_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class ProfilerGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = profiler_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_explain_analyze_buffers_when_method_requires_it_fails(self):
        record = valid_record()
        record["baseline_measurement"]["explain_analyze_buffers"] = "Seq Scan on ledger_entries (cost=0..100)"
        record["post_change_measurement"]["explain_analyze_buffers"] = ""
        result = profiler_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("BASELINE_MEASUREMENT_MISSING_EXPLAIN_ANALYZE_BUFFERS", codes)
        self.assertIn("POST_CHANGE_MEASUREMENT_MISSING_EXPLAIN_ANALYZE_BUFFERS", codes)

    def test_no_measured_improvement_or_p99_regression_fails(self):
        record = valid_record()
        record["post_change_measurement"]["p50_ms"] = 420.0
        record["post_change_measurement"]["p99_ms"] = 995.0
        record["post_change_measurement"]["alloc_bytes_per_op"] = 68450000
        record["post_change_measurement"]["io_roundtrips_per_request"] = 2001
        result = profiler_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NO_MEASURED_PERFORMANCE_IMPROVEMENT", codes)
        self.assertIn("POST_CHANGE_P99_REGRESSED", codes)

    def test_speculative_caching_or_insufficient_gc_mitigations_fails(self):
        record = valid_record()
        record["bottleneck_physics"]["speculative_caching_rejected"] = False
        record["hardware_and_io_remediation"]["gc_pressure_mitigations"] = ["preindex_o1_map_set_lookup"]
        result = profiler_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SPECULATIVE_CACHING_NOT_REJECTED", codes)
        self.assertIn("INSUFFICIENT_GC_PRESSURE_MITIGATIONS", codes)

    def test_source_scanner_flags_loop_io_readfilesync_quadratic_scan_and_alloc_churn(self):
        bad_source = """
        async function slowReconcile(items, tenants) {
          const raw = fs.readFileSync("/tmp/big.ndjson", "utf8");
          const cloned = JSON.parse(JSON.stringify(items));
          const enriched = cloned.map(x => ({ ...x, t: tenants.find(t => t.id === x.tenantId) }));
          for (const item of enriched) {
            await db.query("UPDATE invoices SET status = $1 WHERE id = $2", [item.status, item.id]);
          }
        }
        """
        result = profiler_guard.audit(valid_record(), source_text=bad_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_AWAIT_IO_IN_LOOP", codes)
        self.assertIn("SOURCE_SYNC_WHOLE_FILE_RAM_BUFFER", codes)
        self.assertIn("SOURCE_QUADRATIC_NESTED_ARRAY_SCAN", codes)
        self.assertIn("SOURCE_HOT_PATH_ALLOCATION_CHURN", codes)

    def test_source_scanner_accepts_clean_batched_streaming_example(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = profiler_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_rejecting_unmeasured_blind_caching_request(self):
        record = {
            "schema_version": "1.0",
            "target_path": {
                "component_or_query": "LedgerSettlementEndpoint (/api/v1/ledger/settlements)",
                "workload_cardinality": "50,000 ledger rows per tenant",
                "measurement_method": "explain_analyze_buffers"
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing request to wrap unmeasured slow SQL query in a 5-minute Redis cache and add guessed single-column indexes without EXPLAIN (ANALYZE, BUFFERS) baseline proof.",
                "revisit_triggers": ["Capture EXPLAIN (ANALYZE, BUFFERS) baseline plan on ledger_entries query first"]
            }
        }
        result = profiler_guard.audit(record)
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
