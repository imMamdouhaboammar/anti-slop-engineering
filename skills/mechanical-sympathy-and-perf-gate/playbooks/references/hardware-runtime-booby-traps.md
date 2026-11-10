# Hardware & Runtime Booby-Trap Catalog

This catalog documents the concrete failure mechanics, detection signatures, and production-grade code remedies for hardware and runtime performance hazards.

---

## 1. Data-Oriented Design & Cache Physics (`PERF-DOD-*`)

### `PERF-DOD-001`: Pointer Chasing in Hot Numerical Loops
- **Hazard:** Storing numerical collections as an Array of Objects (`[{ x, y, vx, vy }]`). Each object is allocated independently on the heap. When iterating over 1,000,000 items, the CPU cache line (64 bytes) is filled with irrelevant object headers, and DRAM pointer dereferences stall execution for ~70ns per item.
- **Remedy:** Migrate to Struct of Arrays (SoA) using contiguous `Float64Array` or `Float32Array`.
  ```typescript
  // Hardened SoA Buffer
  class ParticlesSoA {
    public x: Float32Array;
    public y: Float32Array;
    constructor(capacity: number) {
      const buffer = new ArrayBuffer(capacity * 4 * 2);
      this.x = new Float32Array(buffer, 0, capacity);
      this.y = new Float32Array(buffer, capacity * 4, capacity);
    }
  }
  ```

### `PERF-DOD-002`: Hot-Path Heap Allocation Churn
- **Hazard:** Creating closures, intermediate arrays via `.map().filter()`, or spreading objects `{ ...acc, [k]: v }` inside tight loops. Allocates tens of megabytes of short-lived objects per second, triggering frequent Garbage Collector minor/major pauses that spike P99 latency.
- **Remedy:** Pre-size arrays, mutate accumulators in-place, hoist regex/formatter instances, and use single-pass `for` loops.

### `PERF-DOD-003`: Quadratic Nested Scans ($O(N^2)$)
- **Hazard:** Calling `array.find()`, `array.includes()`, or `array.indexOf()` inside a `.map()`, `.filter()`, or `for` loop over dynamic collections.
- **Remedy:** Build an $O(1)$ `Map` or `Set` lookup table outside the loop before iteration.

---

## 2. Client Runtime & Frame Budgets (`PERF-FRAME-*`)

### `PERF-FRAME-001`: Forced Synchronous Layout Thrashing
- **Hazard:** Writing to DOM style properties and immediately querying geometric dimensions (`offsetWidth`, `getBoundingClientRect()`). The browser is forced to pause execution and calculate a full document reflow synchronously.
- **Remedy:** FastDOM two-phase separation: execute all geometric reads in Phase 1; batch all style mutations in Phase 2 via `requestAnimationFrame`.

### `PERF-FRAME-002`: Non-Compositor Transitions & `transition: all`
- **Hazard:** Using `transition: all` or animating layout properties (`height`, `top`, `left`, `margin`, `padding`). Every animation tick invalidates the document layout tree and triggers GPU paint storms, dropping frames below 120Hz/60Hz.
- **Remedy:** Ban `transition: all`. Animate strictly GPU compositor properties (`transform`, `opacity`). Use the FLIP technique for positional layout changes.

### `PERF-FRAME-003`: Main-Thread Synchronous Storage I/O
- **Hazard:** Calling `localStorage.setItem(key, JSON.stringify(bigState))` synchronously inside user interaction, scroll, or input paths. Blocks the JavaScript main thread for 20ms - 80ms, generating browser Long Tasks.
- **Remedy:** Offload persistence to asynchronous IndexedDB or debounce storage writes outside animation frames.

### `PERF-FRAME-004`: Unterminated `requestAnimationFrame` Loops
- **Hazard:** Continuous `requestAnimationFrame` loops that keep scheduling frames long after animation targets have visually stabilized, wasting mobile battery and holding CPU cores at high power states.
- **Remedy:** Add an epsilon convergence check ($\epsilon = 10^{-4}$) and explicitly call `cancelAnimationFrame(handle)`.

---

## 3. Zero-Copy & Streaming Architecture (`PERF-STREAM-*`)

### `PERF-STREAM-001`: Whole-Payload Synchronous RAM Buffering
- **Hazard:** Calling `fs.readFileSync`, `fs.promises.readFile`, `response.text()`, or `response.arrayBuffer()` on multi-megabyte/gigabyte payloads. Incurs $O(N)$ RSS memory consumption, leading to process crashes via OOM.
- **Remedy:** Mandate bounded-chunk streaming (`ReadableStream`, `stream.pipeline`) with explicit `highWaterMark` and backpressure.

### `PERF-STREAM-002`: Cloned Buffer Passing Across Thread Boundaries
- **Hazard:** Calling `worker.postMessage({ data: buffer })` without passing a Transfer List. Copies the entire multi-megabyte buffer across heap spaces.
- **Remedy:** Transfer buffer ownership with zero copies: `worker.postMessage({ data: buffer }, [buffer])` or use `ArrayBuffer.transfer()`.

---

## 4. Empirical Benchmarking & Proof (`PERF-BENCH-*`)

### `PERF-BENCH-001`: Speculative "Trust-Me" Caching & Blind Indexing
- **Hazard:** Slapping a Redis cache or React `useMemo` on a slow endpoint without profiling whether the bottleneck is an unindexed table scan, an N+1 query loop, or an $O(N^2)$ algorithmic bug. Masks architectural debt and introduces stale data bugs.
- **Remedy:** Refuse optimization PRs lacking baseline and post-change flamegraphs and `EXPLAIN (ANALYZE, BUFFERS)` execution plans.

### `PERF-BENCH-002`: The Microbenchmark Noise Trap
- **Hazard:** Claiming a 3% or 5% speedup on a single microbenchmark run without JIT warmup, which falls entirely within measurement noise and system jitter.
- **Remedy:** Enforce the Revert-on-Noise Gate: optimizations must prove $\ge 15\%$ P99 latency reduction or a strict decrease in heap allocations or I/O roundtrips under repeated runs.
