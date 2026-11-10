---
name: zero-downtime-migration-gate
description: Enforces Google Spanner and Stripe zero-downtime data and contract evolution discipline across database schemas, API payloads, and rolling deployments. Use when authoring or reviewing SQL migrations (PostgreSQL/MySQL), modifying database columns/constraints/indexes, evolving JSON/Protobuf/GraphQL wire contracts, or orchestrating multi-stage production rollouts — even if the user doesn't explicitly say "zero-downtime migration". Do NOT use for ephemeral local-only test fixtures, greenfield schemas with zero active consumers, or purely cosmetic UI changes.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Zero-Downtime Migration Gate (Google Spanner / Stripe Evolution Discipline)

> Production never stops. Version $N$ and Version $N-1$ coexist in real time—every schema change and wire contract mutation must survive concurrent multi-version traffic with zero table locks and zero dropped requests.

## Why This Skill Is Needed & Target State

AI coding agents routinely generate destructive, single-shot migrations that assume the universe pauses during deployment: renaming a column directly in SQL, adding an index without `CONCURRENTLY`, attaching a `NOT NULL` or `FOREIGN KEY` constraint that acquires an `ACCESS EXCLUSIVE` lock on a 100M-row table, or mutating an API response field while millions of mobile clients and unrefreshed browser tabs are still running Version $N-1$. During a rolling deployment, these shortcuts trigger lock queues, connection pool exhaustion, `Undefined column` crashes, and client deserialization outages.

The target state is **Google Spanner and Stripe evolution discipline**: every schema and wire change is decomposed into isolated **Expand -> Migrate -> Contract** deployment stages, database DDL operations execute without blocking concurrent reads or writes, and all JSON/Protobuf/GraphQL contracts preserve strict forward and backward compatibility across active client horizons.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Authoring or reviewing PostgreSQL / MySQL schema migrations | Enforce lock-free DDL, explicit `lock_timeout`, and 3-phase Expand -> Migrate -> Contract decomposition |
| Renaming, splitting, changing types, or dropping database columns/tables | Prohibit single-step destructive DDL; require dual-write, chunked backfill, dual-read, and delayed drop |
| Adding indexes, foreign keys, check constraints, or `NOT NULL` rules | Mandate `CREATE INDEX CONCURRENTLY` and `NOT VALID` -> `VALIDATE CONSTRAINT` two-step patterns |
| Modifying REST JSON, Protobuf/gRPC, GraphQL, or event queue payloads | Enforce $N$ and $N-1$ wire compatibility, tolerant readers, additive evolution, and date-pinned versioning |
| Greenfield prototype table not yet deployed or local-only unit test fixture | Do not activate; apply standard Anti-Slop Engineering BUILD/FIX gates |

---

## The Five Absolute Laws

1. **The Concurrent Version Coexistence Axiom ($N$ and $N-1$ Invariant):** During any rolling deployment, canary rollout, or mobile app release window, application code Version $N$ and Version $N-1$ execute simultaneously against the exact same database state. Any database migration must be 100% compatible with Version $N-1$ *before* Version $N$ rolls out, and any contract contraction must wait until 0% of active traffic runs Version $N-1$.
2. **The Three-Phase Evolution Law (Expand -> Migrate -> Contract):** Never combine schema expansion, data backfill, application cutover, and legacy column removal into a single deployment or PR. Every breaking change must traverse three physically separate deployment milestones:
   - **Phase 1 (Expand):** Add nullable columns, new tables, or additive optional API fields alongside legacy structures. Begin dual-writing.
   - **Phase 2 (Migrate):** Backfill historical data in throttled, idempotent batches; verify parity; switch reads from legacy to new structures.
   - **Phase 3 (Contract):** Only after all $N-1$ instances and client caches are drained, remove dual-writes and drop legacy columns or fields.
3. **Zero Blocking Table Locks in Production:** Any DDL operation that blocks concurrent `SELECT`, `INSERT`, `UPDATE`, or `DELETE` queries for more than a few milliseconds is a production outage vector. Every migration must bound lock acquisition with a strict `lock_timeout` (e.g. `2s`) so it fails safely rather than queuing behind a long query and freezing the entire table's traffic.
4. **Hyrum's Law & Tolerant Reader / Conservative Writer Discipline:** Assume active clients depend on every existing field name, type, nullability, and enum value. Writers must remain conservative (emitting both legacy and expanded fields during transition), and readers must be tolerant (ignoring unknown fields and providing safe defaults for omitted optional fields).
5. **Decouple DDL from Long-Running Data Backfills:** Never run bulk `UPDATE` statements inside a schema migration transaction. Schema DDL must execute in sub-second metadata operations; data backfills must run out-of-band in bounded batches (`<= 1,000` rows per transaction) with adaptive sleep/jitter to protect replication lag and IOPS.

---

## Invariant Rules

