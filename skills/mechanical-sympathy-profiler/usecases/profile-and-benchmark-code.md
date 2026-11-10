# Workflow: Profile & Benchmark Code (Allocations & P99 Tail Latency)

Use this workflow when asked to optimize CPU-bound functions, data transformation loops, parsers, serializers, or in-memory hot paths.

## Step-by-Step Procedure

### 1. Capture Baseline Micro-Benchmark Before Editing
1. Build a deterministic benchmark harness over a realistic dataset cardinality (e.g., $N = 10,000$ items, not $N = 3$).
2. Include at least 50 warmup iterations so the JIT compiler (V8/Java/PyPy) stabilizes before recording timers.
3. Measure and record:
   - **`P50` and `P99` execution latency** (`ms` or `µs`).
   - **Heap allocation rate** (`alloc_bytes_per_op` and `allocs_per_op`).
   - **Throughput** (`ops/sec`).

### 2. Classify the Physical Bottleneck
1. **Algorithmic Complexity ($O(N^2)$):** Look for nested `.find()`, `.includes()`, `.indexOf()`, or repeated object-key scans inside loops.
2. **GC / Allocation Churn:** Look for `.map().filter().reduce()` chains creating multiple intermediate arrays, `{ ...acc, [k]: v }` spread copies in loops, `JSON.parse(JSON.stringify())`, or per-iteration closure allocations.
3. **Cache Locality & Boxing:** Look for scattered pointer-chasing objects where contiguous `TypedArray` (`Float64Array`, `Uint32Array`, `Uint8Array`) or flat struct arrays fit in L1/L2 CPU cache lines (`64 bytes`).

### 3. Apply Mechanical Sympathy Transformations
1. **Replace $O(N^2)$ Scans with $O(1)$ Index Lookup:** Pre-index the lookup collection once into a `Map` or `Set` outside the hot loop.
2. **Single-Pass Zero-Allocation Loop:** Collapse `.filter().map().reduce()` chains into a single `for` loop with pre-allocated output capacity (`new Array(count)` or `with_capacity`).
3. **Hoist Loop Invariants:** Move `new RegExp()`, `new Intl.DateTimeFormat()`, `TextEncoder`, and schema validators outside the loop.

### 4. Verify Post-Change Delta & Enforce Revert-on-Noise
1. Run the exact same benchmark harness against the modified implementation.
2. Compare `P50`, `P99`, `alloc_bytes_per_op`, and `allocs_per_op` side-by-side.
3. If `P99` latency or allocation volume does not improve by at least `15%` (or if the change only shifts noise within variance while increasing code complexity), **revert the edit**.
