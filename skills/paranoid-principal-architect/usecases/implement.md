# Hardened Implementation: Defensive Coding Discipline

Use this workflow when generating code, implementing endpoints, writing background workers, or refactoring critical execution paths.

## Implementation Procedure

### 1. Execute Threat & Scale Pre-Mortem
Before writing any implementation code, state:
1. **Threat 1:** How concurrent callers (e.g. 10,000 requests in 10ms) could cause duplicate mutations, negative balances, or race conditions.
2. **Threat 2:** How an adversarial payload (e.g. 50MB body, prototype pollution, script tag, or SQL fragment) could exhaust memory or compromise boundaries.
3. **Threat 3:** How downstream service degradation (e.g. 30s latency or network partition) could lock connection pools or stall the caller.

### 2. Implement the Hardened Code
Follow this structural order:
1. **Perimeter Schema:** Define strict runtime schemas with `.strict()` and bounded field sizes.
2. **Authoritative Context:** Extract caller ID and tenant ID exclusively from authenticated session state; never trust the request body.
3. **Idempotency Gate:** Check for an `Idempotency-Key`; return cached results or acquire a deduplication lock before side effects.
4. **Data Isolation:** Scope database queries to tenant and owner IDs directly within SQL/ORM queries.
5. **Bounded Execution:** Limit queries with cursor-based pagination and apply `AbortSignal.timeout(ms)` to all outbound calls.
6. **Safe Crypto:** Use `crypto.timingSafeEqual` for all secret comparisons and `crypto.randomUUID()` for nonces.
7. **Clean Error Envelope:** Catch exceptions, log internally with trace IDs, and return sanitized error envelopes without leaking infrastructure details.

### 3. Write Adversarial Verification Tests
Deliver tests verifying resilience under hostile conditions:
- **Concurrent Collision Test:** Fire 50 concurrent requests with the same `Idempotency-Key` or resource ID. Verify exactly one mutation succeeds while others receive idempotent replays or conflicts.
- **Oversized / Malformed Payload Test:** Send negative numbers, prototype pollution keys (`__proto__`), strings exceeding max length, and verify early 400 rejection.
- **Downstream Timeout Test:** Mock a hanging downstream service and verify `AbortSignal.timeout` aborts cleanly without leaking resources.
- **Unauthorized Tenant Traversal Test:** Attempt to access or mutate a resource belonging to another tenant/user and verify zero data leakage.
