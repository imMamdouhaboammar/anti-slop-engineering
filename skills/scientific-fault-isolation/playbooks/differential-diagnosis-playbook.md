# Playbook 1: Microsoft / Meta Differential Diagnosis & Logarithmic Fault Isolation

At Microsoft (Windows Kernel & Azure Escalation Engineering) and Meta (Production Engineering & Systems Reliability), debugging is treated as an empirical science governed by strict falsification—never as trial-and-error code editing. When an engineer modifies production code without first proving the fault mechanism, they corrupt the crime scene, introduce secondary regressions, and mask deep concurrency flaws behind superficial symptom patches.

---

## 1. The Anatomy of Shotgun Debugging (And Why AI Agents Default to It)

LLMs optimize for immediate next-token plausibility. When presented with an error log, an unguided agent jumps straight from **Symptom $\to$ Speculative Patch**:
1. Sees `TypeError: Cannot read properties of undefined (reading 'id')`.
2. Immediately edits the file to `item?.id ?? ""`.
3. Runs tests; the crash is gone, but an upstream serialization bug is now silently writing empty-string foreign keys into production tables.
4. Or when a test still fails, the agent layers edit #2 on top of unverified edit #1, thrashing across 6 files until the working tree is an unreviewable mess.

### The Anti-Shotgun Circuit Breaker
- **Rule 0:** Zero production code mutations are permitted during the diagnostic phase.
- **Strike 1:** If a diagnostic probe yields inconclusive output, refine the probe boundary.
- **Strike 2:** If a proposed surgical fix does not turn the deterministic red test green on the first run, **immediately `git checkout -- <prod_files>`**. Never stack a second speculative edit onto a failed fix.

---

## 2. The 3-Hypothesis Differential Diagnosis Protocol

Borrowing from clinical medicine and aerospace fault-tree analysis, you must construct a **Differential Diagnosis Matrix** with at least three competing, mutually exclusive hypotheses before running an experiment:

### Step 1: Span Orthogonal Fault Categories
Do not write three slight variations of the same guess. Span distinct physical layers:
- **Hypothesis $H_1$ (Temporal / Concurrency Ordering):** State is valid when written, but two asynchronous operations interleave out-of-order (e.g. stale response overwrites newer response; TOCTOU read-modify-write).
- **Hypothesis $H_2$ (Boundary Contract / Serialization Skew):** Upstream producer emits a shape, encoding, timezone, or nullability variant that violates the downstream parser's implicit assumption.
- **Hypothesis $H_3$ (State Lifecycle / Cache Invalidation Leak):** Mutable object reference, singleton buffer, connection pool session variable, or memoized cache leaks dirty state from Request $N-1$ into Request $N$.

### Step 2: The Discriminating Probe Matrix
A probe is only high-leverage if its possible outcomes partition $[H_1, H_2, H_3]$. Before running the probe, write down the decision table:
- If Probe Output matches Pattern $\alpha \implies H_1$ is **CONFIRMED**, $H_2$ & $H_3$ are **FALSIFIED**.
- If Probe Output matches Pattern $\beta \implies H_2$ is **CONFIRMED**, $H_1$ & $H_3$ are **FALSIFIED**.
- If Probe Output matches Pattern $\gamma \implies H_3$ is **CONFIRMED**, $H_1$ & $H_2$ are **FALSIFIED**.

---

## 3. $O(\log N)$ Binary Search Isolation Across Space and Time

### A. Commit History Bisection (`git bisect run`)
A regression introduced somewhere across 512 commits takes at most $\log_2(512) = 9$ automated test runs to isolate to a single commit:
1. Extract the failing test into an untracked script `/tmp/repro.sh`.
2. Guard build steps with `|| exit 125` so broken intermediate builds are skipped (`git bisect skip`).
3. Run `git bisect start HEAD <last_known_good_sha> && git bisect run /tmp/repro.sh`.

### B. Call-Stack & Pipeline Bisection
When tracing data corruption across $K$ microservice hops or middleware layers:
1. Place a single assertion/snapshot probe at layer $\lfloor K/2 \rfloor$.
2. Check whether the invariant is intact or already violated at $\lfloor K/2 \rfloor$.
3. Recursively halve the culpable segment until you trap the exact function boundary where valid input becomes corrupt output.

### C. Input Payload Bisection (Zeller's Delta Debugging `ddmin`)
When a bug requires a large input file or multi-step sequence:
1. Halve the input array/JSON tree and re-execute the minimal reproducer.
2. Discard any half whose removal still preserves the exact failure signature.
3. Repeat until reaching the **1-minimal reproducer** (where removing any single remaining line or field stops the bug).

---

## 4. Handoff to `root-fix-gate`

`scientific-fault-isolation` answers **"What exact physical mechanism caused this failure, and how do we reproduce it 100% deterministically?"**
Once answered, if the causal mechanism touches a contract shared by multiple layers (e.g. API controller, domain entity, and database schema), hand the confirmed mechanism to `root-fix-gate` to determine which architectural boundary owns the permanent fix.
