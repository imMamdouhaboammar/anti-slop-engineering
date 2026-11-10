# Contract: Deterministic Simulation & Property Testing Record

Audit schema and data contracts for persistent simulation and property testing records evaluated by `scripts/simulation_guard.py`.

## Record Specification

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DeterministicSimulationAndPropertyRecord",
  "type": "object",
  "required": [
    "schema_version",
    "target_system",
    "property_testing",
    "deterministic_simulation",
    "state_machine_modeling",
    "structure_aware_fuzzing",
    "mutation_falsification",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "enum": ["1.0"] },
    "target_system": {
      "type": "object",
      "required": ["module_under_test", "system_archetype", "example_based_tests_only_banned"],
      "properties": {
        "module_under_test": { "type": "string", "minLength": 10 },
        "system_archetype": {
          "type": "string",
          "enum": [
            "distributed_consensus_and_replication",
            "event_driven_actor_system",
            "financial_transaction_pipeline",
            "parser_codec_deserializer",
            "stateful_workflow_engine"
          ]
        },
        "example_based_tests_only_banned": { "type": "boolean", "const": true }
      }
    },
    "property_testing": {
      "type": "object",
      "required": ["framework", "min_test_cases", "shrinking_enabled", "invariants"],
      "properties": {
        "framework": {
          "type": "string",
          "enum": ["fast-check", "hypothesis", "proptest", "rapid", "custom_deterministic_pbt"]
        },
        "min_test_cases": { "type": "integer", "minimum": 100 },
        "shrinking_enabled": { "type": "boolean", "const": true },
        "invariants": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "required": ["id", "category", "description", "shrink_counterexample_verified"],
            "properties": {
              "id": { "type": "string", "minLength": 3 },
              "category": {
                "type": "string",
                "enum": [
                  "round_trip_invertibility",
                  "idempotency",
                  "metamorphic_relation",
                  "state_model_equivalence",
                  "conservation_law"
                ]
              },
              "description": { "type": "string", "minLength": 15 },
              "shrink_counterexample_verified": { "type": "boolean", "const": true }
            }
          }
        }
      }
    },
    "deterministic_simulation": {
      "type": "object",
      "required": [
        "virtual_clock_enabled",
        "prng_algorithm",
        "seed",
        "reproducibility_verified",
        "fault_injection_matrix"
      ],
      "properties": {
        "virtual_clock_enabled": { "type": "boolean", "const": true },
        "prng_algorithm": {
          "type": "string",
          "enum": ["mulberry32", "xorshift128p", "pcg32", "splitmix64", "chacha8_rng"]
        },
        "seed": { "type": ["string", "integer"] },
        "reproducibility_verified": { "type": "boolean", "const": true },
        "fault_injection_matrix": {
          "type": "array",
          "minItems": 3,
          "items": {
            "type": "object",
            "required": ["fault_type", "probability_or_cadence", "mitigation_or_invariant"],
            "properties": {
              "fault_type": {
                "type": "string",
                "enum": [
                  "network_packet_loss",
                  "clock_skew_drift",
                  "message_reordering",
                  "partition_split_brain",
                  "storage_write_corruption",
                  "node_crash_restart"
                ]
              },
              "probability_or_cadence": { "type": ["string", "number"] },
              "mitigation_or_invariant": { "type": "string", "minLength": 15 }
            }
          }
        }
      }
    },
    "state_machine_modeling": {
      "type": "object",
      "required": [
        "model_name",
        "type_level_impossible_states_prevented",
        "states",
        "transitions",
        "generative_model_test_executed"
      ],
      "properties": {
        "model_name": { "type": "string", "minLength": 5 },
        "type_level_impossible_states_prevented": { "type": "boolean", "const": true },
        "states": {
          "type": "array",
          "minItems": 3,
          "items": { "type": "string", "minLength": 1 }
        },
        "transitions": {
          "type": "array",
          "minItems": 3,
          "items": {
            "type": "object",
            "required": ["from_state", "event", "to_state", "guard_or_effect"],
            "properties": {
              "from_state": { "type": "string", "minLength": 1 },
              "event": { "type": "string", "minLength": 1 },
              "to_state": { "type": "string", "minLength": 1 },
              "guard_or_effect": { "type": "string", "minLength": 1 }
            }
          }
        },
        "generative_model_test_executed": { "type": "boolean", "const": true }
      }
    },
    "structure_aware_fuzzing": {
      "type": "object",
      "required": [
        "target_boundary",
        "fuzz_engine",
        "corpus_strategy",
        "crash_freedom_verified",
        "bounded_recursion_and_memory",
        "max_payload_bytes"
      ],
      "properties": {
        "target_boundary": { "type": "string", "minLength": 5 },
        "fuzz_engine": {
          "type": "string",
          "enum": [
            "libfuzzer",
            "atheris",
            "jazzer",
            "cargo-fuzz",
            "native_go_fuzz",
            "structure_aware_generator"
          ]
        },
        "corpus_strategy": { "type": "string", "minLength": 10 },
        "crash_freedom_verified": { "type": "boolean", "const": true },
        "bounded_recursion_and_memory": { "type": "boolean", "const": true },
        "max_payload_bytes": { "type": "integer", "minimum": 1, "maximum": 10485760 }
      }
    },
    "mutation_falsification": {
      "type": "object",
      "required": [
        "red_green_falsification_verified",
        "mutated_invariant",
        "observed_failure_seed_or_counterexample"
      ],
      "properties": {
        "red_green_falsification_verified": { "type": "boolean", "const": true },
        "mutated_invariant": { "type": "string", "minLength": 20 },
        "observed_failure_seed_or_counterexample": { "type": "string", "minLength": 10 }
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
          "items": { "type": "string", "minLength": 1 }
        }
      }
    }
  }
}
```

## Validation Codes

| Code | Severity | Description |
| --- | --- | --- |
| `INVALID_TARGET_SYSTEM` | BLOCK | Target system definition missing or malformed |
| `EXAMPLE_BASED_TESTS_ONLY_NOT_BANNED` | BLOCK | Relying exclusively on static example tests is prohibited |
| `INSUFFICIENT_PROPERTY_RUNS` | BLOCK | Property-based tests must run $\ge 100$ iterations |
| `SHRINKING_DISABLED` | BLOCK | Automated shrinking to minimal failing counterexamples is required |
| `INSUFFICIENT_INVARIANTS` | BLOCK | At least 2 distinct invariants must be defined |
| `VIRTUAL_CLOCK_DISABLED` | BLOCK | Discrete Event Simulation must use a virtual clock (no wall-clock sleep) |
| `INVALID_SIMULATION_SEED` | BLOCK | PRNG seed must be integer $\ge 0$ or hex string (`0xCAFE_BABE`) |
| `REPRODUCIBILITY_NOT_VERIFIED` | BLOCK | Identical seed must yield 100% reproducible execution trace |
| `INSUFFICIENT_FAULT_INJECTION_MODES` | BLOCK | Fault matrix must include at least 3 distinct fault types |
| `IMPOSSIBLE_STATES_NOT_PREVENTED` | BLOCK | Type system must make impossible states unrepresentable |
| `UNBOUNDED_RECURSION_OR_MEMORY` | BLOCK | Parsers must enforce bounded call-stack depth and payload byte limits |
| `RED_GREEN_FALSIFICATION_NOT_VERIFIED` | BLOCK | Deliberate fault injection must trigger an observable test failure |
| `SOURCE_UNSEEDED_RANDOM_IN_SIMULATION` | BLOCK | Source code contains unseeded `Math.random()` or `random.random()` |
| `SOURCE_WALL_CLOCK_SLEEP_IN_SIMULATION` | BLOCK | Source code contains real wall-clock sleeps (`setTimeout`, `time.sleep`) |
| `SOURCE_IMPOSSIBLE_STATE_BOOLEANS` | BLOCK | Source contains boolean bags (`isLoading`, `isError`, `data`) |
| `SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION` | BLOCK | Source contains tautological checks (`expect(true).toBe(true)`) |
