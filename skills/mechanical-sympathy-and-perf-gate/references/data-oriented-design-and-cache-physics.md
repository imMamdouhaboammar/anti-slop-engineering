# Data-Oriented Design (DOD) & CPU Cache Physics

## 1. The Hardware Reality: CPU Cache Hierarchy

Modern CPUs (Apple Silicon M-series, Intel Core, AMD Zen) execute instructions at gigahertz frequencies, but fetching data from Main Memory (DRAM) is painfully slow:

| Hierarchy Level | Latency (Cycles) | Latency (Nanoseconds) | Size (Typical) |
| --- | --- | --- | --- |
| L1 Data Cache | 4 - 5 cycles | ~1.0 ns | 32 - 128 KB per core |
| L2 Cache | 14 cycles | ~3.5 ns | 1 - 4 MB per core |
| L3 / System Level Cache | 40 - 80 cycles | ~10 - 20 ns | 16 - 96 MB shared |
| Main Memory (DRAM) | 200 - 300 cycles | ~60 - 100 ns | 16 - 128 GB |

### Cache Lines
CPUs never read a single byte or float from memory; they always read a contiguous **64-byte Cache Line**.
- **Spatial Locality:** Accessing adjacent bytes in the same 64-byte line costs 0 extra cycles.
- **Pointer Chasing (The Cache Miss Hazard):** In traditional Object-Oriented programming (Array of Structures / AoS), every object (`{ id, price, qty, status }`) is allocated independently on the heap. Iterating through `orders.map(o => o.price)` forces the CPU to fetch a new cache line from DRAM on every single element, stalling the execution pipeline for 100ns per item ($99\%$ CPU idle wait time).

---

## 2. Struct-of-Arrays (SoA) vs Array-of-Structures (AoS)

### Bad: Array of Structures (Pointer Chasing & Cache Misses)
```typescript
// Memory is fragmented; 64-byte cache lines are loaded with irrelevant fields
interface Order {
  id: string;        // 8-byte pointer to heap string
  price: number;     // 8-byte float
  quantity: number;  // 8-byte float
  status: string;    // 8-byte pointer
  user: User;        // 8-byte pointer
}
const orders: Order[] = fetchOrders(); // Array of pointers
```

### Good: Struct of Arrays (DOD Contiguous Buffer)
Pack homogenous numerical attributes into contiguous, flat TypedArrays (`Float64Array`, `Uint32Array`):
```typescript
class OrderBookSoA {
  public prices: Float64Array;      // 8 bytes per price, perfectly packed
  public quantities: Float64Array;  // contiguous
  public orderIds: Uint32Array;     // contiguous

  constructor(capacity: number) {
    this.prices = new Float64Array(capacity);
    this.quantities = new Float64Array(capacity);
    this.orderIds = new Uint32Array(capacity);
  }
}
```
**Physical Impact:** A single 64-byte cache line loads 8 consecutive order prices simultaneously. The CPU hardware prefetcher detects linear strides and streams cache lines into L1 before the loop even requests them, yielding up to **10x - 50x throughput gains**.

---

## 3. Zero-Allocation Hot Loops (GC Pressure Elimination)

In high-throughput loops (> 10,000 iterations/sec), every heap allocation is a future stop-the-world or incremental Garbage Collection pause.

### Prohibited Allocations in Hot Paths
1. **Closure creation inside loops:**
   ```typescript
   // BAD: Allocates a new closure object on every iteration
   items.forEach((item) => process(item));
   ```
2. **Intermediate Array Chaining:**
   ```typescript
   // BAD: Allocates 3 intermediate arrays of 100k elements each
   const result = items
     .filter(x => x.active)
     .map(x => x.price * 1.1)
     .filter(p => p > 50);
   ```
3. **Object Spread Accumulators in Reduce:**
   ```typescript
   // FATAL: Allocates an entire copy of the accumulator object per item (O(N^2) memory churn)
   const map = items.reduce((acc, x) => ({ ...acc, [x.id]: x }), {});
   ```
4. **Instantiating Regexes, Formatters, or Encoders in Loops:**
   ```typescript
   // BAD: Compiles regex engine on every iteration
   for (const line of lines) {
     const match = new RegExp(/pattern/).exec(line);
   }
   ```

### Hardened Zero-Allocation Patterns
- **Pre-size Collections:** Use `new Array(size)` or TypedArray with fixed capacity; never allow dynamic arrays to reallocate and copy their backing store.
- **In-Place Mutation:** Mutate a pre-allocated accumulator struct passed as a reference.
- **Single-Pass Loop:** Collapse `.filter().map()` into a single `for` loop with index access.
- **Hoist Invariants:** Move `RegExp`, `Intl.DateTimeFormat`, and `TextEncoder` to module scope.
