# Playbook 2: Deterministic Concurrency & Heisenbug Eradication

Intermittent bugs—flaky CI tests, rare double-spends, lost WebSocket frames, and midnight timezone glitches—survive in production for months because engineers treat them as probabilistic events. In reality, software execution is strictly deterministic once you control **the thread/task schedule, the clock, and the entropy source**.

---

## 1. Why `sleep()` Is a Critical Engineering Defect

Adding `await sleep(200)` in a test to "wait for async work to finish" or in production code to "let the database settle" violates Google SRE and Meta reliability doctrine:
- **In Tests:** `sleep(200)` wastes wall-clock time on fast machines and **still flakes** on heavily loaded CI containers when GC pauses or CPU throttling stretches the operation to `210ms`.
- **In Production:** `sleep()` shifts the timing window slightly under low traffic while guaranteeing catastrophic failure under high-concurrency load spikes.

### The Replacement: Explicit Event & Barrier Coordination
Never synchronize on *elapsed wall-clock duration*; synchronize on *causal state transitions*:
- Use **Rendezvous Barriers** (`DeterministicBarrier`) to force concurrent tasks to collide at the exact critical section in tests.
- Use **Deferred Latches** (`Promise.withResolvers()`, `asyncio.Event`, `chan struct{}`) to pause a background worker at a precise checkpoint until the foreground test asserts intermediate state.

---

## 2. Deterministic Concurrency Recipes for Common RaceArchetypes

### Archetype 1: Read-Modify-Write / TOCTOU Double-Spend
- **Fault Mechanism:** Request A and Request B both execute `SELECT balance` before either executes `UPDATE balance`.
- **Determinism Pinning:** Inject a 2-party barrier at the end of `getBalance()` in the test storage adapter. Launch Request A and Request B via `Promise.all([reqA, reqB])`. Both requests block at the barrier until both have read the initial balance (`100`), then release simultaneously.
- **Result:** The race triggers **100% of the time** in `< 2ms` with zero `setTimeout` calls.
- **Surgical Fix:** Replace two-step Read-then-Write with an atomic conditional mutation (`UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1`), optimistic concurrency version check (`WHERE version = $3`), or per-key idempotency lock.

### Archetype 2: Out-of-Order Async Response Overwrite (Stale Closure / Stale Fetch)
- **Fault Mechanism:** User triggers Request 1 (`query="re"`), then 50ms later triggers Request 2 (`query="react"`). Request 2 finishes in 20ms, but Request 1 hits a slow shard and finishes in 300ms, overwriting the UI or cache state with stale data from Request 1.
- **Determinism Pinning:** Replace the network client in the test with a controllable map of deferred promises (`latches.get("re")`, `latches.get("react")`). Resolve `latches.get("react")` first, then resolve `latches.get("re")` second.
- **Result:** Fails 100% deterministically on every test run.
- **Surgical Fix:** Bind an `AbortController` per request cycle (aborting Request 1 when Request 2 starts) or guard state updates with a monotonic request generation counter (`if (reqId !== latestReqId) return;`).

### Archetype 3: Shared Mutable Buffer / Singleton Bleed Across Concurrent Requests
- **Fault Mechanism:** A module-level singleton object, regex with `/g` stateful `lastIndex`, or shared header dictionary is mutated across `await` boundaries by concurrent requests.
- **Determinism Pinning:** Pause Request A at the `await` point inside the function while Request B executes through the same singleton with different tenant data, then resume Request A.
- **Surgical Fix:** Eliminate module-level mutable state; scope state strictly to request-local stack allocations or immutable value objects.

---

## 3. Freezing Time and Entropy Boundaries

1. **Boundary-Value Clock Freezing:**
   - Do not test date logic at `14:22:10 UTC`. Freeze the clock at the exact discontinuity boundaries:
     - Leap day transition: `2028-02-28T23:59:59.999Z` $\to$ `2028-02-29T00:00:00.000Z`
     - Month-end truncation: `2026-01-31T23:59:59.999Z`
     - Token expiration boundary: `issuedAt + ttlMs - 1` (valid) vs. `issuedAt + ttlMs` (expired).
2. **PRNG Seed Capture & Replay:**
   - Every test that uses randomized inputs or jittered backoff must accept a deterministic `seed` or injected `random(): number` function.
   - Pin the exact failing seed in the regression test so it replays the identical sequence forever.

---

## 4. The Red-Green-Revert Verification Gate

Before closing any bug investigation:
1. **RED:** Execute the deterministic reproduction test against unpatched production code $\implies$ Must fail 100% of the time.
2. **GREEN:** Apply the minimal surgical fix $\implies$ Must pass 100% of the time.
3. **REVERT (Falsification Proof):** Temporarily comment out or revert the production fix line while keeping the test $\implies$ Must immediately fail (`RED`) again. This proves the test actually guards the causal fault and did not pass due to a broken assertion.
4. **CLEAN:** Restore the fix and verify `git diff` contains zero temporary `console.log`/`print` debug probes.
