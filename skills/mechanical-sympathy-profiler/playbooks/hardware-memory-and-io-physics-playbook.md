# Playbook 2: Hardware, Memory Hierarchy & I/O Physics

> Write code that works *with* the CPU cache lines, virtual memory subsystem, garbage collector, and network socket buffers—not against them.

## 1. Memory Physics: Bounded Streaming vs. Whole-Payload RAM Buffering

### The Failure Mode
An AI agent writes an export endpoint or file processor using `const buf = fs.readFileSync(filePath)` or `const rows = await db.query('SELECT * FROM audit_logs')`. In staging with 200 rows (`50KB`), tests pass in `3ms`. In production with 2,000,000 rows (`1.2GB`), 4 concurrent requests allocate `4.8GB` on the heap, triggering `FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory` (or Linux OOM-Killer `SIGKILL`).

### The Mechanical Sympathy Law
Memory footprint for data-pipeline, file, and export operations must be **$O(\text{chunk\_size})$ (`O(1)` relative to dataset size)**, never $O(N)$.

1. **Bound the High-Water Mark:** Stream data in `16KB–64KB` byte chunks or `250–1,000` row cursor batches.
2. **Enforce Backpressure End-to-End:** Never attach an unawaited `.on('data', async (chunk) => { ... })` listener (which floods memory when the reader is faster than the writer). Always use async iteration (`for await (const chunk of stream)`) or `stream/promises` `pipeline(source, transform, destination, { signal })`.
3. **Reuse Batch Buffers In-Place:** Clear a fixed batch array via `batch.length = 0` after flushing each chunk so the runtime reuses the underlying array capacity without reallocating.

---

## 2. Garbage Collector Sympathy: Zero-Allocation Hot Paths

### How Hot-Path Allocations Destroy `P99`
Modern generational garbage collectors (V8 Orinoco, Go GC, JVM ZGC/G1) allocate into a young nursery bump-pointer region (`Eden`) very cheaply, **until the nursery fills up**. When a hot loop allocates megabytes of transient objects per request:
- Nursery evacuations occur every few milliseconds.
- Concurrent marker threads steal 25%+ of CPU cores from request workers (GC Assist).
- Objects surviving inside long-running async closures promote to Old Generation, triggering full-heap compaction pauses.

### Five Hot-Loop Rules
1. **Collapse Chained Array Methods into a Single Loop:**
   - Replace `records.filter(...).map(...).filter(...)` with a single `for (let i = 0; i < records.length; i++)` pass.
2. **Pre-Index Lookups Before Entering the Loop:**
   - Never call `items.find(...)`, `items.includes(...)`, or `items.indexOf(...)` inside a loop ($O(N^2)$). Build a `Map` or `Set` once outside the loop ($O(N)$ build + $O(1)$ lookup).
3. **Eliminate Spread-Clone Accumulators:**
   - Never write `array.reduce((acc, item) => ({ ...acc, [item.id]: item }), {})`. Each iteration allocates a brand-new object and copies $1 + 2 + \dots + N = \frac{N(N+1)}{2}$ properties.
4. **Pre-Size Collections & Typed Buffers:**
   - When the output count or maximum bound is known, pre-allocate (`new Array(n)`, `new Float64Array(n)`, `Vec::with_capacity(n)`, `make([]T, 0, n)`) to prevent progressive doubling reallocations and memory copies.
5. **Hoist Heavy Instantiations:**
   - Instantiate `TextEncoder`, `TextDecoder`, `Intl.NumberFormat`, `Intl.DateTimeFormat`, compiled `RegExp`, and cryptographic HMAC/hash contexts outside the loop or at module load.

---

## 3. I/O Physics: Batching & Pipelining Over Loop Roundtrips

### The Physics of the Wire
Even on a fast local loopback or same-AZ VPC network (`0.5ms` RTT), executing 400 sequential queries in a `for` loop guarantees a minimum floor of $400 \times 0.5\text{ms} = 200\text{ms}$ spent purely waiting for photons and TCP ACK packets—before counting database lock acquisition or CPU execution.

### Mandatory Coalescing Patterns
| Loop Anti-Pattern | Mechanical Sympathy Replacement | Roundtrip Delta |
| --- | --- | --- |
| `for (const id of ids) await db.query('SELECT ... WHERE id = $1', [id])` | `await db.query('SELECT ... WHERE id = ANY($1::uuid[])', [ids])` | $N \to 1$ |
| `for (const row of rows) await db.query('INSERT INTO ... VALUES ($1, $2)', ...)` | `await db.query('INSERT INTO ... SELECT * FROM UNNEST($1::uuid[], $2::int[])', [col1, col2])` | $N \to 1$ |
| `for (const row of rows) await db.query('UPDATE ... SET v = $1 WHERE id = $2', ...)` | `UPDATE t SET v = u.v FROM UNNEST($1::uuid[], $2::int[]) AS u(id, v) WHERE t.id = u.id` | $N \to 1$ |
| `for (const k of keys) await redis.get(k)` | `await redis.mget(keys)` or `redis.pipeline()` | $N \to 1$ |
| N+1 GraphQL / Nested Entity Resolvers | Tick-batched `DataLoader` coalescing unique IDs per event-loop turn | $N \to 1$ per layer |
