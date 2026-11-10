# Privacy & Data Lineage Record Contract

> Machine-verifiable contract for validating zero-leakage PII architectures, cryptographic erasure, automated retention TTL, and data lineage flow policies.

Every consequential data architecture, schema migration, or event pipeline handling customer identifiers must produce or validate a JSON assessment matching this contract. Audited via `npx anti-slop-engineering privacy audit <file.json> --json`.

---

## Canonical JSON Schema Specification

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PrivacyAndDataLineageRecord",
  "type": "object",
  "required": [
    "schema_version",
    "system_id",
    "target_system",
    "verdict"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "enum": ["1.0"]
    },
    "system_id": {
      "type": "string",
      "minLength": 5
    },
    "target_system": {
      "type": "object",
      "required": [
        "module_under_test",
        "system_archetype",
        "regulatory_regimes"
      ],
      "properties": {
        "module_under_test": {
          "type": "string",
          "minLength": 5
        },
        "system_archetype": {
          "type": "string",
          "enum": [
            "event_driven_data_lakehouse",
            "user_identity_and_auth_service",
            "telemetry_and_analytics_pipeline",
            "multi_tenant_saas_backend",
            "mobile_client_telemetry"
          ]
        },
        "regulatory_regimes": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        }
      }
    },
    "tainted_pii_types": {
      "type": "object",
      "required": [
        "branded_types_enabled",
        "redaction_wrapper",
        "log_leakage_prevented",
        "unredacted_serialization_banned",
        "audited_pii_fields"
      ],
      "properties": {
        "branded_types_enabled": { "type": "boolean", "const": true },
        "redaction_wrapper": { "type": "string", "minLength": 5 },
        "log_leakage_prevented": { "type": "boolean", "const": true },
        "unredacted_serialization_banned": { "type": "boolean", "const": true },
        "audited_pii_fields": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "required": ["field_name", "sensitivity", "type_brand", "serialization_policy"],
            "properties": {
              "field_name": { "type": "string", "minLength": 2 },
              "sensitivity": {
                "type": "string",
                "enum": ["restricted_pii", "confidential_telemetry", "sensitive_financial", "protected_health"]
              },
              "type_brand": { "type": "string", "minLength": 5 },
              "serialization_policy": { "type": "string", "minLength": 5 }
            }
          }
        }
      }
    },
    "cryptographic_erasure": {
      "type": "object",
      "required": [
        "mechanism",
        "kms_provider",
        "key_derivation_algorithm",
        "immutable_ledger_coverage",
        "revocation_latency_ms",
        "confirmation_receipt_verified"
      ],
      "properties": {
        "mechanism": {
          "type": "string",
          "enum": ["crypto_shredding_key_per_subject"]
        },
        "kms_provider": {
          "type": "string",
          "enum": ["aws_kms", "gcp_kms", "hashicorp_vault", "apple_secure_enclave"]
        },
        "key_derivation_algorithm": {
          "type": "string",
          "enum": ["AES-256-GCM", "XChaCha20-Poly1305"]
        },
        "immutable_ledger_coverage": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 2
        },
        "revocation_latency_ms": {
          "type": "integer",
          "maximum": 5000,
          "minimum": 1
        },
        "confirmation_receipt_verified": { "type": "boolean", "const": true }
      }
    },
    "data_minimization_and_ttl": {
      "type": "object",
      "required": [
        "purpose_binding_declared",
        "retention_ttl_enforced",
        "max_retention_days",
        "automated_gc_pipeline",
        "differential_privacy_or_anonymization"
      ],
      "properties": {
        "purpose_binding_declared": { "type": "boolean", "const": true },
        "retention_ttl_enforced": { "type": "boolean", "const": true },
        "max_retention_days": {
          "type": "integer",
          "minimum": 1,
          "maximum": 730
        },
        "automated_gc_pipeline": { "type": "string", "minLength": 5 },
        "differential_privacy_or_anonymization": { "type": "string", "minLength": 5 }
      }
    },
    "data_lineage_and_flow": {
      "type": "object",
      "required": [
        "lineage_dag_modeled",
        "forbidden_sinks_guarded",
        "telemetry_egress_allowlist",
        "third_party_sharing_fenced"
      ],
      "properties": {
        "lineage_dag_modeled": { "type": "boolean", "const": true },
        "forbidden_sinks_guarded": { "type": "boolean", "const": true },
        "telemetry_egress_allowlist": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        },
        "third_party_sharing_fenced": { "type": "boolean", "const": true }
      }
    },
    "verdict": {
      "type": "object",
      "required": ["action", "rationale", "revisit_triggers"],
      "properties": {
        "action": {
          "type": "string",
          "enum": ["proceed", "pause", "refuse"]
        },
        "rationale": {
          "type": "string",
          "minLength": 20
        },
        "revisit_triggers": {
          "type": "array",
          "items": { "type": "string", "minLength": 5 },
          "minItems": 1
        }
      }
    }
  }
}
```
