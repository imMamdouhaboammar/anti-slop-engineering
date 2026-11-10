---
name: mechanical-sympathy-and-perf-gate
description: Enforces Apple and Google Systems mechanical sympathy, hardware-level cache/memory efficiency, 120Hz (8.3ms) frame budgets, bounded streaming, and empirical benchmark/flamegraph gates. Use when asked to speed up slow code, optimize CPU cache locality, fix 120Hz/60Hz UI frame drops or main-thread jank, eliminate heap allocations in hot loops, prevent OOMs by streaming large payloads, or validate performance optimizations with flamegraphs and benchmarks — even if the user doesn't explicitly say "mechanical sympathy" or "perf gate". Do NOT use for routine CSS color/styling tweaks, static documentation typos, or non-performance functional bug fixes.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Mechanical Sympathy & Performance Gate (Apple & Google Systems Discipline)

> Never optimize in the dark, never fight the physical limits of the CPU cache or display compositor, and never accept speculative caching over broken algorithmics. Measure baseline reality first.

## Why This Skill Is Needed & Target State

AI coding assistants routinely fall into **Speculative Optimization Slop**: guessing bottlenecks without profiling, wrapping slow $O(N^2)$ lookups or unindexed database queries in Redis caches (introducing cache stampedes and stale-data bugs), peppering React components with cargo-cult `useMemo`/`useCallback` wrappers, and causing severe mobile stutter by animating layout properties (`height`, `top`) while violating the 120Hz frame budget.

