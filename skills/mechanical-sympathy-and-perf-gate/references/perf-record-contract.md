# Mechanical Sympathy & Performance Gate Record Contract

When designing high-throughput backends, tuning latency-critical paths, optimizing memory layouts, or eliminating 120Hz/60Hz UI frame drops, record the evaluation as a persistent JSON record (`perf-record.json`) to establish verifiable hardware and runtime compliance.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MechanicalSympathyAndPerfRecord",
  "type": "object",
  "required": [
    "schema_version",
    "target_system",
    "benchmark_proof",
    "data_oriented_design",
    "frame_and_latency_budget",
    "zero_copy_and_streaming",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "target_system": {
      "type": "object",
      "required": ["subsystem_or_flow", "workload_cardinality", "runtime_platform"],
      "properties": {
        "subsystem_or_flow": { "type": "string", "minLength": 10 },
        "workload_cardinality": { "type": "string", "minLength": 5 },
        "runtime_platform": { "type": "string", "minLength": 3 }
      }
    },
    "benchmark_proof": {
      "type": "object",
      "required": [
        "measurement_method",
        "flamegraph_or_trace_artifact",
        "baseline_measurement",
        "post_change_measurement"
      ],
      "properties": {
        "measurement_method": {
          "type": "string",
          "enum": [
            "flamegraph_cpu_heap_profile",
            "microbenchmark_with_alloc_and_p99",
            "explain_analyze_buffers_and_p99",
            "frame_timing_and_trace_profile"
          ]
        },
        "flamegraph_or_trace_artifact": { "type": "string", "minLength": 10 },
        "baseline_measurement": {
          "type": "object",
          "required": ["p50_ms", "p99_ms", "alloc_bytes_per_op", "allocs_per_op", "evidence_cmd_or_plan"],
          "properties": {
            "p50_ms": { "type": "number", "minimum": 0 },
            "p99_ms": { "type": "number", "minimum": 0 },
            "alloc_bytes_per_op": { "type": "integer", "minimum": 0 },
            "allocs_per_op": { "type": "integer", "minimum": 0 },
            "evidence_cmd_or_plan": { "type": "string", "minLength": 10 }
          }
        },
        "post_change_measurement": {
          "type": "object",
          "required": [
            "p50_ms",
            "p99_ms",
            "alloc_bytes_per_op",
            "allocs_per_op",
            "improvement_summary",
            "regression_check_passed"
          ],
          "properties": {
            "p50_ms": { "type": "number", "minimum": 0 },
            "p99_ms": { "type": "number", "minimum": 0 },
            "alloc_bytes_per_op": { "type": "integer", "minimum": 0 },
            "allocs_per_op": { "type": "integer", "minimum": 0 },
            "improvement_summary": { "type": "string", "minLength": 20 },
            "regression_check_passed": { "type": "boolean", "const": true }
          }
        }
      }
    },
    "data_oriented_design": {
      "type": "object",
      "required": [
        "memory_layout",
        "cache_miss_mitigation",
        "hot_loop_allocations_eliminated",
        "allocations_eliminated_details"
      ],
      "properties": {
        "memory_layout": {
          "type": "string",
          "enum": [
            "struct_of_arrays_contiguous",
            "typed_array_flat_buffer",
            "preallocated_fixed_buffer",
            "cacheline_aligned_64b"
          ]
        },
        "cache_miss_mitigation": { "type": "string", "minLength": 15 },
        "hot_loop_allocations_eliminated": { "type": "boolean", "const": true },
        "allocations_eliminated_details": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "enum": [
              "hoisted_regex_and_formatters",
              "preallocated_capacity",
              "in_place_accumulator",
              "zero_intermediate_array_passes",
              "typed_buffer_scratchpad",
              "object_pool_recycling"
            ]
          }
        }
      }
    },
    "frame_and_latency_budget": {
      "type": "object",
      "required": [
        "target_refresh_rate_hz",
        "frame_budget_ms",
        "main_thread_max_script_ms",
        "long_tasks_eliminated",
        "main_thread_offload_strategy",
        "layout_thrashing_eliminated",
        "compositor_only_animated_properties"
      ],
      "properties": {
        "target_refresh_rate_hz": { "type": "integer", "enum": [60, 120] },
        "frame_budget_ms": { "type": "number", "enum": [8.3, 8.33, 16.6, 16.67] },
        "main_thread_max_script_ms": { "type": "number", "maximum": 4.0 },
        "long_tasks_eliminated": { "type": "boolean", "const": true },
        "main_thread_offload_strategy": {
          "type": "string",
          "enum": [
            "web_worker_transferable",
            "scheduler_yield_chunking",
            "background_thread_channel",
            "none_pure_batch_pipeline"
          ]
        },
        "layout_thrashing_eliminated": { "type": "boolean", "const": true },
        "compositor_only_animated_properties": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string", "enum": ["transform", "opacity"] }
        }
      }
    },
    "zero_copy_and_streaming": {
      "type": "object",
      "required": [
        "whole_payload_ram_buffering_prohibited",
        "streaming_mechanism",
        "buffer_chunk_size_bytes",
        "zero_copy_strategy",
        "peak_memory_rss_bounded_o1"
      ],
      "properties": {
        "whole_payload_ram_buffering_prohibited": { "type": "boolean", "const": true },
        "streaming_mechanism": {
          "type": "string",
          "enum": [
            "web_readable_stream_backpressure",
            "node_stream_pipeline",
            "go_bufio_io_copy",
            "rust_bufreader",
            "cursor_chunk_fetch"
          ]
        },
        "buffer_chunk_size_bytes": { "type": "integer", "minimum": 1024, "maximum": 1048576 },
        "zero_copy_strategy": {
          "type": "string",
          "enum": [
            "array_buffer_transfer",
            "subarray_view_sharing",
            "io_copy_kernel_splice",
            "mmap_shared_memory",
            "in_place_slice_parsing"
          ]
        },
        "peak_memory_rss_bounded_o1": { "type": "boolean", "const": true }
      }
    },
    "verdict": {
      "type": "object",
      "required": ["action", "rationale", "revisit_triggers"],
      "properties": {
        "action": { "type": "string", "enum": ["proceed", "pause", "refuse"] },
        "rationale": { "type": "string", "minLength": 20 },
        "revisit_triggers": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

## Audit Tooling

Validate records against this contract using:
```bash
python3 scripts/perf_guard.py audit <record.json> [--source <hot_path.ts>] --json
# or via CLI:
npx anti-slop-engineering perf audit <record.json> [--source <hot_path.ts>] --json
```

Exit codes:
- `0`: Structurally compliant record with verified benchmark delta and clean source code.
- `1`: JSON parsing or file access failure.
- `2`: Validation findings (unmeasured claims, layout thrashing, RAM buffering, or P99 regressions).
