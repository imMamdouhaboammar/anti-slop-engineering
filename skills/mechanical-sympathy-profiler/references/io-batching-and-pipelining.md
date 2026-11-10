# Reference: I/O Batching, Pipelining & Single-Roundtrip Coalescing

Network and IPC roundtrips are the #1 bottleneck in distributed backend services. Performing I/O inside a loop turns a sub-millisecond operation into a multi-second tail-latency outage.

---

## 1. Collapsing Loop SQL Queries into Single-Roundtrip Bulk Operations

### Anti-Pattern: Serial Database Roundtrips in a Loop ($N \times \text{RTT}$)
```typescript
// FORBIDDEN: 500 items = 500 sequential TCP roundtrips + 500 planner/executor cycles
for (const item of invoiceUpdates) {
  await db.query(
    "UPDATE invoices SET status = $1, updated_at = NOW() WHERE tenant_id = $2 AND id = $3",
    [item.status, tenantId, item.id]
  );
}
```

### Mechanical Sympathy Pattern: PostgreSQL `UNNEST` Bulk Mutation ($1 \times \text{RTT}$)
```typescript
// 500 items = 1 network roundtrip, 1 transaction lock cycle, 1 sequential index/heap pass
const ids: string[] = new Array(invoiceUpdates.length);
const statuses: string[] = new Array(invoiceUpdates.length);

for (let i = 0; i < invoiceUpdates.length; i++) {
  ids[i] = invoiceUpdates[i].id;
  statuses[i] = invoiceUpdates[i].status;
}

await db.query(
  `UPDATE invoices AS inv
   SET status = batch.status, updated_at = NOW()
   FROM UNNEST($1::uuid[], $2::text[]) AS batch(id, status)
   WHERE inv.tenant_id = $3 AND inv.id = batch.id`,
  [ids, statuses, tenantId]
);
```

### Bulk Point Reads via `ANY($1)`
```typescript
// Collapses N point lookups into 1 Index Scan over a sorted array of keys
const { rows } = await db.query(
  `SELECT id, status, amount_cents
   FROM invoices
   WHERE tenant_id = $1 AND id = ANY($2::uuid[])`,
  [tenantId, invoiceIds]
);
```

---

## 2. Redis Pipelining & `MGET` Coalescing

Never issue sequential `await redis.get(key)` or `await redis.hset(...)` inside a loop.
- **Bulk Reads:** Use `await redis.mget(keys)` to fetch $N$ keys in a single socket write and read.
- **Heterogeneous Commands:** Use **Pipelining** so the client writes all commands into a single TCP buffer and reads all replies in a single socket read without waiting for per-command RTT:

```typescript
const pipeline = redis.pipeline();
for (let i = 0; i < events.length; i++) {
  const ev = events[i];
  pipeline.hincrby(`metrics:${ev.tenantId}`, ev.counterName, ev.delta);
  pipeline.expire(`metrics:${ev.tenantId}`, 86400);
}
const results = await pipeline.exec();
```

---

## 3. Request-Scoped DataLoader Coalescing (GraphQL / RPC / Microservices)

When independent resolvers or component trees request individual entities by ID during the same tick:
1. Enqueue requested IDs into a tick-scoped batch buffer (`queueMicrotask` or `process.nextTick`).
2. Deduplicate keys with a `Set`.
3. Dispatch a single bulk RPC or `WHERE id = ANY($1)` query for the entire tick.
4. Fan the results back out to the awaiting callers in $O(1)$ via a `Map`.
