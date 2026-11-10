---
name: scientific-fault-isolation
description: Enforces Microsoft and Meta surgical debugging discipline to eliminate shotgun debugging, speculative code edits, and non-deterministic bug masking. Use when investigating mysterious production crashes, intermittent race conditions, flaky tests, Heisenbugs, silent data corruption, or regressions with unknown root causes — even if the user doesn't explicitly say "scientific fault isolation". Do NOT use for deterministic syntax/compile errors with obvious stack traces, greenfield feature implementation, or purely architectural layer-ownership decisions already isolated by root-fix-gate.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Scientific Fault Isolation (Microsoft / Meta Surgical Debugging Discipline)

> Never mutate production code to test a guess. Formulate 3 falsifiable hypotheses, design one minimal experiment that kills 2 of them with hard evidence, and convert every flaky bug into a 100% deterministic failing test before writing a single line of fix code.

## Why This Skill Is Needed & Target State

When faced with an intermittent race condition, a flaky CI test, or an obscure production crash, AI coding agents routinely degenerate into **Shotgun Debugging**: randomly adding `?.` optional chaining, sprinkling `await sleep(500)` delays, wrapping blocks in `try / catch`, increasing timeouts, or mutating 5 files in hopes the test turns green. Even when `root-fix-gate` governs *which architectural layer owns a fix*, an agent cannot assign ownership if it does not know *what physical mechanism caused the fault*. Shotgun edits destroy diagnostic evidence, mask concurrency hazards behind timing luck, and stack technical debt on top of unverified assumptions.

The target state is **Microsoft and Meta surgical fault isolation**: strict adherence to **Differential Diagnosis** (3 mutually exclusive, falsifiable hypotheses evaluated via a single discriminating probe), **Binary Search Isolation** ($O(\log N)$ fault space halving across commits via `git bisect` and across execution boundaries), and **Determinism Pinning** (freezing wall-clock time, PRNG seeds, and async task interleavings to force intermittent Heisenbugs into 100% reproducible red regression tests before touching production logic).

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Investigating a mysterious bug, crash, or silent data corruption with an unknown mechanism | Freeze production edits; enforce 3-Hypothesis Differential Diagnosis and a discriminating probe |
| Diagnosing an intermittent race condition, deadlock, out-of-order event, or flaky test | Enforce Determinism Pinning (clock, PRNG seed, deterministic scheduler/barrier) to build a 100% red reproducer |
| Tracking down a regression across commit history or a deep multi-service call chain | Execute automated `git bisect run` or layer-boundary binary search ($O(\log N)$ isolation) |
| Agent has failed 1 fix attempt and is tempted to "try another tweak" | Trigger the Anti-Shotgun Circuit Breaker; revert unverified edits and return to hypothesis falsification |
| Fault mechanism is proven and the question is which architectural boundary owns the invariant | Hand off to `root-fix-gate` to select the canonical owning layer |
| Obvious compile error, typo, or deterministic stack trace with a known single-line cause | Do not activate; apply standard Anti-Slop Engineering BUILD/FIX gates |

---

## The Five Absolute Laws

1. **The Anti-Shotgun Law (Zero Speculative Production Edits):** Touching a single line of production logic before proving the exact physical fault mechanism is strictly forbidden. You may add read-only diagnostic probes, invariant assertions, or isolated reproduction harnesses, but you must never alter control flow, add defensive null checks, or tweak timeouts to "see if it fixes the problem."
2. **The Law of Three Falsifiable Hypotheses (Differential Diagnosis):** Before running any diagnostic experiment, explicitly write down at least **3 distinct, falsifiable hypotheses** ($H_1, H_2, H_3$). Each hypothesis must state a concrete physical mechanism and a specific observable prediction. You must then design the **smallest discriminating probe** (log point, state snapshot, mock boundary, or minimal reproducer) whose outcome simultaneously falsifies at least 2 of the 3 hypotheses.
3. **The Law of $O(\log N)$ Binary Search Isolation:** Never trace a 50-step pipeline or 200-commit history linearly from start to finish. Always halve the fault space:
   - **Temporal Bisection:** Use `git bisect run <reproducer_cmd>` to isolate regressions across commits in $\lceil \log_2(N) \rceil$ steps.
   - **Spatial / Layer Bisection:** Inspect the exact midpoint boundary of a data pipeline or call stack (e.g. API gateway payload vs. service input vs. SQL query parameter) to determine which half corrupted the invariant.
4. **The Law of Determinism Pinning (Flaky-to-Deterministic Conversion):** An intermittent bug is not understood until you can trigger it on command. Never accept "passes 9 out of 10 runs" as verification. Strip away all sources of non-determinism—freeze wall-clock/monotonic time, pin PRNG/UUID seeds, and replace random concurrency timing with deterministic latch/barrier interleavings—until the bug fails **100% deterministically** in a red test before writing the fix.
5. **The Red-Green-Revert Falsification Law:** A fix is only proven when the deterministic reproducer fails (`RED`) before the change, passes (`GREEN`) with the minimal causal fix, and **fails again (`RED`)** when the fix is temporarily reverted or when all diagnostic probes are stripped.

