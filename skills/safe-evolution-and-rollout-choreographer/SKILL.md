---
name: safe-evolution-and-rollout-choreographer
description: Enforces Meta and Google SRE coexistence, wire compatibility, dark launches, feature flag lifecycle governance, and Strangler Fig migrations. Use when modifying network schemas, altering critical execution paths, introducing feature flags, refactoring legacy services, or planning rolling deployments — even if they do not explicitly say "rollout choreographer". Do NOT use for isolated internal helper refactors with no network, schema, or persistence boundary changes.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Safe Evolution & Rollout Choreographer (Meta & Google SRE Coexistence)

> New code never replaces old code instantly; production is a heterogeneous fleet where N-1 and N+1 coexist continuously.

## Why This Skill Is Needed & Target State

AI agents almost universally suffer from the **"Atomic Cutover Fantasy"**: generating code that assumes deployments happen instantaneously across 100% of servers, databases, and clients simultaneously. In massive-scale architectures (Meta, Google, Netflix), this assumption produces catastrophic outages:
- Deserialization panics when fleet pod $N+1$ sends payloads to pod $N$ during a 4-hour canary rollout.
- Broken mobile clients stuck on version $N-1$ when backend fields are deleted or types change.
- Hidden latency explosions or data corruptions when rewritten critical paths are exposed to live traffic without prior shadow execution.
- Accumulation of zombie feature flags with no kill-switches or expiration dates, metastasizing into untestable combinatorial complexity ($2^N$ execution states).
- Catastrophic "Big-Bang" rewrite failures that attempt to replace legacy monoliths overnight instead of incrementally strangling them behind a facade.

The target state is **Production Coexistence Choreography**: every schema change, critical code optimization, and legacy refactoring is designed for progressive rollout, multi-version coexistence, empirical shadow verification, and deterministic zero-downtime deprecation.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Modifying an API contract, protobuf/Thrift schema, or event payload | Enforce bidirectional wire compatibility ($N-1 \leftrightarrow N+1$), additive-only changes, and two-phase deprecation |
| Rewriting or optimizing a high-throughput read or compute path | Implement asynchronous Dark Launch / Shadow Reads with statistical parity comparison and zero latency penalty |
| Introducing a new feature, experimental algorithm, or critical flow | Wrap in an audited Feature Flag with an instant Kill-Switch, strict TTL ($\le 90$ days), and automated debt retirement |
| Modernizing or replacing an existing monolithic service or legacy subsystem | Apply the Strangler Fig Protocol: interception facade, vertical slice routing, parity canary, and legacy demolition |
| Internal pure helper edits with zero network, schema, or storage boundaries | Do not activate; follow standard Anti-Slop Engineering BUILD/FIX gates |

---

## The Four Absolute Laws of Coexistence

1. **The Wire Compatibility Axiom ($N-1 \leftrightarrow N+1$ Coexistence):** Systems must never assume a uniform version across the fleet. Every serialized payload, gRPC/Thrift buffer, HTTP contract, and database row must be readable by both version $N$ and version $N+1$ simultaneously. All field additions must be optional with safe defaults; deletions and renames require a multi-release expand-contract deprecation cycle.
2. **The Proving Ground Axiom (Shadow Reads & Side-Effect Fencing):** Critical paths must prove statistical correctness and latency equivalence under real production load before serving live user traffic. Shadow execution must run asynchronously, never add latency to user responses, and must be strictly fenced: shadow pipelines are strictly prohibited from mutating persistent state, invoking external payment APIs, or firing real user communications.
3. **The Feature Flag Hygiene & Kill-Switch Axiom:** Every dynamic branch is operational debt. Every flag must possess a sub-second remote Kill-Switch, an explicit owner, a creation timestamp, and a hard TTL ($\le 90$ days). Flags that pass their retirement date fail CI gates. Once a feature graduates to 100%, the flag branch, fallback paths, and configuration keys must be scheduled for immediate demolition.
4. **The Strangler Fig Axiom (Continuous Interception Over Big-Bang Rewrites):** Direct total rewrites of operational legacy systems are prohibited. Modernization must proceed through an edge interception facade, incrementally redirecting vertical domain slices to the new implementation while maintaining continuous end-to-end telemetry and automated rollback capabilities.

---

## Invariant Rules

