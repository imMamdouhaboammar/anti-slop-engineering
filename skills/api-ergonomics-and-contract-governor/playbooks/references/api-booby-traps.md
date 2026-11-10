# Forensic Catalog: API & Contract Booby-Traps

> A forensic inventory of anti-patterns that degrade API ergonomics, compromise developer experience, and introduce runtime bugs.

## 1. The Boolean Parameter Trap

```typescript
// ❌ BOOBY-TRAP: What do true and false mean?
function createSession(userId: string, isGuest: boolean, autoRenew: boolean, rememberMe: boolean): Session;
createSession("usr_123", true, false, true);

// ✅ REMEDY: Named option bag with discriminated union literals
interface SessionOptions {
  readonly mode: "guest" | "authenticated";
  readonly persistence: "transient" | "remember_me";
  readonly renewalPolicy: "manual" | "auto_renew";
}
function createSession(userId: UserId, options: SessionOptions): Session;
```

---

## 2. Stringly-Typed Domain Identifiers

```typescript
// ❌ BOOBY-TRAP: Swapped parameters compile without warning
function transfer(sourceAccountId: string, destinationAccountId: string, authorizedByUserId: string): void;
transfer(userId, destAccountId, sourceAccountId); // Silent disaster!

// ✅ REMEDY: Nominal branded types
function transfer(
  source: AccountId,
  destination: AccountId,
  authorizer: UserId
): void;
```

---

## 3. Option Explosion Soup

```typescript
// ❌ BOOBY-TRAP: Mandatory configuration overload
class ApiClient {
  constructor(options: {
    host: string;
    port: number;
    protocol: string;
    timeout: number;
    retries: number;
    jitter: boolean;
    poolSize: number;
    agent: string;
  }) {}
}

// ✅ REMEDY: Pit-of-success defaults with progressive disclosure
class ApiClient {
  constructor(config: { apiKey: ApiKey; baseUrl?: string; timeoutMs?: number }) {}
}
```

---

## 4. Bare Error Throwing

```typescript
// ❌ BOOBY-TRAP: Callers cannot programmatically distinguish error types
if (res.status === 429) {
  throw new Error("Too many requests, try again later");
}

// ✅ REMEDY: RFC 9457 Problem Details with machine codes and retryability
throw new ProblemDetailsError({
  type: "https://api.example.com/errors/rate_limit_exceeded",
  title: "Too Many Requests",
  status: 429,
  detail: "Quota of 100 req/min exceeded. Retry after 2000ms.",
  instance: `/v1/charges`,
  code: "rate_limit_exceeded",
  retryable: true,
  suggested_action: "Implement exponential backoff or increase rate tier.",
});
```

---

## 5. Ambiguous Return Signatures

```typescript
// ❌ BOOBY-TRAP: Both data and error can be undefined or present simultaneously
function execute(): { data?: Order; error?: string }

// ✅ REMEDY: Tagged discriminated result union
type Result<T, E> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: E };
```
