# Verification Oracle Record Contract

When replacing module mocks (`vi.mock`, `jest.mock`, `unittest.mock`), verifying financial/parser/state-machine invariants, or stress-testing transactional rollback and idempotency under network faults, save the verification architecture assessment as a persistent JSON record (`verification-oracle-record.json`).

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "VerificationOracleRecord",
  "type": "object",
  "required": [
    "schema_version",
    "target_system",
    "verified_in_memory_fakes",
    "property_and_metamorphic_oracles",
    "deterministic_chaos_testing",
    "mutation_falsification",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "target_system": {
      "type": "object",
      "required": ["module_under_test", "domain_category", "module_mocking_banned"],
      "properties": {
        "module_under_test": { "type": "string", "minLength": 10 },
        "domain_category": {
          "type": "string",
          "enum": [
            "financial_ledger_and_payments",
            "parser_serializer_codec",
            "state_machine_and_workflow",
            "distributed_storage_and_sync",
            "authorization_and_policy_engine"
          ]
        },
        "module_mocking_banned": { "type": "boolean", "const": true }
      }
    },
    "verified_in_memory_fakes": {
      "type": "object",
      "required": [
        "port_interface",
        "fake_adapter_name",
        "real_adapter_name",
        "shared_contract_suite",
        "contract_parity_verified",
        "enforced_fake_mechanics"
      ],
      "properties": {
        "port_interface": { "type": "string", "minLength": 5 },
        "fake_adapter_name": { "type": "string", "minLength": 5 },
        "real_adapter_name": { "type": "string", "minLength": 5 },
        "shared_contract_suite": { "type": "string", "minLength": 10 },
        "contract_parity_verified": { "type": "boolean", "const": true },
        "enforced_fake_mechanics": {
          "type": "array",
          "minItems": 3,
          "items": {
            "type": "string",
            "enum": [
              "structured_clone_boundary_isolation",
              "unique_and_check_constraint_enforcement",
              "optimistic_concurrency_version_cas",
              "transactional_snapshot_rollback",
              "composite_tenant_isolation",
              "deterministic_cursor_pagination"
            ]
          }
        }
      }
    },
    "property_and_metamorphic_oracles": {
      "type": "object",
      "required": [
        "framework",
        "generated_runs_per_property",
        "shrinking_enabled",
        "invariants_verified"
      ],
      "properties": {
        "framework": {
          "type": "string",
          "enum": [
            "fast-check",
            "hypothesis",
            "proptest",
            "rapid",
            "deterministic_seeded_property_engine"
          ]
        },
        "generated_runs_per_property": { "type": "integer", "minimum": 100 },
        "shrinking_enabled": { "type": "boolean", "const": true },
        "invariants_verified": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "required": ["name", "category", "assertion_formula"],
            "properties": {
              "name": { "type": "string", "minLength": 5 },
              "category": {
                "type": "string",
                "enum": [
                  "conservation_law",
                  "roundtrip_invertibility",
                  "idempotency_law",
                  "metamorphic_relation",
                  "state_machine_safety"
                ]
              },
              "assertion_formula": { "type": "string", "minLength": 15 }
            }
          }
        }
      }
    },
    "deterministic_chaos_testing": {
      "type": "object",
      "required": [
        "seeded_prng_algorithm",
        "reproduction_seeds",
        "virtual_clock_injected",
        "zero_wall_clock_sleeps",
        "injected_fault_modes",
        "idempotency_and_rollback_proven"
      ],
      "properties": {
        "seeded_prng_algorithm": {
          "type": "string",
          "enum": ["mulberry32", "xorshift32", "pcg32", "chacha8_rng"]
        },
        "reproduction_seeds": {
          "type": "array",
          "minItems": 2,
          "items": { "type": "string", "pattern": "^0x[0-9a-fA-F]{4,16}$" }
        },
        "virtual_clock_injected": { "type": "boolean", "const": true },
        "zero_wall_clock_sleeps": { "type": "boolean", "const": true },
        "injected_fault_modes": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "enum": [
              "pre_commit_connection_drop",
              "post_commit_ack_drop",
              "transient_cas_version_conflict",
              "duplicate_out_of_order_delivery",
              "virtual_clock_lease_skew"
            ]
          }
        },
        "idempotency_and_rollback_proven": { "type": "boolean", "const": true }
      }
    },
    "mutation_falsification": {
      "type": "object",
      "required": [
        "red_green_falsification_verified",
        "mutated_production_invariant",
        "observed_red_failure_signal"
      ],
      "properties": {
        "red_green_falsification_verified": { "type": "boolean", "const": true },
        "mutated_production_invariant": { "type": "string", "minLength": 20 },
        "observed_red_failure_signal": { "type": "string", "minLength": 20 }
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

Validate Verification Oracle records or scan test/source files (`--source`) for banned module mocks (`vi.mock`, `jest.mock`, `sinon.stub`, `unittest.mock.patch`), `no-module-mocking` linter suppressions, unseeded `Math.random()`, wall-clock `setTimeout` sleeps, and tautological assertions using:

```bash
python3 scripts/verification_oracle_guard.py audit <record.json> [--source <test_file.ts>] --json
# or via CLI:
npx anti-slop-engineering verification-oracle audit <record.json> [--source <test_file.ts>] --json
```

Exit codes:
- `0`: Structurally compliant Verification Oracle record (verified contract parity between `InMemoryFake` and `RealAdapter`, `>= 100` property/metamorphic runs, seeded deterministic chaos covering `post_commit_ack_drop` with Virtual Clock, Red-Green mutation falsification proven, and zero mock/determinism hazards in `--source`).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings detected in the record or `--source` file.
