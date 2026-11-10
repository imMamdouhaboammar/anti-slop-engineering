# Reference: Hardware Latency Numbers, Memory Hierarchy & GC Physics

High-throughput systems at Meta and Google are designed around the physical realities of silicon: CPU cache lines (`64 bytes`), virtual memory pages (`4KB`), heap allocator lock contention, and Garbage Collector tracing cost.

---

## 1. Latency Numbers Every Systems Engineer Must Know

| Operation | Approximate Latency | Relative Scale (If L1 Cache = 1 second) |
| --- | --- | --- |
| L1 cache reference | `0.5 ns` | `1 second` |
| Branch mispredict | `5 ns` | `10 seconds` |
| L2 cache reference | `7 ns` | `14 seconds` |
| Mutex lock / unlock | `15 ns` | `30 seconds` |
| Main memory (DRAM) reference | `100 ns` | `3.3 minutes` |
| Compress 1KB with Zstd / LZ4 | `2,000 ns` (`2 µs`) | `1.1 hours` |
| Random NVMe SSD read (4KB) | `20,000 ns` (`20 µs`) | `11 hours` |
| Same-datacenter network roundtrip (RTT) | `500,000 ns` (`0.5 ms`) | `11.5 days` |
| Cross-continent network roundtrip | `150,000,000 ns` (`150 ms`) | `9.5 years` |

**Implication:** Saving 50 CPU instructions while leaving a single sequential database roundtrip inside a loop is optimizing `25 nanoseconds` while wasting `500,000 nanoseconds`.

---

## 2. Streaming & Backpressure vs. Whole-Payload RAM Buffering

When an endpoint or worker processes a file, NDJSON export, or large query result:

### Anti-Pattern: $O(N)$ Whole-Payload RAM Buffering (OOM Generator)
```typescript
// FORBIDDEN: Loads entire 500MB file into V8 heap, then allocates a second 500MB string,
// then allocates millones of parsed objects all at once.
const raw = fs.readFileSync("/data/events.ndjson", "utf8");
const lines = raw.split("\n");
const parsed = lines.filter(Boolean).map((line) => JSON.parse(line));
```

### Mechanical Sympathy Pattern: $O(1)$ Bounded Streaming with Backpressure
```typescript
import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";

export async function processNdjsonStream(
  filePath: string,
  onBatch: (batch: readonly Record<string, unknown>[]) => Promise<void>,
  batchSize = 500
): Promise<number> {
  const fileStream = createReadStream(filePath, { highWaterMark: 64 * 1024, encoding: "utf8" });
  const rl = createInterface({ input: fileStream, crlfDelay: Infinity });

  const batch: Record<string, unknown>[] = [];
  let processed = 0;

  for await (const line of rl) {
    if (line.length === 0) continue;
    batch.push(JSON.parse(line) as Record<string, unknown>);
    if (batch.length >= batchSize) {
      await onBatch(batch);
      processed += batch.length;
      batch.length = 0; // Reuse array backing store in-place; zero new array allocation
    }
  }
  if (batch.length > 0) {
    await onBatch(batch);
    processed += batch.length;
    batch.length = 0;
  }
  return processed;
}
```

---

## 3. Zero-Allocation Hot Paths & Eliminating GC Pressure

In garbage-collected runtimes (V8/Node/Bun, Go, JVM, Python), allocation rate (`MB/sec`) directly dictates GC frequency and `P99` stop-the-world / concurrent-mark assist latency.

1. **Ban Multi-Pass Chained Array Allocations in Hot Loops:**
   - `items.filter(p).map(f).reduce(r, init)` traverses the array 3 times and allocates 2 full intermediate arrays on the heap.
   - Replace with a single `for (let i = 0; i < items.length; i++)` pass in hot paths (`> 1,000` elements or `> 100 req/s`).
2. **Ban Object-Spread Accumulators Inside `reduce`:**
   - `items.reduce((acc, x) => ({ ...acc, [x.id]: x }), {})` copies every existing key on every iteration, turning an $O(N)$ loop into $O(N^2)$ time and $O(N^2)$ garbage allocations.
   - Mutate a `new Map()` or single object accumulator in place.
3. **Replace Nested Linear Scans (`find`/`includes`) with Pre-Indexed `Map`/`Set`:**
   - Calling `orders.map(o => users.find(u => u.id === o.userId))` performs $N \times M$ comparisons.
   - Build `const userById = new Map(users.map(u => [u.id, u]))` once ($O(N + M)$).
4. **Reuse Scratch Buffers & TypedArrays:**
   - For binary encoding, hashing, or telemetry serialization, reuse a pre-allocated `Uint8Array` or `Float64Array` rather than allocating fresh heap objects per record.
