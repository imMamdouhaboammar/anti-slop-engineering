# Playbook: Meta & Google SRE Rollout Choreography

> Progressive canary progression, Automated Canary Analysis (ACA), Gatekeeper dynamic targeting, and automated error budget circuit breaking.

## Architecture of Progressive Release Tiers

Never deploy a non-trivial change across the entire fleet at once. Google SRE and Meta production infrastructure divide rollouts into strict canary tiers, each with a defined baking duration and Automated Canary Analysis (ACA) gates:

```
[Tier 0: Dogfood] ──> [Tier 1: Canary 1%] ──> [Tier 2: Fleet 5%]
 (Internal Users,       (2-Hour Bake,           (4-Hour Bake,
  Zero SLA Impact)       ACA Baseline Diff)      Regional Cohort)
                                                        │
                                                        ▼
[Tier 5: Fleet 100%] <── [Tier 4: Fleet 50%] <── [Tier 3: Fleet 25%]
 (Full Fleet Release)     (24-Hour Bake,          (12-Hour Bake,
                           Cross-Region)           Multi-Region)
```

### Tier Specification Matrix

| Tier | Traffic % | Minimum Bake Time | Primary Validation Gate | Automated Rollback Trigger |
| --- | --- | --- | --- | --- |
| **Tier 0 (Dogfood)** | Internal staff | 4 hours | Functional smoke tests, developer feedback | Unhandled exceptions $> 0.1\%$ |
| **Tier 1 (Canary)** | 1% random hash | 2 hours | Statistical diffing vs identical baseline node | Error rate increase $> 0.05\%$, p99 latency $> 10\%$ |
| **Tier 2 (Regional)** | 5% (1 region) | 4 hours | Regional database connection pool & CPU load | Error budget burn rate $> 14.4\times$ |
| **Tier 3 (Multi-Region)**| 25% | 12 hours | Cache hit ratio parity, downstream RPC health | Error budget burn rate $> 6\times$ |
| **Tier 4 (Majority)** | 50% | 24 hours | Daily peak traffic cycle endurance | Any sustained SLO regression |
| **Tier 5 (Full Fleet)**| 100% | 7 days | Baking window before feature flag deprecation | Automated alerting |

---

## Automated Canary Analysis (ACA) Principles

A common mistake is comparing canary metrics against the entire existing production cluster. The canary cluster must be evaluated against an identically-sized **baseline cluster**:

- **Canary:** Pod running version $N+1$, receiving $X\%$ traffic.
- **Baseline:** Pod running version $N$, receiving $X\%$ traffic, provisioned with identical CPU, memory, and kernel configurations.

Comparing Canary to Baseline isolates code-induced changes from ambient traffic fluctuations, diurnal spikes, or underlying cloud provider degradation.

---

## Meta Gatekeeper Dynamic Targeting Pattern

Meta separates code deployment from feature activation using the Gatekeeper system:
1. **Binary Deploy First:** Code is shipped across 100% of fleet machines while disabled by default.
2. **Dynamic Population Hashing:** Gatekeeper targets cohorts using deterministic user ID hashing:
   $$\text{Hash}(\text{User ID} + \text{Salt}) \pmod{100} < \text{Target Percentage}$$
3. **Multi-Dimensional Gates:** Gatekeeper allows layering criteria:
   - Target: `App Version >= 412.0` AND `Locale == 'ar_SA'` AND `Hash % 100 < 10`.
4. **Emergency Kill-Switch Invalidation:** Configuration updates are propagated via push channels (e.g. Gorilla / Redis PubSub) to in-memory caches on every node within 500 milliseconds.

---

## Automated Error Budget Circuit Breaker Protocol

When an issue occurs during a rollout, humans react in minutes; automated breakers react in seconds:

```
                  ┌───────────────────────────────┐
                  │ Continuous SLO Telemetry Stream│
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │ Error Budget Burn Rate Engine │
                  └───────────────┬───────────────┘
                                  │
              Burn Rate > 14.4x ? │ (2% budget consumed in 1 hr)
                     ┌────────────┴────────────┐
                     │                         │
                   YES                         NO
                     │                         │
                     ▼                         ▼
        ┌─────────────────────────┐   ┌─────────────────────────┐
        │ TRIP AUTOMATED ROLLBACK │   │ Advance to Next Tier    │
        │ - Engage Kill-Switch    │   │ (if bake duration met)  │
        │ - Revert Gateway % to 0%│   └─────────────────────────┘
        │ - Page On-Call SRE      │
        └─────────────────────────┘
```

### Rollback Execution Command Script

```bash
# Emergency single-command feature flag neutralization
curl -X POST "https://config.internal.domain/v1/flags/checkout_v2/kill" \
  -H "Authorization: Bearer ${SRE_EMERGENCY_TOKEN}" \
  -d '{"reason": "SLO burn rate exceeded 14.4x on Tier 2 canary"}'

# Verify fleet-wide propagation within 1 second
curl -s "https://telemetry.internal.domain/v1/metrics/flags/checkout_v2/active_nodes" | jq .
```
