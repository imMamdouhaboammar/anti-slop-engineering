# Playbook 1: Google Spanner & Lock-Free Relational Schema Evolution

> Inspired by Google Cloud Spanner online schema evolution principles and high-throughput PostgreSQL/MySQL DBRE discipline.

## 1. The Spanner Philosophy Applied to Relational Databases

In Google Spanner, schema changes (`ALTER TABLE`) execute online without locking reads or writes by propagating schema versions asynchronously through internal states:
1. **Write-Only / Dual-Write State:** New schema elements exist and receive writes and deletions, but cannot yet be queried as authoritative until historical rows are populated and indexed.
2. **Backfill & Index Build State:** Background storage nodes backfill index entries and validate constraints in bounded ranges without blocking active transactions.
3. **Read-Write State:** Once 100% consistent across all splits, reads cut over to the new schema element.

When operating PostgreSQL or MySQL under rolling deployments, you must orchestrate this exact state machine explicitly across application and database releases.

---

## 2. The Five Stages of Safe Column & Table Evolution

Whenever an engineering task requires renaming a column, changing a column's data type, splitting a column, or moving columns across tables, execute these five distinct steps across **three deployment phases**:

### Stage 1: Schema Expansion (Phase 1A)
- Prepend `SET LOCAL lock_timeout = '2s'; SET LOCAL statement_timeout = '5s';`.
- Add the new column as `NULL` (never `NOT NULL` without a safe default, or Version $N-1$ `INSERT` statements will immediately crash).
- Build supporting indexes using `CREATE INDEX CONCURRENTLY`.

### Stage 2: Application Dual-Write (Phase 1B)
- Deploy Version $N$ application code that writes to **both** the old column and the new column in every `INSERT` and `UPDATE`.
- In the read path, read from the new column if non-null, falling back to the old column (`row.new_col ?? transform(row.old_col)`).
- **Critical Pre-Contraction Step:** If the old column currently has a `NOT NULL` constraint in the database, issue `ALTER TABLE ... ALTER COLUMN old_col DROP NOT NULL;` now so future code can stop populating `old_col` without triggering constraint violations.

### Stage 3: Throttled Out-of-Band Backfill (Phase 2A)
- Run an idempotent background job using primary-key cursor pagination:
  - Batch size: `500` to `2,000` rows per transaction.
  - Inter-batch pause: `50ms` to `250ms` with jitter.
  - Health guard: Query replication lag (`SELECT EXTRACT(EPOCH FROM replay_lag) FROM pg_stat_replication`) and pause if lag exceeds `2.0` seconds.

### Stage 4: Constraint Validation & Read Cutover (Phase 2B)
- Attach `CHECK (new_col IS NOT NULL) NOT VALID`, then run `VALIDATE CONSTRAINT`.
- Promote `new_col` to `SET NOT NULL` (instantaneous in PostgreSQL 12+ once the `CHECK` constraint is validated).
- Deploy application code that reads 100% from `new_col` while retaining dual-writes for safe rollback during the bake window.

### Stage 5: Contraction (Phase 3)
- Confirm zero $N-1$ pods are running and rollback window has closed.
- Deploy application code that stops writing to `old_col` and removes `old_col` from all ORM models and SQL queries.
- Execute `ALTER TABLE ... DROP COLUMN IF EXISTS old_col;` under `lock_timeout = '2s'`.

---

## 3. PostgreSQL Lock Contention Survival Rules

1. **Never wrap `CREATE INDEX CONCURRENTLY` in a transaction.** PostgreSQL throws `ERROR: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`.
2. **Always check for `INVALID` indexes after failed concurrent builds.** Query `pg_index.indisvalid = false` and `DROP INDEX CONCURRENTLY` before retrying.
3. **Never add a column with a volatile default (`uuid_generate_v4()`, `now()` where evaluated dynamically per row in legacy versions) without verifying PG 11+ fast-default behavior.**
4. **Partitioned Tables:** On partitioned tables, create the index `CONCURRENTLY` on each leaf partition individually first, then attach it to the parent table so the parent lock is instantaneous.
