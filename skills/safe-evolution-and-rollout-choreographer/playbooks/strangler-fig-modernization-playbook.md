# Playbook: Strangler Fig Modernization Playbook

> Step-by-step procedural manual for decomposing monoliths into modern microservices using edge facades and zero-downtime slicing.

## Modernization Workflow Overview

```
Phase 0: Inventory ──> Phase 1: Deploy Facade ──> Phase 2: Extract Slice
                                                        │
Phase 5: Demolition <── Phase 4: Canary Shift <── Phase 3: Shadow Parity
```

---

## Phase-by-Phase Procedure

### Phase 0: System Boundary Inventory
1. Profile incoming HTTP/RPC traffic to identify high-volume, low-complexity endpoints.
2. Group endpoints into distinct domain boundaries (e.g. Identity, Catalog, Checkout, Billing).
3. Select the initial target slice: **always start with read-only, non-transactional endpoints** to establish confidence with zero data-corruption risk.

### Phase 1: Deploy Edge Interception Facade
1. Deploy an Envoy or API Gateway cluster in front of the legacy monolith.
2. Update DNS/Ingress routing so that $100\%$ of external requests terminate at the facade.
3. Configure the default route:
   ```yaml
   # envoy.yaml - Initial default pass-through
   routes:
     - match: { prefix: "/" }
       route: { cluster: legacy_monolith_cluster }
   ```
4. Verify that latency and throughput remain within baseline SLOs across 48 hours.

### Phase 2: Extract the Vertical Domain Slice
1. Build the new microservice implementing the target slice (e.g. `GET /api/v1/catalog/{id}`).
2. Connect the new service to the primary or read-replica database.
3. Deploy the new microservice to production behind an internal VIP.

### Phase 3: Shadow Parity Verification
1. Update the facade configuration to mirror traffic to the new microservice:
   ```yaml
   routes:
     - match: { prefix: "/api/v1/catalog" }
       route:
         cluster: legacy_monolith_cluster
         request_mirror_policies:
           - cluster: modern_catalog_service_cluster
             runtime_fraction:
               default_value: { numerator: 100, denominator: HUNDRED }
   ```
2. Feed both legacy and modern responses into an asynchronous diff engine.
3. Verify that:
   - Output mismatch rate is $< 0.001\%$.
   - Shadow p99 latency is equal to or lower than the legacy monolith.
   - Zero memory leaks or crash loops occur across $10^5$ requests.

### Phase 4: Canary Live Traffic Shifting
1. Shift live traffic dynamically using header or user ID hashing:
   - Day 1: $1\%$ live traffic to modern service.
   - Day 2: $5\%$ live traffic.
   - Day 3: $25\%$ live traffic.
   - Day 5: $50\%$ live traffic.
   - Day 7: $100\%$ live traffic.
2. Maintain the legacy path on standby with an instant kill-switch. If modern service error rate spikes $> 0.05\%$, flip routing back to legacy in $< 5$ seconds.

### Phase 5: Legacy Demolition
1. After the modern service runs at $100\%$ for 14 continuous days with zero incidents:
   - Remove the fallback route to the legacy monolith from the facade.
   - Delete the legacy handler code and models from the monolithic repository.
   - Drop obsolete legacy database tables after verifying zero read/write connections.
2. Repeat the process for the next vertical slice.
