# Workflow: Eliminate GC Pressure & RAM Buffering Bloat

Use this workflow when diagnosing Out-of-Memory (OOM) crashes, high container RSS footprint, sawtooth heap profiles, or `P99` tail-latency spikes caused by Garbage Collection pauses.

## Step-by-Step Procedure

### 1. Measure Baseline Heap High-Water Mark & Allocation Rate
1. Capture baseline memory telemetry before modifying code:
   - `process.memoryUsage().heapUsed` and `rss` (Node/Bun), `runtime.ReadMemStats` / `pprof` (`alloc_space`, `inuse_space` in Go), or `tracemalloc` (Python).
   - Record peak RSS growth ($\Delta \text{RSS}$) when processing a realistic large payload (e.g., 50MB file or 100,000 database rows).

### 2. Replace Whole-Payload RAM Buffering with Bounded Streaming
1. Locate any call that materializes an entire file, stream, or query into RAM at once:
   - `fs.readFileSync(path)`, `await fs.promises.readFile(path)`, `await response.text()` / `await response.json()` on multi-MB exports, or `await db.query('SELECT * FROM large_table')` without cursor streaming.
2. Refactor into a **Bounded-Chunk Stream Pipeline** with explicit backpressure:
   - Read chunks of fixed size (e.g., `64KB` `highWaterMark`) via `fs.createReadStream`, Web `ReadableStream`, or DB cursor (`FETCH 1000 FROM cur`).
   - Transform records incrementally via `TransformStream` or async generator (`async function*`).
   - Pipe to the destination sink using `stream/promises` `pipeline(source, transform, sink, { signal })` so slow downstream writes automatically pause upstream reads.

### 3. Eliminate Young-Generation GC Churn in Hot Paths
1. Replace immutable copy-on-write patterns inside hot loops (`acc = { ...acc, [k]: v }`, `arr = [...arr, item]`) with in-place mutations (`acc.set(k, v)`, `arr.push(item)`).
2. Replace `JSON.parse(JSON.stringify(payload))` with targeted shallow projection or `structuredClone` only when mutation isolation is required outside hot loops.
3. Reuse fixed-size `Uint8Array` / `Buffer` scratchpads or bounded object pools (`sync.Pool`) for high-frequency binary encoding/decoding so zero buffers are allocated per frame/request.

### 4. Verify $O(1)$ RSS Flatline & Allocation Drop
1. Re-run the memory benchmark with a $10\times$ larger input payload.
2. Verify that peak RSS remains flat ($O(\text{chunk\_size})$) rather than scaling linearly ($O(N)$) with file size, and confirm `alloc_bytes_per_op` and GC pause duration dropped in the post-change profile.
