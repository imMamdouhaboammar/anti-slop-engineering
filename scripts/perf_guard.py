#!/usr/bin/env python3
"""Check Mechanical Sympathy & Performance Gate records and source files.

Enforces Apple & Google Systems performance discipline:
1. Data-Oriented Design (DOD): CPU cache locality (64B lines), SoA/flat typed buffers, zero hot-loop allocations.
2. Frame & Latency Budgets: 8.33ms (120Hz ProMotion) / 16.67ms (60Hz), <4ms main-thread script time, zero layout thrashing, compositor-only motion.
3. Zero-Copy & Streaming: Bounded-chunk streaming with backpressure (O(1) RSS memory), ArrayBuffer transfer/views, whole-payload RAM buffering prohibited.
4. Benchmark Proof & Flamegraphs: Verified baseline vs post-change telemetry (P50, P99, heap allocations, throughput, buffer hits/reads) proving >=15% P99 improvement or strict allocation/roundtrip reduction, with flamegraph/trace artifacts.
"""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_REFRESH_RATES = {60, 120}
VALID_FRAME_BUDGETS = {8.3, 8.33, 16.6, 16.67}
VALID_COMPOSITOR_PROPS = {"transform", "opacity"}
VALID_MEASUREMENT_METHODS = {
    "flamegraph_cpu_heap_profile",
    "microbenchmark_with_alloc_and_p99",
    "explain_analyze_buffers_and_p99",
    "frame_timing_and_trace_profile",
}
VALID_MEMORY_LAYOUTS = {
    "struct_of_arrays_contiguous",
    "typed_array_flat_buffer",
    "preallocated_fixed_buffer",
    "cacheline_aligned_64b",
}
VALID_ALLOCATION_MITIGATIONS = {
    "hoisted_regex_and_formatters",
    "preallocated_capacity",
    "in_place_accumulator",
    "zero_intermediate_array_passes",
    "typed_buffer_scratchpad",
    "object_pool_recycling",
}
VALID_OFFLOAD_STRATEGIES = {
    "web_worker_transferable",
    "scheduler_yield_chunking",
    "background_thread_channel",
    "none_pure_batch_pipeline",
}
VALID_STREAMING_MECHANISMS = {
    "web_readable_stream_backpressure",
    "node_stream_pipeline",
    "go_bufio_io_copy",
    "rust_bufreader",
    "cursor_chunk_fetch",
}
VALID_ZERO_COPY_STRATEGIES = {
    "array_buffer_transfer",
    "subarray_view_sharing",
    "io_copy_kernel_splice",
    "mmap_shared_memory",
    "in_place_slice_parsing",
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


def check_target_system(record, require):
    target = record.get("target_system")
    require(isinstance(target, dict), "INVALID_TARGET_SYSTEM", "target_system must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("subsystem_or_flow"), 10),
            "MISSING_SUBSYSTEM_OR_FLOW",
            "target_system.subsystem_or_flow must be at least 10 characters")
    require(filled(target.get("workload_cardinality"), 5),
            "MISSING_WORKLOAD_CARDINALITY",
            "target_system.workload_cardinality must describe dataset/concurrency cardinality")
    require(filled(target.get("runtime_platform"), 3),
            "MISSING_RUNTIME_PLATFORM",
            "target_system.runtime_platform must specify runtime (e.g. node_v8, bun_jsc, browser_webkit, rust_native)")


def _validate_telemetry_block(block, block_name, require):
    require(isinstance(block, dict), f"INVALID_{block_name.upper()}",
            f"{block_name} must be a dictionary")
    if not isinstance(block, dict):
        return False

    p50 = block.get("p50_ms")
    p99 = block.get("p99_ms")
    alloc_bytes = block.get("alloc_bytes_per_op")
    allocs = block.get("allocs_per_op")

    require(isinstance(p50, (int, float)) and float(p50) > 0,
            f"{block_name.upper()}_INVALID_P50_MS",
            f"{block_name}.p50_ms must be a positive number")
    require(isinstance(p99, (int, float)) and float(p99) > 0
            and (not isinstance(p50, (int, float)) or float(p99) >= float(p50)),
            f"{block_name.upper()}_INVALID_P99_MS",
            f"{block_name}.p99_ms must be a positive number >= p50_ms")
    require(isinstance(alloc_bytes, int) and alloc_bytes >= 0,
            f"{block_name.upper()}_INVALID_ALLOC_BYTES",
            f"{block_name}.alloc_bytes_per_op must be a non-negative integer")
    require(isinstance(allocs, int) and allocs >= 0,
            f"{block_name.upper()}_INVALID_ALLOCS_PER_OP",
            f"{block_name}.allocs_per_op must be a non-negative integer")
    return True


def check_benchmark_proof(record, require):
    bench = record.get("benchmark_proof")
    require(isinstance(bench, dict), "INVALID_BENCHMARK_PROOF",
            "benchmark_proof must be a dictionary")
    if not isinstance(bench, dict):
        return

    method = bench.get("measurement_method")
    require(choice(method, VALID_MEASUREMENT_METHODS),
            "INVALID_MEASUREMENT_METHOD",
            f"benchmark_proof.measurement_method must be one of: {', '.join(sorted(VALID_MEASUREMENT_METHODS))}")

    require(filled(bench.get("flamegraph_or_trace_artifact"), 10),
            "MISSING_FLAMEGRAPH_OR_TRACE_ARTIFACT",
            "benchmark_proof.flamegraph_or_trace_artifact must cite the flamegraph SVG, trace, or benchmark profile artifact")

    base = bench.get("baseline_measurement")
    post = bench.get("post_change_measurement")

    base_ok = _validate_telemetry_block(base, "baseline_measurement", require)
    if base_ok and isinstance(base, dict):
        require(filled(base.get("evidence_cmd_or_plan"), 10),
                "MISSING_BASELINE_EVIDENCE_CMD",
                "baseline_measurement.evidence_cmd_or_plan must document the reproducible command or plan")

    post_ok = _validate_telemetry_block(post, "post_change_measurement", require)
    if not post_ok or not isinstance(post, dict):
        return

    require(post.get("regression_check_passed") is True,
            "REGRESSION_CHECK_NOT_PASSED",
            "post_change_measurement.regression_check_passed must be true")
    require(filled(post.get("improvement_summary"), 20),
            "MISSING_IMPROVEMENT_SUMMARY",
            "post_change_measurement.improvement_summary must state the quantitative before/after improvement delta (>=20 chars)")

    if base_ok and isinstance(base, dict):
        p99_ok = isinstance(base.get("p99_ms"), (int, float)) and isinstance(post.get("p99_ms"), (int, float))
        alloc_ok = isinstance(base.get("alloc_bytes_per_op"), int) and isinstance(post.get("alloc_bytes_per_op"), int)

        if p99_ok and alloc_ok:
            base_p99 = float(base["p99_ms"])
            post_p99 = float(post["p99_ms"])
            base_alloc = base["alloc_bytes_per_op"]
            post_alloc = post["alloc_bytes_per_op"]

            improved = (
                post_p99 <= (base_p99 * 0.85)
                or post_alloc < base_alloc
                or (post_p99 <= 8.34 and base_p99 > 8.34)
            )
            require(improved,
                    "NO_MEASURED_PERFORMANCE_IMPROVEMENT",
                    "post_change_measurement must demonstrate >=15% P99 improvement or strict reduction in alloc_bytes_per_op or achievement of 120Hz (<8.34ms)")
            require(post_p99 <= base_p99,
                    "POST_CHANGE_P99_REGRESSED",
                    "post_change_measurement.p99_ms regressed above baseline_measurement.p99_ms")


def check_data_oriented_design(record, require):
    dod = record.get("data_oriented_design")
    require(isinstance(dod, dict), "INVALID_DATA_ORIENTED_DESIGN",
            "data_oriented_design must be a dictionary")
    if not isinstance(dod, dict):
        return

    require(choice(dod.get("memory_layout"), VALID_MEMORY_LAYOUTS),
            "INVALID_MEMORY_LAYOUT",
            f"data_oriented_design.memory_layout must be one of: {', '.join(sorted(VALID_MEMORY_LAYOUTS))}")

    require(filled(dod.get("cache_miss_mitigation"), 15),
            "MISSING_CACHE_MISS_MITIGATION",
            "data_oriented_design.cache_miss_mitigation must explain sequential access and CPU cache line (64B) packing")

    require(dod.get("hot_loop_allocations_eliminated") is True,
            "HOT_LOOP_ALLOCATIONS_NOT_ELIMINATED",
            "data_oriented_design.hot_loop_allocations_eliminated must be true")

    mitigations = dod.get("allocations_eliminated_details")
    require(isinstance(mitigations, list) and len(mitigations) >= 2
            and all(isinstance(m, str) and m in VALID_ALLOCATION_MITIGATIONS for m in mitigations),
            "INSUFFICIENT_ALLOCATION_MITIGATIONS",
            f"data_oriented_design.allocations_eliminated_details must declare at least 2 valid mitigations: {', '.join(sorted(VALID_ALLOCATION_MITIGATIONS))}")


def check_frame_and_latency_budget(record, require):
    flb = record.get("frame_and_latency_budget")
    require(isinstance(flb, dict), "INVALID_FRAME_AND_LATENCY_BUDGET",
            "frame_and_latency_budget must be a dictionary")
    if not isinstance(flb, dict):
        return

    hz = flb.get("target_refresh_rate_hz")
    budget = flb.get("frame_budget_ms")
    require(isinstance(hz, int) and hz in VALID_REFRESH_RATES,
            "INVALID_REFRESH_RATE_HZ",
            "frame_and_latency_budget.target_refresh_rate_hz must be 60 or 120")
    require(isinstance(budget, (int, float)) and float(budget) in VALID_FRAME_BUDGETS,
            "INVALID_FRAME_BUDGET_MS",
            "frame_and_latency_budget.frame_budget_ms must be 8.3/8.33 (120Hz) or 16.6/16.67 (60Hz)")

    if hz == 120 and isinstance(budget, (int, float)):
        require(float(budget) <= 8.34,
                "FRAME_BUDGET_EXCEEDS_120HZ",
                "120Hz surface must declare frame_budget_ms <= 8.34ms")

    script_ms = flb.get("main_thread_max_script_ms")
    require(isinstance(script_ms, (int, float)) and 0 < float(script_ms) <= 4.0,
            "MAIN_THREAD_SCRIPT_EXCEEDS_4MS",
            "frame_and_latency_budget.main_thread_max_script_ms must be > 0 and <= 4.0ms to reserve headroom for compositor/layout")

    require(flb.get("long_tasks_eliminated") is True,
            "LONG_TASKS_NOT_ELIMINATED",
            "frame_and_latency_budget.long_tasks_eliminated must be true (zero main-thread tasks > 50ms)")

    require(choice(flb.get("main_thread_offload_strategy"), VALID_OFFLOAD_STRATEGIES),
            "INVALID_OFFLOAD_STRATEGY",
            f"frame_and_latency_budget.main_thread_offload_strategy must be one of: {', '.join(sorted(VALID_OFFLOAD_STRATEGIES))}")

    require(flb.get("layout_thrashing_eliminated") is True,
            "LAYOUT_THRASHING_NOT_ELIMINATED",
            "frame_and_latency_budget.layout_thrashing_eliminated must be true")

    props = flb.get("compositor_only_animated_properties")
    require(isinstance(props, list) and bool(props)
            and all(isinstance(p, str) and p in VALID_COMPOSITOR_PROPS for p in props),
            "NON_COMPOSITOR_ANIMATION_PROPERTIES",
            "frame_and_latency_budget.compositor_only_animated_properties must contain strictly GPU compositor properties ('transform', 'opacity')")


def check_zero_copy_and_streaming(record, require):
    zcs = record.get("zero_copy_and_streaming")
    require(isinstance(zcs, dict), "INVALID_ZERO_COPY_AND_STREAMING",
            "zero_copy_and_streaming must be a dictionary")
    if not isinstance(zcs, dict):
        return

    require(zcs.get("whole_payload_ram_buffering_prohibited") is True,
            "WHOLE_PAYLOAD_RAM_BUFFERING_PERMITTED",
            "zero_copy_and_streaming.whole_payload_ram_buffering_prohibited must be true")

    require(choice(zcs.get("streaming_mechanism"), VALID_STREAMING_MECHANISMS),
            "INVALID_STREAMING_MECHANISM",
            f"zero_copy_and_streaming.streaming_mechanism must be one of: {', '.join(sorted(VALID_STREAMING_MECHANISMS))}")

    chunk_size = zcs.get("buffer_chunk_size_bytes")
    require(isinstance(chunk_size, int) and 1024 <= chunk_size <= 1048576,
            "INVALID_BUFFER_CHUNK_SIZE",
            "zero_copy_and_streaming.buffer_chunk_size_bytes must be an integer between 1024 (1KB) and 1048576 (1MB)")

    require(choice(zcs.get("zero_copy_strategy"), VALID_ZERO_COPY_STRATEGIES),
            "INVALID_ZERO_COPY_STRATEGY",
            f"zero_copy_and_streaming.zero_copy_strategy must be one of: {', '.join(sorted(VALID_ZERO_COPY_STRATEGIES))}")

    require(zcs.get("peak_memory_rss_bounded_o1") is True,
            "PEAK_MEMORY_NOT_BOUNDED_O1",
            "zero_copy_and_streaming.peak_memory_rss_bounded_o1 must be true")


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

    # 1. Whole-file synchronous RAM buffering
    has_sync_read = bool(re.search(r"\b(?:readFileSync|fs\.promises\.readFile|response\.arrayBuffer\(\)|response\.text\(\))\b", source_text))
    require(not has_sync_read, "SOURCE_WHOLE_PAYLOAD_RAM_BUFFERING",
            "Detected whole-payload RAM buffering (readFileSync/readFile/arrayBuffer/text); stream with bounded chunks")

    # 2. Layout thrashing (style write followed by synchronous geometry read)
    has_layout_thrash = bool(
        re.search(
            r"\.style\.(?:top|left|width|height|margin|transform)\s*=[^;]+;[\s\S]{0,160}?\.(?:getBoundingClientRect\s*\(|offsetWidth\b|offsetHeight\b|clientHeight\b|scrollTop\b)",
            source_text,
        )
    )
    require(not has_layout_thrash, "SOURCE_LAYOUT_THRASHING_DETECTED",
            "Detected style write followed immediately by geometry read (Forced Synchronous Layout Thrashing); separate read and write phases")

    # 3. CSS transition all / non-compositor properties
    has_transition_all = bool(re.search(r"transition\s*:\s*all\b|transition-all\b", source_text))
    require(not has_transition_all, "SOURCE_TRANSITION_ALL_FORBIDDEN",
            "Detected 'transition: all' or 'transition-all'; animate strictly compositor properties ('transform', 'opacity')")

    # 4. Quadratic array scans inside loops
    has_quadratic_scan = bool(
        re.search(
            r"\.(?:map|filter|forEach|reduce)\s*\([^;]{1,220}?\.(?:find|includes|indexOf)\s*\(",
            source_text,
            re.DOTALL,
        )
    )
    require(not has_quadratic_scan, "SOURCE_QUADRATIC_NESTED_SCAN",
            "Detected O(N^2) nested .find()/.includes()/.indexOf() inside an array iteration; pre-index into an O(1) Map/Set")

    # 5. Hot-path GC allocation churn (JSON.parse(JSON.stringify) or >=3 chained passes or object spread in reduce)
    has_alloc_churn = bool(
        re.search(r"JSON\.parse\s*\(\s*JSON\.stringify\s*\(", source_text)
        or re.search(r"\.(?:map|filter)\s*\([^)]+\)\s*\.(?:map|filter)\s*\([^)]+\)\s*\.(?:map|filter|reduce)\s*\(", source_text)
        or re.search(r"\.reduce\s*\(\s*\([^)]*\)\s*=>\s*\(?\{\s*\.\.\.[^,]+,", source_text)
    )
    require(not has_alloc_churn, "SOURCE_HOT_PATH_ALLOCATION_CHURN",
            "Detected hot-path heap allocation churn (JSON clone, >=3 chained map/filter passes, or object spread reducer)")

    # 6. Serial await I/O in loops
    has_loop_io = bool(
        re.search(
            r"\b(?:for|while)\s*\([^)]*\)\s*\{[^}]*\bawait\s+(?:fetch\b|db\.|prisma\.|redis\.|axios\.|client\.query\b)",
            source_text,
            re.DOTALL,
        )
    )
    require(not has_loop_io, "SOURCE_SERIAL_AWAIT_IN_LOOP",
            "Detected serial 'await' network/DB/Redis I/O inside a loop; coalesce with batched bulk query or pipeline")

    # 7. Synchronous localStorage/sessionStorage blocking main thread
    has_sync_storage_json = bool(
        re.search(r"\b(?:localStorage|sessionStorage)\.setItem\s*\([^,]+,\s*JSON\.stringify\s*\(", source_text)
    )
    require(not has_sync_storage_json, "SOURCE_MAIN_THREAD_SYNC_STORAGE_STALL",
            "Detected synchronous localStorage/sessionStorage.setItem(JSON.stringify(...)) stalling the Main Thread")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_system(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_benchmark_proof(record, require)
        check_data_oriented_design(record, require)
        check_frame_and_latency_budget(record, require)
        check_zero_copy_and_streaming(record, require)

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
                        help="Optional source file to scan for RAM buffering, layout thrashing, allocation churn, or main-thread stalls")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Invalid Mechanical Sympathy & Performance Gate record: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Mechanical Sympathy & Performance Gate record: {result['record_status']} ({result['verdict_action']})")
        for item in result["findings"]:
            print(f"  [{item['severity']}] {item['code']}: {item['message']}")
        print("Structural audit only: Flamegraphs, 120Hz frame timing, and zero-allocation hot paths must be verified with empirical benchmarks.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
