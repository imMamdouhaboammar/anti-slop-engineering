# Architect System: Day-One 10M Scale & Zero-Trust Design

Use this workflow when creating new services, designing distributed backends, drafting schemas, or defining critical system architecture.

## Step-by-Step Architecture Procedure

### 1. Freeze Scale Profile & Concurrency Model
1. Explicitly baseline the system for **10,000,000 concurrent user sessions**.
2. Apply Little's Law ($L = \lambda \times W$) to calculate in-flight load at 50ms versus 500ms latency.
3. Establish hard SLA targets: P99 latency <= 100ms, zero synchronous global lock points.

### 2. Conduct Threat & Scale Pre-Mortem
Before drawing component boundaries, identify the top 3 fatal failure modes:
- **Hot-key contention:** Which counter, row, or key will saturate under 100k writes/sec?
- **Unbounded resource exhaustion:** Where can an adversary send a 50MB payload or trigger an $O(N)$ query?
- **Race conditions & replay:** How can double-submits or out-of-order retries corrupt financial or domain state?

### 3. Establish Zero-Trust Boundaries
1. Declare explicit schema parsers (Zod / Valibot) at every external entrance (HTTP routes, webhooks, message queues).
2. Enforce field stripping (`strict()` / allowlists) to prevent mass assignment.
3. Scope all data queries to tenant and owner IDs at the query level (`WHERE tenant_id = :tenant_id AND user_id = :user_id`).

### 4. Concurrency & State Architecture
1. **Counters:** Eliminate single-row counters. Use 16-64 sharded counters or an append-only event ledger.
2. **Mutations:** Enforce an `Idempotency-Key` on every mutating POST/PUT/RPC call.
3. **Locks:** Use Optimistic Concurrency Control (OCC) with version stamps or ETags. Prohibit long-lived table locks.
4. **Transaction Seams:** Prohibit network I/O inside database transactions. Complete DB mutations in minimal atomic transactions, commit, and execute network calls asynchronously.

### 5. Bound All Execution
1. **Reads:** Mandate cursor-based keyset pagination backed by composite indexes. Hard-cap reads to 100 records per page.
2. **Workers:** Limit async concurrency via bounded worker pools or semaphores. Ban unbounded `Promise.all(items.map(...))`.
3. **Timeouts:** Attach `AbortSignal.timeout(ms)` to every outbound HTTP call and query.
4. **Retries:** Apply exponential backoff with full jitter to all transient error recovery paths.

### 6. Generate Assessment Record & Audit
Save the architectural design decisions to `paranoid-record.json` and verify with:
```bash
python3 scripts/paranoid_guard.py audit <record.json> --json
```
Only proceed to implementation once structural verification passes with `action: "proceed"`.
