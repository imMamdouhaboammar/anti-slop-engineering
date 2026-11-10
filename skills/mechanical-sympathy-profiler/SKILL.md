---
name: mechanical-sympathy-profiler
description: Enforces Meta and Google Systems performance engineering discipline—requiring empirical baseline and post-change measurements and hardware/memory mechanical sympathy before any optimization. Use when asked to speed up code, optimize slow SQL queries, reduce API P99 latency, fix high memory usage or OOMs, eliminate GC pauses, optimize loops, or add caching/memoization/indexes — even if the user doesn't explicitly say "mechanical sympathy" or "profiler". Do NOT use for purely visual CSS restyling, static documentation edits, or functional bug fixes unrelated to performance or resource consumption.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Mechanical Sympathy & Empirical Profiler (Meta / Google Systems Performance School)

> Never guess, never slap on blind caching, and never fight the physics of the CPU cache, memory allocator, or network wire. Measure baseline and post-change reality first.

## Why This Skill Is Needed & Target State

When asked to "speed up" an endpoint, query, or component, AI coding agents routinely fall into **Speculative Optimization Slop**: guessing the bottleneck, sprinkling `useMemo`/`useCallback` across components, wrapping slow $O(N^2)$ functions or N+1 queries in Redis/in-memory caches (introducing stale-data bugs and cache stampedes), or adding unverified database indexes that slow down writes without covering the query predicate. The code grows twice as complex while P99 latency and memory pressure remain broken.

The target state is **Meta & Google Systems Mechanical Sympathy**:
1. **Zero Optimization Without Baseline & Post-Change Proof:** Every optimization begins with an empirical measurement—`EXPLAIN (ANALYZE, BUFFERS)` for queries, or a reproducible micro-benchmark capturing **Heap Allocations (`bytes/op`, `allocs/op`)** and **Tail Latency (`P50`, `P95`, `P99`)**—and ends with an identical post-change measurement proving the delta.
2. **Hardware, Memory Hierarchy & GC Sympathy:** Stream payloads in bounded chunks (`O(1)` RSS) instead of buffering whole files/datasets in RAM; eliminate transient heap allocations and intermediate array churn inside hot paths to keep the Garbage Collector silent.
3. **I/O Batching & Pipelining Over Loop Roundtrips:** Collapse sequential network/DB queries inside loops (`O(N)` RTTs) into batched single-roundtrip operations (`UNNEST`, `ANY($1)`, `MGET`, pipelining, multiplexed streams).

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Optimizing a slow SQL query, ORM call, or proposing a new database index | Require `EXPLAIN (ANALYZE, BUFFERS)` baseline and post-change execution plans proving buffer-read and latency reduction |
| Speeding up a backend route, worker, loop, parser, or hot computation | Require a before/after micro-benchmark measuring `P50`/`P99` latency and heap allocations (`bytes/op`, `allocs/op`) |
| Processing files, CSV/JSON exports, large DB result sets, or media uploads | Enforce bounded-chunk streaming with backpressure (`O(1)` memory) instead of full-payload RAM buffering |
| Executing database, Redis, or HTTP calls across a collection of items | Ban `await` I/O inside loops; coalesce into bulk queries, pipelines, or bounded batch loaders |
| Request to "add caching", "add Redis", or "wrap in `useMemo`" to fix slowness | Pause and profile the underlying algorithmic complexity ($O(N^2)$) or I/O pattern first; fix the root physics before considering a cache |
| Pure UI color/spacing tweaks, copy edits, or non-performance functional bugs | Do not activate; route to `anti-slop-engineering` or `scientific-fault-isolation` |

---

## The Five Absolute Laws

