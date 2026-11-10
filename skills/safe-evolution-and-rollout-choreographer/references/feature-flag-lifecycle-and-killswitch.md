# Reference: Feature Flag Lifecycle & Kill-Switch Governance

> Every feature flag is a high-interest technical loan; without an explicit expiration date and a working kill-switch, it metastasizes into an operational landmine.

## The Operational Threat of Zombie Flags

In unmanaged systems, feature flags are frequently created to guard a launch but never removed. Over time, codebases accumulate dozens of stale conditional branches (`if (featureEnabled) ... else ...`). This causes:
- **Combinatorial Explosion:** 20 uncoordinated boolean flags produce $2^{20} = 1,048,576$ possible execution permutations, making comprehensive testing impossible.
- **The Knight Capital Disaster (Flag Recycling):** In 2012, Knight Capital reused an obsolete feature flag toggle for an unverified automated trading algorithm. The dead code path reactivated legacy execution logic, generating \$440 million in errant trades and bankrupting the firm within 45 minutes.
- **Code Rot:** Engineers hesitate to touch old paths because nobody knows whether a flag is still active for a VIP customer or internal tester.

---

## The Six-State Flag Lifecycle Machine

```
[1. DRAFT] ──────> [2. SHADOW] ──────> [3. CANARY] ──────> [4. GRADUATED]
(Dev / Local)     (Traffic Mirroring)   (1% -> 100%)       (100% Live)
                                                                 │
                                                                 ▼
[6. TOMBSTONED] <────────────────────────────────────── [5. DEPRECATED]
(Code Stripped,                                          (Demolition PR,
 Key Blacklisted)                                         Fallback Frozen)
```

1. **DRAFT / EXPERIMENTAL:** Feature under development. Restricted to local testing or internal dogfood accounts ($0\%$ public traffic).
2. **SHADOW / DARK:** Code deployed across the fleet, executing in asynchronous shadow mode with outputs diffed against baseline ($0\%$ user-facing traffic).
3. **CANARY / RAMP:** Progressive live deployment across tiered user percentages ($1\% \rightarrow 5\% \rightarrow 25\% \rightarrow 50\% \rightarrow 100\%$).
4. **GRADUATED / STABLE:** Feature running at $100\%$ for all target cohorts. Fallback path remains armed only during the baking observation window (maximum 14 days).
5. **DEPRECATED:** Feature marked for demolition. The fallback code path is frozen. An automated refactoring PR is generated to remove the conditional check.
6. **TOMBSTONED / REMOVED:** Code branches stripped from git repository. The flag identifier is permanently registered in a blacklist to prevent future name reuse.

---

## The Sub-Second Kill-Switch Architecture

When a canary rollout triggers an SLO error budget burn, flipping the kill-switch must neutralize the regression globally within one second without deploying code.

### Invalidation Performance Requirements

| Layer | Requirement | Implementation |
| --- | --- | --- |
| Evaluation Latency | $< 1 \mu\text{s}$ per check | Evaluated directly against an in-process local memory map. Never perform remote HTTP or SQL queries on the request hot path. |
| Invalidation Latency | $< 1,000 \text{ms}$ fleet-wide | Centralized configuration service (etcd, Redis PubSub, Consul, LaunchDarkly) broadcasts update events over long-lived WebSocket / gRPC streams to invalidate node local caches. |
| Fallback on Disconnect | Fail-Safe Default | If a node loses connection to the configuration stream, it must retain its last known stable state and log an operational warning. It must never block execution threads. |

---

## Mandatory Feature Flag Contract

Every feature flag declared in code or configuration must satisfy this schema contract:

```typescript
export interface FeatureFlagDefinition {
  /** Unique snake_case identifier */
  id: string;
  /** Explicit team or engineer email */
  owner: string;
  /** ISO timestamp of flag creation */
  created_at: string;
  /** Hard expiration timestamp (maximum 90 days from creation) */
  expires_at: string;
  /** Current lifecycle phase */
  phase: "draft" | "shadow" | "canary" | "graduated" | "deprecated" | "tombstoned";
  /** Fallback boolean value when kill-switch is engaged */
  kill_switch_fallback: boolean;
  /** Rollout percentage integer [0 - 100] */
  rollout_percentage: number;
  /** Issue tracking ticket for flag code removal */
  demolition_ticket: string;
}
```

---

## Flag Hygiene Guardrails

1. **Hard 90-Day TTL:** No feature flag may have a lifespan exceeding 90 days from `created_at`. Flags surviving beyond `expires_at` automatically fail pre-commit and CI verification checks (`scripts/rollout_guard.py`).
2. **One Flag, One Purpose:** A feature flag must control a single isolated change. Never bundle multiple unrelated functional improvements under a single shared flag.
3. **No Flag Re-Use:** When retiring `enable_v2_checkout`, that exact string must never be declared again for any future experiment. The flag store must reject duplicate identifiers forever.
4. **Demolition PR on Graduation:** When a flag reaches 100% rollout and the baking period expires, the owning engineer must merge the demolition PR stripping the conditional branch within 5 business days.
