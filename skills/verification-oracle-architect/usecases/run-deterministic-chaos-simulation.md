# Workflow: Run a Seeded Deterministic Chaos Simulation

Use this workflow when testing retry loops, distributed sagas, idempotency keys, webhook deduplication, optimistic locking retries, or transactional rollback recovery under network and storage faults.

## Step-by-Step Procedure

### 1. Eliminate `Math.random()` and Wall-Clock `setTimeout`
1. Replace all `Date.now()` and `sleep()` / `setTimeout` calls in the retry/lease path with an injected `VirtualClock` (`nowMs()`, `advanceMs(delta)`).
2. Instantiate a deterministic 32-bit PRNG (`SeededPrng` using `Mulberry32` or `Xorshift32`) initialized with an explicit hex seed (e.g., `0x5EED1001`).

### 2. Wrap the Verified In-Memory Fake in a Chaos Fault Proxy
Configure the chaos proxy to intercept storage/network operations and deterministically trigger:
1. **`pre_commit_connection_drop`:** Throw inside `withTransaction` after the first write but before commit, verifying that the fake's snapshot rollback restores `100%` of pre-transaction state.
2. **`post_commit_ack_drop`:** Allow `withTransaction` to commit the state and receipt inside storage, then throw `SimulatedNetworkDropError("post_commit_ack_drop")` before returning to the caller.
3. **`transient_cas_version_conflict`:** Simulate concurrent version interleaving (`OptimisticConcurrencyError`) to force retry backoff + state reload.
4. **`duplicate_out_of_order_delivery`:** Replay the same command/webhook multiple times across skewed virtual timestamps.

### 3. Execute Multi-Seed Simulation & Assert Global Invariants
1. Run the chaos simulation across a deterministic seed bank (e.g., `0x5EED1001`, `0x5EED1002`, `0x5EED1003`, ...).
2. After all retries settle, assert:
   - Total money across all accounts equals the initial trial balance ($\sum \text{balances}_{\text{after}} = \sum \text{balances}_{\text{before}}$).
   - Every completed `Idempotency-Key` produced **at most one** balance transfer, even when `post_commit_ack_drop` forced retries.
   - Zero partial or orphaned records exist from aborted `pre_commit_connection_drop` transactions.
   - On failure, log `Reproduce deterministic chaos failure with seed=0x...`.
