---
name: verification-oracle-architect
description: Enforces high-fidelity, zero-mock verification architecture—replacing banned module mocks (vi.mock, jest.mock, unittest.mock.patch) and weak static happy-path tests with Verified In-Memory Fakes backed by Shared Contract Test Suites, Property-Based & Metamorphic Testing (fast-check, Hypothesis, proptest), and Seeded Deterministic Chaos Fault Injection. Use when writing unit/integration/contract tests, replacing mocks, testing financial/ledger math, parsers, serializers, or state machines, verifying idempotency and rollback under network failures, or auditing test suites for tautological assertions — even if the user doesn't explicitly say "verification oracle". Do NOT use for purely visual CSS adjustments or static markdown copy edits that have no executable behavioral contract.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Verification Oracle Architect (Verified Fakes, Property Invariants & Deterministic Chaos)

> A mock proves only what you assumed the dependency would do. An example test proves only that `2 + 2 = 4` once. Build verification oracles that cannot be lied to: Contract-Verified In-Memory Fakes, Property-Based Invariants, and Seeded Deterministic Chaos.

## Why This Skill Is Needed & Target State

When strict engineering policies (`install-anti-slop` / `anti-slop/no-module-mocking`) ban `vi.mock`, `jest.mock`, `sinon.stub`, and `unittest.mock.patch`, AI coding agents frequently stall or regress into **Test-Oracle Slop**:
1. **Unverified Ad-Hoc Stubs:** Replacing `vi.mock()` with inline fake lambdas (`const repo = { save: async () => true }`) that ignore unique constraints, concurrency version checks, and transaction rollbacks—drifting silently from the real database.
2. **Toy Happy-Path Examples (`2 + 2 = 4`):** Testing financial split calculations, parsers, or state machines with two hardcoded inputs while missing penny-rounding drift, integer overflow, Unicode boundary corruption, and illegal state transitions.
3. **Fair-Weather Concurrency & Flaky `sleep()` Band-Aids:** Testing retry and rollback logic only when the network succeeds, or sprinkling `await new Promise(r => setTimeout(r, 100))` and unseeded `Math.random()` into tests, creating non-reproducible CI flakes.

The target state is **High-Fidelity Verification Architecture**:
1. **Verified In-Memory Fakes (`100%` Contract Parity):** Every in-memory fake adapter (`InMemoryLedgerRepository`) runs against the **exact same parameterized Contract Test Suite** (`runAdapterContractSuite`) as the production adapter (`PostgresLedgerRepository`).
2. **Property-Based & Metamorphic Oracles:** Financial arithmetic, parsers, serializers, and state machines are verified across hundreds of generated adversarial inputs (`fast-check`, `Hypothesis`, `proptest`, Go `rapid`) checking universal invariants (conservation of cents, roundtrip invertibility, idempotency, metamorphic scaling).
3. **Seeded Deterministic Chaos Testing:** Network delays, dropped connections mid-transaction, duplicate webhook deliveries, and clock skew are injected deterministically via a seeded PRNG (`seed: 0x5EED1234`) and Virtual Clock to prove atomic rollback and idempotency without a single `sleep()`.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Writing tests where the agent is tempted to use `vi.mock`, `jest.mock`, `sinon`, or `unittest.mock.patch` | Ban module mocking; extract a narrow Port interface and build a Stateful In-Memory Fake verified by a Shared Contract Test Suite |
| Testing financial calculations, fee/tax allocations, currency conversions, or billing ledgers | Require Property-Based Testing (`fast-check` / `Hypothesis` / `proptest`) asserting conservation of money ($\sum \text{parts} = \text{total}$) and integer-cent invariants |
| Testing parsers, compilers, serializers, URL/query codecs, or cryptographic envelopes | Require Property-Based Roundtrip (`decode(encode(x)) === x`) and adversarial boundary fuzzing |
| Testing state machines, workflow engines, order lifecycles, or permission gates | Require Property-Based Model/Transition testing proving no command sequence can reach a forbidden state |
| Testing retries, distributed sagas, webhooks, idempotency keys, or database transaction rollbacks | Require Seeded Deterministic Chaos fault injection (seeded PRNG + Virtual Clock) simulating mid-flight network drops, timeouts, and duplicate delivery |
| Auditing existing tests or PR test diffs for quality and falsifiability | Scan for banned module mocks, unverified inline stubs, toy 1-input assertions, unseeded `Math.random()`, `setTimeout` sleeps, and verify Red-Green mutation falsification |
| Static prose edits, README formatting, or pure visual CSS token tweaks without logic | Do not activate; use `anti-slop-engineering` or `apple-craft-and-frame-budget` |

