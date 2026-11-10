# The Invariant Steward Playbook

> Step-by-step procedures for indexing repository invariants, maintaining the living ledger, and powering Gate 0 agent memory.

## 1. Ledger Synchronization Protocol

Whenever a new architectural decision record (`decision-record.json`, `paranoid-record.json`, `rollout-record.json`, `observability-slo-record.json`) is created or approved:

```bash
# Run ledger sync across all repository records
npx anti-slop-engineering steward sync --records skills docs .anti-slop --output .anti-slop/invariant-ledger.json
```

### Verification Steps
1. Verify that the output files `.anti-slop/invariant-ledger.json` and `.anti-slop/invariant-ledger.toon` exist.
2. Run the audit command to confirm schema and cryptographic validity:
   ```bash
   npx anti-slop-engineering steward audit .anti-slop/invariant-ledger.json
   ```
3. Commit the updated ledger and TOON companion to git alongside the source decision record.

---

## 2. Gate 0 Agent Integration

When starting any new task, AI coding agents must execute Gate 0 memory ingestion:

1. **Ingest Compact Memory:** Read `.anti-slop/invariant-ledger.toon`.
2. **Blast Radius Analysis:** Match planned files to modify against `paths` in each active invariant entry.
3. **Bind Contractual Invariants:** If a touched file matches an invariant scope:
   - All `forbid` patterns are added to the prohibited pattern filter.
   - All `assert` requirements are included in the Gate 1 change contract.
4. **Preflight Failure Mode Check:** If the task instructions contradict an active invariant, halt and request a formal Reassessment Trigger before making code edits.

---

## 3. Maintenance of Invariant Lifecycles

Invariants progress through four defined states:

- **`active`**: Currently enforced across all PRs touching governed paths.
- **`superseded`**: Replaced by a newer invariant through a verified Reassessment Trigger and updated decision record.
- **`waived`**: Temporarily granted an exception with a verified milestone/issue reference and expiry date.
- **`deprecated`**: Scheduled for retirement; warnings emitted but merge not blocked.
