# Adversarial Code Review: Radical Simplicity & Operational Audit

Use this workflow when performing code reviews, PR audits, or inline code inspections.

## Review Workflow

### Phase 1: The Heavy Sigh (2–4 Sentences Max)

State what is over-engineered, fragile, or operationally reckless. Ask the uncomfortable question everyone else at the PR review is too polite to ask. No hedging.

Examples of honest opening lines:
- "This is a 6-layer call chain where every layer renames fields and adds no logic."
- "This endpoint has no timeout, no validation, and swallows every exception — it will page someone the first time the downstream service hiccups."
- "You've added Kafka to process 12 events per minute. This is Resume-Driven Development."

### Phase 2: The Subtraction Check

Before proposing any fix, answer:
1. What code can be deleted entirely?
2. What abstraction layer does nothing but rename fields between caller and callee?
3. What third-party package wraps a 10-line native implementation?
4. What class hierarchy can be replaced with a plain data structure and a function?

Report the subtraction verdict explicitly: either list deletions, or explain why nothing can be removed.

### Phase 3: Instant Rejection Scan

Scan the diff or codebase for every item in this checklist:

| Check | Signal | Reference |
| --- | --- | --- |
| Exception swallowing | `catch (e) {}` or `catch (e) { return null; }` | `EXCEP-001` |
| N+1 query | `await db.get()` inside `for` loop or `.map()` | `DB-001` |
| Unbounded async | `Promise.all(items.map(...))` without pool limit | `ASYNC-001` |
| Floating promise | `someAsyncFn()` without `await` or `.catch()` | `ASYNC-002` |
| TOCTOU race | Read-then-write without atomic transaction | `ASYNC-003` |
| Mass assignment | `db.update(req.body)` | `BOUND-001` |
| Client authority | Price, role, or ID sourced from request body | `BOUND-002` |
| Missing timeout | `fetch(url)` without `AbortSignal.timeout()` | `BOUND-003` |
| Offset pagination | `OFFSET <large_number>` in query | `DB-002` |
| Hot-key counter | `UPDATE ... SET count = count + 1` on a shared row | `DB-003` |
| Boolean trap | `fn(a, true, false, true)` | `ABS-002` |
| Stringly-typed logic | `error.message.includes(...)` for control flow | `ABS-003` |
| Mock theater | Test that mocks DB and asserts on the mock | `TEST-001` |

### Phase 4: The 3AM Post-Mortem Check

For every code path being reviewed, state explicitly:
- **Failure mode 1:** What happens when the database is slow or unavailable?
- **Failure mode 2:** What happens when the input is `null`, a 50MB string, or a negative number?
- **Failure mode 3:** What happens when two clients execute this path simultaneously for the same resource?
- **Observability check:** Can an on-call engineer diagnose this failure from logs alone at 3AM without reading source code?

## Review Output Format

```markdown
### Code Review: <PR title or file path>

**The Heavy Sigh:**
<2-4 blunt sentences. The uncomfortable truth.>

**Subtraction Verdict:**
<What was deleted or what cannot be deleted and why.>

### Findings

| Severity | Code | Anti-Pattern | Location | Fix |
| --- | --- | --- | --- | --- |
| CRITICAL | ASYNC-003 | TOCTOU race on balance update | `src/payments.ts:42` | Use atomic UPDATE with WHERE balance >= amount |
| HIGH | EXCEP-001 | Silent exception swallow | `src/worker.ts:88` | Log with structured context and re-raise |
| MEDIUM | ABS-002 | Boolean trap parameters | `src/user.ts:15` | Replace with explicit options object |

### 3AM Survival Assessment
| Failure Mode | Current Behavior | Required Behavior |
| --- | --- | --- |
| DB timeout | Hangs indefinitely | `AbortSignal.timeout(3000)` with structured log |
| Malformed input | Crashes with 500 | Zod parse at boundary; return 400 with error code |
| Concurrent duplicate submit | Double-charges | `Idempotency-Key` deduplication gate |

### Verdict
`APPROVE` | `REQUEST_CHANGES` | `REWRITE_FROM_SCRATCH`
```
