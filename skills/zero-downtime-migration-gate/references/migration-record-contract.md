# Zero-Downtime Migration & Contract Record Contract

When planning or auditing database schema evolutions, data backfills, or wire contract changes across production services, save the evaluation as a persistent JSON record (`migration-record.json`) to prove Expand -> Migrate -> Contract compliance before deployment.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ZeroDowntimeMigrationRecord",
  "type": "object",
  "required": [
    "schema_version",
    "goal",
    "evolution_strategy",
    "ddl_safety",
    "backfill_plan",
    "wire_compatibility",
    "rollback_safety",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "goal": { "type": "string", "minLength": 10 },
    "evolution_strategy": {
      "type": "object",
      "required": ["pattern", "current_phase", "phases"],
      "properties": {
        "pattern": { "type": "string", "const": "expand_migrate_contract" },
        "current_phase": { "type": "string", "enum": ["expand", "migrate", "contract"] },
        "phases": {
          "type": "object",
          "required": ["expand", "migrate", "contract"],
          "properties": {
            "expand": {
              "type": "object",
              "required": ["description", "dual_write_enabled", "n_minus_1_compatible"],
              "properties": {
                "description": { "type": "string", "minLength": 15 },
                "dual_write_enabled": { "type": "boolean" },
                "n_minus_1_compatible": { "type": "boolean", "const": true }
              }
            },
            "migrate": {
              "type": "object",
              "required": ["description", "read_cutover_strategy", "verification_gate"],
              "properties": {
                "description": { "type": "string", "minLength": 15 },
                "read_cutover_strategy": { "type": "string", "minLength": 10 },
                "verification_gate": { "type": "string", "minLength": 10 }
              }
            },
            "contract": {
              "type": "object",
              "required": ["description", "drain_prerequisite"],
              "properties": {
                "description": { "type": "string", "minLength": 15 },
                "drain_prerequisite": { "type": "string", "minLength": 10 }
              }
            }
          }
        }
      }
    },
    "ddl_safety": {
      "type": "object",
      "required": [
        "engine",
        "lock_timeout_ms",
        "statement_timeout_ms",
        "concurrent_index_creation",
        "constraint_validation_strategy",
        "prohibited_operations_absent"
      ],
      "properties": {
        "engine": { "type": "string", "enum": ["postgresql", "mysql", "spanner", "sqlite_local"] },
        "lock_timeout_ms": { "type": "integer", "minimum": 100, "maximum": 5000 },
        "statement_timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 60000 },
        "concurrent_index_creation": { "type": "boolean", "const": true },
        "constraint_validation_strategy": {
          "type": "string",
          "enum": ["not_valid_then_validate", "online_inplace_lock_none", "none_required"]
        },
        "prohibited_operations_absent": { "type": "boolean", "const": true }
      }
    },
    "backfill_plan": {
      "type": "object",
      "required": ["decoupled_from_ddl", "batch_size", "throttle_delay_ms", "idempotent"],
      "properties": {
        "decoupled_from_ddl": { "type": "boolean", "const": true },
        "batch_size": { "type": "integer", "minimum": 1, "maximum": 5000 },
        "throttle_delay_ms": { "type": "integer", "minimum": 10 },
        "idempotent": { "type": "boolean", "const": true }
      }
    },
    "wire_compatibility": {
      "type": "object",
      "required": [
        "formats",
        "backward_compatible_n_reads_n_minus_1",
        "forward_compatible_n_minus_1_reads_n",
        "active_client_horizon",
        "protobuf_reserved_enforced",
        "version_pinning_strategy"
      ],
      "properties": {
        "formats": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string", "enum": ["json", "protobuf", "graphql", "sql_only"] }
        },
        "backward_compatible_n_reads_n_minus_1": { "type": "boolean", "const": true },
        "forward_compatible_n_minus_1_reads_n": { "type": "boolean", "const": true },
        "active_client_horizon": { "type": "string", "minLength": 5 },
        "protobuf_reserved_enforced": { "type": "boolean", "const": true },
        "version_pinning_strategy": {
          "type": "string",
          "enum": ["additive_tolerant_reader", "stripe_date_header_gate", "dual_endpoint_v1_v2", "internal_rolling_only"]
        }
      }
    },
    "rollback_safety": {
      "type": "object",
      "required": ["n_minus_1_binary_safe_without_db_rollback", "rehearsal_evidence"],
      "properties": {
        "n_minus_1_binary_safe_without_db_rollback": { "type": "boolean", "const": true },
        "rehearsal_evidence": { "type": "string", "minLength": 15 }
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

Validate migration records or scan SQL migration files directly against this contract using:
```bash
python3 scripts/migration_guard.py audit <record.json> [--sql <migration.sql>] --json
# or via CLI:
npx anti-slop-engineering migration audit <record.json> [--sql <migration.sql>] --json
```

Exit codes:
- `0`: Structurally compliant record (and zero blocking DDL traps in `--sql` if provided).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings (missing 3-phase decomposition, unbounded lock timeout, coupled backfill, wire incompatibility, or dangerous SQL DDL detected).
