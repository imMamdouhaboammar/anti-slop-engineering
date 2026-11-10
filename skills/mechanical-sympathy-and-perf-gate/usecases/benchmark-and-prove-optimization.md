# Benchmark & Prove Optimization (The Empirical Measurement Gate)

Use this workflow when evaluating or proposing any performance refactoring, SQL query tuning, caching addition, or algorithmic optimization.

## Step-by-Step Procedure

### 1. Reject "Trust-Me" Speculative Caching Upfront
If a PR or task proposes adding Redis, `useMemo`, `useCallback`, in-memory TTL maps, or multi-column database indexes without recorded baseline telemetry:
1. **Stop immediately.** Do not approve or implement.
2. Demand baseline measurements: why is the path slow? Is it $O(N^2)$ algorithmics, missing index, serial loop I/O, or CPU cache misses?
3. Enforce the rule: fix the underlying physics before considering a cache layer.

### 2. Capture Baseline Telemetry & Artifact
1. Run a microbenchmark or database profiler on the unchanged code:
   - For backend/compute paths: Record P50, P90, P99 latency (`ms`), throughput (`ops/sec`), and heap allocations (`alloc_bytes/op`, `allocs/op`).
   - For database queries: Execute `EXPLAIN (ANALYZE, BUFFERS)` and record execution time, `shared hit` vs `shared read` blocks, and scan types.
   - For UI interactions: Record a Chrome/WebKit Performance Trace and capture frame drop percentage and Main Thread script execution time.
2. Save the flamegraph SVG, trace JSON, or benchmark output file in the artifacts directory.

### 3. Implement the Sympathetic Code Change
1. Apply Data-Oriented Design, zero-allocation hot paths, bounded streaming, or batched I/O.
2. Keep the change minimal, focused, and reviewable.

### 4. Capture Post-Change Telemetry Under Identical Conditions
1. Re-run the exact same benchmark harness, dataset cardinality, and load profile.
2. Record post-change P50, P99, allocations, and throughput.

### 5. Evaluate Against the Revert-on-Noise Gate
Compare baseline vs post-change metrics:
- **Pass Criteria:**
  - P99 latency reduction $\ge 15\%$, OR
  - Strict reduction in heap allocations (`alloc_bytes/op`), OR
  - Strict reduction in database buffer reads / network roundtrips, OR
  - Frame delivery meets 120Hz budget ($\le 8.33\text{ms}$).
- **Fail / Revert Criteria:**
  - If P99 latency regresses, OR
  - If improvement is within measurement noise ($< 15\%$) while adding code complexity or stateful caching: **REVERT THE CHANGE**.

### 6. Generate Perf Record & Audit
Write the results into `perf-record.json` and verify with:
```bash
python3 scripts/perf_guard.py audit <record.json> --json
```