1. **Tolerant Reader pattern across all boundaries:** Serializers and deserializers must ignore unknown fields rather than throwing errors. In protobuf/Thrift, field tags must never be renumbered or reused. In JSON/REST, new response fields must never break client parsers.
2. **Two-phase deprecation for deletions:** Never drop an API field or payload key in the same release that introduces its replacement. Release 1: Introduce new field alongside old, write to both. Release 2: Switch reads to new field. Release 3: Deprecate old field. Release 4: Remove old field after client traffic on $N-1$ drops to zero.
3. **Fenced shadow side-effects:** When mirroring traffic for dark launches, write operations must route to synthetic sandboxes, in-memory mocks, or transaction rollbacks. Side-effects that touch external vendors (Stripe, Twilio, SendGrid) must be neutralized in shadow mode via compile-time or runtime guards.
4. **Statistical parity thresholds:** Before promoting a shadow-tested path to a live canary, automated diff engines must measure a payload mismatch rate below the acceptable error budget (e.g. $< 0.001\%$) over at least $10^5$ requests, with p99 latency $\le$ legacy baseline.
5. **Sub-second Kill-Switch mechanism:** Feature flags must be backed by distributed configuration stores with local in-memory caching and real-time push invalidation (e.g., etcd, Redis PubSub, Consul, AWS AppConfig). Evaluating a flag must take $< 1\mu\text{s}$ on the hot path.
6. **Bounded Flag TTL ($\le 90$ days):** No temporary feature flag may exist indefinitely. Every flag definition must record `created_at`, `expires_at`, and `owner`. Any flag alive beyond `expires_at` without an approved operational extension blocks deployment pipelines.
7. **Reverse-proxy routing facade:** Strangler Fig implementations must place an API gateway or reverse proxy in front of legacy services before modifying a single line of business logic. Routing decisions must be dynamically configurable based on headers, user ID hashes, or route prefixes.
8. **Automated canary rollback triggers:** Canaries (1%, 5%, 25%, 100%) must be wired directly to SLO error budget burn rates. If the error rate increases by $> 0.05\%$ or p99 latency spikes by $> 10\%$ during any canary tier, the deployment orchestrator must automatically trip the kill-switch and roll back within 30 seconds.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Rolling deployment schema & API contract evolution | [Audit Wire Compatibility](usecases/audit-wire-compatibility.md) | [Wire Compatibility Matrix](references/wire-compatibility-n-minus-one.md) |
| Dark launching, traffic mirroring & shadow diffing | [Choreograph Rollout](usecases/choreograph-rollout.md) | [Dark Launches & Shadow Reads](references/dark-launches-and-shadow-reads.md) |
| Feature flag addition, kill-switch design & TTL audit | [Choreograph Rollout](usecases/choreograph-rollout.md) | [Feature Flag Lifecycle](references/feature-flag-lifecycle-and-killswitch.md) |
| Monolith decomposition or legacy service replacement | [Strangle Legacy System](usecases/strangle-legacy-system.md) | [Strangler Fig Protocol](references/strangler-fig-protocol.md) |
| Machine-verifiable rollout assessment record audit | [Record Contract](references/rollout-record-contract.md) | `scripts/rollout_guard.py` |

---

## Mandatory Pre-Execution Interrogation Matrix

Before introducing schema updates, feature switches, or service rewrites, evaluate these five vectors:

- **Distrust of Fleet Synchronicity:** What happens if pod A runs version $N+1$ while pod B runs version $N$? If pod A writes an event to Kafka or a row to Redis, can pod B parse it without crashing? If pod B sends an RPC request to pod A, will pod A handle missing newly-added parameters gracefully?
- **Distrust of Client Recency:** What is the oldest active mobile client or external API consumer? Will deleting or renaming this field cause crashes for users who have not updated their mobile app in 6 months?
- **Distrust of Shadow Execution:** Is the shadow execution path truly decoupled from user-facing latency? What guarantees that shadow exceptions never bubble up to fail user requests? Are all external side-effects (database writes, emails, charges) definitively intercepted and neutralized?
- **Distrust of Flag Longevity:** Who owns this feature flag? What is its exact removal date? If the author leaves the company next month, is there a documented plan and verification test to remove the dead branch?
- **Distrust of Rewrite Scope:** Are we attempting a Big-Bang cutover? Why is this not broken down into an edge facade and three independent vertical slices? What is the atomic fallback if the new subsystem experiences a memory leak at 50% traffic?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Single-PR field deletions/renames:** Removing or renaming an active field in an API response, Protobuf definition, or database table without a multi-release deprecation buffer.
2. **Synchronous shadow execution:** Running shadow code inline on the user request thread, adding latency or propagating uncaught shadow panics to the client.
3. **Unfenced shadow writes:** Permitting shadow code paths to perform real mutations against production databases or third-party APIs (e.g., executing credit card auth in shadow mode).
4. **Undead / zombie feature flags:** Introducing feature flags without an `expires_at` timestamp, owner, and kill-switch, leading to perpetual $2^N$ combinatorial testing debt.
5. **Big-Bang cutovers:** Deprecating a legacy system by switching 100% of traffic overnight without an intermediate Strangler Fig facade and canary ramp.
6. **Flag name recycling:** Reusing a retired flag name for a new feature (the exact Knight Capital disaster mechanism).

