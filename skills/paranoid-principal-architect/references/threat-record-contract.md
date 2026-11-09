# Paranoid Threat & Scale Record Contract

When evaluating high-concurrency systems, critical endpoints, or architectural designs, save the evaluation as a persistent JSON record (`paranoid-record.json`) to establish verifiable compliance before implementation.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ParanoidArchitectureRecord",
  "type": "object",
  "required": [
    "schema_version",
    "goal",
    "scale_profile",
    "threat_pre_mortem",
    "trust_boundaries",
    "concurrency_controls",
    "bounded_limits",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "goal": { "type": "string", "minLength": 10 },
    "scale_profile": {
      "type": "object",
      "required": ["target_concurrency", "throughput_rps", "latency_budget_ms"],
      "properties": {
        "target_concurrency": { "type": "integer", "minimum": 10000000 },
        "throughput_rps": { "type": "integer", "minimum": 1000 },
        "latency_budget_ms": { "type": "integer", "maximum": 500 }
      }
    },
    "threat_pre_mortem": {
      "type": "array",
      "minItems": 3,
      "items": {
        "type": "object",
        "required": ["id", "threat_class", "description", "mitigation"],
        "properties": {
          "id": { "type": "string" },
          "threat_class": {
            "type": "string",
            "enum": [
              "race_condition",
              "hot_key_contention",
              "unbounded_concurrency",
              "injection",
              "timing_attack",
              "edos",
              "toctou",
              "memory_leak",
              "network_stall"
            ]
          },
          "description": { "type": "string", "minLength": 15 },
          "mitigation": { "type": "string", "minLength": 15 }
        }
      }
    },
    "trust_boundaries": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "schema_validation", "data_layer_ownership"],
        "properties": {
          "name": { "type": "string" },
          "schema_validation": { "type": "string" },
          "data_layer_ownership": { "type": "string" }
        }
      }
    },
    "concurrency_controls": {
      "type": "object",
      "required": ["idempotency", "locking_strategy"],
      "properties": {
        "idempotency": {
          "type": "object",
          "required": ["enabled", "key_header", "storage"],
          "properties": {
            "enabled": { "type": "boolean" },
            "key_header": { "type": "string" },
            "storage": { "type": "string" }
          }
        },
        "locking_strategy": {
          "type": "string",
          "enum": ["optimistic_occ", "sharded_counters", "event_ledger", "partitioned_lock"]
        }
      }
    },
    "bounded_limits": {
      "type": "object",
      "required": ["max_read_limit", "max_payload_bytes", "network_timeout_ms", "backoff_algorithm"],
      "properties": {
        "max_read_limit": { "type": "integer", "maximum": 100 },
        "max_payload_bytes": { "type": "integer", "maximum": 10485760 },
        "network_timeout_ms": { "type": "integer", "maximum": 10000 },
        "backoff_algorithm": { "type": "string", "const": "exponential_full_jitter" }
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
python3 scripts/paranoid_guard.py audit <record.json> --json
```

Exit codes:
- `0`: Structurally compliant record.
- `1`: JSON parsing or file access failure.
- `2`: Validation findings (missing threats, unbounded limits, or unmitigated risks).
