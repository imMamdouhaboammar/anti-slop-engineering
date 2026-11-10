---
name: deterministic-simulation-and-property-testing
description: Enforces Microsoft Research and AWS rigorous testing discipline. Use when testing distributed consensus, stateful workflows, actor concurrency, codecs/parsers, or untrusted boundaries using Property-Based Testing (fast-check, Hypothesis), Deterministic Simulation Testing (DST with virtual clocks and reproducible seeds), formal State-Machine Modeling with impossible states made unrepresentable, and Structure-Aware Fuzzing — even if they don't explicitly say "deterministic simulation". Do NOT use for trivial UI styling tweaks, simple static text changes, or routine non-consequential scripts.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Deterministic Simulation & Property Testing (Microsoft Research & AWS Rigor)

> Example-based tests verify happy paths; deterministic simulation and property oracles prove mathematical invariants and survive real-world chaos.

## Why This Skill Is Needed & Target State

Standard automated tests suffer from the "example-based test trap": developers write 2-3 static, hardcoded scenarios that verify the code works under expected, happy-path conditions. In production, distributed race conditions, packet loss, message reordering, clock skews, corrupted state machines, and untrusted malformed inputs cause catastrophic outages that example tests never anticipate.

The target state is **formal engineering rigor inspired by Microsoft Research (Coyote, P, Orleans) and AWS/FoundationDB Hermetic Simulation**:
1. Every domain invariant is validated across thousands of pseudo-random inputs via Property-Based Testing with automatic shrinking.
2. Every distributed interaction, network drop, clock skew, and message reordering is simulated deterministically via Discrete Event Simulation with a virtual clock and a reproducible 64-bit seed.
3. Every state machine explicitly defines its transition table and makes impossible states unrepresentable in the type system.
4. Every parser, deserializer, and boundary entry point is subjected to structure-aware fuzzing to guarantee crash freedom and bounded resource consumption.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Authoring or testing distributed systems, consensus, or replication | Mandate Deterministic Simulation Testing (DST) with virtual clock and seeded fault injection |
| Implementing business logic with conservation, round-trip, or idempotency rules | Enforce Property-Based Testing (fast-check, Hypothesis, proptest) with shrinking |
| Designing lifecycles, connection management, or stateful workflows | Construct an explicit State Transition Table; eliminate impossible states via tagged unions |
| Writing or modifying parsers, deserializers, or untrusted boundary decoders | Require Structure-Aware Fuzzing asserting crash freedom, depth limits, and byte caps |
| PR relying exclusively on static example tests for critical invariants | Flag as insufficient; demand property tests or seeded simulation proofs |
| Routine UI styling tweaks, copy typos, or non-consequential local scripts | Do not activate; use standard Anti-Slop Engineering BUILD/FIX gates |

---

## The Four Foundational Pillars

### 1. Property-Based Testing (PBT) & Shrinking
Static examples provide zero proof of invariant correctness across the domain space. Agents must write property tests that generate thousands of randomized inputs to stress invariants. When a failure occurs, the framework must automatically shrink the failing input to its minimal reproducible counterexample.

### 2. Deterministic Simulation Testing (DST)
Real wall-clock timeouts (`setTimeout`, `time.sleep`) create slow, flaky tests that fail to surface edge-case race conditions. All simulation must use Discrete Event Simulation (DES) driven by an injected virtual clock and a seeded pseudo-random number generator (PRNG). Network drops, latency jitter, clock skew, and message reordering must be 100% reproducible bit-for-bit from the root seed.

### 3. State-Machine Formal Modeling & Type Safety
Boolean flag bags (`isLoading`, `isError`, `isSuccess`) allow invalid, corrupted state permutations ($2^N$). State machines must make impossible states unrepresentable using tagged unions or algebraic data types. State transitions must be governed by an explicit transition matrix ($State \times Event \to NextState + Effects$) and validated through generative model-based testing.

