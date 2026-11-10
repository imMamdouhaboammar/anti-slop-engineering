# Design Data-Oriented System (CPU Cache & Memory Optimization)

Use this workflow when creating high-throughput compute services, order matching engines, vector stores, numerical analytics, or batch processing pipelines.

## Step-by-Step Procedure

### 1. Profile Memory Access Patterns & Hot Paths
1. Identify the core loops executing $> 10,000$ iterations per second.
2. Determine whether data is stored as an **Array of Structures (AoS)** (causing pointer chasing and L1/L2 cache misses) or **Struct of Arrays (SoA)** (sequential cache-line streaming).
3. Measure current CPU cache misses using hardware performance counters (`perf stat -e L1-dcache-load-misses,LLC-load-misses` on Linux or Instruments CPU Profiler on macOS).

### 2. Design the Contiguous Struct-of-Arrays (SoA) Layout
1. Separate homogeneous fields into flat typed buffers (`Float64Array`, `Uint32Array`, `Int32Array`).
2. Pack attributes that are read together in the same hot loop into contiguous slices to fit within 64-byte CPU cache lines.
3. Pre-allocate the full buffer capacity upfront; eliminate dynamic array resizes during runtime execution.

### 3. Eliminate Hot-Loop Heap Allocations
1. Pass pre-allocated accumulator structures by reference into the processing function.
2. Ban the creation of per-iteration closures, arrow functions, promises, or regex instances inside the loop.
3. Replace multi-pass array methods (`.filter().map().reduce()`) with a single-pass `for` loop with index access.
4. Replace $O(N^2)$ nested lookups (`.find()` / `.includes()`) with pre-indexed $O(1)$ `Map` or `Set` lookups.

### 4. Implement Bounded-Chunk Streaming
1. If data is ingested from disk or network, mandate Web Streams with backpressure (`ReadableStream` / `TransformStream`).
2. Configure bounded buffer chunk sizes (e.g. 64KB).
3. Strictly prohibit whole-payload RAM buffering (`readFileSync`, `response.text()`).

### 5. Document in Perf Record & Audit
Save the architectural design decisions to `perf-record.json` and verify with:
```bash
python3 scripts/perf_guard.py audit <record.json> --source <system.ts> --json
```
