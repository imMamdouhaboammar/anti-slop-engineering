# Strangle Legacy System: Zero-Downtime Monolith Decomposition

Use this workflow when modernizing a legacy system, replacing a service, or decomposing a monolithic architecture.

## Step-by-Step Modernization Procedure

### 1. Perimeter Mapping & Slicing Strategy
1. Never plan a wholesale "re-platforming" rewrite; reject Big-Bang cutovers.
2. Group monolithic routes by domain boundaries.
3. Select an isolated, read-only vertical slice (e.g. `GET /api/v1/user/settings`) as the initial milestone.

### 2. Deploy the Interception Facade
1. Place an edge proxy (Envoy, Kong, Nginx, or API Gateway) in front of the legacy monolith.
2. Direct all client DNS and ingress traffic to the facade.
3. Configure default routing to forward $100\%$ of traffic to the legacy monolith cluster.
4. Establish baseline latency and error rate telemetry.

### 3. Build & Deploy Target Microservice
1. Implement the selected vertical slice in the modern tech stack.
2. Ensure the new service satisfies all wire compatibility and zero-trust perimeter invariants.
3. Deploy the service to production behind an internal service mesh or private VIP.

### 4. Shadow Mirroring & Parity Validation
1. Configure the facade to asynchronously mirror live traffic for the slice to the new service.
2. Run automated semantic diffing against baseline responses.
3. Verify:
   - Output mismatch rate is $< 0.001\%$.
   - p99 compute latency $\le$ legacy monolith.
   - Resource utilization (CPU/memory) is stable across $10^5$ transactions.

### 5. Deterministic Canary Ramp & Rollback Wiring
1. Route live traffic based on user ID hashing:
   - $1\%$ on Day 1
   - $5\%$ on Day 2
   - $25\%$ on Day 3
   - $50\%$ on Day 5
   - $100\%$ on Day 7
2. Wire automated circuit breaker: if error rates spike $> 0.05\%$, flip routing back to legacy monolith in $< 5$ seconds.

### 6. Legacy Demolition
1. After 14 consecutive days of 100% stable execution:
   - Remove the fallback route from the facade.
   - Strip the legacy handler and models from the monolithic codebase.
   - Decommission legacy database tables and compute resources.
2. Proceed to the next vertical domain slice.
