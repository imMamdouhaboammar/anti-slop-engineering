# Bulletproof Implementation: Boring, Direct, Production-Grade Code

Use this workflow when writing code, implementing features, or refactoring existing implementations.

## Implementation Procedure

### Step 1: The Subtraction Check (Before Writing Anything)

Before writing a single line, ask:
1. Does a native platform API (`URL`, `fetch`, `crypto`, `Intl`, `structuredClone`) already do this?
2. Can an existing function in the codebase be extended rather than duplicated?
3. Is this abstraction needed now, or is it speculative generality?

If a subtraction opportunity exists, take it first. Report what was removed before discussing what was added.

### Step 2: The Heavy Sigh (What Would the Naive Implementation Get Wrong?)

Before writing the implementation, state the two or three ways the obvious naive approach would fail in production:
1. **Concurrency failure:** How does this break when 100 users hit it simultaneously?
2. **Input failure:** What happens with `null`, a 50MB string, or a negative number?
3. **Network failure:** What happens when the downstream service takes 30 seconds to respond?

### Step 3: Implement the Boring Bulletproof Version

Follow this structural discipline in order:

1. **Boundary Validation First.** Parse inputs at the entry point with strict types. Unknown fields are stripped. Invalid inputs return structured errors — never 500s.
2. **Server-Authoritative Context.** Extract user ID, tenant ID, role, and price from server session state. Never from the request body.
3. **Explicit Error Handling.** Every `await` is wrapped in a try/catch that logs structured context and throws or returns a typed error. No silent swallowing.
4. **Explicit Timeouts on All I/O.** Every `fetch`, database query, and cache call has a hard deadline via `AbortSignal.timeout()`.
5. **Bounded Operations.** No unbounded loops, no unbounded query results, no unbounded `Promise.all`.
6. **Structured Observability.** Every failure path emits a log line with: operation name, entity ID, duration, error code, trace ID.
7. **Fail Loudly at Boot.** Required configuration is validated at process startup. Missing config crashes the process — not silently six hours later.

### Step 4: The 3AM Post-Mortem Check

After writing the implementation, verify:

- **Can an on-call engineer diagnose failure from logs alone?** Read the log output of the failure path. Does it contain the operation name, entity ID, error code, and trace ID without reading source?
- **What is the blast radius if this fails?** Is failure isolated to one user, one tenant, or the entire system?
- **What is the recovery path?** Does the system self-heal, or does it require a manual intervention runbook?

## Implementation Output Format

```typescript
// GRUMPY REVIEW: The naive version would create N+1 queries and swallow errors.
// Subtraction applied: removed the UserService wrapper — it did nothing but delegate.

import { z } from "zod";

const CreateOrderSchema = z.object({
  product_id: z.string().uuid(),
  quantity: z.number().int().positive().max(100),
}).strict();

export async function createOrder(
  rawBody: unknown,
  session: { userId: string; tenantId: string },
  ctx: { traceId: string }
): Promise<{ order_id: string }> {
  // Boundary validation — unknown fields stripped by .strict()
  const body = CreateOrderSchema.parse(rawBody);

  // Server-authoritative context — never from request body
  const { userId, tenantId } = session;

  const startMs = Date.now();
  try {
    // Bounded, idempotent, tenant-scoped mutation
    const order = await db.orders.create(
      { userId, tenantId, ...body },
      { signal: AbortSignal.timeout(3000) }
    );

    return { order_id: order.id };
  } catch (err) {
    logger.error({
      op: "order.create",
      user_id: userId,
      tenant_id: tenantId,
      product_id: body.product_id,
      duration_ms: Date.now() - startMs,
      error_code: err instanceof DbError ? err.code : "UNEXPECTED",
      trace_id: ctx.traceId,
    });
    throw new OrderCreationError("Order creation failed", { cause: err });
  }
}
```

**3AM Survival Statement:**
- DB timeout → `AbortSignal.timeout(3000)` aborts the query; structured log fires with duration; caller receives typed `OrderCreationError`.
- Malformed input → Zod throws at the boundary; caller receives a 400 with the exact field that failed.
- Concurrent duplicate submit → Add `Idempotency-Key` deduplication gate before this reaches the DB.
