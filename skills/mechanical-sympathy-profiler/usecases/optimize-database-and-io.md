# Workflow: Optimize Database Queries & Batch Network I/O

Use this workflow when optimizing slow API endpoints, fixing database bottlenecks, designing indexes, or eliminating N+1 query patterns.

## Step-by-Step Procedure

### 1. Capture Baseline `EXPLAIN (ANALYZE, BUFFERS)` & Roundtrip Count
1. Never add an index or rewrite a query from intuition. Execute `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)` on the target query against representative data volume.
2. Record from the physical execution plan:
   - **Execution Time (`ms`)** and **Planning Time (`ms`)**.
   - **Scan Node Type:** `Seq Scan`, `Bitmap Heap Scan`, `Index Scan`, or `Index Only Scan`.
   - **Buffer Telemetry:** `Shared Hit Blocks` (in-memory cache) vs `Shared Read Blocks` (physical disk/OS page reads) and `Rows Removed by Filter`.
   - **Application I/O Roundtrips:** Count total SQL queries, Redis commands, and HTTP calls executed per request.

### 2. Collapse Network-in-a-Loop via Batching & Pipelining
1. Search the request handler and service layer for `for` / `while` / `for...of` loops containing `await db.query`, `await prisma.*`, `await redis.*`, or `await fetch`.
2. **Batch Reads:** Replace $N$ point `SELECT` queries with a single parameterized bulk query (`WHERE id = ANY($1::uuid[])`) or DataLoader batch function.
3. **Batch Writes:** Replace $N$ single-row `INSERT` or `UPDATE` statements with a single `UNNEST($1::uuid[], $2::bigint[])` statement or multi-row `VALUES` batch.
4. **Pipeline Cache Operations:** Replace sequential `await redis.get(k)` calls with `redis.mget(...keys)` or a single `redis.pipeline().get(k1).get(k2).exec()` roundtrip.

### 3. Design Indexes by the ESR Rule (Not Guesswork)
1. Order composite B-Tree index columns strictly by **Equality, Sort, Range (ESR)**:
   - **Equality** predicates first (`WHERE tenant_id = $1 AND status = $2`).
   - **Sort** columns second (`ORDER BY created_at DESC`) to eliminate in-memory or disk `Sort` nodes.
   - **Range** predicates last (`AND amount_cents > 1000`).
2. Add `INCLUDE (col1, col2)` covering columns when `EXPLAIN (ANALYZE, BUFFERS)` shows high `Heap Fetches` on a hot query, turning an `Index Scan` into a zero-heap `Index Only Scan`.
3. Create indexes online (`CREATE INDEX CONCURRENTLY`) to avoid table write locks.

### 4. Verify Post-Change `EXPLAIN (ANALYZE, BUFFERS)` Plan
1. Re-run `EXPLAIN (ANALYZE, BUFFERS)` after applying the query/index or batching change.
2. Confirm that `Seq Scan` / `Rows Removed by Filter` dropped, `Shared Read + Hit` buffers decreased, total network roundtrips collapsed from $O(N)$ to $O(1)$, and execution time improved measurably.