---

## The Five Absolute Laws

1. **The Zero-Mock & Shared Contract Parity Law (Verified In-Memory Fakes):**
   - Module patching (`vi.mock`, `jest.mock`, `mock.module`, `unittest.mock.patch`, `monkeypatch`) and unverified one-liner return stubs (`mockResolvedValue`) are strictly prohibited for domain and persistence boundaries.
   - Instead, implement a **Stateful In-Memory Fake Adapter** that faithfully models constraints: primary/unique key collisions, composite tenant isolation (`org_id`), optimistic locking (`version` mismatch), cursor ordering, and atomic state snapshots on transaction rollback.
   - **Mandatory Contract Parity:** A Fake is illegal unless paired with a parameterized **Shared Contract Test Suite** (`describeRepositoryContract(factory)`) that executes identical behavioral assertions against both the `InMemoryFake` and the `RealAdapter`.
2. **The Property-Based & Metamorphic Invariant Law (Kill `2 + 2 = 4` Example Slop):**
   - Hardcoded example tests (`expect(splitInvoice(100, 3)).toEqual([34, 33, 33])`) are insufficient for algorithmic, financial, parsing, or state-machine logic.
   - You must define **Universal Invariants** and execute them over $\ge 100$ randomized, shrinkable inputs (`fast-check`, `Hypothesis`, `proptest`):
     - **Conservation Invariant:** Splitting, allocating, discounting, or transferring funds must conserve exact integer minor units ($\sum_{i} \text{allocation}_i = \text{principal}$) with zero cent creation or destruction.
     - **Invertibility (Roundtrip) Invariant:** For every valid domain structure $x$, $\text{parse}(\text{format}(x)) \equiv x$ and $\text{deserialize}(\text{serialize}(x)) \equiv x$.
     - **Idempotency & Commutativity Invariant:** Applying an idempotent mutation $N$ times yields the exact same state and response as applying it once: $f(f(s, op)) \equiv f(s, op)$.
     - **Metamorphic Relation Invariant:** When no closed-form oracle exists (e.g., search ranking, fee tiers, graph routing), assert how transforming the input predictably transforms the output (e.g., doubling all line-item quantities with a linear tax rate exactly doubles net tax; permuting arrival order of commutative ledger postings preserves final balance).
3. **The Seeded Deterministic Chaos Law (Reproducible Fault Injection):**
   - Never assume the network, disk, or downstream RPC succeeds cleanly, and never use non-deterministic `Math.random()` or wall-clock `setTimeout` sleeps in tests.
   - Inject faults through a **Deterministic Chaos Harness** controlled by an explicit 32-bit integer seed (`CHAOS_SEED`) and a controllable **Virtual Clock**:
     - Deterministically inject **Pre-Write Failures** (connection refused before mutation), **Mid-Flight / Post-Write Drops** (mutation committed in storage, but socket drops before ACK reaches caller), **Transient Serialization Conflicts (`40001` / `503`)**, **Out-of-Order / Duplicate Retries**, and **Clock Skew / Lease Expiry**.
     - Every chaos run must assert **State Invariant Recovery**: after retries complete or abort, zero partial/orphaned rows exist, balances reconcile to the cent, and any test failure prints the exact `seed` (`Reproduce with: CHAOS_SEED=0x9F4A2C01`) for instant deterministic replay.
4. **The Independent Oracle Law (Never Mirror Implementation in the Test):**
   - A test must never copy-paste the production formula to compute its expected value (`expect(calcFee(x)).toBe(Math.floor(x * 0.029 + 30))`). That only tests that two identical lines of code agree on the same bug.
   - Verify outputs via **Inverse Operations**, **Algebraic Conservation Laws**, **Reference Model Comparison** (comparing a complex optimized algorithm against a dead-simple $O(N)$ reference model in the test), or **Boundary Exhaustion**.
