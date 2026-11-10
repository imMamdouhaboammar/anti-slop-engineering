# Use Case: Reassess Invariant

> How to officially propose, audit, and approve an architectural evolution that modifies an existing invariant.

## When to Run
- When business or technology requirements render an existing invariant obsolete or sub-optimal.
- When replacing one technology (e.g. Redis idempotency) with another (e.g. database conditional constraints).
- When a deliberate waiver is needed for an isolated migration branch.

## Workflow

1. Create a `reassessment-trigger.json` based on the [example](../examples/reassessment-trigger-example.json).
2. Run validation on the reassessment record:
   ```bash
   npx anti-slop-engineering steward reassess reassessment-trigger.json
   ```
3. Run the drift check with the trigger:
   ```bash
   npx anti-slop-engineering steward drift --base HEAD --reassessment reassessment-trigger.json
   ```
4. Once merged, re-sync the ledger to mark the target invariant as `superseded` or `waived`:
   ```bash
   npx anti-slop-engineering steward sync
   ```
