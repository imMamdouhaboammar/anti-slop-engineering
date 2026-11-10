# Playbook 2: Property-Based, Metamorphic & Seeded Deterministic Chaos Testing

## 1. Killing `2 + 2 = 4` Example Slop with Property-Based Testing (PBT)

Static example tests verify only the specific points the author thought of (`allocate(100, [50, 50]) -> [50, 50]`). Bugs live in the discontinuities between those points: prime numbers (`allocate(100, [3333, 3333, 3334])`), zero weights, boundary integers (`Number.MAX_SAFE_INTEGER`), negative adjustments, surrogate-pair UTF-16 strings, and interleaved state transitions.

### 1.1 The Four Universal Invariant Archetypes

| Archetype | Mathematical Formulation | Target Domains |
| --- | --- | --- |
| **Conservation Laws** | $\sum_{i=1}^{k} \text{out}_i + \text{fee} = \text{in}_{\text{total}}$ | Financial ledger splits, tax/discount proration, inventory allocation, token bucketing |
| **Invertibility (Roundtrip)** | $\forall x \in \mathcal{D},\ \text{decode}(\text{encode}(x)) \equiv x$ | Binary/JSON wire codecs, AST parsers, cursor token serializers, URL state encoders |
| **Idempotency & Algebraic Laws** | $f(f(s, m)) \equiv f(s, m)$ and $a \oplus b = b \oplus a$ | Webhook handlers, CRDT state mergers, deduplication stores, retryable RPCs |
| **State Machine Safety** | $\forall \vec{c} \in \text{Commands}^*,\ \text{Valid}(\delta^*(s_0, \vec{c}))$ | Order/escrow lifecycles, auth session machines, workflow orchestrators, raft/lease locks |

### 1.2 Metamorphic Testing (When No Exact Oracle Exists)
When computing the exact expected output for an arbitrary input $x$ would require duplicating the production algorithm inside the test, test **Metamorphic Relations** between a source input $x$ and a transformed follow-up input $T(x)$:
- **Permutation Invariance:** Shuffling the arrival order of independent ledger line items must yield the exact same account trial balance.
- **Additive / Multiplicative Scaling:** Splitting $A + B$ cents across fixed integer weights must never allocate less to any participant than splitting $A$ cents alone ($A, B \ge 0$).
- **Restriction / Filter Subsumption:** Adding an additional filter predicate `AND status = 'SETTLED'` to a query engine must return a strict subset of the unfiltered query results.

---

## 2. Seeded Deterministic Chaos Testing (FoundationDB / TigerBeetle Discipline)

Distributed and transactional bugs rarely appear when the network is healthy. They appear when:
1. A database transaction fails halfway through a multi-table mutation.
2. A downstream service **commits** a state mutation, but the TCP connection drops before the `200 OK` receipt returns to the caller (**Post-Commit ACK Drop**).
3. Two workers race on the same resource while retry timers fire under clock skew.

### 2.1 Ban `Math.random()` and `setTimeout` in Tests
Using `Math.random()` to inject faults makes test failures unreproducible. Using `setTimeout` makes retry tests slow and timing-dependent.
Instead, build every chaos simulation on two deterministic primitives:

1. **Seeded PRNG (`DeterministicPrng` - e.g. Mulberry32 / Xorshift32):**
   - Initialized with an explicit 32-bit integer seed (`0x5EED0001`).
   - Drives every fault decision (`nextFloat() < faultRate`), packet reorder, and backoff jitter calculation.
   - Logged on failure (`Chaos failure reproduced with seed=0x5EED0001`) so any CI failure replays identically in `< 1ms`.
2. **Deterministic Virtual Clock (`VirtualClock`):**
   - Replaces `Date.now()` and `setTimeout`.
   - Advancing retry backoff (`clock.advanceMs(1500)`) immediately expires TTLs, leases, and retry timers without pausing the CPU thread.

### 2.2 The Mandatory Chaos Fault Matrix

Every state-mutating service and retry loop must survive this seeded fault schedule:

| Fault Class | Injection Point | Required System Invariant |
| --- | --- | --- |
| `pre_commit_abort` | Throw before storage snapshot commits | Transaction rolls back cleanly; zero dirty/partial state remains in fake storage |
| `post_commit_ack_drop` | Commit mutation to storage, then throw `NetworkTimeoutError` before returning receipt | Caller retries with identical `Idempotency-Key`; storage replays the committed receipt with **zero duplicate side effects** |
| `transient_cas_conflict` | Simulate concurrent version bump (`ConcurrencyConflictError`) | Retry loop backs off with seeded jitter on `VirtualClock`, reloads fresh state, and either succeeds once or aborts cleanly |
| `duplicate_out_of_order_delivery` | Deliver the same webhook/event payload 3 times across skewed virtual timestamps | State transitions once; stale/duplicate events are ignored deterministically |

---

## 3. Red-Green Mutation Falsification Protocol

Before signing off on any verification oracle:
1. **Mutate Production:** Introduce one deliberate semantic bug into the production target (e.g., comment out `this.restoreSnapshot(snapshot)` on rollback, change remainder distribution so 1 cent is dropped, or bypass the `Idempotency-Key` lookup).
2. **Confirm RED:** Run the test suite and verify that the Contract Suite, Property Generator, or Seeded Chaos test fails immediately and reports the exact counterexample or seed.
3. **Restore & Confirm GREEN:** Revert the deliberate mutation and re-run the full suite. Record the falsified mutation in the Verification Oracle Record (`mutation_falsification`).