1. **The Empirical Measurement Law (Zero Blind Optimization):** You are strictly prohibited from modifying code or schemas in the name of performance without capturing a baseline measurement first and a post-change measurement after.
   - **Database & Query Path:** Run or specify `EXPLAIN (ANALYZE, BUFFERS)` (or the storage engine's physical plan profiler) and record actual execution time (`ms`), `Shared Hit Blocks` vs `Shared Read Blocks`, scan type (`Seq Scan` vs `Index Scan` / `Index Only Scan`), and heap fetches before and after.
   - **Application & Compute Path:** Run a deterministic micro-benchmark or profiler trace recording **`P50` / `P99` latency**, **throughput (`ops/sec`)**, and **memory allocations (`bytes/op`, `allocs/op`)** before and after.
   - **Revert-on-Noise Gate:** If the post-change measurement fails to improve the bottleneck metric beyond measurement noise ($\ge 15\%$ reduction in P99 latency, allocations, or buffer reads) while adding complexity, **revert the change**.
2. **The Memory Hierarchy & Streaming Law (`O(1)` Working Set Over RAM Buffering):** Respect the physical capacity and bandwidth of RAM.
   - Never load whole files, multi-megabyte JSON/CSV exports, or unbounded SQL result sets into contiguous heap memory (`fs.readFileSync`, `await response.text()` on large payloads, unbounded `SELECT *`).
   - Use **Streaming with Backpressure** (Web `ReadableStream` / `TransformStream`, Node `stream.pipeline`, Go `io.Copy` / `bufio.Scanner`, Rust `BufReader`, PostgreSQL server cursors) so peak resident memory remains bounded ($O(\text{chunk\_size})$) regardless of whether the input is 10KB or 100GB.
3. **The Zero-Allocation Hot-Path Law (GC Pressure Discipline):** Garbage collection pauses and allocator lock contention dominate tail latency (`P99` / `P99.9`). Every byte allocated in a hot loop must later be traced and swept.
   - Eliminate intermediate allocations in hot loops: ban multi-pass array chaining (`.map().filter().reduce()`), object cloning (`JSON.parse(JSON.stringify(x))` or `{ ...acc, [k]: v }` inside `reduce`), closure allocation per iteration, and regex/formatter instantiation inside loops.
   - Pre-size arrays/maps when length is known (`with_capacity`, `new Array(n)`), mutate a single accumulator in place during tight loops, and reuse pre-allocated byte buffers (`Uint8Array` / `Buffer` pools / `sync.Pool`).
4. **The I/O Physics Law (Batching & Pipelining Over Network-in-a-Loop):** An L1 cache read takes `0.5ns`; a same-datacenter network roundtrip takes `500,000ns` (`0.5ms`). Network I/O inside a loop multiplies tail latency and saturates connection pools.
   - **Zero Serial I/O in Loops:** Never execute `await db.query()`, `await redis.get()`, or `await fetch()` inside a `for`/`while` loop.
   - **Batch & Pipeline:** Coalesce $N$ point lookups or writes into a single bulk operation (`WHERE id = ANY($1::uuid[])`, `INSERT INTO ... SELECT * FROM UNNEST(...)`, Redis `MGET` / `pipeline()`, or request-scoped DataLoader coalescing) to collapse $N$ serial roundtrips into $1$ roundtrip.
5. **The Algorithmic Physics Before Caching Law:** Caching is not a performance fix for bad data structures or unindexed queries; it is a stateful liability that masks $O(N^2)$ debt until a cache miss or cold start triggers a cascading outage.
   - Always reduce asymptotic complexity first (e.g., converting an $O(N \times M)$ nested `.find()` / `.includes()` loop into an $O(N + M)$ pre-indexed `Map` or `Set` lookup) and verify physical index coverage before proposing any cache layer or `useMemo`.

---

## Invariant Rules

1. **Explain the Number against hardware limits.** Always compare observed latency against the theoretical hardware floor (e.g., if a local in-memory function takes `40ms` to process 1,000 items, that is `40,000ns` per item—tens of thousands of wasted instructions or hidden I/O/allocation stalls).
2. **Inspect `BUFFERS`, not just query cost estimates.** PostgreSQL planner cost estimates (`EXPLAIN` without `ANALYZE, BUFFERS`) lie when statistics are skewed. Always inspect actual buffer hits/reads and row-estimate accuracy (`rows=actual` vs `rows=planned`).
3. **Verify index selectivity and column ordering.** Follow the **ESR Rule (Equality, Sort, Range)** when designing composite B-Tree indexes, and use covering indexes (`INCLUDE`) when heap fetches dominate `EXPLAIN (ANALYZE, BUFFERS)`.
4. **Single-pass iteration on large collections.** When transforming and filtering collections of $> 1,000$ items on a hot path, use a single `for` loop or generator rather than chaining `.filter().map().flatMap()`, which allocates and garbage-collects multiple intermediate arrays.
5. **Hoist loop-invariant allocations.** Move `new RegExp()`, `new Intl.DateTimeFormat()`, `TextEncoder`, schema compilers, and configuration parsing to module scope or outside the loop boundary.
6. **Bound streaming high-water marks.** Explicitly configure `highWaterMark` / chunk buffer sizes (e.g., `64KB`) and wire cancellation (`AbortSignal`) through every stream pipeline so slow consumers apply backpressure to fast producers without unbounded queue growth.
7. **Benchmark with realistic payload distributions and warmup.** Always include JIT/cache warmup iterations before sampling, test against production-representative cardinalities (not a 3-item toy array), and report `P50`, `P99`, and `alloc_bytes_per_op`.
8. **Never add `useMemo` or `useCallback` without profiling render/allocation cost.** Memoizing cheap primitive expressions costs more in closure allocation and dependency-array comparison than recomputing the value.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Speeding up CPU/memory hot paths, loops, parsers, or algorithms | [Profile & Benchmark Code](usecases/profile-and-benchmark-code.md) | [Empirical Measurement & EXPLAIN](references/empirical-measurement-and-explain.md) |
| Optimizing slow SQL queries, fixing N+1s, or batching network/DB I/O | [Optimize Database & I/O](usecases/optimize-database-and-io.md) | [I/O Batching & Pipelining](references/io-batching-and-pipelining.md) |
| Fixing OOMs, high RSS memory, or GC latency spikes (`P99` stalls) | [Eliminate GC & Memory Bloat](usecases/eliminate-gc-and-memory-bloat.md) | [Memory Hierarchy & GC Physics](references/memory-hierarchy-and-gc-physics.md) |
| Durable performance & mechanical-sympathy record generation & audit | [Record Contract](references/profiler-record-contract.md) | `scripts/profiler_guard.py` |

---

## Mandatory Pre-Optimization Interrogation Matrix

Before writing a single line of "optimization" code, adding an index, or introducing a cache, answer these five questions with hard numbers:

- **The Baseline Proof Check:** Where is the baseline `EXPLAIN (ANALYZE, BUFFERS)` output or micro-benchmark showing current `P50`, `P99`, `alloc_bytes_per_op`, and `io_roundtrips_per_request`? If none exists, **stop and measure first**.
- **The Bounding Resource Check:** Is this path physically bound by **Network RTT count**, **Disk/Buffer I/O reads**, **Heap Allocation / GC sweep rate**, **CPU instruction count ($O(N^2)$)**, or **Lock Contention**?
- **The Memory & GC Footprint Check:** Does peak memory scale as $O(N)$ with file/dataset size (`readFileSync`, full array materialization) when it should be $O(1)$ via streaming? How many transient objects and intermediate arrays are allocated per request on the hot path?
- **The Wire Roundtrip Check:** How many serial network or database roundtrips occur for a batch of $N$ items? Can $N$ roundtrips be collapsed into $1$ batched query (`UNNEST` / `ANY`) or pipeline?
- **The Caching Justification Check:** If someone proposed caching or `useMemo`, why is the underlying operation slow in the first place? Have we eliminated $O(N^2)$ lookups, N+1 queries, and missing composite indexes first?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Unmeasured "Trust-Me" Optimization:** Submitting a performance refactor, caching layer, `useMemo` wrapper, or database index without recorded before-and-after measurements (`EXPLAIN (ANALYZE, BUFFERS)` or `P99` + allocation benchmark).
2. **Serial I/O Inside Loops (`await` in `for`/`while`):** Executing database queries, Redis commands, or HTTP requests sequentially inside a loop instead of batching or pipelining.
3. **Whole-File / Unbounded Dataset RAM Buffering:** Calling `fs.readFileSync`, `fs.promises.readFile`, `response.arrayBuffer()`, or unbounded `SELECT *` on large or user-scaled payloads instead of streaming with backpressure.
4. **Quadratic $O(N^2)$ Lookups in Hot Loops:** Calling `array.find()`, `array.includes()`, or `array.indexOf()` inside another `.map()`, `.filter()`, or `for` loop over dynamic collections instead of building an $O(1)$ `Map` or `Set` index once.
5. **Hot-Path Allocation Churn & Object Spread Reducers:** Using `items.reduce((acc, x) => ({ ...acc, [x.id]: x }), {})` ($O(N^2)$ object copies), `JSON.parse(JSON.stringify(obj))` deep clones, or multi-stage `.map().filter().map()` chains inside latency-critical paths.
6. **Speculative Caching Over Broken Physics:** Masking an unindexed sequential table scan or an N+1 query loop behind Redis or an in-memory TTL cache instead of fixing the query and index.

---

## Required Output & Review Workflow

Structure all performance optimizations, query tuning tasks, and bottleneck investigations through this 4-phase discipline:

1. **Baseline Telemetry & Bottleneck Physics Classification:** Execute and report the baseline measurement (`EXPLAIN (ANALYZE, BUFFERS)` plan or micro-benchmark `P50`/`P99` latency, `alloc_bytes_per_op`, `allocs_per_op`, and `io_roundtrips_per_request`). Identify the physical bounding resource.
2. **Mechanical Sympathy Remediation Design:** State the exact hardware/I/O/algorithmic transformation—replacing RAM buffering with bounded streaming, eliminating hot-loop heap allocations, collapsing $O(N)$ I/O roundtrips into $O(1)$ batched/pipelined operations, or indexing via the ESR rule—without speculative caching.
3. **Sympathetic Implementation:** Emit clean, minimal code or DDL that respects memory locality, backpressure, zero-allocation hot paths, and bulk I/O semantics.
4. **Post-Change Verification & Delta Table:** Re-run the exact same benchmark or `EXPLAIN (ANALYZE, BUFFERS)` command, present a side-by-side **Before vs. After Delta Table** (`P50`, `P99`, `alloc_bytes/op`, `allocs/op`, `buffer reads`, `I/O roundtrips`), and verify with `scripts/profiler_guard.py`.

When a durable performance engineering record is warranted, save a JSON assessment following the [Profiler Record Contract](references/profiler-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering profiler audit <record.json> --json
# or: python3 scripts/profiler_guard.py audit <record.json> [--source <hot_path.ts>] --json
```

---

## Domain References

- **[Mechanical Sympathy & Profiler Playbook Suite](playbooks/README.md)**: Central orchestration index for Meta/Google systems profiling and hardware physics.
- **[Empirical Measurement, Benchmarking & EXPLAIN Playbook](playbooks/measurement-and-benchmarking-playbook.md)**: Micro-benchmarking P99 tail latency and heap allocations, reading PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)`, Flame Graphs, and the Revert-on-Noise gate.
- **[Hardware, Memory Hierarchy & I/O Physics Playbook](playbooks/hardware-memory-and-io-physics-playbook.md)**: Jeff Dean latency numbers, streaming backpressure vs RAM buffering, zero-allocation hot loops, GC ergonomics, and SQL/Redis/HTTP batching & pipelining.
- **[Empirical Measurement & EXPLAIN Reference](references/empirical-measurement-and-explain.md)**: Exact benchmark harness templates (TypeScript/Bun, Go, Python, Rust) and `EXPLAIN (ANALYZE, BUFFERS)` diagnostic matrix.
- **[Memory Hierarchy & GC Physics Reference](references/memory-hierarchy-and-gc-physics.md)**: Allocation elimination patterns, pre-sizing, typed buffers, object pooling, and backpressure streams.
- **[I/O Batching & Pipelining Reference](references/io-batching-and-pipelining.md)**: `UNNEST` bulk inserts/updates, `ANY($1)` batch reads, Redis pipelining, and DataLoader coalescing.
- **[Profiler Record Contract](references/profiler-record-contract.md)**: JSON schema and verification rules for `scripts/profiler_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Blind caching slop | Agent adds Redis/in-memory cache or `useMemo` without measuring why the path is slow | Remove speculative cache; run `EXPLAIN (ANALYZE, BUFFERS)` or profiler and fix the underlying query or $O(N^2)$ loop |
| Unverified index bloat | New DB index added, but query still does `Seq Scan` or `Rows Removed by Filter: 500000` | Run `EXPLAIN (ANALYZE, BUFFERS)` and reorder composite index columns per Equality-Sort-Range (ESR) |
| Network-in-a-loop stall | Endpoint latency scales linearly with item count ($N \times \text{RTT}$) | Replace `for (... await db/redis/fetch)` with a single batched `ANY($1)`/`UNNEST` query or pipeline |
| Whole-payload OOM spike | Worker RSS memory spikes by hundreds of MBs during file or export processing | Replace `readFileSync` / full array materialization with bounded-chunk streaming (`pipeline` / `ReadableStream`) |
| GC tail-latency sawtooth | `P50` is `2ms` but `P99` spikes to `180ms` during concurrent load | Eliminate `.map().filter()` chains, spread-Clone reducers, and per-iteration closures in hot loops |
| Quadratic CPU freeze | CPU hits 100% when array size grows from $100$ to $10,000$ items | Pre-index the lookup collection into a `Map` or `Set` ($O(1)$ lookup) outside the loop |

---

## Delegated Skills

- `anti-slop-engineering`: Enforce clean-room KISS/DRY/YAGNI gates and test integrity alongside performance changes.
- `paranoid-principal-architect`: Pair bulk I/O and streaming pipelines with explicit byte caps, cursor pagination, `AbortSignal.timeout()`, and 10M-concurrent-user scale protection.
- `apple-craft-and-frame-budget`: When the hot path is a 60/120Hz client UI animation or DOM rendering loop, apply compositor-only frame budgets (`8.3ms`) and Web Worker offloading.
- `scientific-fault-isolation`: When diagnosing whether a latency spike is caused by a lock regression or a code commit, use binary search (`git bisect`) and differential diagnosis.

---

## Completion and Limits

The task is complete when baseline and post-change measurements (`EXPLAIN (ANALYZE, BUFFERS)` or `P50`/`P99` + heap allocation micro-benchmarks) are captured and compared side-by-side, speculative unmeasured caching is rejected, large payloads stream in bounded memory, hot loops avoid transient GC allocation churn, loop I/O is coalesced into batched/pipelined operations, and `scripts/profiler_guard.py` reports zero findings. A review may validly output `refuse` or `pause` if an optimization is proposed without baseline telemetry or relies on blind caching over unmeasured bottlenecks.
