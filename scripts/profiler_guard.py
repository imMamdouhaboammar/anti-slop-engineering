#!/usr/bin/env python3
"""Check Mechanical Sympathy & Empirical Profiler records and source files for baseline/post-change measurements (EXPLAIN ANALYZE BUFFERS, P99 latency, heap allocations), bounded-chunk streaming, zero-allocation hot paths, and I/O batching/pipelining."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_MEASUREMENT_METHODS = {
    "microbenchmark_and_explain_analyze_buffers",
    "microbenchmark_alloc_and_latency",
    "explain_analyze_buffers",
    "heap_and_cpu_flamegraph_profile",
}
EXPLAIN_REQUIRED_METHODS = {
    "microbenchmark_and_explain_analyze_buffers",
    "explain_analyze_buffers",
}
VALID_PRIMARY_BOUNDS = {
    "network_io_roundtrips",
    "disk_buffer_io",
    "memory_allocation_gc",
    "algorithmic_complexity",
    "cpu_cycles",
    "lock_contention",
}
VALID_MEMORY_STRATEGIES = {
    "bounded_chunk_streaming",
    "preallocated_buffer_reuse",
    "in_place_single_pass",
    "index_only_covering_scan",
}
VALID_GC_MITIGATIONS = {
    "eliminate_intermediate_array_chains",
    "preindex_o1_map_set_lookup",
    "reuse_typed_buffer_scratchpad",
    "hoist_loop_invariant_allocations",
    "in_place_accumulator_mutation",
    "bounded_stream_backpressure",
}
VALID_IO_BATCHING_STRATEGIES = {
    "sql_unnest_or_any_batch",
    "redis_mget_or_pipeline",
    "dataloader_request_coalescing",
    "streaming_cursor_fetch",
    "none_pure_cpu_memory_path",
}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_target_path(record, require):
    target = record.get("target_path")
    require(isinstance(target, dict), "INVALID_TARGET_PATH", "target_path must be a dictionary")
    if not isinstance(target, dict):
        return None
    require(filled(target.get("component_or_query"), 10),
            "MISSING_COMPONENT_OR_QUERY",
            "target_path.component_or_query must be at least 10 characters")
    require(filled(target.get("workload_cardinality"), 5),
            "MISSING_WORKLOAD_CARDINALITY",
            "target_path.workload_cardinality must describe dataset cardinality")
    method = target.get("measurement_method")
    require(choice(method, VALID_MEASUREMENT_METHODS),
            "INVALID_MEASUREMENT_METHOD",
            "target_path.measurement_method must be one of: %s"
            % ", ".join(sorted(VALID_MEASUREMENT_METHODS)))
    return method


def _validate_telemetry_block(block, block_name, method, require):
    require(isinstance(block, dict), "INVALID_%s" % block_name.upper(),
            "%s must be a dictionary" % block_name)
    if not isinstance(block, dict):
        return False
    p50 = block.get("p50_ms")
    p99 = block.get("p99_ms")
    alloc_bytes = block.get("alloc_bytes_per_op")
    allocs = block.get("allocs_per_op")
    roundtrips = block.get("io_roundtrips_per_request")

    require(isinstance(p50, (int, float)) and float(p50) > 0,
            "%s_INVALID_P50_MS" % block_name.upper(),
            "%s.p50_ms must be > 0" % block_name)
    require(isinstance(p99, (int, float)) and float(p99) > 0
            and (not isinstance(p50, (int, float)) or float(p99) >= float(p50)),
            "%s_INVALID_P99_MS" % block_name.upper(),
            "%s.p99_ms must be > 0 and >= p50_ms" % block_name)
    require(isinstance(alloc_bytes, int) and alloc_bytes >= 0,
            "%s_INVALID_ALLOC_BYTES" % block_name.upper(),
            "%s.alloc_bytes_per_op must be a non-negative integer" % block_name)
    require(isinstance(allocs, int) and allocs >= 0,
            "%s_INVALID_ALLOCS_PER_OP" % block_name.upper(),
            "%s.allocs_per_op must be a non-negative integer" % block_name)
    require(isinstance(roundtrips, int) and roundtrips >= 0,
            "%s_INVALID_IO_ROUNDTRIPS" % block_name.upper(),
            "%s.io_roundtrips_per_request must be a non-negative integer" % block_name)

    if method in EXPLAIN_REQUIRED_METHODS:
        plan = block.get("explain_analyze_buffers")
        has_buffers = filled(plan, 20) and ("Buffers:" in plan or "shared hit=" in plan)
        require(has_buffers,
                "%s_MISSING_EXPLAIN_ANALYZE_BUFFERS" % block_name.upper(),
                "%s.explain_analyze_buffers must include physical buffer telemetry ('Buffers:' / 'shared hit=')"
                % block_name)
    return True


def check_measurements_and_delta(record, method, require):
    base = record.get("baseline_measurement")
    post = record.get("post_change_measurement")
    base_ok = _validate_telemetry_block(base, "baseline_measurement", method, require)
    if base_ok:
        require(filled(base.get("evidence_artifact"), 15),
                "MISSING_BASELINE_EVIDENCE_ARTIFACT",
                "baseline_measurement.evidence_artifact must cite the benchmark command or plan artifact")

    post_ok = _validate_telemetry_block(post, "post_change_measurement", method, require)
    if not post_ok:
        return
    require(post.get("regression_check_passed") is True,
            "REGRESSION_CHECK_NOT_PASSED",
            "post_change_measurement.regression_check_passed must be true")
    require(filled(post.get("improvement_summary"), 20),
            "MISSING_IMPROVEMENT_SUMMARY",
            "post_change_measurement.improvement_summary must state the before/after delta")

    if not base_ok:
        return
    p99_ok = isinstance(base.get("p99_ms"), (int, float)) and isinstance(post.get("p99_ms"), (int, float))
    alloc_ok = isinstance(base.get("alloc_bytes_per_op"), int) and isinstance(post.get("alloc_bytes_per_op"), int)
    io_ok = isinstance(base.get("io_roundtrips_per_request"), int) and isinstance(post.get("io_roundtrips_per_request"), int)
    if p99_ok and alloc_ok and io_ok:
        improved = (
            float(post["p99_ms"]) <= float(base["p99_ms"]) * 0.85
            or post["alloc_bytes_per_op"] < base["alloc_bytes_per_op"]
            or post["io_roundtrips_per_request"] < base["io_roundtrips_per_request"]
        )
        require(improved,
                "NO_MEASURED_PERFORMANCE_IMPROVEMENT",
                "post_change_measurement must demonstrate >=15% P99 improvement or a strict reduction in alloc_bytes_per_op / io_roundtrips_per_request")
        require(float(post["p99_ms"]) <= float(base["p99_ms"]),
                "POST_CHANGE_P99_REGRESSED",
                "post_change_measurement.p99_ms regressed above baseline_measurement.p99_ms")


def check_bottleneck_and_remediation(record, require):
    physics = record.get("bottleneck_physics")
    require(isinstance(physics, dict), "INVALID_BOTTLENECK_PHYSICS",
            "bottleneck_physics must be a dictionary")
    if isinstance(physics, dict):
        require(choice(physics.get("primary_bound"), VALID_PRIMARY_BOUNDS),
                "INVALID_PRIMARY_BOUND",
                "bottleneck_physics.primary_bound must be a valid physical resource bound")
        require(physics.get("speculative_caching_rejected") is True,
                "SPECULATIVE_CACHING_NOT_REJECTED",
                "bottleneck_physics.speculative_caching_rejected must be true")
        require(filled(physics.get("root_mechanic"), 20),
                "MISSING_ROOT_MECHANIC",
                "bottleneck_physics.root_mechanic must explain the physical bottleneck")

    rem = record.get("hardware_and_io_remediation")
    require(isinstance(rem, dict), "INVALID_HARDWARE_AND_IO_REMEDIATION",
            "hardware_and_io_remediation must be a dictionary")
    if not isinstance(rem, dict):
        return
    require(choice(rem.get("memory_strategy"), VALID_MEMORY_STRATEGIES),
            "INVALID_MEMORY_STRATEGY",
            "hardware_and_io_remediation.memory_strategy must be a valid mechanical sympathy strategy")
    mitigations = rem.get("gc_pressure_mitigations")
    require(isinstance(mitigations, list) and len(mitigations) >= 2
            and all(isinstance(m, str) and m in VALID_GC_MITIGATIONS for m in mitigations),
            "INSUFFICIENT_GC_PRESSURE_MITIGATIONS",
            "hardware_and_io_remediation.gc_pressure_mitigations must list at least 2 valid GC mitigations")
    require(choice(rem.get("io_batching_strategy"), VALID_IO_BATCHING_STRATEGIES),
            "INVALID_IO_BATCHING_STRATEGY",
            "hardware_and_io_remediation.io_batching_strategy must be a valid batching/pipelining strategy")
    require(filled(rem.get("roundtrip_reduction"), 5),
            "MISSING_ROUNDTRIP_REDUCTION",
            "hardware_and_io_remediation.roundtrip_reduction must state the roundtrip reduction")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    has_loop_io = bool(
        re.search(
            r"\b(?:for|while)\s*\([^)]*\)\s*\{[^}]*\bawait\s+(?:fetch\b|db\.|prisma\.|redis\.|axios\.|client\.query\b)",
            source_text,
            re.DOTALL,
        )
    )
    require(not has_loop_io, "SOURCE_AWAIT_IO_IN_LOOP",
            "Detected serial 'await' network/DB/Redis I/O inside a loop; batch with UNNEST/ANY($1) or pipeline()")

    has_sync_file_buffer = bool(re.search(r"\breadFileSync\s*\(", source_text))
    require(not has_sync_file_buffer, "SOURCE_SYNC_WHOLE_FILE_RAM_BUFFER",
            "Detected synchronous whole-file RAM buffering (readFileSync); use bounded-chunk streaming with backpressure")

    has_quadratic_scan = bool(
        re.search(
            r"\.(?:map|filter|forEach|reduce)\s*\([^;]{1,220}?\.(?:find|includes|indexOf)\s*\(",
            source_text,
            re.DOTALL,
        )
    )
    require(not has_quadratic_scan, "SOURCE_QUADRATIC_NESTED_ARRAY_SCAN",
            "Detected O(N^2) nested .find()/.includes()/.indexOf() inside an array loop; pre-index into an O(1) Map or Set")

    has_alloc_churn = bool(
        re.search(r"JSON\.parse\s*\(\s*JSON\.stringify\s*\(", source_text)
        or re.search(
            r"\.(?:map|filter)\s*\([^)]+\)\s*\.(?:map|filter)\s*\([^)]+\)\s*\.(?:map|filter|reduce)\s*\(",
            source_text,
        )
    )
    require(not has_alloc_churn, "SOURCE_HOT_PATH_ALLOCATION_CHURN",
            "Detected hot-path heap allocation churn (JSON.parse(JSON.stringify) or >=3 chained .map/.filter passes)")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    method = check_target_path(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_measurements_and_delta(record, method, require)
        check_bottleneck_and_remediation(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    return {
        "record_status": "incomplete" if findings else "complete",
        "verdict_action": action,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--source", type=Path, default=None,
                        help="Optional source file to scan for loop I/O, whole-file RAM buffering, O(N^2) scans, or GC allocation churn")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Mechanical Sympathy & Profiler record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Mechanical Sympathy & Profiler record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: EXPLAIN (ANALYZE, BUFFERS) plans and P99/allocation benchmarks must be executed against live workloads.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
