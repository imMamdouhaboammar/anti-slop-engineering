# Adversarial Review: Zero-Trust & Scale Audit

Use this workflow when auditing pull requests, reviewing existing codebases, or performing deep security and performance assessments.

## Review Audit Checklist

### 1. Scan for the Six Instant Rejections
1. **Unbounded `Promise.all`:** Search for `.map(` followed by `Promise.all`. Require bounded worker pools.
2. **Client-supplied authority:** Check if prices, timestamps, roles, or tenant IDs originate from user input. Require server-authoritative resolution.
3. **Unprotected Polling:** Check `setInterval` for missing `document.visibilityState` pauses, error backoff, or cleanup handles.
4. **Floating Promises:** Ensure every asynchronous call has explicit `await`, `.catch()`, or `void` with internal logging.
5. **TOCTOU Flaws:** Check for read-then-write patterns outside atomic transactions or optimistic locking.
6. **Sensitive Leaks:** Check if raw database entities or passwords/tokens are returned directly without an allowlisted DTO.

### 2. Boundary Verification
- Are all route inputs parsed with strict runtime schemas (Zod/Valibot)?
- Are unknown fields stripped to prevent mass-assignment attacks?
- Are string lengths, array counts, and payload byte-sizes strictly capped?

### 3. Concurrency & Contention Inspection
- Are database mutations idempotent via `Idempotency-Key`?
- Is there any single-row global counter that will lock under 100k writes/sec?
- Are database transactions held open across external HTTP requests? (Must reject immediately if found).

### 4. Network & Failure Hardening
- Does every external `fetch` use `AbortSignal.timeout()`?
- Do retry mechanisms implement exponential backoff with full jitter?
- Are errors sanitized so internal infrastructure details and stack traces never reach the client?

## Review Output Format

Provide audit findings structured as follows:

```markdown
### 1. Adversarial Findings
- **[CRITICAL / HIGH / MEDIUM]** <Concise title>
  - **Vector:** How an attacker or 10M-user load exploits this flaw.
  - **Location:** File path and line numbers.
  - **Remediation:** Concrete code patch eliminating the defect.

### 2. Invariant Compliance Matrix
| Invariant | Status | Evidence |
| --- | --- | --- |
| Zero-Trust Boundary Validation | PASS / FAIL | Zod schema parses all route params |
| Data-Layer Authorization | PASS / FAIL | WHERE user_id enforced in query |
| Bounded Limits & Pagination | PASS / FAIL | Keyset cursor pagination with LIMIT 50 |
| Network Timeouts & Cancellation | PASS / FAIL | AbortSignal.timeout(3000) applied |

### 3. Verdict
`PROCEED`, `PAUSE`, or `REFUSE`
```
