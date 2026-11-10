# Workflow: Deflake Race Condition & Pin Determinism

Use this workflow when investigating intermittent test failures, concurrency race conditions (TOCTOU, lost updates, out-of-order events, deadlocks), clock/timezone boundary bugs, or PRNG-dependent failures.

## Step-by-Step Procedure

### 1. Identify the Hidden Non-Deterministic Input
Audit the suspect code path for every unpinned environmental dependency:
- **Concurrency Schedule:** Multiple promises, worker threads, or database transactions executing without a deterministic coordinator.
- **System Clock:** Calls to `Date.now()`, `new Date()`, `performance.now()`, or TTL expirations near millisecond/day boundaries.
- **Randomness:** Calls to `Math.random()`, unseeded fuzzers, or random jitter loops.
- **Ordering:** Unordered SQL queries, hash-map iteration, or `Promise.all` resolution order.

### 2. Inject Deterministic Pinning Seams (Zero `sleep()` Allowed)
1. **For Concurrency Races:**
   - Identify the critical window (e.g. between `readState()` and `writeState()`).
   - In the test double or storage port, inject a deterministic **Rendezvous Barrier** (`DeterministicBarrier(2)` using `Promise.withResolvers()`, `asyncio.Barrier(2)`, or `sync.WaitGroup` + channel latch).
   - Hold Fiber/Thread A at the midpoint after its read until Fiber/Thread B also completes its read, then release both simultaneously to force the race collision on 100% of runs.
2. **For Time-Sensitive Bugs:**
   - Replace wall-clock calls with an injected `Clock` port or fake timer frozen at the exact edge timestamp (e.g. `2026-11-10T23:59:59.999Z` or token expiry boundary `exp * 1000`).
3. **For Seed-Sensitive Bugs:**
   - Pin the PRNG seed explicitly (`seed = 0x5F3759DF`) and log the seed in the test assertion message.

### 3. Verify 100% Red Determinism
Run the isolated reproduction test repeatedly (e.g. 10 consecutive iterations) **before** touching production code:
- Every single run must fail (`RED`) with the exact target symptom.
- If the test passes even once out of 10 runs while the bug is still present, your determinism pinning is incomplete—tighten the barrier or clock pin before proceeding.

### 4. Apply Surgical Fix & Execute Red-Green-Revert Falsification
1. Implement the minimal synchronization or invariant fix (e.g. atomic compare-and-swap, transactional row lock, `AbortController` cancellation of stale requests, or UTC normalization).
2. Run the pinned test $\implies$ must pass **10/10 times (`GREEN`)**.
3. Temporarily revert only the production fix $\implies$ must fail **10/10 times (`RED`)**.
4. Restore the production fix, strip all temporary debug probes, and run the full test suite.
