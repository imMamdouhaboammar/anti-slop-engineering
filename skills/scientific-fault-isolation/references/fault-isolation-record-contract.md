# Scientific Fault Isolation Record Contract

When diagnosing a complex production bug, intermittent race condition, or regression across commits/layers, save the investigation as a persistent JSON record (`fault-isolation-record.json`) to prove that Differential Diagnosis, Binary Search Isolation, Determinism Pinning, and Red-Green-Revert verification were completed without shotgun debugging.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ScientificFaultIsolationRecord",
  "type": "object",
  "required": [
    "schema_version",
    "symptom",
    "differential_diagnosis",
    "discriminating_probe",
    "binary_search_isolation",
    "determinism_pinning",
    "red_green_verification",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "symptom": {
      "type": "object",
      "required": ["observable_failure", "reproduction_frequency_before", "affected_boundary"],
      "properties": {
        "observable_failure": { "type": "string", "minLength": 15 },
        "reproduction_frequency_before": {
          "type": "string",
          "enum": ["intermittent_flaky", "deterministic_regression", "load_dependent_race", "environment_specific"]
        },
        "affected_boundary": { "type": "string", "minLength": 5 }
      }
    },
    "differential_diagnosis": {
      "type": "object",
      "required": ["zero_production_edits_before_probe", "hypotheses"],
      "properties": {
        "zero_production_edits_before_probe": { "type": "boolean", "const": true },
        "hypotheses": {
          "type": "array",
          "minItems": 3,
          "items": {
            "type": "object",
            "required": ["id", "mechanism", "prediction", "falsified_if", "status", "evidence"],
            "properties": {
              "id": { "type": "string", "minLength": 2 },
              "mechanism": { "type": "string", "minLength": 15 },
              "prediction": { "type": "string", "minLength": 10 },
              "falsified_if": { "type": "string", "minLength": 10 },
              "status": { "type": "string", "enum": ["confirmed", "falsified", "pending"] },
              "evidence": { "type": "string", "minLength": 10 }
            }
          }
        }
      }
    },
    "discriminating_probe": {
      "type": "object",
      "required": ["probe_type", "design", "observed_outcome", "killed_hypothesis_ids", "confirmed_hypothesis_id"],
      "properties": {
        "probe_type": {
          "type": "string",
          "enum": ["minimal_reproducer", "structured_boundary_log", "state_invariant_assertion", "git_bisect_script", "packet_or_query_capture"]
        },
        "design": { "type": "string", "minLength": 15 },
        "observed_outcome": { "type": "string", "minLength": 15 },
        "killed_hypothesis_ids": {
          "type": "array",
          "minItems": 2,
          "items": { "type": "string" }
        },
        "confirmed_hypothesis_id": { "type": "string", "minLength": 2 }
      }
    },
    "binary_search_isolation": {
      "type": "object",
      "required": ["method", "initial_fault_space", "isolated_boundary", "steps_taken"],
      "properties": {
        "method": {
          "type": "string",
          "enum": ["git_bisect", "layer_boundary_halving", "delta_debugging_input", "call_graph_midpoint"]
        },
        "initial_fault_space": { "type": "string", "minLength": 10 },
        "isolated_boundary": { "type": "string", "minLength": 10 },
        "steps_taken": { "type": "integer", "minimum": 1, "maximum": 30 }
      }
    },
    "determinism_pinning": {
      "type": "object",
      "required": ["controls_applied", "sleep_based_timing_absent", "deterministic_red_test_command", "reproduction_rate_after_pinning"],
      "properties": {
        "controls_applied": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "enum": [
              "pinned_prng_seed",
              "frozen_monotonic_clock",
              "concurrency_barrier_latch",
              "deterministic_task_scheduler",
              "hermetic_fixture_isolation",
              "fixed_chunk_boundary"
            ]
          }
        },
        "sleep_based_timing_absent": { "type": "boolean", "const": true },
        "deterministic_red_test_command": { "type": "string", "minLength": 5 },
        "reproduction_rate_after_pinning": { "type": "string", "const": "100_percent_deterministic" }
      }
    },
    "red_green_verification": {
      "type": "object",
      "required": [
        "failed_before_fix",
        "passed_after_fix",
        "failed_again_on_fix_revert",
        "diagnostic_probes_removed",
        "root_fix_owner_layer"
      ],
      "properties": {
        "failed_before_fix": { "type": "boolean", "const": true },
        "passed_after_fix": { "type": "boolean", "const": true },
        "failed_again_on_fix_revert": { "type": "boolean", "const": true },
        "diagnostic_probes_removed": { "type": "boolean", "const": true },
        "root_fix_owner_layer": { "type": "string", "minLength": 5 }
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

Validate fault-isolation records or scan proposed fix/test files for shotgun debugging hazards (`sleep` band-aids, leftover debug probes, empty catch blocks) using:
```bash
python3 scripts/fault_isolation_guard.py audit <record.json> [--source <file_or_patch>] --json
# or via CLI:
npx anti-slop-engineering fault-isolation audit <record.json> [--source <file_or_patch>] --json
```

Exit codes:
- `0`: Structurally compliant fault isolation record (at least 3 falsifiable hypotheses, >=2 falsified, 1 confirmed, determinism pinned at 100%, Red-Green-Revert verified, zero shotgun hazards in `--source`).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings (fewer than 3 hypotheses, <2 killed hypotheses, production edits before probe, sleep-based timing band-aid, missing revert falsification, or leftover debug probes detected).
