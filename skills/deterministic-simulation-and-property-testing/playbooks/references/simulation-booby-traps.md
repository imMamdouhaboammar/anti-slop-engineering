# Simulation & Property Testing Booby-Traps

Common anti-patterns and failure mechanics in simulation, property-based testing, state-machine modeling, and fuzzing.

## 1. Unseeded PRNG Leakage

- **Symptom:** A race condition or invariant violation is discovered in CI, but re-running the test passes cleanly.
- **Root Cause:** A component or library under test calls `Math.random()`, `random.random()`, or `crypto.randomUUID()` internally instead of using an injected PRNG instance.
- **Remedy:** Inject a deterministic PRNG interface (`Mulberry32` or `PCG32`) into all system constructors. Ban ambient random sources in static linting via `scripts/simulation_guard.py`.

## 2. Real Wall-Clock Pollution

- **Symptom:** Simulation tests take 45 seconds to run, occasionally time out under heavy CI CPU load, and fail intermittently.
- **Root Cause:** Developers used `setTimeout(..., 100)` or `time.sleep(0.1)` to wait for asynchronous network events instead of advancing a virtual clock.
- **Remedy:** Mandate a `DeterministicVirtualClock`. Virtual time advances instantaneously to the next event in the queue. Physical sleep calls are blocked.

## 3. Shallow Shrinkers & Generator Bias

- **Symptom:** Property tests pass 10,000 iterations, but production crashes on the first day.
- **Root Cause:** The arbitrary generator had subtle bias (e.g. only generated positive integers $[1, 100]$ or non-empty strings), completely omitting `0`, `-1`, `NaN`, `Number.MAX_SAFE_INTEGER`, empty strings, or null bytes.
- **Remedy:** Audit generator coverage with custom distribution checks. Ensure generators explicitly include boundary values and negative domains. Verify automatic shrinking works by introducing a deliberate mutation.

## 4. Boolean Bag State Explosion

- **Symptom:** Edge cases arise where an entity is simultaneously marked as `isCompleted === true` and `isFailed === true`, resulting in double billing or corrupted inventory.
- **Root Cause:** State is stored as multiple mutable boolean flags on a single entity record.
- **Remedy:** Replace boolean flags with strict Tagged Unions or Algebraic Data Types. Make impossible states unrepresentable in the type system.

## 5. Dumb Byte Fuzzing on Grammar-Bound Parsers

- **Symptom:** Fuzzer runs for 24 hours with zero crashes found, but a user payload with a deep JSON structure crashes the server immediately.
- **Root Cause:** A dumb bit-flipping fuzzer mutated raw bytes, so $99.99\%$ of generated payloads failed initial JSON tokenization at byte 0, never reaching the semantic parser.
- **Remedy:** Implement structure-aware fuzzing using grammar-based tree generators that construct valid or near-valid syntax trees with extreme field values and nesting depths.

## 6. Tautological Property Tests

- **Symptom:** Property tests pass with $100\%$ green badges, but catch zero bugs.
- **Root Cause:** The property assertion mirrors the exact implementation formula (e.g. testing `calcTotal(x, y)` by asserting `result === x + y`, where `calcTotal` is implemented as `return x + y`).
- **Remedy:** Test external invariants: round-trip invertibility, conservation laws, metamorphic relations, or equivalence against an independent reference oracle.