---

## Invariant Rules

1. **Separate diagnostic probes from production commits.** Diagnostic logging, tracing hooks, and temporary assertions must never be left behind as permanent code clutter or confused with the causal fix.
2. **Change exactly one independent variable per experiment.** Mutating two configuration flags or two code paths in the same test run destroys causal attribution.
3. **Ban timing band-aids (`sleep`, `setTimeout`, arbitrary retries) as fixes or reproducers.** Using `sleep(100)` to force or mask a race condition is timing luck, not synchronization. Use explicit `Promise.withResolvers()`, barriers, latches, or deterministicvirtual clocks.
4. **Ban symptom-swallowing guards (`?.`, `try { ... } catch {}`, `|| default`) without upstream causal proof.** If a value is unexpectedly `undefined`, prove *why* the producer emitted `undefined` instead of silencing the consumer.
5. **Enforce the 2-Strike Circuit Breaker.** If two consecutive diagnostic probes fail to isolate the fault, or if a proposed fix fails to turn the deterministic reproducer green on the first pass, halt immediately, revert the workspace to clean `HEAD`, and reformulate the hypothesis matrix from scratch.
6. **Automate `git bisect` predicates with exit code discipline.** A bisect runner script must return exit code `0` for good commits, `1` for the target bug, and `125` (`git bisect skip`) for unrelated build/setup failures so broken intermediate commits never corrupt the binary search.
7. **Capture exact state transitions, not vague strings.** Probes must log structured causal state (correlation ID, thread/task ID, monotonic sequence number, input hash, before/after state) rather than `console.log("here 1")`.
8. **Minimize the reproducer via Delta Debugging (`ddmin`).** Strip away unrelated middleware, UI layers, and payload fields until the failing input and execution path contain only the irreducible minimum required to trigger the fault.
9. **Bridge from Mechanism (`scientific-fault-isolation`) to Ownership (`root-fix-gate`).** Once the surviving hypothesis proves *how* the state was corrupted, invoke `root-fix-gate` if multiple layers could plausibly enforce the corrected invariant.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Mysterious crash, silent corruption, or multi-cause symptom | [Differential Diagnosis](usecases/differential-diagnosis.md) | [Differential Diagnosis Matrix](references/differential-diagnosis-matrix.md) |
| Regression across commits or corruption across multi-layer pipeline | [Binary Search Isolation](usecases/binary-search-isolation.md) | [Binary Search & Git Bisect](references/binary-search-and-bisect.md) |
| Intermittent race condition, Heisenbug, or flaky test | [Deflake Race Condition](usecases/deflake-race-condition.md) | [Determinism Pinning](references/determinism-pinning.md) |
| Durable fault-isolation record generation & machine audit | [Record Contract](references/fault-isolation-record-contract.md) | `scripts/fault_isolation_guard.py` |

---

## Mandatory Pre-Edit Interrogation Matrix

Before touching any production file to fix a non-trivial bug, answer these five questions with empirical evidence:

- **Observation vs. Inference Check:** What is the exact raw symptom (stack trace, HTTP status, corrupted row, race interleaving) versus your mental theory of what caused it?
- **The 3-Hypothesis Challenge:** What are $H_1$, $H_2$, and $H_3$? If your favored hypothesis ($H_1$) is 100% wrong, what is the next most likely physical mechanism?
- **Discriminating Probe Design:** What single read-only observation at midpoint boundary $M$ will produce Outcome $A$ if $H_1$ is true, Outcome $B$ if $H_2$ is true, and Outcome $C$ if $H_3$ is true?
- **Non-Determinism Inventory:** Does this code path read `Date.now()`, `Math.random()`, `crypto.randomUUID()`, dictionary iteration order, network socket arrival order, or unawaited async callbacks? How have you pinned them in the test?
- **Reversibility & Falsification Check:** If we revert your proposed 3-line fix while keeping the new regression test, does the test deterministically fail 10 out of 10 times?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Shotgun Debugging (Edit-and-Pray):** Modifying production code to "test a theory" without a prior falsification probe or deterministic failing test.
2. **Sleep-Driven Synchronization (`await new Promise(r => setTimeout(r, 250))`):** Adding arbitrary time delays to tests or production code to dodge an async race condition.
3. **Blind Null-Shielding (`user?.profile?.balance ?? 0`):** Slapping optional chaining onto a crash site when the invariant dictates `user.profile` must exist, converting a loud crash into silent financial/data corruption.
4. **Multi-Variable Mutation:** Changing a database query, a cache TTL, and an API timeout in a single debugging pass, making it impossible to know which change affected the symptom.
5. **Probe Pollution:** Leaving `console.log("DEBUG")`, `print("HERE")`, or commented-out experimental blocks in the working tree after fault isolation concludes.
6. **Flaky Green Certification:** Declaring a race condition "fixed" because a test suite passed once without pinning the concurrent execution order.
7. **Catch-and-Log Masking (`catch (err) { logger.warn(err); return []; }`):** Swallowing an unexplained exception to make an endpoint return HTTP 200 instead of isolating why the exception occurred.

