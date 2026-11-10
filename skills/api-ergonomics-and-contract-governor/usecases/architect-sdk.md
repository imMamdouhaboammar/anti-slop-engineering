# Use Case: Architect a Public SDK or Client Library

> Step-by-step workflow for designing a production-grade TypeScript SDK with Pit of Success defaults, discriminated unions, and progressive disclosure.

## Step 1: Establish Domain Types & Branded Identifiers

1. Identify all primary entities and their identifiers (e.g. `CustomerId`, `ChargeId`, `ApiKey`).
2. Define nominal branding helpers in `src/types/brands.ts`.
3. Model entity lifecycle statuses as tagged Discriminated Unions with a `status` discriminator.

---

## Step 2: Configure Pit-of-Success Defaults

1. Default network timeout: 10,000ms (`AbortSignal.timeout(10_000)`).
2. Default retries: 3 attempts with full-jitter exponential backoff on HTTP 408, 429, 502, 503, 504.
3. Automatic idempotency: auto-populate `Idempotency-Key` via `crypto.randomUUID()` on state mutations if omitted.
4. Default pagination limit: 20, ceiling: 100.

---

## Step 3: Implement 3-Tier Progressive Disclosure

1. **Tier 1 (One-Liner):** Expose simple methods on resource namespaces:
   ```typescript
   await client.charges.create({ amount: 5000, currency: "USD" });
   ```
2. **Tier 2 (Configured Options):** Provide optional secondary options argument for custom headers, timeout overrides, or metadata.
3. **Tier 3 (Escape Hatch):** Provide `client.raw.request()` and `ClientBuilder` for custom transports or streaming.

---

## Step 4: Standardize on RFC 9457 Problem Details

1. Define `ProblemDetailsError` extending `Error`.
2. Map HTTP non-2xx responses to structured problem details with machine codes (`code`), invalid parameters (`invalid_params`), and retryability (`retryable`).
3. Ensure `.toJSON()` masks sensitive credentials.

---

## Step 5: Verify Contract Ergonomics

1. Test hover readability: verify IDE tooltip renders clean type names.
2. Test exhaustiveness: verify `assertNever` catches missing switch branches.
3. Run `npx anti-slop-engineering contract audit <record.json> --json`.
