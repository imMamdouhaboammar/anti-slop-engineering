# Workflow: 3-Hypothesis Differential Diagnosis

Use this workflow whenever a bug, crash, or unexpected behavior does not have an immediately self-evident, single-line deterministic cause.

## Step-by-Step Procedure

### 1. Freeze Production Code & Capture the Raw Symptom
1. **Verify Clean Baseline:** Run `git status` and `git diff` to ensure zero speculative edits exist in production files. If previous unverified "guesses" were applied, revert them immediately.
2. **Record the Exact Failure Signature:** Capture the exact exception type, stack frame, corrupted field value, or HTTP status code. Never summarize `"login is broken"`—record `"POST /api/v1/session returns 401 INVALID_NONCE when two tabs refresh within 20ms"`.

### 2. Construct the 3-Hypothesis Matrix ($H_1, H_2, H_3$)
Draft at least three mutually exclusive, falsifiable hypotheses covering distinct failure classes (e.g. concurrency race vs. boundary serialization vs. stale cache state):

| ID | Physical Mechanism | Observable Prediction | Falsified If |
| --- | --- | --- | --- |
| **$H_1$** | Exact code path $A$ mutates state $X$ before lock acquisition | Probe at boundary $M$ shows two concurrent calls reading the same `version = 1` | Calls at boundary $M$ are strictly serialized with incrementing versions |
| **$H_2$** | Upstream caller sends malformed/truncated payload under condition $B$ | Probe at ingress boundary shows missing/null field before service logic runs | Ingress payload is 100% valid on failing requests |
| **$H_3$** | Downstream cache/timezone conversion shifts value during serialization | Database row holds valid value, but serialized DTO holds shifted value | Database row itself already contains the corrupted value |

### 3. Design & Execute the Single Discriminating Probe
1. **Locate the Partition Point:** Choose the single inspection boundary where $H_1$, $H_2$, and $H_3$ predict mutually exclusive states.
2. **Apply Minimal Read-Only Instrumentation:**
   - Prefer a hermetic unit/integration test harness probe first.
   - If instrumenting code temporarily, log structured JSON with correlation IDs and monotonic sequence counters—never mutate control flow.
3. **Execute & Record Raw Evidence:** Run the probe once, capture the exact output, and mark at least two hypotheses as `falsified` and the matching hypothesis as `confirmed` (or reformulate if all three are falsified).

### 4. Bridge to Deterministic Reproducer & Root Ownership
1. Convert the confirmed hypothesis into a 100% deterministic failing test (`usecases/deflake-race-condition.md`).
2. Remove all temporary diagnostic probes from production files.
3. If the confirmed fault spans multiple layers (e.g. controller vs. domain service vs. schema), invoke `root-fix-gate` to choose the canonical owning boundary before writing the fix.
