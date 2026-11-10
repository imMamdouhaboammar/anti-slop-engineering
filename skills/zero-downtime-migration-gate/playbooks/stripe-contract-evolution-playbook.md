# Playbook 2: Stripe Wire Contract & API Evolution Discipline

> Inspired by Stripe's industry-standard API versioning architecture, Protocol Buffers wire safety, and GraphQL continuous evolution.

## 1. The Multi-Version Client Reality

Unlike database connections (which you control within your server fleet), external wire consumers operate on asynchronous release cadences:
- **Rolling Server Fleet ($N$ and $N-1$):** Internal microservices, SSR frontends, and queue consumers coexist for 5–60 minutes during canary/rolling deploys.
- **Browser Web Apps (SPAs):** Users leave browser tabs open for days. A new backend deployment immediately serves requests from yesterday's JavaScript bundle.
- **Mobile Apps (iOS / Android):** App Store review delays and user update habits mean Version $N-1$, $N-2$, and $N-3$ remain active in the wild for 6–12 months.
- **Partner Webhooks & Public SDKs:** Third-party integrations expect stable JSON payloads for years.

---

## 2. Dual-Payload & Tolerant Reader Architecture

When evolving a field in REST/JSON without changing the API version header:

### Request Evolution (Client $\rightarrow$ Server)
Accept **both** the legacy shape and the expanded shape at the boundary schema parser, normalizing them into the canonical domain model:

```typescript
import { z } from "zod";

export const UpdateCustomerRequestSchema = z.object({
  // Accept new split fields OR legacy fullName field during Phase 1 & 2
  givenName: z.string().min(1).max(120).optional(),
  familyName: z.string().min(1).max(120).optional(),
  fullName: z.string().min(1).max(240).optional(),
}).refine(
  (data) => Boolean((data.givenName && data.familyName) || data.fullName),
  { message: "Must supply either (givenName + familyName) or legacy fullName" }
);
```

### Response Evolution (Server $\rightarrow$ Client)
Emit **both** the new fields and the synthesized legacy field until all $N-1$ clients have drained:

```typescript
export interface CustomerResponseDto {
  id: string;
  givenName: string;
  familyName: string;
  /** @deprecated Retained for N-1 client forward compatibility until Phase 3 */
  fullName: string;
}
```

---

## 3. Stripe-Style Date-Pinned Version Gates

When a change cannot be expressed purely additively (e.g. changing a nested object structure or replacing a float currency field with an integer minor-unit structure), isolate compatibility transformations into declarative **Version Change Modules**:

1. **Canonical Core:** Controllers and domain services only speak the latest schema (`2026-11-10`).
2. **Version Resolution:** Extract caller version from `Stripe-Version` / `X-API-Version` header, falling back to the account's pinned default version.
3. **Response Downcasting Pipeline:** If caller version `< 2026-11-10`, apply pure transformation functions in reverse chronological order:
   - Transform `2026-11-10 -> 2026-05-01`: Copy `amount_cents` back into legacy `amount` field and preserve legacy status enum mapping.
4. **Zero Domain Pollution:** Business logic remains 100% clean of `if (apiVersion === 'old')` branches; all compatibility logic lives strictly in the version transform gateway.

---

## 4. Event Queue & Pub/Sub Schema Evolution (Kafka / SQS / PubSub)

In asynchronous messaging, an $N$ producer may publish messages consumed by an $N-1$ worker, or an $N$ worker may replay dead-letter queue (DLQ) messages written 14 days ago by an $N-1$ producer:
1. **Never rename event types in place** without registering dual-consumers first.
2. **Envelope Versioning:** Include `schema_version: 1` in every event envelope.
3. **Protobuf Wire Safety:** Enforce `buf breaking` rules—never reuse tag numbers, always mark removed tags and names `reserved`, and ensure every enum starts with `ENUM_NAME_UNSPECIFIED = 0`.
