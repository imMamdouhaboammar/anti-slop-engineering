# Gate 0 Memory Integration Protocol

> Instructions for autonomous AI coding agents on how to read the Invariant Ledger in Gate 0 to ensure zero-drift implementation.

## Agent Gate 0 Discovery Steps

In every task session, during Gate 0 (Discover; do not improvise):

1. **Locate the Ledger:** Look for `.anti-slop/invariant-ledger.toon`. If missing, check `.anti-slop/invariant-ledger.json`. If neither exists, run `npx anti-slop-engineering steward sync` to generate it.
2. **Read the Compact TOON Block:** Ingest the TOON entries into context. Notice that TOON representation is optimized to consume < 300 tokens for dozens of invariants.
3. **Map Task Scope to Invariant Scopes:**
   - Identify all files intended for modification in the current task.
   - Cross-reference them with the `paths` of each entry in the ledger.
4. **Enforce Boundary Constraints in Gate 1:**
   - Add every governed invariant's assertion into the Gate 1 change contract under "Architectural Invariants".
   - Note all forbidden patterns to ensure they are never emitted during code generation.
5. **Preflight Drift Verification:**
   - If the task objective directly conflicts with an active invariant, halt immediately. Do not attempt a "silent workaround".
   - Present the conflict to the user and request an official Reassessment Trigger before proceeding.
