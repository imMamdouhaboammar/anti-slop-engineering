# Reference: Empirical Measurement, Micro-Benchmarking & `EXPLAIN (ANALYZE, BUFFERS)`

Performance engineering without pre-change and post-change empirical numbers is superstition. Every performance hypothesis must be tested against physical telemetry.

---

## 1. PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` Diagnostic Matrix

Always execute `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)` (inside `BEGIN; ... ROLLBACK;` for mutating queries) to inspect actual runtime behavior rather than planner estimates.

| Plan Signal | Physical Meaning | Mechanical Sympathy Fix |
| --- | --- | --- |
| `Seq Scan on invoices` + `Rows Removed by Filter: 480000` | Engine reads every 8KB heap page from shared buffers/disk and discards 99% of rows on CPU | Add a composite B-Tree index ordered by Equality, Sort, Range (ESR) or a partial index (`WHERE archived_at IS NULL`) |
| `Index Scan` with `Heap Fetches: 95000` + high `Shared Read Blocks` | Index narrows row TIDs, but random heap page hops fetch non-indexed columns or check visibility map | Add `INCLUDE (col1, col2)` to create a covering index (`Index Only Scan`) and ensure `VACUUM` keeps the Visibility Map fresh |
| `Sort Method: external merge Disk: 64200kB` | `ORDER BY` spilled out of `work_mem` onto temporary disk files | Extend the composite B-Tree index to match the `ORDER BY` direction so rows stream pre-sorted without a `Sort` node |
| `Nested Loop` with `loops=2500` on inner remote/disk scan | Query planner underestimated outer row count (`rows=1` planned vs `rows=2500` actual) | Run `ANALYZE table`, create extended multi-column statistics (`CREATE STATISTICS`), or rewrite correlated subqueries as hash/batch joins |
| `Shared Read Blocks: 42000` ($42000 \times 8\text{KB} \approx 336\text{MB}$) | Query pulls 336MB from OS cache/NVMe per execution due to wide row bloat or missing predicate pushdown | Project only required columns (never `SELECT *` on wide JSONB/TEXT columns), partition by tenant/time, and cover hot predicates |

---

## 2. Reproducible Micro-Benchmarking (Latency & Allocations)

A valid application micro-benchmark must measure **both time distribution (`P50`, `P95`, `P99`) and memory allocation volume (`bytes/op`, `allocs/op`)**. Average (`mean`) latency alone hides GC spikes.

### TypeScript / Bun / Node Allocation & P99 Harness

```typescript
export interface BenchmarkMetrics {
  readonly iterations: number;
  readonly p50Ms: number;
  readonly p99Ms: number;
  readonly allocBytesPerOp: number;
}

export function runAllocationBenchmark(
  fn: () => unknown,
  warmupIterations = 100,
  sampleIterations = 500
): BenchmarkMetrics {
  for (let i = 0; i < warmupIterations; i++) {
    fn();
  }

  const samplesMs = new Float64Array(sampleIterations);
  const heapBefore = process.memoryUsage().heapUsed;

  for (let i = 0; i < sampleIterations; i++) {
    const startNs = Bun.nanoseconds();
    fn();
    const elapsedNs = Bun.nanoseconds() - startNs;
    samplesMs[i] = elapsedNs / 1_000_000;
  }

  const heapAfter = process.memoryUsage().heapUsed;
  samplesMs.sort();

  const p50Index = Math.floor(sampleIterations * 0.5);
  const p99Index = Math.floor(sampleIterations * 0.99);
  const netBytes = Math.max(0, heapAfter - heapBefore);

  return {
    iterations: sampleIterations,
    p50Ms: Number(samplesMs[p50Index].toFixed(4)),
    p99Ms: Number(samplesMs[p99Index].toFixed(4)),
    allocBytesPerOp: Math.round(netBytes / sampleIterations),
  };
}
```

### Go Native Allocation & Latency Benchmark (`testing.B`)

```bash
go test -bench=BenchmarkHotPath -benchmem -count=5 ./...
```
Look directly at `ns/op`, `B/op` (`alloc_bytes_per_op`), and `allocs/op`. Every reduction in `allocs/op` directly lowers Go GC mark/assist overhead at P99.

---

## 3. The Revert-on-Noise Rule

1. Capture at least 5 runs or 500 sample iterations.
2. Require a meaningful, falsifiable improvement on the bounding metric:
   - $\ge 15\%$ reduction in `P99` latency, OR
   - $\ge 25\%$ reduction in `alloc_bytes_per_op` / `Shared Read + Hit Buffers`, OR
   - Elimination of $O(N)$ network roundtrips / $O(N)$ RAM growth.
3. If the delta is $< 3\%$ and within run-to-run jitter, **reject the optimization and keep the simpler baseline code**.