5. **The Red-Green Mutation Falsification Law:**
   - A test suite is unverified until proven capable of failing. Before declaring any test suite complete, perform a **Mutation Falsification Check**: deliberately break the core production invariant (e.g., skip the rollback restore, drop the remainder cent, or disable the idempotency check), confirm the new oracle fails immediately with a clear diagnostic, and restore the production fix.

---

## Invariant Rules

1. **Contract suites are parameterized by an adapter factory.** Write `export function runLedgerStorageContractSuite(name: string, createAdapter: () => Promise<LedgerStoragePort>)` once, and invoke it for `InMemoryLedgerStorage` in unit tests and `PostgresLedgerStorage` in integration tests.
2. **In-Memory Fakes must clone state across boundary reads/writes.** Never store or return direct mutable object references inside an In-Memory Fake; use `structuredClone()` or immutable snapshots so caller mutations cannot corrupt internal fake storage without calling `.save()`.
3. **In-Memory Fakes must support transactional rollback snapshots.** When simulating a transaction (`withTransaction(tx => ...)`), the fake must snapshot its state on entry and restore the exact snapshot if an error or chaos fault is thrown mid-transaction.
4. **Configure Property-Based Tests with explicit run counts and seed logging.** Always run at least `numRuns: 200` (or `max_examples=200` in Hypothesis) and ensure shrinking and seed reporting are enabled so counterexamples reduce to the minimal failing input.
5. **All time-dependent behavior uses an injected `Clock` port.** Ban `Date.now()` and `new Date()` inside testable domain/retry logic; inject `ClockPort { nowMs(): number; advanceMs(delta: number): void }` so TTL expiration, lease timeouts, and exponential backoff jitter execute in `0ms` of real wall-clock time.
6. **Distinguish Pre-Commit vs. Post-Commit Chaos Faults.** A chaos harness must test both *fail-before-commit* (nothing written, safe to retry or abort) and *fail-after-commit-before-response* (side effect occurred, caller timed out and retries with the same `Idempotency-Key`, which must return the original receipt without double-charging).
7. **Ban assertion-free and tautological tests.** Every test case must assert concrete state transitions and domain invariants—never `expect(result).toBeDefined()`, `expect(mockFn).toHaveBeenCalled()`, or `assert True`.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Replacing `vi.mock`/`jest.mock` or building a fast, high-fidelity test double for DB/RPC/Queue | [Build Verified In-Memory Fake](usecases/build-verified-in-memory-fake.md) | [Verified Fakes & Contracts](references/verified-in-memory-fakes-and-contracts.md) |
| Testing financial math, parsers, codecs, compilers, or state machines beyond static examples | [Author Property & Metamorphic Suite](usecases/author-property-and-metamorphic-suite.md) | [Property-Based & Metamorphic Testing](references/property-based-and-metamorphic-testing.md) |
| Testing retries, idempotency, transactional rollback, or distributed resilience under network faults | [Run Deterministic Chaos Simulation](usecases/run-deterministic-chaos-simulation.md) | [Deterministic Chaos & Fault Injection](references/deterministic-chaos-and-fault-injection.md) |
| Durable verification-oracle assessment record generation & audit | [Record Contract](references/verification-oracle-record-contract.md) | `scripts/verification_oracle_guard.py` |

---

## Mandatory Pre-Verification Interrogation Matrix

Before writing a single `describe()`, `test()`, or `def test_()` block, answer these five questions:

