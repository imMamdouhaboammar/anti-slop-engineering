# Author Safe Migration: Lock-Free DDL & Batched Backfill Discipline

Use this workflow when writing SQL migration files, ORM migrations (Prisma, Drizzle, Alembic, Flyway, Goose, Rails ActiveRecord), or data backfill scripts.

## Implementation Procedure

### 1. Execute Coexistence & Lock Pre-Mortem
Before writing a single line of SQL or migration code, document:
1. **Lock Mode Analysis:** State the exact PostgreSQL or MySQL lock acquired by each DDL statement (e.g. `SHARE UPDATE EXCLUSIVE` vs `ACCESS EXCLUSIVE`).
2. **$N-1$ Compatibility Proof:** Prove that existing running queries (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) from Version $N-1$ will succeed immediately after this migration applies.
3. **Timeout Guard:** State the exact `lock_timeout` and `statement_timeout` configured at the top of the migration.

### 2. Author Lock-Free SQL DDL
Follow these non-negotiable structural rules:

1. **Always Set Timeouts First:**
   ```sql
   SET LOCAL lock_timeout = '2s';
   SET LOCAL statement_timeout = '10s';
   ```
2. **Concurrent Indexing Outside Transactions:**
   - Disable the migration runner's automatic transaction wrapper (`-- migrate: no-transaction` or `disable_ddl_transaction!`).
   - Run `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (column_name);`
3. **Two-Step Foreign Keys & Check Constraints:**
   ```sql
   -- Step A: Metadata attach without scanning table
   ALTER TABLE orders
     ADD CONSTRAINT fk_orders_customer
     FOREIGN KEY (customer_id) REFERENCES customers (id)
     NOT VALID;

   -- Step B: Non-blocking background scan
   ALTER TABLE orders
     VALIDATE CONSTRAINT fk_orders_customer;
   ```
4. **Safe `NOT NULL` Addition on Existing Columns:**
   ```sql
   -- Step A: Add NOT VALID check constraint
   ALTER TABLE users
     ADD CONSTRAINT chk_users_email_not_null
     CHECK (email IS NOT NULL) NOT VALID;

   -- Step B: Validate without blocking writes
   ALTER TABLE users
     VALIDATE CONSTRAINT chk_users_email_not_null;

   -- Step C: Instantaneous metadata promotion (PG 12+)
   ALTER TABLE users
     ALTER COLUMN email SET NOT NULL;

   -- Step D: Clean up redundant check constraint
   ALTER TABLE users
     DROP CONSTRAINT chk_users_email_not_null;
   ```

### 3. Implement Out-of-Band Keyset Backfill Worker
Never embed `UPDATE table SET new_col = old_col;` inside a DDL migration file on a table with `> 10,000` rows. Implement a standalone, resumable batch worker:
1. **Keyset Cursor:** Query the next batch of primary keys where `id > lastCursorId` ordered by `id ASC LIMIT 1000`.
2. **Scoped Batch Transaction:** Update only that batch inside a short transaction with `AbortSignal.timeout(5000)`.
3. **Adaptive Backpressure:** Sleep with full jitter (`50ms–200ms`) between batches; if replica lag exceeds `2000ms`, pause until replicas catch up.

### 4. Write Multi-Version Compatibility Tests
Deliver automated tests proving zero downtime:
- **$N-1$ Query Survival Test:** Run the test suite's legacy $N-1$ repository queries (`INSERT` omitting the new column, `SELECT` expecting legacy columns) against a database where Phase 1 DDL has been applied.
- **Idempotent Backfill Test:** Run the backfill worker twice over the same dataset and verify identical final state with zero duplicate side effects.
- **Wire Coexistence Test:** Verify $N-1$ client JSON/Protobuf deserializers cleanly parse Version $N$ responses, and Version $N$ endpoints cleanly accept Version $N-1$ request bodies.
