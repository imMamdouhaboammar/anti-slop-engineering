# Code Smell Catalog: Exhaustive Anti-Pattern Reference

Companion reference to the Grumpy Senior Staff Engineer skill. Maps each failure class to its observable signal, production blast radius, and surgical hardened remedy.

---

## Family 1: Exception Handling Crimes

### `EXCEP-001` — The Silent Swallow
```typescript
// CRIMINAL — hides a production fire
try {
  await processPayment(order);
} catch (e) {}

// or the coward's return null
try {
  return await db.users.findOne(id);
} catch (e) {
  return null; // null-pointer three functions downstream, 3AM Sunday
}
```
**Blast radius:** Failure is invisible in monitoring. The system appears healthy while silently corrupting state.
**Remedy:**
```typescript
try {
  await processPayment(order);
} catch (err) {
  logger.error({
    op: "payment.process",
    order_id: order.id,
    error_code: err instanceof PaymentError ? err.code : "UNEXPECTED",
    trace_id: ctx.traceId,
  });
  throw new PaymentProcessingError("Payment failed", { cause: err });
}
```

### `EXCEP-002` — The Catch-and-Rethrow Theater
```typescript
// USELESS — adds zero information
try {
  await fn();
} catch (err) {
  throw err; // exactly the same as not catching at all
}
```
**Remedy:** Delete the try/catch entirely.

---

## Family 2: Async & Concurrency Crimes

### `ASYNC-001` — Unbounded Promise Storm
```typescript
// FATAL — creates N simultaneous connections, exhausts pools
await Promise.all(recipients.map(r => sendEmail(r)));
```
**Blast radius:** 10,000 recipients → 10,000 simultaneous sockets. Node.js file descriptor limit hit in milliseconds.
**Remedy:**
```typescript
async function mapConcurrent<T, R>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T) => Promise<R>
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await fn(items[idx]!);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker));
  return results;
}

await mapConcurrent(recipients, 10, sendEmail);
```

### `ASYNC-002` — Floating Promise
```typescript
// SILENT FAILURE — errors vanish into the void
user.events.forEach(e => sendNotification(e)); // no await, no catch
```
**Remedy:** Either `await Promise.all(...)` with bounded concurrency, or `void sendNotification(e).catch(logger.error)` with explicit void intent.

### `ASYNC-003` — TOCTOU Race Condition
```typescript
// FATAL RACE — 10,000 concurrent requests, 10,000 negative balances
const balance = await db.query("SELECT balance FROM accounts WHERE id = ?", [id]);
await db.query("UPDATE accounts SET balance = ? WHERE id = ?", [balance - amount, id]);
```
**Remedy:**
```typescript
// Atomic compare-and-swap — single round-trip, no race
const result = await db.query(
  "UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ? RETURNING balance",
  [amount, id, amount]
);
if (result.rowCount === 0) throw new InsufficientFundsError();
```

---

## Family 3: API & Boundary Crimes

### `BOUND-001` — Mass Assignment Vulnerability
```typescript
// CRITICAL — client can elevate their own role, set any field
await db.users.update(req.body); // req.body = { role: "admin", id: 1 }
```
**Remedy:**
```typescript
const schema = z.object({
  display_name: z.string().max(100),
  bio: z.string().max(500).optional(),
}).strict(); // strips all undeclared fields

const data = schema.parse(req.body); // throws on invalid input
await db.users.update({ id: session.userId }, data); // server-authoritative ID
```

### `BOUND-002` — Client-Supplied Authority
```typescript
// EXPLOITABLE — client dictates price, role, or permissions
app.post("/purchase", (req, res) => {
  const { price, productId } = req.body; // client sets the price
  await charge(user, price);
});
```
**Remedy:** Resolve price, roles, permissions, and all authority exclusively from server-side state. Never trust the request body for these.

### `BOUND-003` — Missing Timeout on External Call
```typescript
// POOL EXHAUSTION — hangs forever if payment gateway degrades
const result = await fetch("https://payment.example.com/charge", { method: "POST" });
```
**Remedy:**
```typescript
const result = await fetch("https://payment.example.com/charge", {
  method: "POST",
  signal: AbortSignal.timeout(5000), // hard 5-second deadline
});
```

---

## Family 4: Database Crimes

### `DB-001` — N+1 Query Pattern
```typescript
// SERIAL MASSACRE — 100 items = 101 database round-trips
const orders = await db.orders.findAll({ where: { userId } });
for (const order of orders) {
  order.items = await db.orderItems.findAll({ where: { orderId: order.id } });
}
```
**Remedy:** Use a JOIN, `IN` clause, or dataloader batching to fetch in 2 queries maximum.

### `DB-002` — Offset Pagination at Scale
```sql
-- DEGRADES TO O(N) full scan at large offsets
SELECT * FROM articles ORDER BY created_at DESC LIMIT 20 OFFSET 500000;
```
**Remedy:**
```sql
-- O(log N) keyset cursor — constant time regardless of depth
SELECT * FROM articles
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### `DB-003` — Synchronous Hot-Key Counter
```sql
-- LOCK CONTENTION — 100k writes/sec on one row = cascading brownout
UPDATE metrics SET view_count = view_count + 1 WHERE id = :id;
```
**Remedy:** Use 16–64 sharded counter rows; sum them on read. Or append to an event ledger and materialize asynchronously.

---

## Family 5: Abstraction & Structure Crimes

### `ABS-001` — Speculative Generality
```typescript
// INVENTED for a future that never arrives
abstract class AbstractUserRepositoryFactory {
  abstract createRepository(): IUserRepository;
}
class ConcreteUserRepositoryFactory extends AbstractUserRepositoryFactory { ... }
// There is exactly one implementation.
```
**Remedy:** Write the concrete function. Introduce the interface when the second real implementation exists.

### `ABS-002` — Boolean Trap Parameters
```typescript
// UNREADABLE — what do true, false, true mean?
processUser(user, true, false, true);
```
**Remedy:**
```typescript
processUser(user, { sendWelcomeEmail: true, skipAudit: false, notifyAdmin: true });
```

### `ABS-003` — Stringly-Typed Control Flow
```typescript
// FRAGILE — brittle to message changes, invisible to the type checker
if (error.message.includes("duplicate key")) { ... }
if (status === "ACTIVE_PREMIUM_TRIAL") { ... }
```
**Remedy:** Use exhaustive discriminated union types or enums. Parse error types structurally, not by message substring.

---

## Family 6: Testing Crimes

### `TEST-001` — Mock Theater
```typescript
// PROVES NOTHING — mocked DB, mocked network, mocked filesystem
// This test has 100% coverage of your mock, not your production behavior
vi.mock("../db");
vi.mock("../emailService");
it("creates a user", async () => {
  (db.create as Mock).mockResolvedValue({ id: "1" });
  await createUser({ name: "Alice" });
  expect(db.create).toHaveBeenCalledWith({ name: "Alice" });
});
```
**Remedy:** Write one integration test against a real test database. It will catch the actual bugs.

### `TEST-002` — Assertion-Free Test
```typescript
it("does not throw", async () => {
  await expect(processOrder(order)).resolves.toBeDefined();
});
```
**Remedy:** Assert on the actual state change — the database record, the event emitted, the response body. Test behavior, not absence of exceptions.
