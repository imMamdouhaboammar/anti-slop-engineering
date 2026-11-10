# Workflow: Binary Search Isolation (`git bisect` & Layer Halving)

Use this workflow when isolating a regression across commit history or pinpointing where an invariant is corrupted across a multi-stage call graph or data pipeline.

## Step-by-Step Procedure

### Track A: Temporal Regression Isolation (`git bisect`)

1. **Establish Hermetic Reproducer outside the Working Tree:**
   - Write a standalone reproduction test or script in `/tmp/bisect_repro.sh` (so `git checkout` during bisection never deletes or conflicts with the test).
   - Verify `/tmp/bisect_repro.sh` exits `1` (BAD) on `HEAD` and exits `0` (GOOD) on the last known working tag/commit.
2. **Enforce Exit Code `125` for Build Failures:**
   - Wrap compilation/setup commands with `|| exit 125` inside `/tmp/bisect_repro.sh` so uncompilable intermediate commits are skipped rather than misclassified as having the bug.
3. **Run Non-Interactive Bisection:**
   ```bash
   git bisect start HEAD <good_commit_or_tag>
   git bisect run /tmp/bisect_repro.sh
   ```
4. **Inspect the First Bad Commit & Reset:**
   - Record the offending commit SHA and inspect its exact diff (`git show <sha>`).
   - Always return the repository to the original branch via `git bisect reset`.

### Track B: Spatial Layer Bisection ($O(\log N)$ Pipeline Halving)

1. **Enumerate the End-to-End Boundary Chain:**
   - List the $N$ ordered boundaries from producer to consumer: $B_1 \to B_2 \to \dots \to B_N$.
2. **Probe Midpoint $B_{\lfloor N/2 \rfloor}$:**
   - Assert the domain invariant on the exact data structure crossing $B_{\lfloor N/2 \rfloor}$.
   - If the invariant holds at $B_{\lfloor N/2 \rfloor}$, discard the upstream half $[B_1 \dots B_{\lfloor N/2 \rfloor}]$ and bisect $[B_{\lfloor N/2 \rfloor + 1} \dots B_N]$.
   - If the invariant is already violated at $B_{\lfloor N/2 \rfloor}$, discard the downstream half and bisect $[B_1 \dots B_{\lfloor N/2 \rfloor}]$.
3. **Terminate at the Single Corrupting Transition:**
   - Stop when you isolate boundary $B_k$ where input into $B_k$ satisfies the invariant and output from $B_k$ violates it.

### Track C: Payload Bisection (Delta Debugging `ddmin`)

1. Take the complex failing input payload $P$ (e.g. 500-item array or 40-field JSON object).
2. Remove 50% of the fields/elements and re-run the deterministic reproducer.
3. Keep removing halves until you reach the **1-minimal payload** where deleting any single remaining property stops triggering the bug.
