# Determinism Pinning: Converting Flaky Bugs & Race Conditions into 100% Red Tests

An intermittent bug (a "flaky test" or "Heisenbug") is simply a deterministic bug whose inputs include unpinned environmental variables: **thread/task scheduling order, wall-clock time, pseudo-random number generators (PRNG), hash-map iteration order, or network I/O latency**.

Never attempt to fix a flaky bug while it fails only 5% of the time. If it fails 5% of the time before your edit, a single green test run after your edit has a 95% false-positive rate. You must force the failure rate to **100%** first.

---

## 1. The Five Axes of Non-Determinism

| Axis | Unpinned Source | Deterministic Pinning Mechanism |
| --- | --- | --- |
| **1. Async / Thread Interleaving** | Concurrent promises, goroutines, or threads racing to a shared resource | Inject an explicit `ExecutionBarrier` / `DeferredLatch` seam or use a deterministic scheduler (`loom` in Rust) to force the exact failing order: `Task A reads -> Task B reads -> Task A writes -> Task B writes` |
| **2. Wall-Clock & Monotonic Time** | `Date.now()`, `new Date()`, `performance.now()`, `time.time()`, TTL expiration | Inject a `Clock` interface or freeze fake timers (`vi.useFakeTimers()`, `sinon.useFakeTimers()`, `freezegun`) at the exact boundary millisecond (e.g. `23:59:59.999Z`) |
| **3. Entropy & PRNG Seeds** | `Math.random()`, `random.randint()`, `crypto.randomUUID()`, property-based fuzzers | Seed the PRNG explicitly (`SEED=0xDEADBEEF`), capture and replay the failing fuzzer seed (`fast-check` / `Hypothesis`), or inject a deterministic ID sequence generator |
| **4. Collection & Query Ordering** | SQL `SELECT` without `ORDER BY`, parallel `Promise.all` push order, Go map iteration | Force explicit adversarial ordering in test fixtures (e.g. reverse arrival order) and verify invariant holds |
| **5. Resource Contention & Chunking** | TCP packet fragmentation, stream chunk boundaries, CPU throttling | Feed the parser a deterministic stream that splits chunks mid-character or mid-JSON-token (e.g. `1 byte` per chunk) |

---

## 2. Pinning Async Race Conditions (Barrier / Latch Injection)

### The Anti-Pattern: `sleep()` Roulette
```typescript
// PROHIBITED: Relies on OS timer luck; flakes on busy CI runners
const p1 = service.withdraw(accountId, 100);
await new Promise((r) => setTimeout(r, 10)); // Hoping p1 passed SELECT but hasn't hit UPDATE
const p2 = service.withdraw(accountId, 100);
```

### The Surgical Pattern: Deterministic Rendezvous Barrier
Instead of guessing how many milliseconds a query takes, control the exact interleaving in your test double or storage seam using deterministic promises (`Promise.withResolvers()`):

```typescript
// DETERMINISTIC: Forces 100% TOCTOU overlap on every single run without timers
export class DeterministicBarrier {
  private arrived = 0;
  private readonly gate = Promise.withResolvers<void>();

  constructor(private readonly parties: number) {}

  async wait(): Promise<void> {
    this.arrived += 1;
    if (this.arrived >= this.parties) {
      this.gate.resolve();
    }
    await this.gate.promise;
  }
}
```

When two concurrent callers hit `storage.getBalance()` in the reproduction test, the test storage adapter awaits `readBarrier.wait()` before returning the balance to both callers simultaneously. Both callers are now guaranteed—with mathematical certainty—to observe the exact same pre-mutation balance before either executes `storage.setBalance()`.

---

## 3. Language-Specific Determinism Tools

- **TypeScript / JavaScript (Bun / Vitest):**
  - Freeze clocks: `vi.setSystemTime(new Date("2026-11-10T00:00:00.000Z"))`
  - Property-based seed pinning: `fc.assert(property, { seed: 1482910421, path: "4:1:0" })`
  - Async ordering: `Promise.withResolvers()` rendezvous barriers inside repository ports.
- **Python (`unittest` / `pytest`):**
  - Pin RNG: `random.seed(42)`, `numpy.random.seed(42)`
  - Pin Hypothesis seed: `@seed(318492019284)` or `@reproduce_failure(...)`
  - Asyncio barrier: `asyncio.Barrier(2)` or `asyncio.Event()` inside mock coroutines.
- **Rust (`cargo test` / `loom` / `proptest`):**
  - Exhaustive concurrency permutation checking: `loom::model(|| { ... })` explores all valid C11 memory-model threadavings deterministically.
  - Seeded RNG: `StdRng::seed_from_u64(0xCAFEBABE)`
- **Go (`go test` / `testing/synctest`):**
  - Race detector: `go test -race -count=1 ./...`
  - Deterministic virtualized concurrency time (Go 1.24+): `synctest.Run(func() { ... })` with `synctest.Wait()`.
