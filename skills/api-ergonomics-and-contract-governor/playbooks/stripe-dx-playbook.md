# Playbook: Stripe World-Class Developer Experience (DX)

> An API should feel intuitive, predictable, and forgiving. Developers should be able to integrate without reading a manual, and when things fail, the system must explain exactly what went wrong and how to fix it.

## 1. The Core Stripe DX Principles

1. **Predictable Naming & Uniform Resource Architecture:** URLs and SDK namespaces mirror nouns: `/v1/customers`, `/v1/payment_intents`, `/v1/refunds`. Methods follow consistent verb patterns: `create()`, `retrieve()`, `update()`, `list()`, `cancel()`.
2. **Idempotency Keys on All Mutations:** Every POST or state-changing call accepts or generates an `Idempotency-Key` header. If a network drops or client retries, the server returns the cached response with zero duplicate charges or state corruption.
3. **Cursor-Based Pagination:** Ban SQL `OFFSET` pagination. Every collection returns `{ data: T[], has_more: boolean, next_cursor: string | null }` using `starting_after` and `ending_before`.
4. **Machine-Actionable Error Contracts:** Errors are never vague text strings; they provide machine-readable error codes (`card_declined`, `insufficient_funds`), parameter paths (`invalid_params`), and remediation links.
5. **Progressive Expansion:** Support selective resource expansion (`expand: ["customer", "payment_method"]`) to prevent $N+1$ round-trips while keeping default payloads lightweight.

---

## 2. Idempotency Key Discipline

Network retries must never cause duplicate side effects:

```typescript
export interface IdempotencyOptions {
  readonly idempotencyKey?: IdempotencyKey;
}

export function resolveIdempotencyKey(options?: IdempotencyOptions): IdempotencyKey {
  if (options?.idempotencyKey) {
    return options.idempotencyKey;
  }
  // Auto-generate safe UUIDv4 if omitted by caller
  return `idem_${crypto.randomUUID()}` as IdempotencyKey;
}
```

---

## 3. Cursor Pagination Standard

```typescript
export interface CursorPageParams {
  readonly limit?: number; // default: 20, max: 100
  readonly startingAfter?: string;
  readonly endingBefore?: string;
}

export interface PaginatedList<T> {
  readonly object: "list";
  readonly data: readonly T[];
  readonly hasMore: boolean;
  readonly nextCursor: string | null;
}
```

---

## 4. Webhook Signature Verification

Never accept raw webhook payloads without cryptographic HMAC-SHA256 verification and replay timestamp bounds:

```typescript
export function verifyWebhookSignature(
  payload: string,
  signatureHeader: string,
  secret: string,
  toleranceSeconds: number = 300
): boolean {
  const parts = signatureHeader.split(",");
  const timestampPart = parts.find((p) => p.startsWith("t="));
  const signaturePart = parts.find((p) => p.startsWith("v1="));

  if (!timestampPart || !signaturePart) return false;

  const timestamp = parseInt(timestampPart.slice(2), 10);
  const now = Math.floor(Date.now() / 1000);

  if (Math.abs(now - timestamp) > toleranceSeconds) {
    return false; // Replay attack prevention
  }

  // Cryptographic constant-time comparison follows...
  return true;
}
```
