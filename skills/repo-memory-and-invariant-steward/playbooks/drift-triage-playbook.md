# Drift Triage & Remediation Playbook

> Operational guide for triaging, investigating, and resolving architectural drift violations flagged by the steward guard.

## 1. Drift Incident Response Flow

When `npx anti-slop-engineering steward drift --base HEAD` exits with code 2:

```
                  Drift Finding Reported
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
      Accidental Regression    Intentional Architecture Change
               │                         │
               ▼                         ▼
        [Path A: Fix]             [Path B: Evolve]
   Revert violating edit or   File formal reassessment-trigger.json
   restore required tokens    with trade-off delta and load proof
               │                         │
               ▼                         ▼
       Re-run drift check       Run: steward reassess trigger.json
         (Must pass 0)         Pass drift check with --reassessment
```

---

## 2. Resolving Accidental Regressions (Path A)

1. Inspect the finding output:
   - Identify the `invariant_id` (e.g. `INV-PARANOID-IDEMPOTENCY`).
   - Note the `violating_line` or `removed_pattern`.
2. Locate the file in the PR diff.
3. Restore the required pattern (e.g. restore the `Idempotency-Key` validation check in the controller).
4. Remove any forbidden patterns (e.g. replace `Math.random()` with `crypto.randomUUID()`).
5. Re-run drift verification:
   ```bash
   npx anti-slop-engineering steward drift --base HEAD
   ```

---

## 3. Authoring an Official Reassessment Trigger (Path B)

If the change represents a planned, superior architectural evolution:

1. Draft `reassessment-trigger.json` following the schema.
2. Fill out:
   - `target_invariant_id`: exact ID from the ledger.
   - `action`: `supersede`, `waive`, or `deprecate`.
   - `justification`: comprehensive technical rationale.
   - `trade_off_delta`: explicit `gain` vs `risk`.
   - `authority`: author and PR/issue reference.
   - `verification_proof`: empirical evidence (e.g. load test result, benchmark, security audit).
3. Validate the record:
   ```bash
   npx anti-slop-engineering steward reassess reassessment-trigger.json
   ```
4. Run drift check with the reassessment trigger:
   ```bash
   npx anti-slop-engineering steward drift --base HEAD --reassessment reassessment-trigger.json
   ```
5. Merge the PR and run `steward sync` to update the ledger status.
