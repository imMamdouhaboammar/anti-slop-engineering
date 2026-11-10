# Zero-Copy & Streaming Architecture (Bounded O(1) Memory Physics)

## 1. The RAM Buffering Anti-Pattern (O(N) RSS Exhaustion)

When processing files, exports, or network payloads, naive code loads the entire dataset into contiguous heap memory:

```typescript
// FATAL: If file is 1.5GB, allocates 1.5GB string, then another 3GB in split arrays!
const content = fs.readFileSync("/data/export.ndjson", "utf8");
const records = content.split("\n").map(JSON.parse);
```

### Physical Hazards
1. **Heap Memory Explosion & OOM:** Node.js/V8 and Bun heap limits (typically 2GB or 4GB) are instantly exceeded, terminating the process with `SIGSEGV` or `Fatal error: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.
2. **Page Faults & Memory Swapping:** Allocating gigabytes of heap memory forces the OS kernel to swap pages to disk, slowing down system throughput by 10,000x.
3. **GC Lockup:** Tracing millions of small parsed JSON objects in memory triggers tens of seconds of GC pause time.

---

## 2. Bounded-Chunk Streaming with Backpressure

Under the **Zero-Copy & Streaming Law**, peak resident set size (RSS) memory must remain bounded at $O(\text{chunk\_size})$ ($O(1)$ relative to total dataset size).

```
[ Producer: File / Socket ] 
       │ 64KB chunk
       ▼ (highWaterMark applied)
[ TransformStream: Line Splitter / Parser ] 
       │ parsed slice
       ▼ (backpressure applied if consumer is slow)
[ Consumer: DB Writer / Processor ]
```

### Web Streams Implementation (Platform-Agnostic)
```typescript
import { ReadableStream, TransformStream } from "node:stream/web";

export async function processNdjsonStream(
  byteStream: ReadableStream<Uint8Array>,
  handleRecord: (record: unknown) => Promise<void>
): Promise<void> {
  const lineDecoder = new TextDecoderStream();
  const reader = byteStream.pipeThrough(lineDecoder).getReader();

  let leftover = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = leftover + value;
    const lines = chunk.split("\n");
    leftover = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      await handleRecord(JSON.parse(line));
    }
  }

  if (leftover.trim()) {
    await handleRecord(JSON.parse(leftover));
  }
}
```

---

## 3. Zero-Copy Buffer Sharing & Transfer

Copying byte arrays between functions, threads, or workers wastes memory bandwidth and CPU cycles.

### Strategies
1. **`ArrayBuffer.transfer()` (TC39 Standard):** Move buffer ownership to another context or resize in place without copying data:
   ```typescript
   // Transfers ownership; sourceBuffer is detached (0 bytes copied)
   const transferred = sourceBuffer.transfer();
   ```
2. **Subarray Views Over Clones:** Never call `.slice()` on a `Uint8Array` when reading header fields; use `.subarray()` to create a zero-copy pointer view:
   ```typescript
   // ZERO-COPY: Points to the same underlying memory without allocating new buffer
   const headerView = fullBuffer.subarray(0, 32);
   ```
3. **Worker Transfer List:** Transfer `ArrayBuffer` instances to Web Workers by specifying them in the second argument:
   ```typescript
   worker.postMessage({ buffer }, [buffer]); // Zero-copy memory handoff
   ```
4. **Kernel Splice & `io.Copy`:** In Go or Rust native backends, use `sendfile` or `splice` system calls to pipe socket bytes to disk or vice-versa directly in kernel space without copying to user-space memory buffers.
