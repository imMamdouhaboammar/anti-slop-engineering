# Use Case: Invariant Ledger Sync

> How to compile, deduplicate, and index all repository decision records into a single living Invariant Ledger.

## When to Run
- At the end of an architectural design session that created a new `*record*.json`.
- In a CI pipeline or pre-commit hook to guarantee ledger freshness.
- When onboarding an AI agent to an existing codebase.

## Workflow

1. Execute the sync command:
   ```bash
   npx anti-slop-engineering steward sync --records skills docs .anti-slop --output .anti-slop/invariant-ledger.json
   ```
2. Verify output summary:
   - Scanned records count.
   - Invariants indexed count.
   - Generated TOON file path.
3. Audit the generated ledger:
   ```bash
   npx anti-slop-engineering steward audit .anti-slop/invariant-ledger.json
   ```
4. Commit `.anti-slop/invariant-ledger.json` and `.anti-slop/invariant-ledger.toon` to version control.
