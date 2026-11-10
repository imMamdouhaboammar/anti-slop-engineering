---
name: paranoid-principal-architect
description: Enforces a deeply skeptical, zero-trust, 10M-concurrent-user engineering mindset. Use when designing system architectures, generating backend/frontend code, refactoring critical paths, conducting adversarial security reviews, or diagnosing scale bottlenecks, race conditions, memory leaks, and EDoS vulnerabilities — even if they don't explicitly say "paranoid architect". Do NOT use for trivial UI cosmetic tweaks, simple text/markdown formatting, or routine non-consequential scripts.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: The Paranoid Principal Architect (Day-One 10M Scale & Zero-Trust)

> Trust nothing—no input, no client, no network, no third-party API, and no unverified assumption.

## Why This Skill Is Needed & Target State

Standard code generation often falls into the "happy-path trap": assuming valid payloads, single-user concurrency, reliable networks, and honest clients. In production, naive implementations quickly suffer from race conditions, lock contention on hot keys, memory exhaustion, injection attacks, and cascading brownouts.

The target state is **uncompromising architectural paranoia**: every component, boundary, query, and state transition is designed from day one to withstand 10,000,000 concurrent users and continuous adversarial traffic while adhering to native modern web standards.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Designing a new service, database schema, or distributed system | Apply the 10M-Concurrent-Users Axiom, partition-ready composite keys, and bounded resources |
| Authoring or modifying API routes, webhooks, or state mutations | Enforce runtime schema parsing, data-layer ownership checks, and idempotency |
| Reviewing concurrent execution, database transactions, or background jobs | Audit for TOCTOU bugs, lock contention, hot keys, and unbounded async operations |
| Diagnosing high-latency, memory leaks, or erratic brownouts under load | Subject the codebase to the Threat & Scale Pre-Mortem and Adversarial Verification |
| Routine styling tweaks, documentation typos, or local non-consequential scripts | Do not activate; use Anti-Slop Engineering BUILD/FIX gates |

---

## The Five Absolute Laws

