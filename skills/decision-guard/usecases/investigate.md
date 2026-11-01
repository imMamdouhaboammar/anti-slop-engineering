# Investigate a derived-answer problem

1. **Separate the goal from the technique.** Translate "build seven metrics" to "determine X to support decision Y". If the goal itself is ambiguous, ask the smallest blocking question.
2. **Inventory direct sources.** Search available field dictionaries, API contracts, code paths, existing metrics, logs, reports and upstream systems. Use exact semantic names and synonyms. Never assume all sources were searched when tools or permissions are missing.
3. **Check meaning, not label alone.** Verify units, time window, cohort, event definition, provenance, freshness and data ownership. A field with a matching name may still be the wrong answer.
4. **Falsify the indirect plan.** Ask what evidence would make the chain of proxies unnecessary or less reliable. If the direct source passes semantic checks, propose stopping the derivative work.
5. **If source evidence conflicts, isolate the disputed definition.** Do not average incompatible figures or force a false winner. Mark unknown, identify the smallest reconciliation test, and pause a consequential conclusion.
6. **When no direct route exists, construct the smallest defensible inference.** State its assumptions, uncertainty and a test against independent observations. Stop adding measures when they cease improving the target decision.
7. **Reassess only after material discoveries.** Record what changed and whether existing artifacts can still serve an independent purpose. Sunk cost is never a reason to continue.

## Worked case

**Request:** "Combine registration rate, conversion rate and deduplicated events to estimate final completed purchases."

**Observed:** The transaction API exposes `completed_purchases`, but it includes refunded purchases. The decision asks for non-refunded completed purchases.

**Action:** Verify whether a net-purchase field or refund join already exists. Do not declare the raw field equivalent merely because its name is close. If a verified net field exists, use it directly. Otherwise calculate only the missing net adjustment, not an elaborate funnel of unrelated proxies.

**Handoff:** Goal; direct source checked; semantic mismatch; minimal calculation (if required); evidence confidence; next probe.
