# Reference: Rollout Choreography Record Contract

> JSON schema and operational contract for machine-auditable safe evolution and rollout choreography records.

## Purpose

The Rollout Choreography Record is a machine-readable JSON artifact documenting the verification of wire compatibility ($N-1 \leftrightarrow N+1$), dark launch shadow parity, feature flag governance with instant kill-switches, and Strangler Fig progression.

Records are validated via `scripts/rollout_guard.py` before deployment authorization:
```bash
python3 scripts/rollout_guard.py audit <record.json> --json
# or
npx anti-slop-engineering rollout audit <record.json> --json
```

---

## Contract Schema (`rollout-record-contract.v1.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RolloutChoreographyRecord",
  "type": "object",
  "required": [
    "schema_version",
    "system_identity",
    "wire_compatibility",
    "dark_launch_and_shadow",
    "feature_flag_governance",
    "strangler_fig_protocol",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "enum": ["1.0"] },
    "system_identity": {
      "type": "object",
      "required": ["service_name", "component", "owner_team", "target_environment"],
      "properties": {
        "service_name": { "type": "string", "minLength": 3 },
        "component": { "type": "string", "minLength": 2 },
        "owner_team": { "type": "string", "minLength": 3 },
        "target_environment": { "type": "string", "enum": ["production", "staging", "canary"] }
      }
    },
    "wire_compatibility": {
      "type": "object",
      "required": [
        "protocol",
        "compatibility_mode",
        "tolerant_reader_enforced",
        "additive_only_verified",
        "deprecation_phase"
      ],
      "properties": {
        "protocol": {
          "type": "string",
          "enum": ["protobuf", "thrift", "json_rest", "graphql", "grpc"]
        },
        "compatibility_mode": {
          "type": "string",
          "enum": [
            "bidirectional_n_minus_one_n_plus_one",
            "backward_only",
            "breaking_migration_fenced"
          ]
        },
        "tolerant_reader_enforced": { "type": "boolean" },
        "additive_only_verified": { "type": "boolean" },
        "deprecation_phase": {
          "type": "string",
          "enum": [
            "expand",
            "dual_read",
            "contract",
            "decommission",
            "none_additive_only"
          ]
        }
      }
    },
    "dark_launch_and_shadow": {
      "type": "object",
      "required": [
        "shadow_mode_enabled",
        "traffic_mirror_percentage",
        "execution_isolation",
        "side_effect_fencing",
        "parity_gate"
      ],
      "properties": {
        "shadow_mode_enabled": { "type": "boolean" },
        "traffic_mirror_percentage": { "type": "number", "minimum": 0, "maximum": 100 },
        "execution_isolation": {
          "type": "string",
          "enum": ["asynchronous_worker", "edge_proxy_tee", "event_queue", "none_direct_canary"]
        },
        "side_effect_fencing": {
          "type": "object",
          "required": [
            "storage_mutations_blocked",
            "external_apis_mocked",
            "user_communications_suppressed"
          ],
          "properties": {
            "storage_mutations_blocked": { "type": "boolean" },
            "external_apis_mocked": { "type": "boolean" },
            "user_communications_suppressed": { "type": "boolean" }
          }
        },
        "parity_gate": {
          "type": "object",
          "required": [
            "sample_size_evaluated",
            "measured_mismatch_rate",
            "p99_latency_shadow_ms",
            "p99_latency_baseline_ms"
          ],
          "properties": {
            "sample_size_evaluated": { "type": "integer", "minimum": 0 },
            "measured_mismatch_rate": { "type": "number", "minimum": 0, "maximum": 1 },
            "p99_latency_shadow_ms": { "type": "integer", "minimum": 0 },
            "p99_latency_baseline_ms": { "type": "integer", "minimum": 0 }
          }
        }
      }
    },
    "feature_flag_governance": {
      "type": "object",
      "required": [
        "flag_id",
        "lifecycle_phase",
        "kill_switch_mechanism",
        "kill_switch_tested",
        "kill_switch_latency_ms",
        "created_at",
        "expires_at",
        "demolition_ticket"
      ],
      "properties": {
        "flag_id": { "type": "string", "minLength": 3 },
        "lifecycle_phase": {
          "type": "string",
          "enum": ["draft", "shadow", "canary", "graduated", "deprecated", "tombstoned"]
        },
        "kill_switch_mechanism": {
          "type": "string",
          "enum": ["in_memory_push", "redis_pubsub", "etcd_watch", "aws_appconfig"]
        },
        "kill_switch_tested": { "type": "boolean" },
        "kill_switch_latency_ms": { "type": "integer", "minimum": 1, "maximum": 5000 },
        "created_at": { "type": "string", "format": "date-time" },
        "expires_at": { "type": "string", "format": "date-time" },
        "demolition_ticket": { "type": "string", "minLength": 3 }
      }
    },
    "strangler_fig_protocol": {
      "type": "object",
      "required": [
        "facade_type",
        "active_vertical_slice",
        "canary_percentage",
        "automated_rollback_slo_triggers",
        "decommission_target_date"
      ],
      "properties": {
        "facade_type": {
          "type": "string",
          "enum": ["api_gateway", "reverse_proxy", "service_mesh", "none_in_service_evolution"]
        },
        "active_vertical_slice": { "type": "string", "minLength": 3 },
        "canary_percentage": { "type": "number", "minimum": 0, "maximum": 100 },
        "automated_rollback_slo_triggers": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        },
        "decommission_target_date": { "type": "string", "format": "date-time" }
      }
    },
    "verdict": {
      "type": "object",
      "required": ["status", "findings", "sign_off_sre"],
      "properties": {
        "status": { "type": "string", "enum": ["proceed", "pause", "refuse"] },
        "findings": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["severity", "code", "message"],
            "properties": {
              "severity": { "type": "string", "enum": ["block", "warning", "info"] },
              "code": { "type": "string" },
              "message": { "type": "string" }
            }
          }
        },
        "sign_off_sre": { "type": "string", "minLength": 3 }
      }
    }
  }
}
```

---

## Validation Gate Rules

To achieve a `proceed` verdict, an audit must verify:
1. `wire_compatibility.tolerant_reader_enforced` must be `true`.
2. `wire_compatibility.additive_only_verified` must be `true`.
3. If `dark_launch_and_shadow.shadow_mode_enabled` is `true`:
   - `side_effect_fencing.storage_mutations_blocked` must be `true`.
   - `side_effect_fencing.external_apis_mocked` must be `true`.
   - `side_effect_fencing.user_communications_suppressed` must be `true`.
   - `parity_gate.measured_mismatch_rate` must be $\le 0.001$ ($0.1\%$).
4. `feature_flag_governance.kill_switch_tested` must be `true`.
5. `feature_flag_governance.kill_switch_latency_ms` must be $\le 1000\text{ms}$.
6. `feature_flag_governance.expires_at` must not exceed 90 days from `created_at`.
7. `strangler_fig_protocol.automated_rollback_slo_triggers` must contain at least one explicit error-rate or latency trigger.