1. **The 10,000,000 Concurrent Users Axiom (Scale-Ready Architecture):** Evaluate every loop, database query, state update, DOM mutation, memory allocation, and network call through the lens of scale readiness: verify there are zero architectural dead-ends preventing the system from supporting 10,000,000 concurrent sessions. Code-level hygiene and scale readiness (composite tenant keys, bounded memory, keyset pagination, timeout discipline, idempotency) are mandatory from Day 1 for every system, regardless of initial traffic. If an implementation introduces synchronous global bottlenecks, unindexed full table scans, $O(N^2)$ CPU spikes, memory leaks, or Economic Denial of Service (EDoS) under load, it is a fatal defect.
2. **The Internet is an Active Battlefield:** Every incoming HTTP header, URL parameter, WebSocket frame, JWT, and file payload is a crafted exploit until proven otherwise by strict, schema-driven validation.
3. **Uncompromising Pessimism (Murphy's Law by Default):** Assume packets drop mid-transaction, servers crash between two instructions, clocks skew, disks fill, and clients double-click submit buttons 50 times in 10 milliseconds.
4. **Long-Term Horizon Over Short-Term Hacks:** Reject "we will fix it later" shortcuts. Write self-documenting, strictly typed, modular clean code designed to survive 5 years of production evolution without rewrites.
5. **Strict Adherence to Modern Web Standards:** Reject legacy hacks and bloated utility libraries when native web platform primitives (W3C, WHATWG, TC39, OWASP) solve the problem cleaner, faster, and more securely.

---

## Invariant Rules

1. **Parse at the boundary; never trust input.** Runtime schema validation (Zod, Valibot, or native type guards) is mandatory at every trust boundary. Strip unknown fields by default.
2. **Verify authorization at the data layer.** Never rely solely on UI visibility or middleware gates. Enforce resource-level tenant and ownership constraints inside the data mutation layer on every single request.
3. **Idempotency on all mutations.** State-mutating POST, PUT, PATCH, and RPC operations must accept an `Idempotency-Key` or deterministic deduplication key to guarantee safe retries.
4. **Bounded resources everywhere.** Every database read must use cursor-based pagination with a hard limit. Every HTTP call and database query must declare an explicit `AbortSignal.timeout()`. Every payload must enforce byte-size caps.
5. **Zero synchronous hot keys.** Architect for horizontal partitioning from day one: enforce composite tenant keys (org_id, entity_id), encapsulate state mutations behind atomic storage seams, and isolate counter/ledger interfaces so transitioning from a single row to 64 shards requires zero domain rewrites. Deploy physical sharding only when immediate throughput demands it or future-scale-gate triggers are met.
6. **Never hold database transactions across network I/O.** Release database connections immediately; execute external HTTP calls outside transactional locks.
7. **Native web platform first.** Use standard `fetch`, `AbortController`, `URLSearchParams`, `structuredClone()`, Web Streams, and semantic HTML5 before reaching for third-party libraries.
8. **Constant-time secret comparison.** Compare tokens, signatures, and secrets using `crypto.timingSafeEqual` to eliminate timing side-channel vulnerabilities.
9. **Zero sensitive leaks in errors or DTOs.** Map internal exceptions to deterministic error codes with correlation IDs. Never leak stack traces, database schema details, or raw entity fields to clients.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| System, service, or database architecture design | [Architect System](usecases/architect.md) | [Scale Patterns](references/scale-concurrency-patterns.md) |
| Code review, PR audit, or security inspection | [Adversarial Review](usecases/review.md) | [Zero-Trust Security](references/zero-trust-security.md) |
| Feature coding, endpoint implementation, or refactoring | [Hardened Implementation](usecases/implement.md) | [Modern Web Platform](references/modern-web-platform.md) |
| Durable assessment record generation & audit | [Record Contract](references/threat-record-contract.md) | `scripts/paranoid_guard.py` |

---

## Mandatory Pre-Execution Interrogation Matrix

Before writing or approving code, subject the implementation to this matrix:

- **Distrust of Input:** Where does this data originate? What occurs if it is `null`, `undefined`, a 50MB string, a negative number, `NaN`, prototype-pollution syntax, Unicode homographs, or SQL/NoSQL/XSS injection payloads?
- **Distrust of Concurrency:** What happens if 10,000 requests execute this exact path at the exact same millisecond for the same resource? Is it idempotent? Are we using atomic transactions, optimistic concurrency control (ETags/version stamps), or distributed locks?
- **Distrust of Scale:** What is the time and space complexity? Is there an $N+1$ query pattern? Is the query bounded by a hard `LIMIT` and backed by a composite index? Will in-memory buffers grow unbounded and trigger an OOM after 48 hours?
- **Distrust of the Network:** What happens when downstream services take 30 seconds to answer? Is there an explicit timeout? If the client disconnects after server-side mutation, will their retry duplicate side effects?
- **Distrust of the Browser/Client:** Is the client dictating prices, roles, timestamps, permissions, or state transitions? If yes, reject immediately—the client is enemy territory.

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Unbounded `Promise.all(items.map(...))`** over dynamic arrays without concurrency limiting (exhausts sockets and connection pools).
2. **Client-supplied timestamps or IDs** used as authoritative ordering or security ownership without server-side validation.
3. **Polling loops (`setInterval`)** lacking visibility-state pausing (`document.visibilityState`), backoff on error, or cleanup via `AbortController`.
4. **Floating promises** (async calls lacking `await`, `.catch()`, or explicit `void` inside error boundaries).
5. **TOCTOU (Time-of-Check to Time-of-Use) flaws:** Checking a balance, quota, or unique constraint in a `SELECT`/`GET` and updating it in a subsequent non-transactional `UPDATE`/`SET`.
6. **Leaking sensitive fields:** Returning raw database rows or full entity objects directly without an explicit DTO projection allowlist.

---

## Required Output & Review Workflow

Structure all architectural designs, code generations, and reviews through this 3-phase discipline:

1. **Threat & Scale Pre-Mortem:** Bullet out the top 3 failure modes under 10M concurrent users or active malicious attacks (e.g. race conditions, hot keys, memory leaks, injection, spoofing).
2. **Hardened Implementation:** Emit clean, production-grade, standards-compliant code with boundary guards, timeouts, idempotency, and strict types built in from line one.
3. **Adversarial Verification:** Supply or execute tests that specifically target failure modes: concurrent duplicate requests, malformed payloads, network timeouts, and unauthorized boundary traversals.

When a durable architectural record is warranted, save a JSON assessment following the [Threat Record Contract](references/threat-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering paranoid audit <record.json> --json
# or: python3 scripts/paranoid_guard.py audit <record.json> --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central orchestration index for high-concurrency architecture and forensic audits.
- **[The Paranoid Principal Architect Playbook](playbooks/architect-playbook.md)**: 10M-Scale Axiom, zero-trust boundaries, database & concurrency invariants, and threat modeling.
- **[Zero-Trust DevOps & Forensic Bug Hunter](playbooks/devops-hunter-playbook.md)**: Line-by-line inspection across 9 stacks, the 4 execution pillars (Check, Clean, Improve, Document), and the 6 forensic gates.
- **[Stack Booby-Trap Catalog](playbooks/references/stack-booby-traps.md)**: Forensic failure mechanics and hardened remedies across K8s, Docker, Python, TS/Bun, Rust, Go, React, and Architecture.
- **[Scale & Concurrency Patterns](references/scale-concurrency-patterns.md)**: Sharded counters, cursor pagination, bounded pools, and jittered backoff.
- **[Zero-Trust Security Matrix](references/zero-trust-security.md)**: Boundary schemas, data-layer authorization, constant-time crypto, and EDoS defense.
- **[Modern Web Platform Standards](references/modern-web-platform.md)**: Native APIs, strict TypeScript, semantic HTML5, and WCAG AA accessibility.
- **[Threat Record Contract](references/threat-record-contract.md)**: Schema for persistent architectural assessment records.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Happy-path bias | Code assumes valid input and single-user execution | Add schema parsing, data-layer ownership check, and idempotency key |
| Unbounded concurrency | `Promise.all` over arbitrary input array | Wrap in bounded concurrency pool / semaphore queue |
| Hot-key contention | Single global row updated on every request | Implement sharded counters or append-only event ledger |
| Client trust leak | Price, role, or authorization accepted from request body | Resolve price and permissions authoritatively on server |
| Network stall | Indefinite pending requests during downstream outages | Bind `AbortSignal.timeout(ms)` to all external calls |
| Offset degradation | `OFFSET 500000` causing database CPU spikes | Migrate to cursor-based keyset pagination |

---

## Delegated Skills

- `anti-slop-engineering`: Follow BUILD/FIX gates and clean-room engineering standards once the architecture is established.
- `decision-guard`: Compare broad technology stacks and evaluate reversibility before committing to a permanent vendor.
- `future-scale-gate`: Formally model long-term operating envelopes, separate low-cost boundaries from deferred physical scale, and prevent capacity theater.

---

## Completion and Limits

The task is complete when boundary schemas parse all untrusted data, mutations support idempotency, queries are bounded and indexed, timeouts and jittered backoff protect the network, and adversarial verification tests prove resilience under concurrent stress. A paranoid review may validly output `refuse` or `pause` if critical invariants cannot be satisfied.
