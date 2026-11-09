# Scale & Concurrency Patterns (Day-One 10M Concurrent Users)

## 1. Mathematical Modeling & Little's Law

Under the 10,000,000 Concurrent Users Axiom, capacity and latency cannot be left to intuition. System concurrency is governed by Little's Law:

$$L = \lambda \times W$$

Where:
- $L$ = Number of concurrent requests in-flight across the system
- $\lambda$ = Arrival rate (throughput in requests per second)
- $W$ = Average response time (latency in seconds)

### Concrete Scale Horizon
- Assume 10,000,000 active concurrent user sessions.
- If 1% make an API request in any given second, arrival rate $\lambda = 100,000\text{ req/sec}$.
- **Scenario A (Healthy Latency):** Average latency $W = 50\text{ ms } (0.05\text{ s})$.
  $$L = 100,000 \times 0.05 = 5,000\text{ concurrent in-flight requests}$$
- **Scenario B (Degraded Latency / Hot Key Lock):** A single unindexed query or row lock slips average latency to $W = 500\text{ ms } (0.5\text{ s})$.
  $$L = 100,000 \times 0.5 = 50,000\text{ concurrent in-flight requests}$$
- **Result:** A 10x latency regression triggers a 10x surge in in-flight requests. Thread pools, database connection pools, file descriptors, and socket buffers saturate immediately, triggering cascading system brownout.

---

## 2. Hot-Key Defense & Contention Elimination

In high-concurrency systems, synchronous row updates on a single entity (e.g. `UPDATE products SET inventory = inventory - 1`, or `UPDATE metrics SET views = views + 1`) introduce devastating lock contention.

### Strategy A: Sharded Counters
Divide a monolithic counter row into $N$ distinct shards (e.g., 16 or 64 shards):
- **Write Path:** The writer randomly selects shard index $i \in [0, N-1]$ and increments shard $i$. Contention drops by a factor of $N$.
- **Read Path:** Compute the sum across all $N$ shards using a single query:
  ```sql
  SELECT COALESCE(SUM(count), 0) FROM metric_shards WHERE metric_id = :id;
  ```

### Strategy B: Append-Only Event Ledgers
Never update an account balance or inventory count in place synchronously:
1. Append an immutable transaction record into an append-only ledger (`ledger_entries`).
2. Materialize balances periodically or asynchronously via event streaming / stream processors.
3. For immediate balance checks, query `SELECT COALESCE(SUM(delta), 0) FROM ledger_entries WHERE account_id = :id`.

### Strategy C: Asynchronous Batch Rollups
For high-frequency, non-transactional metrics (views, likes, heartbeats):
1. Buffer mutations in high-throughput in-memory or Redis hyperloglogs / queues.
2. Flush to persistent storage in micro-batches (e.g., every 500ms or 1,000 items) using bulk operations (`INSERT ... ON CONFLICT DO UPDATE`).

---

## 3. Keyset (Cursor) Pagination vs Offset Degradation

Offset pagination (`LIMIT 100 OFFSET 1000000`) forces the database engine to perform a full scan over 1,000,100 index entries or rows, discarding the first million. Under high concurrency, this locks buffer pools and consumes gigabytes of I/O.

### Mandatory Cursor Keyset Invariant
Use deterministic composite cursor ordering:
```sql
SELECT id, title, created_at
FROM articles
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT 100;
```
Required composite index:
```sql
CREATE INDEX idx_articles_created_at_id ON articles (created_at DESC, id DESC);
```
- Seek time remains $O(\log N)$ regardless of how deep the user paginates.
- Hard bound: Every read query must specify a maximum limit (default: 50, max: 100).

---

## 4. Bounded Concurrency & Pool Management

Unbounded parallel operations will rapidly exhaust Node.js/Go/Rust file descriptors, thread pools, and downstream database connections.

### Prohibited
```typescript
// FATAL DEFECT: If items has 10,000 elements, creates 10,000 simultaneous sockets/queries
await Promise.all(items.map(item => processItem(item)));
```

### Mandatory Bounded Concurrency
Use a semaphore or bounded concurrency queue (e.g. limit concurrency to 10-25 workers):
```typescript
async function mapConcurrent<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, signal: AbortSignal) => Promise<R>,
  signal: AbortSignal
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let nextIndex = 0;

  async function worker(): Promise<void> {
    while (nextIndex < items.length) {
      if (signal.aborted) throw signal.reason;
      const index = nextIndex++;
      results[index] = await fn(items[index]!, signal);
    }
  }

  const pool = Array.from({ length: Math.min(limit, items.length) }, () => worker());
  await Promise.all(pool);
  return results;
}
```

---

## 5. Exponential Backoff with Full Jitter

When a downstream service degrades or drops connections, naive retries or flat sleep intervals create a **thundering herd** that ensures the downstream service can never recover.

### The Full Jitter Algorithm
For retry attempt $i \ge 0$, calculate delay $T_i$:
$$T_{\text{temp}} = \min(T_{\max}, T_{\text{base}} \times 2^i)$$
$$T_i = \text{random}(0, T_{\text{temp}})$$

```typescript
function calculateJitteredBackoff(
  attempt: number,
  baseMs = 100,
  maxMs = 5000
): number {
  const expCap = Math.min(maxMs, baseMs * (2 ** attempt));
  return Math.floor(Math.random() * expCap);
}
```

---

## 6. Timeouts & Cancellation

Every external interaction (HTTP request, database query, cache call, inter-process call) must be bounded by a non-negotiable timeout.

```typescript
// Modern native timeout using AbortSignal.timeout
async function safeFetch(url: string, init?: RequestInit, timeoutMs = 3000): Promise<Response> {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const combinedSignal = init?.signal
    ? AbortSignal.any([init.signal, timeoutSignal])
    : timeoutSignal;

  return fetch(url, { ...init, signal: combinedSignal });
}
```

---

## 7. Idempotency & Transaction Discipline

### The Idempotency Key Pattern
1. Client generates a deterministic or UUID `Idempotency-Key` header on state mutations.
2. Server stores the request key in an atomic fast-path cache (e.g. Redis `SET key ... NX EX 86400`) with status `IN_PROGRESS`.
3. If duplicate key arrives while `IN_PROGRESS`, return `409 Conflict` or poll/await completion.
4. When mutation completes, update cache with the serialized response. Re-deliver cached response on subsequent retries.

### Transaction Seam Discipline
**Never hold a database transaction open across network calls.**
```
BAD:
BEGIN TRANSACTION
  UPDATE accounts SET balance = balance - 100
  await fetch("https://payment-gateway/charge") // NETWORK CALL INSIDE TRANSACTION!
  UPDATE payments SET status = 'COMPLETED'
COMMIT

GOOD:
1. Reserve funds via Optimistic Concurrency or state = 'PENDING' in short local transaction.
2. COMMIT local transaction.
3. Perform external HTTP call with explicit timeout and idempotency key.
4. Update state to 'CONFIRMED' in a second short local transaction.
```