- **The Mock Elimination Check:** Am I reaching for `vi.mock`, `jest.mock`, `sinon.stub`, `unittest.mock.patch`, or an inline `{ method: () => fakeValue }` stub? If yes, **stop**. What is the Port interface, how does the Stateful In-Memory Fake enforce real constraints (uniqueness, tenant isolation, version locking, rollback), and where is the Shared Contract Test Suite that proves parity with the real adapter?
- **The Invariant vs. Example Check:** If I am testing calculations, allocations, parsing, serialization, or state transitions, what universal mathematical or structural invariant holds for *all* valid inputs $x \in \mathcal{X}$? Why am I writing a single `2 + 2 = 4` example when a property generator (`fc.assert(fc.property(...))`) can test 500 edge cases (0, negative, `MAX_SAFE_INTEGER`, remainder cents, empty strings, Unicode) automatically?
- **The Post-Commit Chaos Check:** What happens when the database or payment gateway *commits* the write on attempt #1, the network socket drops before the response arrives, and the caller retries attempt #2 with the same `Idempotency-Key`? Does our Seeded Chaos Harness prove the system neither double-executes nor corrupts state?
- **The Determinism & Zero-Sleep Check:** Does this test rely on wall-clock `setTimeout`, `sleep()`, or unseeded `Math.random()`? If this test fails on CI at 3:00 AM, what exact 32-bit `seed` reproduces the exact fault interleaving on a developer's laptop in `1ms`?
- **The Mutation Falsification Check:** Which specific line of production code did I temporarily mutate to prove that this test suite turns RED when the invariant is violated?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Module Mocking (`vi.mock`, `jest.mock`, `unittest.mock.patch`, `sinon.stub`):** Patching module imports or spying on internal implementation calls (`expect(repo.save).toHaveBeenCalledWith(...)`) instead of asserting observable state in a Contract-Verified In-Memory Fake.
2. **Unverified Inline Stubs (Divergent Fakes):** Creating ad-hoc mock objects inside test files that return hardcoded happy-path payloads while ignoring constraints (e.g., allowing duplicate keys, skipping version increments, or mutating objects in place without rollback).
3. **Static Happy-Path Example Slop on Rich Domains:** Testing financial splits, tax calculations, parsers, or state machines exclusively with 1–3 hand-picked integers (`100`, `200`) instead of Property-Based generators (`fast-check` / `Hypothesis` / `proptest`).
4. **Tautological Implementation-Mirroring Oracles:** Computing the `expected` value in a test by copying the exact production formula (`expect(fn(a, b)).toBe(productionFormula(a, b))`) or asserting only `toBeDefined()` / `toBeTruthy()`.
5. **Unseeded Randomness in Tests (`Math.random()`, `random.random()`, `uuid4()` without seed):** Generating random test inputs or fault schedules without a deterministic, logged PRNG seed, making failures impossible to replay.
6. **Wall-Clock `sleep()` / `setTimeout` Synchronization in Tests:** Waiting real milliseconds/seconds for timeouts, retries, or TTL expirations instead of driving an injected Virtual Clock deterministically.

---

## Required Output & Review Workflow

Structure all test engineering, mock-replacement refactors, and resilience verification tasks through this 4-phase discipline:

1. **Boundary & Invariant Specification:** Define the Port interface, list the storage/protocol invariants the In-Memory Fake must enforce, specify the Universal Domain Properties (conservation, invertibility, idempotency, state-machine safety), and define the Chaos Fault Catalog.
2. **Verified Fake & Shared Contract Suite Implementation:** Implement the Stateful In-Memory Fake (with `structuredClone` isolation, optimistic locking, and transactional rollback snapshots) alongside the parameterized Shared Contract Test Suite (`runContractSuite`) targeting both Fake and Real adapters.
3. **Property-Based & Seeded Deterministic Chaos Suite:** Author the property-based generators (`fast-check` / `Hypothesis` / `proptest`) and the Seeded Deterministic Chaos Harness (PRNG + Virtual Clock) testing pre-commit drops, post-commit ACK drops, duplicate retries, and rollback recovery.
4. **Mutation Falsification & Guard Audit:** Verify Red-Green falsification against a deliberate production mutation and audit the verification record and test source with `scripts/verification_oracle_guard.py`.

