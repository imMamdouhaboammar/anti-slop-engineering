# API Contract Record Contract

> Machine-verifiable contract for validating API ergonomics, Pit of Success defaults, Discriminated Unions, Branded Types, Progressive Disclosure, and RFC 9457 Problem Details.

Every public SDK, CLI tool, or critical internal module boundary must produce or validate a JSON assessment matching this contract. Audited via `npx anti-slop-engineering contract audit <file.json> --json`.

---

## Canonical JSON Schema Specification

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ApiContractRecord",
  "type": "object",
  "required": [
    "schema_version",
    "contract_id",
    "target_interface",
    "verdict"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "enum": ["1.0"]
    },
    "contract_id": {
      "type": "string",
      "minLength": 5
    },
    "target_interface": {
      "type": "object",
      "required": [
        "module_path",
        "interface_type",
        "language"
      ],
      "properties": {
        "module_path": { "type": "string", "minLength": 3 },
        "interface_type": {
          "type": "string",
          "enum": ["public_sdk", "internal_service_client", "cli_tool", "domain_module"]
        },
        "language": {
          "type": "string",
          "enum": ["typescript", "python", "go", "rust"]
        }
      }
    },
    "pit_of_success_defaults": {
      "type": "object",
      "required": [
        "enabled",
        "default_timeout_ms",
        "auto_retry_max_attempts",
        "backoff_strategy",
        "default_page_limit",
        "max_page_limit_ceiling",
        "safe_tls_enforced"
      ],
      "properties": {
        "enabled": { "type": "boolean", "const": true },
        "default_timeout_ms": { "type": "integer", "minimum": 1000, "maximum": 60000 },
        "auto_retry_max_attempts": { "type": "integer", "minimum": 1, "maximum": 10 },
        "backoff_strategy": {
          "type": "string",
          "enum": ["exponential_full_jitter", "exponential_equal_jitter", "decorrelated_jitter"]
        },
        "default_page_limit": { "type": "integer", "minimum": 1, "maximum": 100 },
        "max_page_limit_ceiling": { "type": "integer", "minimum": 50, "maximum": 1000 },
        "safe_tls_enforced": { "type": "boolean", "const": true }
      }
    },
    "illegal_states_unrepresentable": {
      "type": "object",
      "required": [
        "discriminated_unions_enforced",
        "discriminator_field",
        "branded_types_enforced",
        "branded_type_identifiers",
        "exhaustive_match_enforced",
        "zero_boolean_traps_verified"
      ],
      "properties": {
        "discriminated_unions_enforced": { "type": "boolean", "const": true },
        "discriminator_field": { "type": "string", "minLength": 2 },
        "branded_types_enforced": { "type": "boolean", "const": true },
        "branded_type_identifiers": {
          "type": "array",
          "items": { "type": "string", "minLength": 3 },
          "minItems": 2
        },
        "exhaustive_match_enforced": { "type": "boolean", "const": true },
        "zero_boolean_traps_verified": { "type": "boolean", "const": true }
      }
    },
    "progressive_disclosure": {
      "type": "object",
      "required": [
        "tier_1_one_liner_facade",
        "tier_2_options_bag_supported",
        "tier_3_power_escape_hatch",
        "namespace_pollution_prevented"
      ],
      "properties": {
        "tier_1_one_liner_facade": { "type": "string", "minLength": 10 },
        "tier_2_options_bag_supported": { "type": "boolean", "const": true },
        "tier_3_power_escape_hatch": { "type": "string", "minLength": 10 },
        "namespace_pollution_prevented": { "type": "boolean", "const": true }
      }
    },
    "rfc9457_problem_details": {
      "type": "object",
      "required": [
        "standard_compliance",
        "error_type_uri_prefix",
        "deterministic_machine_codes",
        "invalid_params_breakdown_supported",
        "remediation_action_supported",
        "retryability_metadata_exposed"
      ],
      "properties": {
        "standard_compliance": {
          "type": "string",
          "enum": ["RFC_9457", "RFC_7807"]
        },
        "error_type_uri_prefix": { "type": "string", "minLength": 5 },
        "deterministic_machine_codes": {
          "type": "array",
          "items": { "type": "string", "minLength": 3 },
          "minItems": 2
        },
        "invalid_params_breakdown_supported": { "type": "boolean", "const": true },
        "remediation_action_supported": { "type": "boolean", "const": true },
        "retryability_metadata_exposed": { "type": "boolean", "const": true }
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
          "items": { "type": "string", "minLength": 5 },
          "minItems": 1
        }
      }
    }
  }
}
```
