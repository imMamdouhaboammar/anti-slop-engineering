# Lock-Free SQL Patterns (PostgreSQL & MySQL)

## 1. The Lock-Queue Amplification Hazard

Why does a fast metadata operation like `ALTER TABLE users ADD COLUMN bio TEXT;` cause a 10-minute production outage?

1. Session A starts a 45-second analytical `SELECT` query on `users` (acquires `ACCESS SHARE` lock).
2. Session B runs `ALTER TABLE users ADD COLUMN bio TEXT;` without a `lock_timeout`. It requests an `ACCESS EXCLUSIVE` lock, which conflicts with Session A's `ACCESS SHARE` lock, so Session B enters the lock wait queue.
3. Sessions C, D, E... (10,000 incoming OLTP `SELECT` and `INSERT` queries) arrive. Because PostgreSQL's lock queue is fair, **all incoming reads and writes block behind waiting Session B**.
4. Connection pools hit 100% saturation within 3 seconds, cascading into a total service outage.

### Mandatory Defense: Explicit `lock_timeout` Retry Loop
Every DDL script MUST set a bounded `lock_timeout`:
```sql
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';
```
If the lock cannot be acquired within 2 seconds, the DDL aborts harmlessly without blocking OLTP traffic, and the migration runner retries with jittered backoff.

---

## 2. PostgreSQL Safe vs Unsafe DDL Matrix

| Operation | Unsafe SQL (Blocks Production) | Lock Acquired (Unsafe) | Safe Zero-Downtime SQL | Lock Acquired (Safe) |
| --- | --- | --- | --- | --- |
| **Add Index** | `CREATE INDEX idx ON tbl (col);` | `SHARE` (Blocks all writes for minutes/hours) | `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx ON tbl (col);` | `SHARE UPDATE EXCLUSIVE` (Allows reads & writes) |
| **Drop Index** | `DROP INDEX idx;` | `ACCESS EXCLUSIVE` (Blocks reads & writes) | `DROP INDEX CONCURRENTLY IF EXISTS idx;` | `SHARE UPDATE EXCLUSIVE` (Allows reads & writes) |
| **Add Foreign Key** | `ALTER TABLE t ADD CONSTRAINT fk FOREIGN KEY (c) REFERENCES p(id);` | `SHARE ROW EXCLUSIVE` + full table scan | `ALTER TABLE t ADD CONSTRAINT fk FOREIGN KEY (c) REFERENCES p(id) NOT VALID;` then `VALIDATE CONSTRAINT fk;` | Brief metadata lock, then `SHARE UPDATE EXCLUSIVE` |
| **Add Check Constraint** | `ALTER TABLE t ADD CONSTRAINT chk CHECK (c > 0);` | `ACCESS EXCLUSIVE` + full table scan | `ALTER TABLE t ADD CONSTRAINT chk CHECK (c > 0) NOT VALID;` then `VALIDATE CONSTRAINT chk;` | Brief metadata lock, then `SHARE UPDATE EXCLUSIVE` |
| **Add `NOT NULL`** | `ALTER TABLE t ALTER COLUMN c SET NOT NULL;` | `ACCESS EXCLUSIVE` + full table scan | Add `CHECK (c IS NOT NULL) NOT VALID` -> `VALIDATE CONSTRAINT` -> `SET NOT NULL` (PG 12+) | Brief metadata lock, no exclusive table scan |
| **Add Column with Default** | `ADD COLUMN c TEXT DEFAULT random()::text;` | `ACCESS EXCLUSIVE` + full table rewrite (volatile default) | `ADD COLUMN c TEXT DEFAULT 'standard';` (constant non-volatile default in PG 11+) | Brief metadata catalog update only |
| **Widen `VARCHAR(N)`** | `ALTER COLUMN c TYPE CHAR(100);` | `ACCESS EXCLUSIVE` + full table rewrite | `ALTER COLUMN c TYPE VARCHAR(100);` or `TYPE TEXT;` (binary compatible in PG) | Brief metadata catalog update |

---

## 3. Copy-Pasteable PostgreSQL Recipes

### Recipe A: Concurrent Index Creation & Cleanup
Note: `CREATE INDEX CONCURRENTLY` cannot run inside a transaction (`BEGIN ... COMMIT`). If a concurrent index build fails midway, PostgreSQL leaves an `INVALID` index behind. Always drop any invalid remnant before re-creating:
```sql
-- migrate: no-transaction
SET statement_timeout = '0';
SET lock_timeout = '2s';

DROP INDEX CONCURRENTLY IF EXISTS idx_invoices_tenant_created_at;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_tenant_created_at
  ON invoices (tenant_id, created_at DESC);
```

### Recipe B: Safe Foreign Key Addition
```sql
-- Migration 1: Attach constraint for new writes only (sub-millisecond)
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '5s';

ALTER TABLE line_items
  ADD CONSTRAINT fk_line_items_invoice_id
  FOREIGN KEY (invoice_id) REFERENCES invoices (id)
  NOT VALID;
COMMIT;

-- Migration 2: Validate historical rows without blocking writes
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '0';

ALTER TABLE line_items
  VALIDATE CONSTRAINT fk_line_items_invoice_id;
COMMIT;
```

### Recipe C: Zero-Lock `NOT NULL` Promotion (PostgreSQL 12+)
```sql
-- Step 1: Attach NOT VALID check constraint
BEGIN;
SET LOCAL lock_timeout = '2s';
ALTER TABLE payments
  ADD CONSTRAINT chk_payments_currency_not_null
  CHECK (currency IS NOT NULL) NOT VALID;
COMMIT;

-- Step 2: Validate existing rows under SHARE UPDATE EXCLUSIVE (non-blocking)
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '0';
ALTER TABLE payments
  VALIDATE CONSTRAINT chk_payments_currency_not_null;
COMMIT;

-- Step 3: Promote to native NOT NULL (PG 12+ skips full scan because chk is validated!)
BEGIN;
SET LOCAL lock_timeout = '2s';
ALTER TABLE payments
  ALTER COLUMN currency SET NOT NULL;
ALTER TABLE payments
  DROP CONSTRAINT chk_payments_currency_not_null;
COMMIT;
```

---

## 4. MySQL 8.0+ Online DDL Rules (`InnoDB`)

In MySQL, silent fallback to `ALGORITHM=COPY` locks the table and duplicates disk usage. Always assert `ALGORITHM=INSTANT` or `ALGORITHM=INPLACE, LOCK=NONE` explicitly so MySQL fails fast if an operation would copy the table:

```sql
SET SESSION lock_wait_timeout = 2;

-- Adding a nullable column instantaneously (MySQL 8.0.12+)
ALTER TABLE orders
  ADD COLUMN idempotency_key VARCHAR(64) NULL,
  ALGORITHM=INSTANT;

-- Adding a secondary index online without blocking DML
ALTER TABLE orders
  ADD INDEX idx_orders_idempotency (idempotency_key),
  ALGORITHM=INPLACE,
  LOCK=NONE;
```
When altering massive MySQL tables with operations that do not support `INSTANT` or `LOCK=NONE` (such as changing column data types), use **gh-ost** or **Vitess Online DDL** to shadow-copy via binlog replication and cut over atomically.
