# Binary Search Isolation & Automated `git bisect` Patterns

Linear debugging scales at $O(N)$—reading 40 files in a call chain or manually checking 150 commits one by one wastes context and invites human error. Binary search isolation reduces fault localization to $O(\log_2 N)$ steps. Even across 1,024 commits or a 16-stage data pipeline, the exact fault boundary is isolated in at most 10 steps (`4–10` checks in practice).

---

## 1. Temporal Bisection: Automated `git bisect run`

When a behavior worked in commit $A$ (e.g. `v1.5.0` or 3 days ago) and fails in `HEAD`, never guess which PR broke it. Run an automated, non-interactive `git bisect`.

### Exit Code Contract for Bisect Scripts

Git requires strict exit codes from the verification script passed to `git bisect run`:
- **`0` (Good):** The commit does **not** exhibit the bug.
- **`1` through `127` except `125` (Bad):** The commit exhibits the target bug.
- **`125` (Skip):** The commit cannot be tested (e.g. syntax error, broken build, missing dependency). Returning `1` on a build failure corrupts the binary search!
- **`> 127` (Abort):** Immediately aborts `git bisect run`.

### Canonical Hermetic Bisect Harness (`bisect-probe.sh`)

Keep the bisect script outside tracked repository files (e.g. `/tmp/bisect-probe.sh`) so `git bisect` checkouts never overwrite or conflict with the reproducer:

```bash
#!/usr/bin/env bash
set -u

# Step 1: Compile or prepare build; if compilation fails, exit 125 (SKIP)
bun run build >/dev/null 2>&1 || exit 125

# Step 2: Run the isolated deterministic reproducer test
# Exit 0 = bug absent (GOOD), Exit 1 = bug present (BAD)
bun test /tmp/reproduce_issue.test.ts
status=$?

if [ "$status" -eq 0 ]; then
  exit 0
else
  exit 1
fi
```

Execute non-interactively and always `reset` afterward:
```bash
git bisect start HEAD v1.5.0
git bisect run /tmp/bisect-probe.sh
git bisect reset
```

---

## 2. Spatial Bisection: Halving the Execution & Data Pipeline

When a bug is not a recent commit regression (or commit history is unavailable), apply binary search across the **spatial execution path**.

Suppose a request traverses 8 sequential boundaries:
`[1. Browser Form] -> [2. Next.js Middleware] -> [3. API Route Parser] -> [4. Domain Service] -> [5. ORM Serializer] -> [6. PostgreSQL Trigger] -> [7. Read Replica] -> [8. DTO Response Mapper]`

### The Midpoint Partition Protocol

1. **Select Midpoint $M_1$ (Boundary 4 -> 5):** Inspect the exact payload exiting `Domain Service` and entering `ORM Serializer`.
   - **Case A (Payload is already corrupted at $M_1$):** Boundaries `5, 6, 7, 8` are exonerated in a single check. The fault is strictly in `[1..4]`.
   - **Case B (Payload is 100% valid at $M_1$):** Boundaries `1, 2, 3, 4` are exonerated. The fault is strictly in `[5..8]`.
2. **Select Midpoint $M_2$ (e.g. Boundary 2 -> 3 if in `[1..4]`):** Inspect the payload exiting `Next.js Middleware`.
3. **Select Midpoint $M_3$:** Isolate the exact single boundary where valid input enters and corrupted output exits.

---

## 3. Input Space Bisection: Delta Debugging (`ddmin`)

When a crash only occurs on a massive 5MB JSON payload, a 2,000-line configuration file, or a 50-step user session log:

1. Split the failing input payload $I$ into two halves: $I_1$ and $I_2$.
2. Run the minimal harness with $I_1$ alone, then $I_2$ alone.
3. If $I_1$ reproduces the exact same exception signature, discard $I_2$ and recursively halve $I_1$.
4. If neither half fails alone (interaction fault), hold $I_1$ fixed and bisect $I_2$ to find the second interacting element, then bisect $I_1$ while holding that element fixed.
5. Continue until removing any single field or array item causes the bug to disappear (the **1-minimal failing input**).
