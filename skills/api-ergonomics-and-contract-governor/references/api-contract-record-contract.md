# API Contract Record Contract

> Machine-verifiable contract for validating API ergonomics, Pit of Success defaults, Discriminated Unions, Branded Types, Progressive Disclosure, and RFC 9457 Problem Details.

Every public SDK, CLI tool, or critical internal module boundary must produce or validate a JSON assessment matching this contract. Run `bunx anti-slop-engineering contract preflight <file.json> --json` to check the record envelope and required sections. Run `bunx anti-slop-engineering contract audit <file.json> --json` for the complete audit.

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

### Local Python compiler and declaration evidence

Run the read-only helper from a checkout or package. Select the precise `site-packages` directory for the environment under review.

```sh
python3 -I -S scripts/python_api_evidence.py consumer.py \
  --site-packages /path/to/venv/lib/python3.12/site-packages \
  --distribution example-package --consumer-import
```

You can also specify `--module` and `--symbol` directly instead of using `--consumer-import`.

The `compiler` object records the actual Python interpreter and either a successful in-memory compile, a syntax diagnostic with its source range, or `not_checked`. The helper then locates the requested distribution's installed metadata and exact file ownership list. In `--consumer-import` mode, it parses the consumer's top-level `from <module> import <symbol>` statements to find the single explicit import owned by that distribution. It then reads a regular source file or stub owned by that distribution without importing project modules. Use `-I -S` to disable user site startup and Python site hooks in the verifier process.

`installed_api.status: declared` means a direct declaration is visible in the installed source or stub at the reported location. When using `--consumer-import`, the receipt includes `import_span` (the consumer's import location), `declaration_span` (the installed file's path and location), and `provenance` (the installation root and module file). It does not prove Python can import it from the consumer's actual working directory, that a guarded or dynamic export works, or that the API type-checks. `not_declared` means no direct declaration in the selected stub. Missing metadata, namespace or binary modules, unresolved symbols in normal source, dynamic stubs, or ambiguous imports can yield `inconclusive`.

Exit status 0 requires both a completed syntax check and declaration evidence. Status 1 is a compiler diagnostic. Status 2 means the requested evidence was unavailable or inconclusive. No dependencies are installed, no registry is queried, and neither source file is executed.

### Optional TypeScript compiler fixture

```sh
python3 -I -S scripts/typescript_compiler_evidence.py \
  --node /path/to/trusted/node --tsc-js /path/to/trusted/typescript/lib/tsc.js
```

Select an installed compiler that you trust. The probe compares the compiler's reported version with its installed package metadata. On macOS it first verifies that a loopback bind is denied, then checks fixed positive and negative TypeScript fixtures in a temporary directory. The run passes explicit strict, no-emit, no-resolve and library flags, empty type roots, and a clean environment. There is no project path input, project configuration or plugin load, or import of consumer code.

The result records the selected compiler version, passing control, and an actual diagnostic with its code and source position. The helper has per-child wall-time, CPU and output limits. The Node heap target is not an operating-system memory cap. A missing compiler, unsupported platform, failed sandbox probe or unrecognized diagnostic returns `not_checked`. The network sandbox profile is not a guarantee of filesystem isolation for an untrusted compiler.
