# Differential Diagnosis Matrix & Discriminating Probe Design

Differential diagnosis prevents confirmation bias during debugging. When an engineer or AI agent forms only a single hypothesis, every observation is subconsciously interpreted to support that guess, leading directly to shotgun debugging.

---

## 1. Anatomy of a Falsifiable Hypothesis

A valid engineering hypothesis must contain three mandatory components:
1. **Physical Mechanism (`mechanism`):** The exact state mutation, race interleaving, boundary serialization mismatch, or resource exhaustion causing the fault.
2. **Observable Prediction (`prediction`):** What must be true in memory, on the wire, or in logs if and only if this mechanism is the cause.
3. **Falsification Condition (`falsified_if`):** The exact observation that immediately kills this hypothesis with 100% certainty.

### Weak vs. Falsifiable Hypotheses

| Weak (Unfalsifiable Slop) | Surgical (Falsifiable Hypothesis) |
| --- | --- |
| "Maybe Redis is slow or dropping connections." | "$H_1$: `SessionStore.get()` returns stale `null` because `saveSession()` fires without `await` in `AuthController.login` (line 84), allowing the redirect `GET /dashboard` to read Redis before the `SETEX` command completes." |
| "There might be a timezone issue in the billing cron." | "$H_2$: `InvoiceGenerator` truncates `billing_period_end` using local server time (`Date.getHours()`) instead of UTC (`Date.getUTCHours()`), shifting 00:00 UTC invoices in `America/New_York` into the previous calendar day." |
| "The React state isn't updating fast enough." | "$H_3$: The `useEffect` cleanup on `SearchInput` does not abort the in-flight `fetch`, causing an older, slower query response (`q='a'`) to resolve after the newer query (`q='ab'`) and overwrite `results` state." |

---

## 2. Designing the Single Discriminating Probe

Instead of running three separate experiments sequentially (or editing production code three times), design **one minimal, read-only discriminating probe** placed at a strategic boundary that partitions the hypothesis space:

```
                  [ Discriminating Probe at Boundary M ]
                     /               |               \
          Outcome A /      Outcome B |                \ Outcome C
                   v                 v                 v
           Confirm H1         Confirm H2         Confirm H3
         (Kills H2, H3)     (Kills H1, H3)     (Kills H1, H2)
```

### Example: Intermittent Duplicate Webhook Charge

- **Symptom:** 0.4% of Stripe `invoice.paid` webhooks result in two ledger entries for the same `invoice_id`.
- **Hypotheses:**
  - **$H_1$ (Upstream Duplicate Delivery + Missing Idempotency Fast-Path):** Stripe sends two concurrent webhook POSTs within 15ms; both pass `SELECT id FROM ledger WHERE invoice_id = $1` before either `INSERT` commits (classic TOCTOU race).
  - **$H_2$ (Internal Queue Retry on Post-Commit Timeout):** A single webhook arrives, commits the database `INSERT`, but times out while sending the downstream Slack notification, causing the internal BullMQ worker to retry the entire handler.
  - **$H_3$ (Batch Cursor Off-By-One in Reconciliation Cron):** The webhook handler writes only once, but the hourly reconciliation cron uses `WHERE created_at >= :last_ts` instead of `>`, re-importing the boundary invoice.
- **Single Discriminating Probe:** Query or log `(invoice_id, source_caller, request_correlation_id, worker_attempt, timestamp_ns)` on every entry into `recordLedgerEntry()`:
  - **Outcome A:** Two entries share `source_caller = "webhook"`, `worker_attempt = 1`, distinct `request_correlation_id`s, and timestamps within `12ms` $\implies$ **$H_1$ confirmed; $H_2$ and $H_3$ falsified.**
  - **Outcome B:** Two entries share the exact same `request_correlation_id` with `worker_attempt = 1` and `worker_attempt = 2` $\implies$ **$H_2$ confirmed; $H_1$ and $H_3$ falsified.**
  - **Outcome C:** Entry 1 has `source_caller = "webhook"` and Entry 2 has `source_caller = "reconciliation_cron"` $\implies$ **$H_3$ confirmed; $H_1$ and $H_2$ falsified.**

---

## 3. Probe Hygiene & Zero-Pollution Contract

1. **Read-Only by Default:** A probe inspects state, asserts invariants, or captures an in-memory trace buffer. It must never mutate business state or alter return values.
2. **Avoid Observer-Effect Timing Shifts:** When diagnosing microsecond race conditions (Heisenbugs), synchronous `console.log` or disk I/O serializes threads and makes the bug vanish. Record timestamps and thread IDs into a pre-allocated in-memory array (`traceBuffer.push({ step, seq: ++counter })`) and dump it only after the failure assertion triggers.
3. **Mandatory Probe Cleanup:** Before committing the surgical fix, verify via `git diff` that 100% of temporary diagnostic probes have been removed from production files. Only the permanent deterministic regression test and the minimal causal fix may remain.
