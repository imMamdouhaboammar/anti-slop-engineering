# Reassessment Trigger Protocol & Schema

> Formal protocol for proposing, reviewing, and approving modifications or retirement of active architectural invariants.

## Protocol Purpose

Invariants are permanent by default, but architectures must evolve. The Reassessment Protocol ensures that changes to architectural invariants are intentional, documented, and backed by evidence—never accidental.

## Reassessment Trigger Schema

A valid `reassessment-trigger.json` must contain:

```json
{
  "schema_version": "1.0.0",
  "target_invariant_id": "INV-PARANOID-IDEMPOTENCY",
  "action": "supersede | waive | deprecate",
  "justification": "Comprehensive explanation of why the existing invariant is being altered",
  "trade_off_delta": {
    "gain": "Concrete operational or performance improvement achieved",
    "risk": "Risk or edge cases introduced and how they are mitigated"
  },
  "authority": {
    "author": "Architect Name",
    "pr_or_issue": "PR or Issue reference",
    "approved_at": "ISO-8601 Timestamp"
  },
  "verification_proof": "Empirical evidence (e.g. load test result, security audit, benchmark) proving the new approach satisfies reliability requirements"
}
```

## Lifecycle Actions

1. **`supersede`**: Replaces the old invariant with a new, superior invariant. The old invariant status moves to `superseded` in the ledger upon merge.
2. **`waive`**: Grants a temporary scoped exception (e.g. for an isolated legacy migration or temporary prototype). Must include an issue milestone or expiry date.
3. **`deprecate`**: Marks the invariant as no longer enforced. The invariant remains in historical records with status `deprecated`.