When a durable verification-oracle record is warranted, save a JSON assessment following the [Verification Oracle Record Contract](references/verification-oracle-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering verification-oracle audit <record.json> --json
# or: python3 scripts/verification_oracle_guard.py audit <record.json> [--source <test_file.ts>] --json
```

---

## Domain References

- **[Verification Oracle Architect Playbook Suite](playbooks/README.md)**: Central orchestration index for zero-mock verification, property testing, and deterministic simulation.
- **[Verified In-Memory Fakes & Shared Contract Suites Playbook](playbooks/verified-fakes-and-contract-suites-playbook.md)**: Port/Adapter boundaries, stateful in-memory fake mechanics (rollback snapshots, `structuredClone`, CAS versioning, unique keys), and parameterized contract test suites across Fake and Real DB adapters.
- **[Property-Based, Metamorphic & Deterministic Chaos Playbook](playbooks/property-based-and-deterministic-chaos-playbook.md)**: Algebraic invariants, metamorphic testing relations, stateful model-based command testing, seeded PRNG fault injection (FoundationDB/TigerBeetle deterministic simulation style), and Virtual Clocks.
- **[Verified In-Memory Fakes & Contracts Reference](references/verified-in-memory-fakes-and-contracts.md)**: Production TypeScript, Python, Rust, and Go templates for contract-verified fakes and transactional snapshot rollback.
- **[Property-Based & Metamorphic Testing Reference](references/property-based-and-metamorphic-testing.md)**: Invariant catalogs and `fast-check` / `Hypothesis` / `proptest` recipes for financial math, codecs, and state machines.
- **[Deterministic Chaos & Fault Injection Reference](references/deterministic-chaos-and-fault-injection.md)**: Seeded PRNG (`Mulberry32`), Virtual Clock, Pre-Commit vs. Post-Commit fault injection, and idempotency/rollback verification.
- **[Verification Oracle Record Contract](references/verification-oracle-record-contract.md)**: JSON schema and verification rules for `scripts/verification_oracle_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Banned module mock regression | Test imports `vi.mock`, `jest.mock`, `sinon.stub`, or `unittest.mock.patch` | Delete module mock; extract Port interface and inject a Contract-Verified In-Memory Fake |
| Divergent fake drift | Unit tests pass against fake, but production fails on unique constraint or rollback | Run the parameterized Shared Contract Test Suite against both `InMemoryFake` and `RealAdapter` |
| Penny-rounding / boundary leak | Static test `split(100, 2)` passes, but `split(100, 3)` loses `1` cent in prod | Replace static example with a `fast-check` / `Hypothesis` conservation property ($\sum \text{parts} = \text{total}$) over `200+` runs |
| Post-commit retry double-charge | Network drops after DB commit; retry executes a second charge | Inject `post_commit_ack_drop` fault via Seeded Chaos Harness and enforce atomic `Idempotency-Key` receipt replay |
| Non-reproducible CI flake | Test uses `Math.random()` or `setTimeout(..., 50)` and fails 1 in 40 runs | Replace with explicit seeded PRNG (`seed: 0x5EED1234`) and deterministic `VirtualClock` |
| Tautological green suite | Production bug introduced, yet all unit tests stay green | Enforce Red-Green Mutation Falsification; replace implementation-mirroring expectations with independent algebraic oracles |

---

## Delegated Skills

- `anti-slop-engineering`: Enforce Gate 2 (Test Integrity) and Gate 4 (Verify Beyond Green Tests) alongside verification oracle construction.
- `install-anti-slop`: Enforce `anti-slop/no-module-mocking` at the linter level while using `verification-oracle-architect` to build the architectural replacement.
- `scientific-fault-isolation`: When a property test or deterministic chaos seed uncovers a minimal failing counterexample, use the 4-step root-cause isolation protocol.
- `paranoid-principal-architect`: Pair deterministic chaos testing with 10M-concurrent-user idempotency keys, CAS optimistic locking, and zero-trust boundary schemas.

---

## Completion and Limits

The task is complete when all banned module mocks (`vi.mock`, `jest.mock`, `unittest.mock.patch`) and unverified inline stubs are replaced by a Stateful In-Memory Fake passing a Shared Contract Test Suite (`100%` parity with the real adapter), universal domain invariants are verified via Property-Based / Metamorphic tests (`>= 100` runs with shrinking), resilience and rollback are proven under Seeded Deterministic Chaos fault injection with a Virtual Clock (zero `sleep()` calls), Red-Green mutation falsification is confirmed, and `scripts/verification_oracle_guard.py` reports zero findings. A review may validly output `refuse` or `pause` if a test suite relies on module mocking, unseeded randomness, or lacks contract parity proof.
