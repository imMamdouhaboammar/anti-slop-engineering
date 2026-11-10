# SPDX-License-Identifier: MIT
# Unit tests for scripts/perf_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "perf_guard.py"
EXAMPLE = ROOT / "skills" / "mechanical-sympathy-and-perf-gate" / "examples" / "perf-gate-record.json"
TS_EXAMPLE = ROOT / "skills" / "mechanical-sympathy-and-perf-gate" / "examples" / "perf-hardened-pipeline.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import perf_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class PerfGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_target_system_fields_fail(self):
        record = valid_record()
        record["target_system"]["subsystem_or_flow"] = "too short"
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_SUBSYSTEM_OR_FLOW", codes)

    def test_missing_flamegraph_artifact_fails(self):
        record = valid_record()
        record["benchmark_proof"]["flamegraph_or_trace_artifact"] = ""
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_FLAMEGRAPH_OR_TRACE_ARTIFACT", codes)

    def test_no_measured_improvement_or_p99_regression_fails(self):
        record = valid_record()
        record["benchmark_proof"]["post_change_measurement"]["p50_ms"] = 15.0
        record["benchmark_proof"]["post_change_measurement"]["p99_ms"] = 30.0
        record["benchmark_proof"]["post_change_measurement"]["alloc_bytes_per_op"] = 1500000
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NO_MEASURED_PERFORMANCE_IMPROVEMENT", codes)
        self.assertIn("POST_CHANGE_P99_REGRESSED", codes)

    def test_data_oriented_design_invalid_layout_or_allocations_fails(self):
        record = valid_record()
        record["data_oriented_design"]["memory_layout"] = "linked_list_pointer_soup"
        record["data_oriented_design"]["hot_loop_allocations_eliminated"] = False
        record["data_oriented_design"]["allocations_eliminated_details"] = ["typed_buffer_scratchpad"]
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_MEMORY_LAYOUT", codes)
        self.assertIn("HOT_LOOP_ALLOCATIONS_NOT_ELIMINATED", codes)
        self.assertIn("INSUFFICIENT_ALLOCATION_MITIGATIONS", codes)

    def test_frame_budget_exceeding_120hz_or_non_compositor_props_fails(self):
        record = valid_record()
        record["frame_and_latency_budget"]["frame_budget_ms"] = 16.67
        record["frame_and_latency_budget"]["main_thread_max_script_ms"] = 7.5
        record["frame_and_latency_budget"]["compositor_only_animated_properties"] = ["transform", "height"]
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FRAME_BUDGET_EXCEEDS_120HZ", codes)
        self.assertIn("MAIN_THREAD_SCRIPT_EXCEEDS_4MS", codes)
        self.assertIn("NON_COMPOSITOR_ANIMATION_PROPERTIES", codes)

    def test_zero_copy_whole_payload_buffering_fails(self):
        record = valid_record()
        record["zero_copy_and_streaming"]["whole_payload_ram_buffering_prohibited"] = False
        record["zero_copy_and_streaming"]["buffer_chunk_size_bytes"] = 512  # Below 1024
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("WHOLE_PAYLOAD_RAM_BUFFERING_PERMITTED", codes)
        self.assertIn("INVALID_BUFFER_CHUNK_SIZE", codes)

    def test_refuse_verdict_permits_rejecting_unmeasured_optimization(self):
        record = {
            "schema_version": "1.0",
            "target_system": {
                "subsystem_or_flow": "RealtimeTransactionFeed",
                "workload_cardinality": "100k events/sec",
                "runtime_platform": "node_v8"
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing proposed optimization PR: author claims 2x speedup by adding useMemo and Redis caching, but provides zero flamegraph or benchmark numbers before/after.",
                "revisit_triggers": ["Provide flamegraph profiles and microbenchmark before and after"]
            }
        }
        result = perf_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")
        self.assertEqual(result["findings"], [])

    def test_source_scanner_flags_hazards(self):
        bad_source = """
        async function badPipeline(items, db) {
          const raw = fs.readFileSync("/data/large.ndjson", "utf8");
          const map = items.reduce((acc, x) => ({ ...acc, [x.id]: x }), {});
          const found = items.map(x => items.find(y => y.id === x.parentId));
          element.style.top = "10px";
          const h = element.offsetHeight;
          localStorage.setItem("cache", JSON.stringify(items));
          for (const item of items) {
            await db.query("SELECT * FROM table WHERE id = $1", [item.id]);
          }
        }
        """
        result = perf_guard.audit(valid_record(), source_text=bad_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_WHOLE_PAYLOAD_RAM_BUFFERING", codes)
        self.assertIn("SOURCE_LAYOUT_THRASHING_DETECTED", codes)
        self.assertIn("SOURCE_QUADRATIC_NESTED_SCAN", codes)
        self.assertIn("SOURCE_HOT_PATH_ALLOCATION_CHURN", codes)
        self.assertIn("SOURCE_SERIAL_AWAIT_IN_LOOP", codes)
        self.assertIn("SOURCE_MAIN_THREAD_SYNC_STORAGE_STALL", codes)

    def test_source_scanner_accepts_clean_example(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = perf_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
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
