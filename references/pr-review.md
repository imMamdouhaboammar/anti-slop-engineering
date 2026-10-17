# Evidence-Based PR Review Protocol

Review an entire change as a **behavioral delta** and a **maintenance commitment**, not a file diff with pretty formatting.

## Reviewer sequence

1. Identify problem statement, acceptance criteria, target branch, current diff/base and pre-existing failures.
2. Check existing architecture, nearby utilities, contracts and existing issue/PR overlap.
3. Reconstruct the old behavior and the intended new behavior without using the author's implementation as the sole oracle.
4. Enumerate changed production paths, changed old tests, changed public interfaces, data migrations, permissions, dependencies, CI and configuration.
5. Read risk hotspots first: auth/authz, deserialization, injection, shell/filesystem, money, data loss, scheduling, caching, retries, concurrency and cancellation.
6. Assess maintenance: unnecessary layers, duplicate business rules, hidden state, new dependencies, broad refactors, cyclomatic/cognitive complexity, long methods and code ownership.
7. Validate actual commands, outputs, screenshots/traces/benchmarks as appropriate. Never claim an unrun command passed.
8. Compare changed test assertions to approved external behavior, not to generated implementation output.
9. Report exact file:line findings, impact, reproducible evidence, corrective action; explicitly distinguish blocking findings from personal style preferences.
10. Re-review after fixes; verify that improvements did not erase required safeguards. Merge only under explicit authority and repository controls.

## Risk-weighted review

- **Critical:** exploitable data leak, unauthorized action, data loss, falsified test/CI, unbounded production side effects.
- **High:** confirmed regression, broken user flow, race/data corruption, silently changed public contract, destructive schema change, dangerous dependency.
- **Medium:** serious maintainability cost, API drift, weak test signal for high-risk behavior, substantial scope creep or unreviewable PR.
- **Low:** local naming, harmless redundancy, aesthetics; fix when cheap without inducing churn.

Severity requires impact and evidence. An emoji, a particular variable name, or raw LOC alone is not a security defect.

## PR size principle

Prefer **one coherent, independently testable change**; use separate PRs for unrelated formatting and redesign. Large changes can be justified by generated files, migrations or strongly coupled work. Line counts can trigger review but cannot prove code quality. Never split changes so finely that APIs ship unused or broken.

## Report template

```text
Decision: BLOCK | REWORK | REVIEW | PASS
Scope: target branch; base commit; changed paths; expected contract
Baseline: command -> original result (or NOT RUN)
Verification: command -> result / artifact (or NOT RUN)
Test integrity: existing test diffs; authorized behavior changes; new tests
Findings:
- [severity] path:line | observation | impact | proof | fix
Unverified: exact gaps / affected risks
Exceptions: documented reason, owner, reviewer
Merge: recommended / not recommended; authorization requirements
```

**Reviewer ethics:** Do not reject solely because a PR is AI-authored. Don't let AI reviewer agreement substitute for independent evidence. A second agent can help find defects but does not create an independent ground truth if it relies on the same flawed assumptions.
