# Invariant Ledger Contract & Schema Specification

> Defines the schema, fields, hash provenance, and TOON compaction format for the repository Invariant Ledger.

## Canonical JSON Schema

The living Invariant Ledger (`.anti-slop/invariant-ledger.json`) adheres to the following structure:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "ISO-8601 Timestamp",
  "invariants_count": 4,
  "ledger_hash": "SHA-256 string",
  "invariants": [
    {
      "id": "INV-<DOMAIN>-<NUMBER_OR_NAME>",
      "category": "concurrency_and_scale | security_and_auth | api_contract | telemetry_and_slo | data_lineage | rollout_and_compatibility | hardware_and_perf | testing_and_simulation | architecture",
      "assertion": "Explicit non-negotiable invariant statement",
      "rationale": "Why this invariant exists and what catastrophic failure it prevents",
      "enforcement_scope": {
        "paths": ["glob/pattern/**"],
        "patterns": ["required_token"],
        "forbidden_patterns": ["banned_token"]
      },
      "authority": {
        "record_type": "source_record_type",
        "record_file": "path/to/source-record.json",
        "record_sha256": "SHA-256 of source record",
        "author": "Architect Name"
      },
      "status": "active | superseded | deprecated | waived",
      "superseded_by": "Optional INV-ID that replaced this entry",
      "reassessment_threshold": "Conditions required to unlock or evolve this rule"
    }
  ]
}
```

## TOON Compact Representation (`.anti-slop/invariant-ledger.toon`)

Designed for token-thrifty ingestion by AI agents during Gate 0:

```toon
invariant_ledger[count=N,hash=<12_char_sha>]:
  entry[id=INV-ID,cat=<category>,status=active,paths=<comma_separated_globs>]:
    assert: <assertion>
    forbid: <forbidden_patterns>
```