---

## Required Output & Review Workflow

Structure all rollout designs, code changes, and PR reviews through this 3-phase discipline:

1. **Coexistence Pre-Mortem:** Identify fleet version skews ($N-1 \leftrightarrow N+1$), potential serialization mismatches, and shadow side-effect hazards.
2. **Choreographed Implementation:** Emit code equipped with bidirectional schema defaults, asynchronous shadow diffing, kill-switch wiring, and explicit flag expiration dates.
3. **Verifiable Canary & Demolition Plan:** Provide concrete canary progression stages (1% -> 5% -> 25% -> 100%), automated rollback SLO triggers, and a scheduled demolition ticket to strip dead fallback code once stable.

When a durable architectural record is warranted, save a JSON assessment following the [Rollout Record Contract](references/rollout-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering rollout audit <record.json> --json
# or: python3 scripts/rollout_guard.py audit <record.json> --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central orchestration index for safe evolutions and rollout choreography.
- **[Meta & Google SRE Rollout Playbook](playbooks/meta-google-sre-rollout-playbook.md)**: Gatekeeper patterns, canary tiers, baking periods, and automated circuit breaking.
- **[Strangler Fig Modernization Playbook](playbooks/strangler-fig-modernization-playbook.md)**: Step-by-step monolith decomposition, facade routing, and legacy decommissioning.
- **[Rollout Booby-Trap Catalog](playbooks/references/rollout-booby-traps.md)**: Forensic case studies of catastrophic rollout failures (Knight Capital, serialization panics, shadow double-billing).
- **[Wire Compatibility Matrix](references/wire-compatibility-n-minus-one.md)**: In-depth protocols for Protobuf, Thrift, JSON, and GraphQL forward/backward coexistence.
- **[Dark Launches & Shadow Reads](references/dark-launches-and-shadow-reads.md)**: Architecture for traffic mirroring, asynchronous diffing, side-effect fencing, and statistical parity.
- **[Feature Flag Lifecycle & Kill-Switch Governance](references/feature-flag-lifecycle-and-killswitch.md)**: State machine, sub-second kill-switches, TTL enforcement, and debt eradication.
- **[Strangler Fig Protocol](references/strangler-fig-protocol.md)**: Edge facade patterns, slice decomposition, parity routing, and teardown milestones.
- **[Rollout Record Contract](references/rollout-record-contract.md)**: Schema for persistent, machine-auditable rollout assessment records.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Deserialization crash | `UnexpectedFieldException` or missing tag errors on older fleet pods | Adopt Tolerant Reader, set default values, and do not remove fields |
| Shadow latency spillover | User-facing p99 latency increases proportionally to shadow complexity | Decouple shadow execution to async queue or fire-and-forget worker |
| Shadow side-effect leak | Duplicate notifications sent or test records in production databases | Mock/stub mutation sinks and inject no-op execution guards in shadow context |
| Zombie flag proliferation | Hundreds of stale `if (isFeatureEnabled())` branches littering codebase | Enforce max 90-day TTL; fail CI on expired flags; schedule demolition PRs |
| Big-Bang cutover brownout | 500 errors and CPU spikes immediately following 100% traffic shift | Roll back to 0%; place Strangler facade; ramp traffic in canary increments |

---

## Delegated Skills

- `anti-slop-engineering`: Follow clean-room development rules and prevent code bloat once the rollout strategy is locked.
- `zero-downtime-migration-gate`: Coordinate low-level database schema migrations (Expand-Migrate-Contract) supporting the rollout.
- `paranoid-principal-architect`: Enforce 10M scale, zero-trust perimeter validation, and race condition defenses on both old and new paths.
- `observability-and-slo-gate`: Define telemetry, metrics, and error budget burn alerts driving automated canary rollbacks.

---

## Completion and Limits

The task is complete when wire compatibility is proven for $N-1$ and $N+1$, shadow execution operates asynchronously with fenced side-effects and parity checks, feature flags possess tested kill-switches and expiry dates, and the Strangler Fig facade permits immediate safe rollback. An audit may validly emit `refuse` or `pause` if a proposed rollout introduces breaking wire changes or un-fenced mutations without canary stages.