The target state is **Apple & Google Systems Mechanical Sympathy**:
1. **Data-Oriented Design (DOD):** Structure memory into contiguous flat buffers (Struct of Arrays) to maximize 64-byte CPU cache line hits, eliminate pointer chasing, and guarantee zero heap allocations in hot loops.
2. **120Hz (8.33ms) / 60Hz (16.67ms) Frame Budgets:** Reserve at least 4.3ms of headroom per frame for layout and compositing by keeping main-thread JavaScript execution under **`4.0ms`**, eliminating forced synchronous layout thrashing (FastDOM reads before writes), and animating strictly GPU compositor properties (`transform`, `opacity`).
3. **Zero-Copy & Streaming Architecture:** Stream multi-megabyte/gigabyte payloads in bounded chunks (e.g. 64KB) with backpressure so peak resident memory remains $O(1)$ without whole-payload RAM buffering (`readFileSync`, `response.text()`).
4. **Empirical Benchmark Proof & Flamegraphs:** Refuse any optimization claim without reproducible before-and-after numbers (P50, P99 latency, heap allocations, throughput, and PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` buffer hits/reads) proving a $\ge 15\%$ P99 latency reduction.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Speeding up backend loops, numerical compute, vector search, or parsers | Enforce Data-Oriented Design (SoA / TypedArrays), 64-byte cache line packing, and zero-allocation hot paths |
| Authoring or auditing UI animations, gestures, scroll handlers, or canvas rendering | Enforce 120Hz (`8.33ms`) frame budget, <4ms main-thread script budget, FastDOM separation, and compositor-only motion |
| Processing files, CSV/NDJSON exports, large DB query results, or file uploads | Mandate bounded-chunk streaming with backpressure ($O(1)$ RSS memory); prohibit whole-payload RAM buffering |
| PR claiming "speed improvements", adding Redis/in-memory caches, or adding database indexes | Demand baseline vs post-change flamegraphs and microbenchmarks; apply the Revert-on-Noise gate ($\ge 15\%$ improvement) |
| Routine UI styling tweaks, copy edits, or non-performance functional bug fixes | Do not activate; route to `anti-slop-engineering` |

---

## The Five Absolute Laws

1. **The Empirical Measurement & Flamegraph Law (Zero Blind Optimization):** Modifying code in the name of performance without recorded baseline and post-change telemetry is strictly prohibited. Capture CPU/Heap flamegraphs, P50/P99 latency, and heap allocations (`alloc_bytes/op`, `allocs/op`). If post-change telemetry fails to demonstrate a $\ge 15\%$ reduction in P99 latency or a strict decrease in heap allocations or buffer reads while adding code complexity, **revert the change**.
2. **The Data-Oriented Design & Cache Locality Law (Spatial Locality Over Pointer Chasing):** CPUs fetch data in 64-byte cache lines. Monolithic object arrays (Array of Structures / AoS) force pointer chasing across DRAM, stalling the pipeline for 100ns per item. Pack hot attributes into contiguous TypedArrays (Struct of Arrays / SoA) to allow hardware prefetchers to stream memory at bus speed.
3. **The Zero-Allocation Hot-Path Law (GC Tail-Latency Elimination):** Every byte allocated in a hot loop must later be traced and swept by the Garbage Collector, causing unpredictable P99 latency spikes. Pre-allocate collections, mutate accumulators in-place, hoist regex/formatter instances, and ban intermediate array chaining (`.map().filter().reduce()`).
4. **The 120Hz (8.33ms) Frame Budget Physics Law:** On 120Hz ProMotion displays, the browser has `8.33ms` per frame. Per-frame JavaScript work on the Main Thread must remain under **`4.0ms`** with zero tasks exceeding `50ms` (Long Tasks). Animate strictly GPU compositor properties (`transform`, `opacity`), eliminate forced synchronous layout thrashing, and offload heavy computation to Web Workers.
5. **The Zero-Copy & Bounded Streaming Law ($O(1)$ Memory Over RAM Buffering):** Loading whole files or large payloads into RAM (`fs.readFileSync`, `await response.text()`, full array materialization) is a fatal defect that causes OOM process termination. Stream data in bounded chunks with backpressure, and transfer buffer ownership without cloning (`ArrayBuffer.transfer()`, Transferable Objects).

---

## Invariant Rules

1. **FastDOM Phase Separation:** Separate geometric layout reads (`getBoundingClientRect()`, `offsetWidth`, `scrollTop`) from style mutations. Perform all reads first, then batch writes in `requestAnimationFrame`.
2. **Ban `transition: all`:** Enumerate explicit compositor properties (`transform`, `opacity`). Never animate layout properties (`width`, `height`, `top`, `left`, `margin`, `padding`).
3. **Inspect PostgreSQL `BUFFERS`, not just cost estimates:** Always run `EXPLAIN (ANALYZE, BUFFERS)` and verify `shared hit` vs `shared read` blocks and scan selectivity.
4. **Single-pass iteration:** Collapse multi-stage array chains (`.filter().map().filter()`) into a single-pass `for` loop with index access.
5. **Pre-index quadratic scans:** Never nest `.find()`, `.includes()`, or `.indexOf()` inside array loops ($O(N^2)$); construct an $O(1)$ `Map` or `Set` before the loop.
6. **Epsilon-terminated `requestAnimationFrame`:** Always terminate continuous animation loops when $|\text{current} - \text{target}| < 10^{-4}$.
7. **Bound stream high-water marks:** Explicitly configure chunk buffer sizes (e.g. 64KB) and wire cancellation (`AbortSignal`) through stream pipelines.
8. **Transferable worker messages:** Pass large `ArrayBuffer` instances in the transfer list (`[buffer]`) to eliminate thread-boundary memory copies.
9. **Eliminate object-spread reducers:** Ban `items.reduce((acc, x) => ({ ...acc, [x.id]: x }), {})` ($O(N^2)$ memory churn) in favor of mutating a `Map` or pre-allocated object.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Designing compute engines, numerical pipelines, or cache-aligned memory | [Design Data-Oriented System](usecases/design-data-oriented-system.md) | [Data-Oriented Design Reference](references/data-oriented-design-and-cache-physics.md) |
| Auditing or fixing 120Hz/60Hz UI frame drops, layout thrashing, or main-thread stalls | [Audit & Eliminate Latency Jank](usecases/audit-and-eliminate-latency-jank.md) | [Frame & Latency Budgets Reference](references/frame-and-latency-budgets-120hz.md) |
| Proving performance optimizations, query tuning, or refactoring hot loops | [Benchmark & Prove Optimization](usecases/benchmark-and-prove-optimization.md) | [Flamegraphs & Benchmarking Reference](references/flamegraphs-and-empirical-benchmarking.md) |
| Durable mechanical sympathy & perf record generation and automated guard audit | [Record Contract](references/perf-record-contract.md) | `scripts/perf_guard.py` |

---

## Mandatory Pre-Optimization Interrogation Matrix

Before modifying a single line of code, adding an index, or introducing a cache, answer these five questions:

- **The Baseline Proof Check:** Where is the baseline flamegraph SVG or benchmark report showing current P50/P99 latency, `alloc_bytes/op`, and throughput? If none exists, stop and measure first.
- **The Memory Locality Check:** Is data packed into contiguous TypedArrays to exploit 64-byte CPU cache lines, or is the CPU pointer-chasing across thousands of individual heap objects?
- **The Hot-Loop Allocation Check:** Does the loop allocate closures, temporary arrays, regexes, or object spreads? How many bytes are allocated per operation?
- **The 120Hz Frame Deadline Check:** For UI code, does JavaScript execution finish in $< 4.0\text{ms}$? Does any DOM read trigger forced synchronous layout reflow after a write?
- **The Bounded Streaming Check:** Does peak memory scale as $O(1)$ via bounded streaming, or does the code buffer entire payloads into RAM?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Unmeasured "Trust-Me" Optimization:** Submitting an optimization refactor, cache layer, or index without before-and-after flamegraph or benchmark numbers.
2. **Whole-File RAM Buffering:** Calling `fs.readFileSync`, `fs.promises.readFile`, `response.text()`, or `response.arrayBuffer()` on unbounded or user-scaled files.
3. **Forced Synchronous Layout Thrashing:** Mutating style properties and subsequently reading geometric dimensions (`offsetHeight`, `getBoundingClientRect()`) within the same frame.
4. **CSS `transition: all`:** Animating layout properties (`height`, `top`, `margin`) instead of GPU compositor properties (`transform`, `opacity`).
5. **Quadratic Lookups in Loops:** Calling `.find()`, `.includes()`, or `.indexOf()` inside array iterations instead of building an $O(1)$ `Map`/`Set`.
6. **Hot-Path Object Spread Reducers:** Using `{ ...acc, [k]: v }` inside `.reduce()` on dynamic collections ($O(N^2)$ heap allocation churn).
7. **Synchronous `localStorage` / `sessionStorage`:** Blocking the main thread with synchronous stringification inside render or scroll paths.

---

## Required Output & Review Workflow

Structure all performance engineering designs, reviews, and implementations through this 4-phase discipline:

1. **Baseline Profiling & Flamegraph:** Capture and report the baseline measurement (flamegraph profile, P50/P99 latency, heap allocations, and buffer reads).
2. **Mechanical Sympathy Design:** Specify the exact hardware/memory transformation (SoA typed buffers, zero-allocation loop, <4ms frame slice, or bounded streaming).
3. **Sympathetic Implementation:** Emit clean, production-grade code adhering to cache locality, backpressure, and compositor physics.
4. **Post-Change Verification & Delta Table:** Re-run the benchmark under identical conditions, present a side-by-side Before vs After Delta Table, and verify with `scripts/perf_guard.py`.

When a durable performance record is warranted, save `perf-record.json` and audit with:
```bash
npx anti-slop-engineering perf audit <record.json> [--source <hot_path.ts>] --json
# or: python3 scripts/perf_guard.py audit <record.json> [--source <hot_path.ts>] --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central orchestration index for Apple and Google Systems mechanical sympathy.
- **[Systems Mechanical Sympathy Playbook](playbooks/mechanical-sympathy-systems-playbook.md)**: DOD memory packing, cache locality, and zero-copy streams.
- **[Client Runtime Frame Budget Playbook](playbooks/client-runtime-frame-budget-playbook.md)**: 120Hz/60Hz frame budgets, FastDOM read/write batching, and FLIP animations.
- **[Hardware & Runtime Booby-Traps](playbooks/references/hardware-runtime-booby-traps.md)**: Catalog of exact failure mechanics and code remedies.
- **[Data-Oriented Design & Cache Physics](references/data-oriented-design-and-cache-physics.md)**: 64-byte cache lines, SoA layouts, and zero-allocation hot paths.
- **[Frame & Latency Budgets (120Hz)](references/frame-and-latency-budgets-120hz.md)**: Compositor pipeline, FastDOM phase separation, and Web Worker offloading.
- **[Zero-Copy & Streaming Architecture](references/zero-copy-and-streaming-architecture.md)**: Bounded streams with backpressure, $O(1)$ RSS, and buffer transfers.
- **[Flamegraphs & Empirical Benchmarking](references/flamegraphs-and-empirical-benchmarking.md)**: Generating flamegraphs, `EXPLAIN BUFFERS`, and the Revert-on-Noise gate.
- **[Perf Record Contract](references/perf-record-contract.md)**: Schema and automated verification rules for `scripts/perf_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| CPU Cache Miss Stalls | High CPU time in loop with low instructions per cycle (IPC) | Migrate from AoS to SoA typed arrays; pack data into 64-byte cache lines |
| GC Tail-Latency Sawtooth | P50 is 2ms but P99 spikes to 180ms during high throughput | Eliminate intermediate `.map().filter()` chains and object spreads; mutate in-place |
| Layout Thrashing Jank | Frame drops (> 8.33ms on 120Hz displays) during scroll or animation | FastDOM phase separation: batch all geometry reads before style writes |
| Whole-Payload OOM Crash | Worker process killed by kernel during large file export | Replace `readFileSync` with bounded Web Streams (`TransformStream`) with backpressure |
| Speculative Caching Slop | Redis cache or `useMemo` added without baseline measurement | Revert cache; profile root algorithmic or query bottleneck with flamegraph |

---

## Delegated Skills

- `anti-slop-engineering`: Enforce clean-room KISS/DRY/YAGNI gates and test integrity.
- `paranoid-principal-architect`: Pair performance optimizations with zero-trust boundary schema parsing, idempotency, and 10M-concurrent-user limits.
- `scientific-fault-isolation`: Isolate whether a latency regression originated from a database lock, a commit, or a runtime upgrade using binary search and differential diagnosis.

---

## Completion and Limits

The task is complete when baseline and post-change measurements prove $\ge 15\%$ P99 latency reduction or strict allocation/buffer reduction, memory is structured for 64-byte CPU cache locality, UI interactions meet the 120Hz (8.33ms) frame deadline with zero layout thrashing, payloads stream in bounded $O(1)$ memory, and `scripts/perf_guard.py` reports zero findings. A review may validly output `refuse` or `pause` if an optimization is proposed without empirical baseline proof or relies on speculative caching over unmeasured bottlenecks.
