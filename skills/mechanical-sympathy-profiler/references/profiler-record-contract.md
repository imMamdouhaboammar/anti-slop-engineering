# Mechanical Sympathy & Profiler Record Contract

When optimizing a slow query, backend endpoint, streaming worker, or hot loop, save the empirical assessment as a persistent JSON record (`mechanical-sympathy-profiler-record.json`) to verify compliance with the Empirical Measurement Law (`EXPLAIN (ANALYZE, BUFFERS)` or `P99` + allocation micro-benchmark before and after), Memory/GC Streaming Physics, and I/O Batching/Pipelining.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MechanicalSympathyProfilerRecord",
  "type": "object",
  "required": [
    "schema_version",
    "target_path",
    "baseline_measurement",
    "bottleneck_physics",
    "hardware_and_io_remediation",
    "post_change_measurement",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "target_path": {
      "type": "object",
      "required": ["component_or_query", "workload_cardinality", "measurement_method"],
      "properties": {
        "component_or_query": { "type": "string", "minLength": 10 },
        "workload_cardinality": { "type": "string", "minLength": 5 },
        "measurement_method": {
          "type": "string",
          "enum": [
            "microbenchmark_and_explain_analyze_buffers",
            "microbenchmark_alloc_and_latency",
            "explain_analyze_buffers",
            "heap_and_cpu_flamegraph_profile"
          ]
        }
      }
    },
    "baseline_measurement": {
      "type": "object",
      "required": [
        "p50_ms",
        "p99_ms",
        "alloc_bytes_per_op",
        "allocs_per_op",
        "io_roundtrips_per_request",
        "evidence_artifact"
      ],
      "properties": {
        "p50_ms": { "type": "number", "exclusiveMinimum": 0 },
        "p99_ms": { "type": "number", "exclusiveMinimum": 0 },
        "alloc_bytes_per_op": { "type": "integer", "minimum": 0 },
        "allocs_per_op": { "type": "integer", "minimum": 0 },
        "io_roundtrips_per_request": { "type": "integer", "minimum": 0 },
        "explain_analyze_buffers": { "type": "string" },
        "evidence_artifact": { "type": "string", "minLength": 15 }
      }
    },
    "bottleneck_physics": {
      "type": "object",
      "required": ["primary_bound", "speculative_caching_rejected", "root_mechanic"],
      "properties": {
        "primary_bound": {
          "type": "string",
          "enum": [
            "network_io_roundtrips",
            "disk_buffer_io",
            "memory_allocation_gc",
            "algorithmic_complexity",
            "cpu_cycles",
            "lock_contention"
          ]
        },
        "speculative_caching_rejected": { "type": "boolean", "const": true },
        "root_mechanic": { "type": "string", "minLength": 20 }
      }
    },
    "hardware_and_io_remediation": {
      "type": "object",
      "required": [
        "memory_strategy",
        "gc_pressure_mitigations",
        "io_batching_strategy",
        "roundtrip_reduction"
      ],
      "properties": {
        "memory_strategy": {
          "type": "string",
          "enum": [
            "bounded_chunk_streaming",
            "preallocated_buffer_reuse",
            "in_place_single_pass",
            "index_only_covering_scan"
          ]
        },
        "gc_pressure_mitigations": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "enum": [
              "eliminate_intermediate_array_chains",
              "preindex_o1_map_set_lookup",
              "reuse_typed_buffer_scratchpad",
              "hoist_loop_invariant_allocations",
              "in_place_accumulator_mutation",
              "bounded_stream_backpressure"
            ]
          }
        },
        "io_batching_strategy": {
          "type": "string",
          "enum": [
            "sql_unnest_or_any_batch",
            "redis_mget_or_pipeline",
            "dataloader_request_coalescing",
            "streaming_cursor_fetch",
            "none_pure_cpu_memory_path"
          ]
        },
        "roundtrip_reduction": { "type": "string", "minLength": 5 }
      }
    },
    "post_change_measurement": {
      "type": "object",
      "required": [
        "p50_ms",
        "p99_ms",
        "alloc_bytes_per_op",
        "allocs_per_op",
        "io_roundtrips_per_request",
        "regression_check_passed",
        "improvement_summary"
      ],
      "properties": {
        "p50_ms": { "type": "number", "exclusiveMinimum": 0 },
        "p99_ms": { "type": "number", "exclusiveMinimum": 0 },
        "alloc_bytes_per_op": { "type": "integer", "minimum": 0 },
        "allocs_per_op": { "type": "integer", "minimum": 0 },
        "io_roundtrips_per_request": { "type": "integer", "minimum": 0 },
        "explain_analyze_buffers": { "type": "string" },
        "regression_check_passed": { "type": "boolean", "const": true },
        "improvement_summary": { "type": "string", "minLength": 20 }
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

Validate Mechanical Sympathy & Profiler records or scan source files (`--source`) for serial `await` I/O inside loops, whole-file synchronous RAM buffering (`readFileSync`), $O(N^2)$ nested `.find()`/`.includes()` lookups, and hot-path allocation churn (`JSON.parse(JSON.stringify(...))` or multi-stage `.map().filter().map()`) using:

```bash
python3 scripts/profiler_guard.py audit <record.json> [--source <hot_path.ts>] --json
# or via CLI:
npx anti-slop-engineering profiler audit <record.json> [--source <hot_path.ts>] --json
```

Exit codes:
- `0`: Structurally compliant Mechanical Sympathy & Profiler record (verified baseline and post-change improvements in `P99` latency, heap allocations, or I/O roundtrips, `EXPLAIN (ANALYZE, BUFFERS)` evidence when SQL/DB is involved, speculative caching rejected, and zero mechanical sympathy hazards in `--source`).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings detected in the record or `--source` file.
