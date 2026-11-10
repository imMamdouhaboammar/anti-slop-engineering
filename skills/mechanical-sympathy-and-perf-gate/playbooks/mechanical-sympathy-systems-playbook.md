# Playbook: Systems-Level Mechanical Sympathy & Hardware Architecture

## 1. Psychological Stance & Philosophy

When operating under this playbook, you treat the underlying hardware—CPU cache lines, memory buses, TLB (Translation Lookaside Buffer), and network sockets—as active physical constraints, not abstract mathematical conveniences.

The five systems performance laws govern every architectural decision:

1. **The Cache Locality Axiom:** Modern CPUs are starving for data. A cache miss to DRAM costs ~200-300 cycles (~70ns). If an algorithm incurs a cache miss on every iteration, 99% of CPU execution time is spent idling. Data must be structured to exploit spatial locality (sequential 64-byte cache line reads).
2. **The Memory Allocation Tax Law:** Every byte allocated on the heap inside a hot path requires future tracing, sweeping, and memory compaction by the Garbage Collector, producing unpredictable P99 and P99.9 latency spikes.
3. **The Bounded Memory Axiom:** The memory footprint of processing an $N$-byte stream must remain $O(1)$. Whole-file buffering in RAM is a fatal engineering defect.
4. **The Roundtrip Elimination Law:** An L1 cache hit takes $1\text{ns}$; a cross-datacenter roundtrip takes $50,000,000\text{ns}$. Serial I/O inside loops destroys throughput.
5. **The Empirical Proof Invariant:** An optimization without baseline and post-change flamegraphs and P99 numbers is speculative slop.

---

## 2. Data-Oriented Memory Design (DOD)

### Struct of Arrays (SoA) for Analytical & High-Throughput Paths
When processing large collections of records, transition from Array of Structures (AoS) to Struct of Arrays (SoA):

```
AoS (Fragmented, Pointer Chasing):
[ Obj1: {id, price, qty} ] -> [ Obj2: {id, price, qty} ] -> [ Obj3: {id, price, qty} ]

SoA (Contiguous Typed Buffers):
prices:      [ float64, float64, float64, float64 ... ]  <-- 8 floats per 64-byte cache line!
quantities:  [ float64, float64, float64, float64 ... ]
orderIds:    [ uint32,  uint32,  uint32,  uint32  ... ]
```

### Pre-Allocated Scratchpads
- Pre-size all collections before entering hot loops.
- Pass a single mutable context/accumulator struct by reference.
- Reuse static typed buffers (`Uint8Array`, `Buffer` pools) across incoming network requests.

---

## 3. Zero-Copy & Streaming Architecture

1. **Backpressure & Bounded Buffers:** Configure stream pipelines with an explicit `highWaterMark` (e.g., 64KB). When consumer processing slows down, backpressure signals propagate upstream to pause socket or disk reads.
2. **Transferable Objects:** Transfer `ArrayBuffer` ownership directly across thread and worker boundaries without duplicating memory in the heap.
3. **Subarray Windowing:** Use `.subarray(begin, end)` to inspect headers and byte frames without allocating new sub-buffers.

---

## 4. Database Buffer & I/O Physics

1. **Inspect PostgreSQL Shared Buffers:** When running `EXPLAIN (ANALYZE, BUFFERS)`:
   - Ensure `shared read` blocks are minimal compared to `shared hit` blocks.
   - High `shared read` blocks indicate random disk I/O; add covering indexes (`INCLUDE`) to enable **Index Only Scans**.
2. **Batch Point Lookups:** Replace individual queries inside loops with single-roundtrip bulk queries using `WHERE id = ANY($1::uuid[])` or `UNNEST`.
