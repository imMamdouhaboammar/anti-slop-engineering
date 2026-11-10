# Instant Rejection Catalog

Exhaustive reference of every anti-pattern that triggers an immediate rejection from the Grumpy Senior Staff Engineer. Each entry carries: observable signal, production blast radius, and surgical hardened remedy.

Cross-referenced from the [Code Smell Catalog](../playbooks/references/code-smell-catalog.md).

---

## Quick Reference Table

| Code | Family | Pattern | Blast Radius | Severity |
| --- | --- | --- | --- | --- |
| `EXCEP-001` | Exceptions | Silent exception swallow | Invisible failures, corrupted state | CRITICAL |
| `EXCEP-002` | Exceptions | Catch-and-rethrow theater | Zero value; delete it | LOW |
| `ASYNC-001` | Async | Unbounded `Promise.all` over dynamic array | Socket exhaustion, OOM, self-inflicted DoS | CRITICAL |
| `ASYNC-002` | Async | Floating promise | Error disappears; state inconsistency undetected | HIGH |
| `ASYNC-003` | Async | TOCTOU race condition | Negative balances, double charges, corrupted state | CRITICAL |
| `BOUND-001` | Boundaries | Mass assignment | Role escalation, BOLA/IDOR | CRITICAL |
| `BOUND-002` | Boundaries | Client-supplied authority (price, role, ID) | Financial fraud, privilege escalation | CRITICAL |
| `BOUND-003` | Boundaries | Missing timeout on external call | Connection pool starvation, cascading brownout | HIGH |
| `DB-001` | Database | N+1 query | 100 items → 101 round-trips; exponential DB load | HIGH |
| `DB-002` | Database | OFFSET pagination at scale | O(N) full scan; gigabytes of wasted I/O | HIGH |
| `DB-003` | Database | Synchronous hot-key counter | Lock contention under load; cascading brownout | CRITICAL |
| `ABS-001` | Abstraction | Speculative generality | Unmaintainable; complexity without benefit | MEDIUM |
| `ABS-002` | Abstraction | Boolean trap parameters | Unreadable call sites; maintenance time bombs | MEDIUM |
| `ABS-003` | Abstraction | Stringly-typed control flow | Brittle to message changes; invisible to type checker | HIGH |
| `TEST-001` | Testing | Mock theater | 100% coverage of your mock; zero confidence in production | HIGH |
| `TEST-002` | Testing | Assertion-free test | Proves absence of exceptions; not correctness | MEDIUM |
| `LOG-001` | Observability | Context-free log line | Ungrep-able at 3AM | HIGH |
| `CONF-001` | Configuration | Missing fail-loud-at-boot | Silent config failure 6 hours into production | HIGH |

---

## `LOG-001` — Context-Free Log Line

```typescript
// CRIMINAL — useless at 3AM
console.log(err);
logger.error("Something went wrong");
logger.error(err.stack); // leaks infrastructure details
```
**Blast radius:** On-call engineer cannot determine the failing operation, entity, or whether the system recovered.
**Remedy:**
```typescript
logger.error({
  op: "order.create",           // which operation
  order_id: orderId,            // which entity
  user_id: userId,              // who triggered it
  duration_ms: elapsed,         // how long before failure
  error_code: "DB_TIMEOUT",     // machine-readable code
  recovered: false,             // did system self-heal
  trace_id: ctx.traceId,       // distributed trace correlation
});
```

---

## `CONF-001` — Silent Configuration Failure

```typescript
// CRIMINAL — null crash discovered 6 hours into production
const dbUrl = process.env.DATABASE_URL; // possibly undefined
const db = new Database(dbUrl!);       // silent type lie
```
**Blast radius:** Process starts, appears healthy, fails on first database call with a cryptic null error.
**Remedy:**
```typescript
// Called at module initialization — before the HTTP server starts
function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`FATAL: Required environment variable "${key}" is not set.`);
  }
  return value;
}

const config = {
  databaseUrl: requireEnv("DATABASE_URL"),
  redisUrl: requireEnv("REDIS_URL"),
};
```