### 4. Structure-Aware Fuzzing on Untrusted Boundaries
Dumb byte-flipping fuzzers fail on structured protocols because inputs are rejected at byte 0. All parsers, deserializers, and schema decoders must be tested using grammar-aware, structure-aware fuzz harnesses that generate valid syntax trees with pathological leaf values, deep nesting, and boundary edge cases.

---

## Invariant Rules

1. **Ban example-based tests as the sole verification of critical invariants.** Code that computes money, mutates critical state, or decodes untrusted input must include property-based or fuzz tests.
2. **Zero real wall-clock sleeps in simulation code.** `setTimeout`, `sleep()`, and `Date.now()` are forbidden in simulation harnesses; all delays must be scheduled through a `DeterministicVirtualClock`.
3. **Explicit seeded PRNG for all simulation & property generation.** Unseeded `Math.random()`, `random.random()`, or ambient system entropy are prohibited in test execution paths.
4. **Mandatory shrinking on property failures.** Any property testing setup must support automated shrinking to minimal counterexamples.
5. **No boolean bags for state representation.** Replace independent boolean flags with strict tagged unions, ADTs, or sealed traits.
6. **Explicit state transition completeness.** Every state machine must define an exhaustive transition matrix and reject undefined transitions deterministically.
7. **Crash-freedom on untrusted parsers.** Parsers must never panic, segfault, or throw unhandled exceptions when fed fuzzed inputs.
8. **Bounded recursion depth and payload byte limits.** Every parser must enforce explicit recursion counters ($\le 16$ levels) and byte caps ($\le 10\text{MB}$) to eliminate call-stack and allocation bombs.
9. **Red-green mutation falsification.** A property or simulation suite is unverified until a deliberate invariant mutation fails the test and produces an observable counterexample.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Specification |
| --- | --- | --- |
| Distributed system, actor engine, or consensus testing | [Build Deterministic Simulator](usecases/build-deterministic-simulator.md) | [Discrete Event Simulation](references/discrete-event-simulation-and-fault-injection.md) |
| Mathematical invariants, ledgers, or round-trip codecs | [Author Property Tests](usecases/author-property-tests.md) | [Property-Based Testing](references/property-based-testing-and-shrinking.md) |
| Lifecycle, workflow, or protocol state machine | [Model State Machine](usecases/model-state-machine.md) | [State-Machine Modeling](references/state-machine-modeling-and-type-invariants.md) |
| Untrusted parser, deserializer, or decoder boundary | [Fuzz Parser Boundaries](usecases/fuzz-parser-boundaries.md) | [Structure-Aware Fuzzing](references/structure-aware-fuzzing-and-parsers.md) |
| Persistent simulation audit record generation & verification | [Record Contract](references/simulation-record-contract.md) | `scripts/simulation_guard.py` |

---

## Mandatory Pre-Execution Interrogation Matrix

Before writing or approving tests, subject the suite to this matrix:

- **Distrust of Examples:** Are we testing only 2 or 3 happy-path examples? What happens when input is empty, negative, max-int, contains Unicode null bytes, or is deeply nested?
- **Distrust of Time:** Does this test rely on `setTimeout`, `time.sleep()`, or real wall-clock delays? How will this test behave on a heavily loaded CI runner with 100% CPU contention?
- **Distrust of Flakiness:** If this test fails in CI, can an engineer immediately reproduce the exact failure locally using a single command and seed?
- **Distrust of State:** Can this entity ever be in an invalid state combination? Why are there 4 boolean flags instead of a single tagged union?
- **Distrust of Untrusted Input:** What happens if an adversary sends a 5MB payload with 10,000 nested brackets? Will the parser stack overflow, OOM the process, or reject it in 5ms?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Unseeded Randomness in Tests:** Using `Math.random()` or `random.random()` without an explicit seed, creating non-reproducible CI failures.
2. **Wall-Clock Sleeps as Sync Band-Aids:** Using `await sleep(500)` or `setTimeout` to wait for background tasks in distributed tests.
3. **Boolean State Bags:** Defining interfaces with multiple mutable boolean flags (`isLoading`, `isError`, `isSuccess`) allowing illegal permutations.
4. **Tautological Property Assertions:** Asserting `expect(add(a, b)).toBe(a + b)` where `add` is implemented as `return a + b`, without testing independent algebraic properties.
5. **Dumb Byte Fuzzing on Grammar Inputs:** Throwing raw random bytes at a JSON parser and claiming high fuzz coverage when $99.9\%$ of inputs fail at byte 0.
6. **Disabling Shrinking:** Configuring property tests with `{ shrink: false }` or ignoring counterexamples.

