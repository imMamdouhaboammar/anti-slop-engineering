# Flamegraphs & Empirical Benchmarking Discipline

## 1. The Empirical Measurement Law

Never optimize in the dark. AI agents and developers routinely introduce "optimizations" that add cognitive complexity, memory leaks, and stale-data caching bugs while failing to improve runtime latency or throughput.

### Absolute Grounding Invariant
Every performance optimization PR or commit must be backed by:
1. **Baseline Measurement:** Hard numbers before any code change.
2. **Post-Change Measurement:** Identical test workload and harness executed after the change.
3. **Flamegraph or Trace Artifact:** SVG or JSON profile proving where CPU cycles or heap allocations were spent.

---

## 2. Generating & Reading Flamegraphs

A Flamegraph represents call stacks on the vertical axis and execution time or memory allocation on the horizontal axis. Wide plateaus indicate functions consuming excessive CPU cycles or allocations.

### CPU Profiling Commands by Platform
- **Node.js:**
  ```bash
  node --prof app.js
  node --prof-process isolate-0x*.log > processed.txt
  # Or with 0x:
  npx 0x app.js
  ```
- **Bun:**
  ```bash
  bun test --profile tests/perf/hot_loop.bench.ts
  ```
- **Go:**
  ```bash
  go test -bench=. -cpuprofile=cpu.pprof -memprofile=mem.pprof
  go tool pprof -http=:8080 cpu.pprof
  ```
- **Rust:**
  ```bash
  cargo flamegraph --bin my_service
  ```
- **Chromium / WebKit:**
  Open DevTools -> Performance Panel -> Record trace -> Inspect CPU Top-Down Tree and Flame Chart.

---

## 3. Database Execution Profiling: EXPLAIN (ANALYZE, BUFFERS)

In SQL databases (PostgreSQL), `EXPLAIN` alone is only a planner estimate. Always execute `EXPLAIN (ANALYZE, BUFFERS)`.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, amount, created_at
FROM transactions
WHERE tenant_id = 'ten_123' AND created_at >= NOW() - INTERVAL '7 days';
```

### Key Metrics to Audit
- **Buffers:**
  - `shared hit`: 8KB data blocks already present in PostgreSQL shared buffer memory (fast).
  - `shared read`: 8KB data blocks that had to be read from disk / OS page cache (slow).
  - `shared dirtied` / `shared written`: modifications written to buffer cache or disk.
- **Scan Types:**
  - `Seq Scan` on a table with > 10,000 rows indicates a missing or unselected index.
  - `Index Scan` vs `Index Only Scan`: an `Index Only Scan` avoids heap fetches entirely, providing the fastest query path.
- **Rows Removed by Filter:** High numbers indicate poor index selectivity or wrong column ordering in composite indexes.

---

## 4. Benchmark Harness Discipline & The Revert-on-Noise Gate

### Harness Guidelines
1. **Warmup Phase:** Run at least 1,000 iterations to allow the JIT compiler (V8 TurboFan, JSC FTL) to optimize bytecode and stabilize CPU branch predictors.
2. **Measure Tail Latency:** Never rely on averages. Measure **P50**, **P90**, **P99**, and **P99.9**.
3. **Measure Memory Allocations:** Capture `alloc_bytes/op` and `allocs/op` alongside latency.

### The Revert-on-Noise Gate
If the post-change measurement fails to achieve:
- **$\ge 15\%$ reduction in P99 latency**, OR
- **Strict reduction in heap allocations (`alloc_bytes/op`)**, OR
- **Achievement of the 120Hz frame budget ($\le 8.33\text{ms}$)**

...while adding code complexity or stateful caching, **the change must be reverted immediately**. Speculative caching and complex micro-optimizations that deliver negligible improvements are slop.