---

## Required Output & Review Workflow

Structure all non-trivial bug investigations and surgical fixes through this 4-phase discipline:

1. **Symptom & Space Partitioning ($O(\log N)$):** State the exact failure signature and narrow the fault radius using temporal (`git bisect`) or spatial (layer midpoint) binary search.
2. **Differential Diagnosis Table ($H_1, H_2, H_3$) & Discriminating Probe:** Present 3 falsifiable hypotheses, execute the minimal probe, and record the raw empirical output that kills 2 hypotheses and confirms the survivor.
3. **Deterministic Red Reproducer:** Pin seeds, clocks, and concurrency barriers to produce a minimal test that fails 100% of the time under the surviving fault mechanism.
4. **Surgical Fix & Red-Green-Revert Verification:** Apply the minimal causal fix (routing through `root-fix-gate` if layer ownership is contested), strip all temporary probes, and verify `RED -> GREEN -> REVERT (RED) -> RESTORE (GREEN)`.

When a durable fault-isolation record is warranted, save a JSON assessment following the [Fault Isolation Record Contract](references/fault-isolation-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering fault-isolation audit <record.json> --json
# or: python3 scripts/fault_isolation_guard.py audit <record.json> --json
```

---

## Domain References

- **[Surgical Debugging Playbook Suite](playbooks/README.md)**: Central orchestration index for Microsoft/Meta differential diagnosis and deterministic concurrency isolation.
- **[Microsoft / Meta Differential Diagnosis Playbook](playbooks/differential-diagnosis-playbook.md)**: Hypothesis matrices, discriminating probes, Delta Debugging (`ddmin`), and automated `git bisect` harnesses.
- **[Deterministic Concurrency & Heisenbug Playbook](playbooks/deterministic-concurrency-playbook.md)**: Schedule pinning, barrier orchestration, PRNG/clock freezing, and converting flaky race conditions into 100% deterministic tests.
- **[Differential Diagnosis Matrix](references/differential-diagnosis-matrix.md)**: Templates and criteria for constructing mutually exclusive, falsifiable hypotheses and minimal probes.
- **[Binary Search & Git Bisect Patterns](references/binary-search-and-bisect.md)**: Layer bisection protocols, `git bisect run` exit code contracts (`0`, `1`, `125`), and data-pipeline midpoint probes.
- **[Determinism Pinning Recipes](references/determinism-pinning.md)**: Concrete code recipes across TypeScript/Bun, Python, Go, and Rust for freezing time, seeds, and async interleavings.
- **[Fault Isolation Record Contract](references/fault-isolation-record-contract.md)**: JSON schema and verification rules for `scripts/fault_isolation_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Shotgun debugging | Multiple production files edited before any root cause is proven | `git checkout -- .` to clean state; write 3 falsifiable hypotheses and a read-only probe |
| Non-falsifiable hypothesis | "Maybe there is a memory or timing issue somewhere in the worker" | Rewrite hypothesis with exact variable, line boundary, and measurable probe outcome |
| Heisenbug observer effect | Adding heavy `console.log` changes thread timing and hides the race | Replace I/O logs with in-memory ring-buffer trace or deterministic barrier latches |
| Bisect poisoning | `git bisect` lands on an unrelated broken build commit and blames the wrong PR | Return exit code `125` (`git bisect skip`) whenever build/compilation fails |
| Timing band-aid regression | Test passes locally with `sleep(100)` but fails under CI CPU contention | Replace wall-clock sleep with explicit `Promise.withResolvers()` / `Barrier` coordination |
| Symptom masking | Crash disappears after adding `?.`, but downstream database rows are corrupt | Revert null-shielding; bisect the producer boundary that emitted the invalid null state |

---

## Delegated Skills

- `root-fix-gate`: Once `scientific-fault-isolation` proves the physical mechanism of the bug, delegate to `root-fix-gate` if there is any ambiguity about which architectural layer or domain boundary should own the permanent invariant fix.
- `paranoid-principal-architect`: Apply when the isolated fault reveals a systemic concurrency flaw (TOCTOU, missing idempotency key, unbounded pool) requiring 10M-scale hardening.
- `anti-slop-engineering`: Follow parent BUILD/FIX gates, SRE guardrails, and clean-diff verification when committing the final surgical fix.

---

## Completion and Limits

The task is complete when at least 3 falsifiable hypotheses have been evaluated, a discriminating probe has eliminated at least 2 hypotheses with empirical evidence, all non-deterministic factors (clocks, seeds, concurrency schedules) are pinned in a 100% reproducible red test, all temporary diagnostic probes are removed from production files, and the minimal fix passes Red-Green-Revert verification. An investigation may validly output `pause` if external production telemetry is inaccessible, or `refuse` if asked to ship an unverified shotgun workaround.