1. **Ban direct `RENAME COLUMN`, `RENAME TABLE`, and in-place `ALTER COLUMN TYPE`.** Renaming or retyping in place immediately breaks running $N-1$ application pods that reference the old identifier or wire type.
2. **Enforce `CREATE INDEX CONCURRENTLY` (PostgreSQL) / `ALGORITHM=INPLACE, LOCK=NONE` (MySQL).** Standard index creation locks writes across the entire table. Note that `CONCURRENTLY` cannot run inside a transaction block (`BEGIN ... COMMIT`); configure migration runners accordingly.
3. **Add constraints as `NOT VALID` first, then `VALIDATE CONSTRAINT`.** Adding a `FOREIGN KEY` or `CHECK` constraint directly scans the entire table under an `ACCESS EXCLUSIVE` lock. Adding it `NOT VALID` enforces it on new writes immediately with a brief metadata lock; `VALIDATE CONSTRAINT` scans existing rows afterward under a non-blocking `SHARE UPDATE EXCLUSIVE` lock.
4. **Safe `NOT NULL` enforcement via Check Constraints (PostgreSQL 12+).** Never run `ALTER TABLE ... ALTER COLUMN ... SET NOT NULL` directly on an unvalidated large table. First add `CHECK (col IS NOT NULL) NOT VALID`, run `VALIDATE CONSTRAINT`, and only then set `NOT NULL` (which PostgreSQL completes instantaneously by recognizing the validated check constraint).
5. **New columns added while $N-1$ is live must be nullable or carry a non-volatile server default.** If $N-1$ inserts rows without knowing about the new column, a strict `NOT NULL` column without a default will crash every $N-1$ `INSERT`.
6. **Prepend explicit `lock_timeout` and `statement_timeout` to every DDL script.** Prevent lock-queue amplification (where a brief `ALTER TABLE` waits behind an analytical query and blocks all subsequent OLTP traffic behind it).
7. **Protobuf & gRPC wire permanence.** Never reuse a deleted Protobuf field number or field name; always mark removed fields with `reserved <number>; reserved "<name>";`. Never change the wire type of an existing tag.
8. **JSON & GraphQL additive evolution.** Never remove, rename, or tighten the nullability of an existing JSON response property or GraphQL field in place. Add the new field, mark the old field `@deprecated(reason: "...")`, monitor usage to zero, or gate structural shifts behind Stripe-style date-pinned API version headers (`Stripe-Version: 2026-11-10`).
9. **Enum expansion safety.** Adding a new response enum variant breaks strict client switch statements in mobile/frontend apps ($N-1$). Either map new variants to an existing fallback for $N-1$ callers, require clients to implement an `UNKNOWN` catch-all branch, or gate new enum variants behind an explicit client version capability.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Planning a schema or contract evolution across deployments | [Plan 3-Phase Evolution](usecases/plan-evolution.md) | [Expand-Migrate-Contract](references/expand-migrate-contract.md) |
| Authoring lock-free SQL migrations & batched backfills | [Author Safe Migration](usecases/author-migration.md) | [Lock-Free SQL Patterns](references/lock-free-sql-patterns.md) |
| Auditing PR diffs, SQL files, or API schemas for downtime hazards | [Review Migration & Contracts](usecases/review-migration.md) | [Wire Compatibility Matrix](references/wire-compatibility-matrix.md) |
| Durable migration assessment record generation & audit | [Record Contract](references/migration-record-contract.md) | `scripts/migration_guard.py` |

---

## Mandatory Pre-Migration Interrogation Matrix

Before generating or approving any schema migration or API contract change, interrogate the change against these five axes:

- **Coexistence Check ($N-1$ vs $N$):** What happens in the 15-minute window after this SQL migration runs, while 100% of production pods are still running code Version $N-1$? Will `SELECT *`, ORM column mappings, or `INSERT` statements fail?
- **Lock Amplification Check:** What exact lock mode does this statement acquire in PostgreSQL/MySQL? If a 30-second reporting query is running on this table when the migration starts, will the migration queue up and block all incoming production reads and writes?
- **Rollback Survival Check:** If Version $N$ application code panics 5 minutes after deploy and we roll the binary back to Version $N-1$ without rolling back the database, will Version $N-1$ continue operating cleanly?
- **Backfill Blast Radius:** How many rows are affected? If the table has 50M rows, is the data mutation separated from DDL and throttled with primary-key cursor pagination and replication-lag pauses?
- **Client Horizon Check:** Are the consumers internal backend services (minutes to update), browser SPAs (hours/days of open tabs), native iOS/Android apps (months of un-updated builds), or external third-party webhooks (years)?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **`ALTER TABLE ... RENAME COLUMN` or `RENAME TABLE` in a live table** (instantly breaks $N-1$ queries).
2. **`ALTER TABLE ... DROP COLUMN` in the same release that removes code references** (breaks $N-1$ during rollout and prevents binary rollback).
3. **`CREATE INDEX` without `CONCURRENTLY`** on existing populated PostgreSQL tables (blocks all writes for the duration of the index build).
4. **Running `CREATE INDEX CONCURRENTLY` inside a `BEGIN ... COMMIT` transaction block** (rejected by PostgreSQL syntax/runtime).
5. **Adding `FOREIGN KEY` or `CHECK` constraints without `NOT VALID`** (acquires `ACCESS EXCLUSIVE` lock while scanning the entire table).
6. **In-migration bulk `UPDATE table SET col = val` without batching** (bloats MVCC dead tuples, spikes WAL/binlog replication lag, and holds row locks for minutes).
7. **Reusing Protobuf tag numbers or deleting fields without `reserved`** (causes silent wire corruption and type confusion across services).
8. **Changing an existing JSON/GraphQL response field from single value to array (or vice versa) in place** (crashes mobile and frontend JSON parsers).

