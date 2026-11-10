# Operational Survival Guide: Production-Grade Engineering Discipline

## 1. Structured Logging Contract

Every log line in a production system must be grep-able by an on-call engineer at 3AM without reading source code.

### Required Fields
```typescript
interface StructuredLogLine {
  op: string;          // "payment.charge" — what operation failed
  entity_id: string;   // "ord_abc123" — which entity was involved
  tenant_id?: string;  // multi-tenant scope when applicable
  user_id?: string;    // acting user when applicable
  duration_ms: number; // how long before failure
  error_code: string;  // "PAYMENT_GATEWAY_TIMEOUT" — machine-readable
  recovered: boolean;  // did the system self-heal?
  trace_id: string;    // distributed trace correlation ID
}
```

### Banned Log Patterns
| Pattern | Why It's Useless |
| --- | --- |
| `console.log(err)` | No context, not structured, not grep-able |
| `logger.error("Something went wrong")` | No operation, no entity, unactionable at 3AM |
| `logger.error(err.stack)` | Leaks infrastructure details to log aggregators |
| `logger.info("Processing request")` | High-volume noise with zero signal |

---

## 2. Safe Database Migration Discipline (Expand-and-Contract)

Never write a schema migration that:
- Locks a table that is read by the currently deployed version
- Drops a column still referenced by the N-1 deployed version
- Cannot be rolled back safely without downtime

### The Expand-and-Contract Pattern (3 Deployments)

```
Deploy 1 (Expand):   Add new column `user_name_new` as nullable.
                     Both old and new code work. No lock. No downtime.

Deploy 2 (Migrate):  Backfill `user_name_new` from `user_name` in a background job.
                     New code writes to both columns. Old code writes to old column only.

Deploy 3 (Contract): Drop old column `user_name` after all instances run Deploy 2.
                     Composite index can now be created on `user_name_new`.
```

### Banned Migration Patterns
- `ALTER TABLE ... RENAME COLUMN` while the old column name is in production code
- `DROP COLUMN` without verifying zero references in deployed code
- `CREATE INDEX CONCURRENTLY` inside a transaction (it blocks)
- Any migration with `LOCK TABLE` on a high-traffic table

---

## 3. Backpressure & Timeout Discipline

Every I/O operation must declare an explicit deadline. No exceptions.

### HTTP Calls
```typescript
// Mandatory pattern — never bare fetch
const res = await fetch(url, {
  signal: AbortSignal.timeout(5000),  // 5-second hard deadline
  method: "POST",
  body: JSON.stringify(payload),
});
if (!res.ok) throw new UpstreamError(res.status, await res.text());
```

### Database Queries
```typescript
// Bounded by default — cursor pagination, explicit limit
const results = await db.query(
  "SELECT id, name FROM products WHERE tenant_id = $1 AND (created_at, id) < ($2, $3) ORDER BY created_at DESC, id DESC LIMIT 50",
  [tenantId, cursor.createdAt, cursor.id],
  { queryTimeout: 3000 }  // db driver timeout
);
```

### Worker Pools (Never Unbounded Promise.all)
```typescript
// CORRECT — bounded concurrency
await mapConcurrent(items, 10, processItem); // max 10 concurrent workers
```

---

## 4. Graceful Degradation vs Fail Loudly

| Context | Required Behavior |
| --- | --- |
| Missing required config (DATABASE_URL, API key) | **Fail loudly at boot** — crash the process immediately |
| Missing optional config (ANALYTICS_API_KEY) | **Log a warning and continue** — degrade gracefully |
| External service unavailable | **Return degraded response** with explicit `Service-Unavailable` error code — never hang |
| Invalid user input | **Return 400 immediately** at the boundary — never swallow or coerce |
| Unexpected internal error | **Log with full context, return 500 with correlation ID** — never leak stack trace |

---

## 5. Idempotency Gate Pattern

Every state-mutating operation exposed to external callers must support safe retries.

```typescript
async function createCharge(
  idempotencyKey: string,
  payload: ChargePayload
): Promise<ChargeResult> {
  // 1. Check for existing result (fast path)
  const cached = await redis.get(`idempotency:${idempotencyKey}`);
  if (cached) return JSON.parse(cached) as ChargeResult;

  // 2. Acquire lock (prevent concurrent duplicates)
  const acquired = await redis.set(
    `idempotency:lock:${idempotencyKey}`,
    "1",
    "NX", "EX", 30  // 30-second lock TTL
  );
  if (!acquired) throw new ConflictError("Duplicate request in progress");

  try {
    // 3. Execute the mutation
    const result = await chargePaymentGateway(payload);

    // 4. Cache the result for future retries (24h TTL)
    await redis.set(
      `idempotency:${idempotencyKey}`,
      JSON.stringify(result),
      "EX", 86400
    );

    return result;
  } finally {
    await redis.del(`idempotency:lock:${idempotencyKey}`);
  }
}
```
