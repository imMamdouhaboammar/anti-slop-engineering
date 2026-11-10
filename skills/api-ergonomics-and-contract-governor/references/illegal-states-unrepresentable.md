# Illegal States Unrepresentable

> Design domain types such that invalid runtime states cannot even be formulated or compiled. Shift runtime validation errors into compile-time type errors.

## The Core Problem: Loose Primitives & Optionality Soup

A common anti-pattern in API design is bundling all possible fields into a single flat interface where multiple fields are optional, permitting contradictory combinations:

```typescript
// ❌ ANTI-PATTERN: Illegal states are representable
interface AsyncJob {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
  result?: string;
  error?: string;
  workerId?: string;
}
// This type permits: { status: "pending", result: "Done!", error: "Crash" }
```

---

## Pillar 1: Discriminated Unions

Model every distinct state as an independent object variant sharing a single literal discriminator property (e.g. `status` or `kind`):

```typescript
// ✅ HARDENED: Impossible states cannot be represented
export interface PendingJob {
  readonly status: "pending";
  readonly queuedAt: string;
}

export interface RunningJob {
  readonly status: "running";
  readonly workerId: WorkerId;
  readonly progress: number; // 0..100
  readonly startedAt: string;
}

export interface CompletedJob {
  readonly status: "completed";
  readonly workerId: WorkerId;
  readonly result: JobResult;
  readonly completedAt: string;
}

export interface FailedJob {
  readonly status: "failed";
  readonly workerId?: WorkerId;
  readonly error: JobError;
  readonly failedAt: string;
}

export type Job = PendingJob | RunningJob | CompletedJob | FailedJob;
```

---

## Pillar 2: Nominal Branded Types

TypeScript's structural type system treats all strings identically, allowing callers to transpose arguments (`transfer(userId, accountId)`). Branded types enforce nominal boundaries at compile time:

```typescript
declare const BrandSymbol: unique symbol;

export type Brand<T, B> = T & { readonly [BrandSymbol]: B };

export type CustomerId = Brand<string, "CustomerId">;
export type AccountId = Brand<string, "AccountId">;
export type PaymentIntentId = Brand<string, "PaymentIntentId">;
export type CurrencyCode = Brand<string, "CurrencyCode">;

export function asCustomerId(id: string): CustomerId {
  if (!id.startsWith("cus_")) {
    throw new Error(`Invalid CustomerId prefix: expected 'cus_', got '${id}'`);
  }
  return id as CustomerId;
}

export function asAccountId(id: string): AccountId {
  if (!id.startsWith("acct_")) {
    throw new Error(`Invalid AccountId prefix: expected 'acct_', got '${id}'`);
  }
  return id as AccountId;
}

// Compile error if transposed:
// transferFunds(accountId, customerId); -> Argument of type 'CustomerId' is not assignable to 'AccountId'.
```

---

## Pillar 3: Compile-Time Exhaustiveness Checking

When handling discriminated unions, ensure that introducing a new variant immediately produces a compiler error in every unhandled switch or conditional branch:

```typescript
export function assertNever(x: never, message?: string): never {
  throw new Error(message ?? `Unexpected unreachable value: ${JSON.stringify(x)}`);
}

export function formatJobStatus(job: Job): string {
  switch (job.status) {
    case "pending":
      return `Job is queued as of ${job.queuedAt}`;
    case "running":
      return `Job is running on ${job.workerId} (${job.progress}%)`;
    case "completed":
      return `Job completed with result: ${job.result.id}`;
    case "failed":
      return `Job failed: ${job.error.title}`;
    default:
      return assertNever(job); // Compile error if a new state (e.g. "cancelled") is added!
  }
}
```