---

## Required Output & Review Workflow

Structure all migration designs, SQL scripts, and contract reviews through this 3-phase discipline:

1. **Coexistence & Lock Pre-Mortem:** Explicitly list the lock mode acquired by every DDL statement, the behavior of Version $N-1$ against the post-migration schema, and the active client horizon.
2. **Phased Expand -> Migrate -> Contract Implementation:** Emit separated migration artifacts (Phase 1 Expand DDL + Dual-Write, Phase 2 Throttled Backfill + Read Cutover, Phase 3 Contract Cleanup) with explicit `lock_timeout` guards.
3. **Compatibility & Rollback Verification:** Provide verification checks proving Version $N-1$ queries pass against the Phase 1 schema, Protobuf/OpenAPI/GraphQL backward-compatibility rules hold, and binary rollback requires zero emergency down-migrations.

When a durable migration record is warranted, save a JSON assessment following the [Migration Record Contract](references/migration-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering migration audit <record.json> --json
# or: python3 scripts/migration_guard.py audit <record.json> --json
```

---

## Domain References

- **[Migration & Contract Playbook Suite](playbooks/README.md)**: Central orchestration index for zero-downtime database evolution and Stripe-style API versioning.
- **[Google Spanner Zero-Downtime Schema Playbook](playbooks/spanner-schema-evolution-playbook.md)**: Multi-phase DDL choreography, PostgreSQL/MySQL lock matrices, and throttled backfill engines.
- **[Stripe Wire Contract & API Evolution Playbook](playbooks/stripe-contract-evolution-playbook.md)**: Forward/backward compatibility across JSON, Protobuf, and GraphQL, plus date-pinned version transform gates.
- **[Expand -> Migrate -> Contract Architecture](references/expand-migrate-contract.md)**: Detailed state transitions, dual-write/dual-read patterns, and verification gates per phase.
- **[Lock-Free SQL Patterns (PostgreSQL & MySQL)](references/lock-free-sql-patterns.md)**: Copy-pasteable safe DDL recipes vs dangerous lock-inducing equivalents.
- **[Wire Compatibility Matrix](references/wire-compatibility-matrix.md)**: Exhaustive compatibility rules for JSON/REST, Protobuf/gRPC, and GraphQL schemas.
- **[Migration Record Contract](references/migration-record-contract.md)**: JSON schema and verification rules for `scripts/migration_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Lock-queue amplification | Brief `ALTER TABLE` blocks behind a slow read, freezing all table queries | Prepend `SET LOCAL lock_timeout = '2s'` with retry loop |
| Simultaneous cutover crash | `column "old_name" does not exist` errors during rolling deploy | Split into Phase 1 (Add column + dual-write), Phase 2 (Backfill + switch read), Phase 3 (Drop old column) |
| MVCC table bloat & replica stall | Full-table `UPDATE` spikes CPU, disk I/O, and replication lag | Move backfill out of DDL into keyset-paginated batches of 1,000 rows |
| Zombie client crash | Old mobile app or cached SPA crashes on renamed/removed JSON key | Keep legacy field populated via dual-response adapter or version gate until client horizon expires |
| Protobuf tag collision | Deserialization produces corrupted values after field replacement | Mark deleted tags and field names as `reserved` permanently |
| Irreversible deploy panic | Binary rollback fails because migration already dropped a column | Enforce strict rule: Phase 1 & 2 migrations must be 100% backward-compatible with $N-1$ binary |

---

## Delegated Skills

- `paranoid-principal-architect`: Combine with Zero-Trust and 10M-Concurrent-Users rules when designing sharded backfills or idempotent dual-write endpoints.
- `future-scale-gate`: Evaluate long-term schema partitioning and storage engine reversibility before committing to foundational data models.
- `anti-slop-engineering`: Follow BUILD/FIX gates and test integrity standards when writing dual-read/dual-write adapters and contract tests.

---

## Completion and Limits

The task is complete when all breaking schema or wire mutations are decomposed into isolated Expand -> Migrate -> Contract phases, every SQL DDL statement avoids blocking table locks and declares an explicit `lock_timeout`, data backfills are decoupled and batched, and wire compatibility between Version $N$ and Version $N-1$ is verified. A migration review may validly output `refuse` or `pause` if a single-step destructive migration is requested for a live production system.
