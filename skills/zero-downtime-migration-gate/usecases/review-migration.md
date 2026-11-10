# Review Migration & Contracts: Zero-Downtime Audit

Use this workflow when reviewing pull requests containing SQL migrations, ORM schema diffs, OpenAPI/JSON Schema edits, Protobuf `.proto` changes, or GraphQL schema modifications.

## Review Audit Checklist

### 1. Scan for the Eight Instant Rejections
1. **In-place Rename:** `RENAME COLUMN` or `RENAME TABLE` on an active table. Reject and require Expand -> Migrate -> Contract.
2. **Premature Drop:** `DROP COLUMN` or `DROP TABLE` in the same PR that removes the code reference. Reject; code removal must deploy and bake before column drop.
3. **Blocking Index Creation:** `CREATE INDEX` or `DROP INDEX` lacking `CONCURRENTLY` (PostgreSQL) or `ALGORITHM=INPLACE, LOCK=NONE` (MySQL).
4. **Transactional Concurrent Index:** `CREATE INDEX CONCURRENTLY` wrapped inside `BEGIN ... COMMIT`. Reject; PostgreSQL aborts this at runtime.
5. **Unvalidated Constraint Lock:** `ADD CONSTRAINT ... FOREIGN KEY` or `CHECK` without `NOT VALID`, or direct `SET NOT NULL` without a pre-validated check constraint.
6. **Unbounded In-Migration Backfill:** Full-table `UPDATE` or `DELETE` without `LIMIT` batching inside a DDL migration file.
7. **Protobuf Wire Corruption:** Changing a field tag number, changing field types incompatibly, or deleting a field without adding `reserved <tag>; reserved "<name>";`.
8. **Breaking JSON/GraphQL Mutation:** Renaming a response property, changing a field from scalar to object/array, tightening an input from optional to required, or emitting a new enum value to unguarded $N-1$ clients.

### 2. Lock & Timeout Verification
- Does every DDL script declare an explicit `lock_timeout` (e.g. `<= 5000ms`)?
- Does any statement acquire an `ACCESS EXCLUSIVE` lock for longer than a metadata catalog update?
- If `ADD COLUMN ... DEFAULT ...` is used, is the default expression non-volatile (constants ok in PG 11+; volatile functions like `random()` or `clock_timestamp()` trigger a full table rewrite in older engines)?

### 3. Rollback & Coexistence Verification
- Can the deployment be rolled back purely by reverting the application binary to Version $N-1$, without running a down-migration?
- If the PR drops a column in Phase 3, was the `NOT NULL` constraint already removed in an earlier phase so $N-1$ / $N$ writes did not fail?

## Review Output Format

Provide audit findings structured as follows:

```markdown
### 1. Zero-Downtime & Compatibility Findings
- **[CRITICAL / HIGH / MEDIUM]** <Concise title>
  - **Downtime / Breakage Vector:** Exact lock mode acquired (`ACCESS EXCLUSIVE`) or $N-1$ client crash mechanism during rolling deploy.
  - **Location:** File path and line numbers.
  - **Remediation:** Concrete 3-phase (Expand -> Migrate -> Contract) SQL or wire patch.

### 2. Evolution Gate Compliance Matrix
| Invariant | Status | Evidence |
| --- | --- | --- |
| Expand -> Migrate -> Contract Separation | PASS / FAIL | Phase 1 adds nullable column only; drop deferred |
| Lock-Free DDL & Timeout Guards | PASS / FAIL | `lock_timeout = '2s'`, `CONCURRENTLY`, `NOT VALID` |
| Out-of-Band Batched Backfill | PASS / FAIL | Keyset batches of 1,000 rows outside DDL |
| $N$ / $N-1$ Forward & Backward Wire Compatibility | PASS / FAIL | Additive optional fields; legacy fields preserved |

### 3. Verdict
`PROCEED`, `PAUSE`, or `REFUSE`
```
