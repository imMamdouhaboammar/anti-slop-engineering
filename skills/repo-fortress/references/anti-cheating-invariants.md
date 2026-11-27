# Anti-Cheating Invariants & Elimination Recipes

This reference provides concrete before/after patterns to eliminate the 5 AI cheating anti-patterns without breaking existing functionality.

---

## 1. Anti-Suppression Invariant

### Prohibited
```typescript
// ❌ WRONG: Silencing the linter
// @ts-ignore
const token = user.auth.token;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parse(data: any) {}

# ❌ WRONG in Python
result = calculate()  # noqa: E501
```

### Compliant Remediation
```typescript
// ✅ RIGHT: Proper optional chaining, nullish coalescing & narrowing
const token = user.auth?.token ?? null;

// ✅ RIGHT: Use unknown with a schema validator or type guard
function parse(data: unknown): UserPayload {
  if (isUserPayload(data)) return data;
  throw new Error("Invalid payload structure");
}
```

---

## 2. Zero Type-Laundering Invariant

### Prohibited
```typescript
// ❌ WRONG: Type laundering through unknown
const user = (await response.json()) as unknown as User;

// ❌ WRONG: Non-null assertion on unchecked access
const firstItem = items[0]!;
```

### Compliant Remediation
```typescript
// ✅ RIGHT: Type-safe runtime boundary decoder
function decodeUser(input: unknown): User {
  if (
    typeof input === "object" &&
    input !== null &&
    "id" in input &&
    typeof input.id === "string"
  ) {
    return input as User; // Safe after field narrowing
  }
  throw new Error("Payload does not satisfy User schema");
}

// ✅ RIGHT: Safe bounds checking
const firstItem = items[0];
if (!firstItem) {
  throw new NotFoundError("Items collection is empty");
}
```

---

## 3. Zero Silent Catches Invariant

### Prohibited
```typescript
// ❌ WRONG: Swallowing errors
try {
  await client.sync();
} catch {}

fetchUser().catch(() => {});
```

### Compliant Remediation
```typescript
// ✅ RIGHT: Explicit typing, credential scrubbing, structured error handling
try {
  await client.sync();
} catch (err: unknown) {
  const message = err instanceof Error ? err.message : String(err);
  logger.error("Sync operation failed", { error: scrubSensitive(message) });
  // Rethrow if caller needs failure notification, or handle deterministically
}

// ✅ RIGHT: Fire-and-forget background dispatch with explicit catch & void
void fetchUser().catch((err: unknown) => {
  logger.warn("Non-critical background fetch failed", {
    error: err instanceof Error ? err.message : String(err),
  });
});
```

---

## 4. Strictness Directionality Invariant

Linter configurations must only move in the direction of **greater strictness**.
- **Allowed (Framework Alignment)**: Turning off `react/react-in-jsx-scope` in React 19 / JSX transform projects because it is a legacy rule producing false positives.
- **Prohibited (Weakening)**: Turning off `no-floating-promises`, `@typescript-eslint/no-explicit-any`, or removing `"strict": true` from `tsconfig.json`.

---

## 5. Root-Cause Logic Fixes over Dummy Underscores

### Prohibited
```typescript
// ❌ WRONG: Silencing unused variable without investigating why it was unused
function processOrder(order: Order, _analyticsService: AnalyticsService) {
  return repo.save(order);
}
```

### Compliant Remediation
```typescript
// ✅ RIGHT: Wire up the forgotten parameter if intended
function processOrder(order: Order, analyticsService: AnalyticsService) {
  const saved = repo.save(order);
  analyticsService.track("order_processed", { id: order.id });
  return saved;
}

// OR delete the dead parameter if never needed
function processOrder(order: Order) {
  return repo.save(order);
}
```