---

## Required Output & Review Workflow

Structure all simulation, property testing, and fuzzing deliverables through this 3-phase discipline:

1. **Formal Invariant & Transition Mapping:** Define the mathematical invariants, the explicit state transition table, and the failure modes to simulate.
2. **Hardened Test Implementation:** Emit production-grade test suites using virtual clocks, seeded PRNGs, tagged unions, and structure-aware arbitraries.
3. **Red-Green Mutation Verification:** Prove the suite catches real defects by introducing a deliberate mutation and verifying that the harness fails with a minimal counterexample.

When a durable simulation audit record is required, save a JSON assessment following the [Record Contract](references/simulation-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering sim audit <record.json> --json
# or: python3 scripts/simulation_guard.py audit <record.json> --source <test_file.ts> --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central orchestration index for simulation, property testing, and fuzzing.
- **[Microsoft Research & AWS DST Playbook](playbooks/microsoft-aws-dst-playbook.md)**: FoundationDB hermetic simulation, Coyote actor testing, virtual clocks, and fault matrix.
- **[State-Machine & Fuzzing Playbook](playbooks/state-machine-and-fuzzing-playbook.md)**: Formal state matrices, tagged unions, and grammar-based fuzz targets.
- **[Simulation Booby-Traps](playbooks/references/simulation-booby-traps.md)**: Common traps: unseeded PRNGs, wall-clock leaks, shallow shrinkers, and tautological properties.
- **[Discrete Event Simulation Contract](references/discrete-event-simulation-and-fault-injection.md)**: Virtual time priority queues, fault injection, and deterministic replay.
- **[Property-Based Testing Guide](references/property-based-testing-and-shrinking.md)**: Invariant categories, shrinking mechanics, and framework comparison.
- **[State-Machine Modeling Guide](references/state-machine-modeling-and-type-invariants.md)**: Tagged unions, transition tables, and model-based generative testing.
- **[Structure-Aware Fuzzing Guide](references/structure-aware-fuzzing-and-parsers.md)**: Untrusted parsers, recursion/payload bounds, and crash freedom.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Example-based complacency | Only 2 static tests exist for complex calculation | Write property test generating 1,000+ random inputs with shrinking |
| Flaky race conditions in CI | Tests fail intermittently under high CI load | Replace `setTimeout` with `DeterministicVirtualClock` and seeded event queue |
| Non-reproducible failure | Test failed once in CI but passes locally | Enforce explicit 64-bit seed logged on every run; replay with identical seed |
| Corrupted entity lifecycle | Entity has `isCompleted=true` and `isFailed=true` | Refactor to tagged union; make impossible states unrepresentable |
| Call-stack exhaustion / DoS | Deeply nested payload crashes parser with stack overflow | Enforce recursion depth counter (`depth <= 16`) and structure-aware fuzz tests |

---

## Delegated Skills

- `anti-slop-engineering`: Follow core BUILD/FIX gates and zero-dependency discipline.
- `paranoid-principal-architect`: Apply 10M concurrent user scale invariants and zero-trust perimeter defenses.
- `verification-oracle-architect`: Implement contract-verified in-memory fakes and dual-adapter testing parity.

---

## Completion and Limits

The task is complete when mathematical invariants are verified across $\ge 1,000$ iterations with automatic shrinking, distributed race conditions are simulated via a deterministic virtual clock with a reproducible seed, impossible states are eliminated by the type system, and untrusted parsers prove crash freedom and resource bounds under structure-aware fuzzing.
