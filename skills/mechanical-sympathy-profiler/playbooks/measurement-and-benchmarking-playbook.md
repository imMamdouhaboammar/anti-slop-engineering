# Playbook 1: Empirical Measurement, Micro-Benchmarking & `EXPLAIN (ANALYZE, BUFFERS)`

> "In God we trust; all others must bring `EXPLAIN (ANALYZE, BUFFERS)` and `P99` allocation profiles."

## 1. The Anti-Guessing Mandate

AI coding agents and hurried engineers routinely commit the **Blind Optimization Fallacy**:
- Adding Redis or an in-memory `Map` cache in front of a slow endpoint without checking why the query took `450ms`—introducing cache coherency bugs, cold-cache stampedes, and memory leaks while leaving the broken query intact.
- Wrapping React values in `useMemo` and functions in `useCallback` where closure allocation and dependency comparison cost more than the computation itself.
- Creating single-column database indexes that the query planner ignores because the query filters on `(tenant_id, status)` and sorts by `created_at DESC`.

### The Iron Rule of Systems Performance
Every performance task has two mandatory artifacts:
1. **Baseline Telemetry Artifact:** Captured on the unmodified code before any optimization edit.
2. **Post-Change Telemetry Artifact:** Captured using the exact same workload, cardinality, and harness after the edit.

---

## 2. Database Profiling Protocol (`EXPLAIN (ANALYZE, BUFFERS)`)

### Step 1: Capture the Physical Plan
Run `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)` on a realistic dataset cardinality. Never rely on bare `EXPLAIN` (which only prints the planner's statistical guess without executing the query or touching buffers).

```sql
BEGIN;
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, customer_id, total_cents, created_at
FROM ledger_entries
WHERE tenant_id = '7f9c2a10-3b44-4d1a-9c01-88a12b34c567'
  AND status = 'SETTLED'
  AND created_at >= '2026-01-01T00:00:00Z'
ORDER BY created_at DESC
LIMIT 50;
ROLLBACK;
```

### Step 2: Read the Four Physical Signals
1. **`Buffers: shared hit=X read=Y`**:
   - Every block in PostgreSQL is `8KB`. If a query returning 50 rows touches `shared hit=18400 read=6200` (`24,600` blocks $\times 8\text{KB} \approx 196.8\text{MB}$), the database is reading nearly `200MB` of memory/disk pages to return `4KB` of payload.
2. **`Rows Removed by Filter: N`**:
   - High numbers indicate the index predicate did not cover the `WHERE` clause, forcing the engine to fetch heap tuples and discard them on CPU.
3. **`Heap Fetches: N` inside an `Index Only Scan`**:
   - Indicates that table pages are not marked all-visible in the Visibility Map (`VACUUM` needed) or non-indexed columns forced an `Index Scan` instead of a covering `Index Only Scan`.
4. **`Sort Method: external merge Disk: NkB`**:
   - The index order did not match the `ORDER BY` clause, forcing an expensive sort that spilled to disk.

### Step 3: Apply the ESR Composite Index Discipline
Design composite B-Tree indexes strictly in **ESR Order**:
1. **E — Equality columns first:** `tenant_id, status` (narrows the B-Tree search space to a single contiguous key prefix).
2. **S — Sort columns next:** `created_at DESC` (delivers tuples in exact `ORDER BY` sequence so `LIMIT 50` stops after reading 50 index entries with zero sort step).
3. **R — Range columns last:** (if distinct from sort) and **`INCLUDE (customer_id, total_cents)`** to satisfy the projection purely from the index leaf pages (`Heap Fetches: 0`).

```sql
CREATE INDEX CONCURRENTLY idx_ledger_entries_tenant_status_created_cov
ON ledger_entries (tenant_id, status, created_at DESC)
INCLUDE (customer_id, total_cents);
```

---

## 3. Application Micro-Benchmarking Protocol (`P50`, `P99` & `Alloc Bytes/Op`)

### Why Mean Latency Lies
If 99 requests take `1ms` and the 100th request triggers a `150ms` Major GC stop-the-world pause because the previous 99 requests allocated `50MB` of short-lived objects each, the average latency is `2.49ms`—looking deceptively healthy while `P99` is `150ms`.

### Mandatory Benchmark Dimensions
Every application micro-benchmark must record:
1. **`p50_ms`**: Median execution latency after JIT warmup.
2. **`p99_ms`**: 99th-percentile tail latency capturing allocator/GC stalls.
3. **`alloc_bytes_per_op`**: Net heap bytes allocated per operation.
4. **`allocs_per_op`**: Count of distinct heap allocations per operation.
5. **`io_roundtrips_per_request`**: Count of network/DB/IPC roundtrips per request.

---

## 4. The Revert-on-Noise Gate

Before finalizing any optimization:
- Compare `post_change_measurement` against `baseline_measurement`.
- If `post_change.p99_ms >= baseline.p99_ms` AND `post_change.alloc_bytes_per_op >= baseline.alloc_bytes_per_op` AND `post_change.io_roundtrips_per_request >= baseline.io_roundtrips_per_request`, the optimization **failed**.
- Even if a metric improved by `1%–2%`, if the code became harder to read or maintain, **revert the change**. Complexity must buy at least a `15%+` verified reduction in latency, allocations, or I/O buffers.
