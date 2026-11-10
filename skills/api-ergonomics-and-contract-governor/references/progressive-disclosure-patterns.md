# Progressive Disclosure Patterns

> Progressive disclosure organizes complexity so that common tasks are trivial, while advanced, edge-case controls remain fully accessible without cluttering the primary surface.

## The 3-Tier API Architecture

```
┌────────────────────────────────────────────────────────┐
│  Tier 1: High-Level Facade (1-liner, zero friction)    │
│  await client.charges.create({ amount: 5000, ... })     │
└───────────────────────────┬────────────────────────────┘
                            │ Delegates to
┌───────────────────────────▼────────────────────────────┐
│  Tier 2: Configured Options (structured overrides)     │
│  { captureMethod: "manual", idempotencyKey: "...",     │
│    metadata: { orderId: "123" }, timeoutMs: 15000 }    │
└───────────────────────────┬────────────────────────────┘
                            │ Powered by
┌───────────────────────────▼────────────────────────────┐
│  Tier 3: Core Primitives & Pipeline Engine             │
│  ClientBuilder, RequestSigner, StreamingTransport,     │
│  CustomRetryStrategy, RawHttpExecutor                  │
└────────────────────────────────────────────────────────┘
```

---

## Tier 1: One-Liner High-Level Facade

The primary entry point addresses the 80% developer scenario with minimal syntax and maximal readability:

```typescript
// Tier 1: 80% use case in a single call
const charge = await client.charges.create({
  amount: 5000,
  currency: asCurrencyCode("USD"),
});
```

- Zero unnecessary constructor hops.
- Defaults apply automatically: automatic idempotency key, default 10s timeout, automatic retries with exponential backoff and jitter.

---

## Tier 2: Configured Options Bag

When callers need specialized behavior (e.g. manual authorization, custom metadata, or tighter timeout bounds), they supply typed options without changing the method signature:

```typescript
// Tier 2: Explicit operational tuning
const charge = await client.charges.create(
  {
    amount: 5000,
    currency: asCurrencyCode("USD"),
    captureMethod: "manual",
    metadata: { orderId: "ord_9901" },
  },
  {
    idempotencyKey: asIdempotencyKey("user_req_abc123"),
    timeoutMs: 5_000,
    headers: { "X-Audit-Context": "compliance-flow" },
  }
);
```

- Options are placed in an optional second argument (or nested bag) to keep the primary payload uncluttered.
- Every option is strictly typed with autocomplete hints and docstrings.

---

## Tier 3: Core Primitives & Escape Hatches

For power users who need custom transport protocols, mock transports, custom telemetry middleware, or raw byte-level streaming:

```typescript
// Tier 3: Power user escape hatch
const rawResponse = await client.raw.request({
  method: "POST",
  path: "/v1/charges",
  body: rawStream,
  headers: { "Content-Type": "application/octet-stream" },
  signal: abortController.signal,
});

// Or fluent pipeline builder:
const customClient = new ClientBuilder()
  .withApiKey(apiKey)
  .withTransport(new CustomHttp2Transport())
  .withRetryStrategy(new StrictBackoffStrategy({ maxRetries: 5 }))
  .build();
```

- Primary API objects hold references to Tier 3 primitives, but Tier 3 primitives do not pollute the root autocomplete index of `client.*`.
