# Reference: Dark Launches & Shadow Reads

> Never test in the dark by guessing; verify critical code paths in shadow mode under full production concurrency before flipping live traffic.

## Core Definition & Operating Paradigm

A **Dark Launch** deploys code to production without exposing its behavior or results directly to end users. A **Shadow Read** mirrors live incoming production traffic to an unreleased secondary implementation, compares the resulting output against the baseline legacy implementation, and logs discrepancies without affecting user latency or availability.

$$\text{User Request} \longrightarrow \text{Baseline Engine (N)} \xrightarrow{\text{Immediate Return}} \text{User Response}$$
$$\qquad\qquad\qquad\quad \searrow \text{Shadow Worker (N+1, Async \& Fenced)} \xrightarrow{\text{Compare \& Telemetry}} \text{Diff Store}$$

---

## The Four Iron Rules of Shadow Execution

1. **Zero User Latency Impact (Decoupled Asynchrony):** Shadow calls must never execute sequentially in the blocking path of a user request. They must run in background worker threads, dedicated goroutines, or via asynchronous event queues (Kafka, Redis, SQS).
2. **Absolute Side-Effect Fencing:** Shadow execution is strictly prohibited from mutating persistent production state or calling external third-party services. Shadow runs must use sandbox storage, in-memory stubs, or database transactions that execute an unconditional `ROLLBACK`.
3. **Fail-Silent Isolation:** An uncaught exception, panic, or timeout in shadow code must never propagate to the user request. Shadow errors must increment telemetry counters and terminate cleanly without interrupting the primary response.
4. **Automated Resource Guardrails:** Shadow workers must enforce strict CPU, memory, and timeout caps. If shadow processing consumes more than 10% of node CPU, or error rates exceed 1%, an automatic circuit breaker must disarm shadow traffic instantly.

---

## Architectural Topologies for Traffic Mirroring

### Topology A: Edge Proxy Mirroring (Envoy / Nginx / Cloudflare)
Best for stateless microservices and HTTP read APIs.

- **Mechanism:** The ingress proxy clones the HTTP request body and headers. One copy routes to the stable cluster (upstream N); the second copy asynchronously tees to the shadow cluster (upstream N+1) via `shadow_policy` in Envoy.
- **Advantage:** Completely isolated compute and memory; primary service code is unmodified.
- **Limitation:** Cannot easily compare outputs in real-time without an out-of-band diff collector.

### Topology B: In-Process Asynchronous Mirroring (TypeScript / Go / Rust)
Best for algorithmic refactors, database query changes, and ranking models.

- **Mechanism:** The application controller invokes the primary service, schedules the shadow call on an asynchronous microtask or worker pool, and returns the primary result immediately:
```typescript
// Fast primary response
const primaryResult = await primaryService.compute(input);

// Asynchronous, unblocked shadow execution
queueMicrotask(async () => {
  try {
    const shadowResult = await shadowService.compute(input, { dryRun: true });
    diffEngine.compare(primaryResult, shadowResult, { context: input.id });
  } catch (err) {
    telemetry.increment("shadow.failure", { reason: err.message });
  }
});

return primaryResult;
```

---

## The Semantic Diffing & Normalization Engine

Naive JSON string comparison produces false-positive parity failures due to non-deterministic fields. The comparison engine must normalize:

1. **Timestamps & Epochs:** Strip or mask `created_at`, `updated_at`, `timestamp`.
2. **Dynamic Request & Trace Identifiers:** Ignore `trace_id`, `request_id`, `span_id`.
3. **Floating Point Rounding:** Compare floating point numbers with an epsilon tolerance ($\epsilon = 10^{-6}$).
4. **Unordered Collections:** Sort arrays of objects by canonical IDs before diffing.
5. **Masked PII / Token Salts:** Normalize random salts or ephemeral session tokens.

### Statistical Parity Criteria for Promotion

A shadow implementation is eligible for promotion to a live canary only when:
- **Sample Size:** Minimum $100,000$ consecutive production requests evaluated.
- **Mismatch Rate:** $< 0.001\%$ unexplained semantic differences.
- **Latency Parity:** Shadow p95 and p99 compute latency $\le$ baseline p95 and p99.
- **Resource Footprint:** Memory allocation per request does not exhibit monotonic growth (zero memory leaks).

---

## Side-Effect Fencing Checklist

Before enabling shadow mirroring for any endpoint:
- [ ] Are all database write handles replaced with read-only replicas or rollback mocks?
- [ ] Are email, SMS, and push notification dispatchers replaced with null sinks?
- [ ] Are third-party payment gateways (Stripe, Adyen, PayPal) completely disabled or routed to mock sandboxes?
- [ ] Are Kafka/RabbitMQ producer topics directed to a `.shadow` dead-letter queue?
- [ ] Is shadow execution wrapped in a top-level `try/catch` with zero possibility of user-facing failure?
