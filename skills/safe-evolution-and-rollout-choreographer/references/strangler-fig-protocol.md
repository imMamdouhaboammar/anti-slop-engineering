# Reference: The Strangler Fig Protocol (Hyperscale Modernization)

> Never attempt a Big-Bang rewrite; encircle the monolith with an interception facade and strangle it slice by slice.

## The Big-Bang Rewrite Anti-Pattern

Attempting to replace a production monolithic service by writing a complete ground-up replacement in a separate repository and switching 100% of traffic on a scheduled weekend is one of the most reliable failure modes in software engineering:
- **Scope Creep & Schedule Slips:** The legacy system continues to evolve during the rewrite; the new system chases a moving target for months or years.
- **Undocumented Business Edge Cases:** Over years of operation, the legacy system accumulated hundreds of nuanced bug fixes and regulatory quirks that are omitted from the new specification.
- **Unbounded Blast Radius:** If the new system fails on cutover day, diagnosing the root cause across a brand-new codebase under 100% load is nearly impossible, forcing embarrassing rollbacks.

---

## The Strangler Fig Architecture

The Strangler Fig pattern (named after Australian strangler figs that germinate in the canopy of a host tree, slowly envelop it from outside, and eventually replace it) eliminates Big-Bang risk by running legacy and modern services concurrently behind an intelligent routing facade.

```
                  ┌───────────────────────────────┐
                  │      Client Applications      │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │   Edge Interception Facade    │
                  │   (API Gateway / Reverse Proxy)│
                  └───┬───────────────────────┬───┘
                      │                       │
           (Canary Traffic % / Slices)   (Unmigrated Paths)
                      │                       │
                      ▼                       ▼
          ┌───────────────────────┐   ┌───────────────────────┐
          │   Modern Microservice │   │    Legacy Monolith    │
          │   (Target System)     │   │    (Host System)      │
          └───────────────────────┘   └───────────────────────┘
```

---

## The Five Execution Phases

### Phase 1: Deploy the Interception Facade
Before touching any business logic, insert an edge routing layer (Envoy, Nginx, Cloudflare Workers, or Kong) directly in front of the legacy monolith. All client DNS and ingress traffic routes through this facade. Initially, the facade routes $100\%$ of requests directly to the legacy backend.

### Phase 2: Carve Vertical Domain Slices
Decompose the legacy monolith into bounded domain slices. Strict slicing sequence:
1. **Slice 1: Read-Only Paths:** Low-risk, high-throughput queries with zero persistent side-effects (e.g. `GET /api/v1/user/profile`).
2. **Slice 2: Asynchronous Events:** Background workers and event subscribers that can be processed idempotently from a shared queue.
3. **Slice 3: Idempotent State Mutations:** State-changing endpoints equipped with idempotency keys (e.g. `POST /api/v1/orders`).
4. **Slice 4: Complex Multi-Entity Transactions:** The most tightly coupled monolithic workflows, migrated only after storage and identity seams are proven.

### Phase 3: Shadow Parity Verification
Deploy the new microservice for the target slice. Configure the facade to mirror live requests in shadow mode. Run semantic diffing to verify output parity and latency characteristics over at least $10^5$ transactions without serving live traffic.

### Phase 4: Dynamic Canary Traffic Shifting
Shift live traffic to the new service using deterministic routing rules:
- **Tenant or User ID Hashing:** `hash(user_id) % 100 < canary_percentage` guarantees that a given user consistently hits the same version, preventing session oscillation.
- **Canary Tier Ramp:** $1\% \rightarrow 5\% \rightarrow 25\% \rightarrow 50\% \rightarrow 100\%$.
- **Automated Rollback Circuit:** If the facade observes $> 0.05\%$ HTTP 5xx errors or a $> 15\%$ p99 latency regression from the modern service, it immediately flips traffic back to the legacy monolith in $< 5$ seconds.

### Phase 5: Legacy Demolition & Decommissioning
Once the modern service sustains $100\%$ of traffic for the agreed baking period (typically 7–14 days):
1. Remove routing rules for that slice from the legacy monolith.
2. Delete unused database columns, tables, and internal helpers in the monolith.
3. Once all vertical slices are migrated, shut down the legacy compute cluster and simplify the facade.

---

## Migration Invariants

- **Zero Client Awareness:** Clients must never be required to change API URLs, headers, or authentication tokens during migration; the facade presents an invariant external contract.
- **Atomic State Synchronization:** If both legacy and modern systems write to shared data during the transition, use the Expand-Migrate-Contract pattern with dual-writing or CDC (Change Data Capture) replication to ensure zero data drift.
- **Uniform Telemetry:** Both legacy and modern handlers must export identical Prometheus/OpenTelemetry metrics (request count, error rate, p50/p90/p99 latency) to enable side-by-side dashboard evaluation.
