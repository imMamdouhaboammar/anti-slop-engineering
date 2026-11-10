# Plan 3-Phase Evolution: Expand -> Migrate -> Contract

Use this workflow when designing database schema modifications, service data model changes, or external API wire evolutions that must deploy with zero downtime.

## Step-by-Step Evolution Procedure

### 1. Establish the Client & Deployment Horizon
1. **Inventory Active Consumers:** Identify every caller reading from or writing to the database table or API endpoint:
   - Internal backend pods during rolling deployment (coexistence window: 5–30 minutes).
   - Browser SPAs with unrefreshed tabs (coexistence window: 24–72 hours).
   - Native iOS / Android applications (coexistence window: 30–180 days).
   - External partner webhooks / public API integrations (coexistence window: 1–3 years or pinned API version header).
2. **Determine Coexistence Invariant:** Version $N-1$ and Version $N$ MUST operate concurrently without throwing errors, corrupting rows, or failing payload validation.

### 2. Design Phase 1: EXPAND (Additive & Backward-Compatible)
1. **Database Layer:**
   - Add new columns as `NULL` (or with fast non-volatile metadata defaults).
   - Create new tables or join structures without altering existing tables.
   - Build new indexes using `CREATE INDEX CONCURRENTLY` (PostgreSQL) or `ALGORITHM=INPLACE, LOCK=NONE` (MySQL).
   - Attach new constraints with `NOT VALID` so existing rows are not scanned under an exclusive lock.
2. **Application Layer (Dual-Write, Old-Read):**
   - Deploy application code that writes to **both** the legacy column/table and the newly expanded column/table within the same unit of work.
   - Continue serving reads exclusively from the legacy column/table (since historical rows are not yet backfilled).
3. **Wire Contract Layer:**
   - Add new optional fields to JSON/Protobuf/GraphQL responses while keeping all legacy fields populated.
   - Accept both legacy and new fields in incoming request payloads.

### 3. Design Phase 2: MIGRATE (Backfill, Validate & Cutover Reads)
1. **Out-of-Band Batched Backfill:**
   - Run an idempotent background worker that iterates over primary key ranges (`WHERE id > :last_id ORDER BY id ASC LIMIT 1000`).
   - Update only rows where the new column is still `NULL` or out-of-sync.
   - Pause `50ms–200ms` between batches and monitor replica lag (`pg_stat_replication` / `Seconds_Behind_Master`).
2. **Constraint Validation & Parity Check:**
   - Verify 0 unmigrated rows remain.
   - Run `ALTER TABLE ... VALIDATE CONSTRAINT ...` (acquires only `SHARE UPDATE EXCLUSIVE`, allowing reads and writes to continue).
   - Compare checksums or shadow-read metrics between legacy and new columns.
3. **Application Layer (Dual-Write, New-Read):**
   - Switch application read paths to consume the new column/table.
   - Keep dual-writing to the legacy column so that an emergency binary rollback to Phase 1 code sees up-to-date data in the legacy column.

### 4. Design Phase 3: CONTRACT (Retire Legacy Artifacts)
1. **Drain Verification:**
   - Confirm 0% of running pods are on Version $N-1$.
   - For API fields, confirm access telemetry shows zero requests relying on the deprecated field across the required client horizon.
2. **Application Layer (Single-Write, New-Read):**
   - Deploy code that stops writing to or referencing the legacy column/table.
   - If the database column still has a `NOT NULL` constraint, drop the `NOT NULL` constraint *before* deploying code that stops writing to it!
3. **Database & Wire Cleanup:**
   - Execute `ALTER TABLE ... DROP COLUMN ...` with `SET LOCAL lock_timeout = '2s'`.
   - In Protobuf schemas, remove the field definition and immediately add `reserved <tag>; reserved "<field_name>";`.

### 5. Generate Migration Record & Audit
Save the 3-phase design to `migration-record.json` and verify structural compliance before executing Phase 1:
```bash
python3 scripts/migration_guard.py audit <record.json> --json
```
Only proceed when the audit passes with `action: "proceed"`.
