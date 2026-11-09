# Google Site Reliability Engineering (SRE) Discipline

Engineering discipline guidelines for AI coding agents and human engineers based on Google Site Reliability Engineering (SRE) principles: Simplicity (KISS), Single Source of Truth (DRY), Anti-Speculation (YAGNI), and Fixing Issues at Scale (Eliminating Toil).

---

## 1. Simplicity (KISS) — The Prerequisite to Reliability

> "Software simplicity is a prerequisite to reliability."
> — *Site Reliability Engineering: How Google Runs Production Systems*, Chapter 9

Reliability and complexity are fundamentally at odds. Every unnecessary abstraction, configuration knob, indirection layer, or nested branch expands the state space of a system, creates unmapped failure modes, increases cognitive load during outages, and makes automated testing exponentially harder.

### Core Invariants

1. **Boring Architecture Over Novelty:** Prefer standard, battle-tested components (e.g., standard libraries, proven primitives) over custom frameworks, bespoke micro-libraries, or elaborate design patterns.
2. **Shallow Call Hierarchies:** Avoid wrapper chains where Function A calls Function B solely to call Function C without transforming data, enforcing security, or adding operational context.
3. **Bounded Nesting Depth:** Keep cyclomatic nesting under 5 levels. Code requiring deep indentation (`if` inside `for` inside `try` inside `if`) must be refactored into guard clauses or focused sub-routines.
4. **Single-Purpose Components:** Functions exceeding 80 lines or concentrating multiple lifecycle stages (parsing, persistence, validation, presentation) must be decomposed into single-responsibility units.
5. **Small, Reversible Changes:** Every modification must have an explicit blast radius and an obvious rollback path.

---

## 2. Single Source of Truth (DRY) — Eliminating Divergent Invariants

In distributed and high-scale systems, code duplication is not an aesthetic flaw—it is a reliability hazard. When domain invariants, validation rules, or error translation tables are copy-pasted across multiple locations, subsequent bug fixes or policy changes inevitably miss one of the copies. The resulting divergence produces silent data corruption, authorization escapes, or inconsistent error responses.

### Core Invariants

1. **Canonical Validation Seams:** A single business invariant must be validated by exactly one canonical function or schema. Never re-implement regexes, range checks, or authorization rules across separate handlers.
2. **Unified Data Schemas:** API contracts, database persistence shapes, and message queue payloads must originate from a single canonical definition (e.g., protobuf, OpenAPI, Zod, or Pydantic models).
3. **Centralized Error Taxonomy:** Domain errors must map to machine-readable codes through a centralized mapper, preventing fragmented HTTP status codes or contradictory client retry behaviors.
4. **Test Setup Exception (DAMP over DRY in Tests):** Descriptive and Meaningful Phrases (DAMP) are permitted in test fixtures to keep tests self-contained and readable, but production invariants exercised by tests must remain strictly DRY.

---

## 3. Anti-Speculation (YAGNI) — Zero Dead-Weight Engineering

> "The most reliable component is the one that isn't there."

AI agents frequently anticipate future requirements by adding unused configuration flags, speculative parameters, premature multi-tenant hooks, and generic plugin architectures with a single consumer. This speculative scaffolding increases maintenance toil, attracts bugs, and complicates code navigation.

### Core Invariants

1. **Concrete Over Speculative:** Implement only the contract required for verified current specifications. Never introduce abstract factory layers or extensibility interfaces for hypothetical future requirements.
2. **No Dead Knobs or Ghost Parameters:** Every function parameter, environment variable, or configuration key must be actively referenced and tested by active code. Remove `_unused`, `future_kwargs`, and placeholder toggles.
3. **No Speculative Comments or Stub Routes:** Reject comments like `// TODO(future): support clustering` or routes returning stubbed `501 Not Implemented` unless explicitly part of an approved staged API contract.
4. **Ruthless Dead Code Elimination:** Delete deprecated branches, orphaned helpers, and unused imports immediately. Version control is the archive; production code is not a museum.

---

## 4. Fix Issues at Scale — Eliminating Toil & Systemic Resilience

> "If a human operator needs to touch a system during normal operations, you have an operational bug. Fix it at scale."
> — *Google SRE Philosophy*

### Definition of Toil (Google SRE Chapter 5)

Toil is operational work that is:
- **Manual:** Executing ad-hoc scripts, restarting services by hand, or manual data backfills.
- **Repetitive:** Running the same triage or mitigation repeatedly.
- **Automatable:** Tasks that a machine or automated policy could handle without human judgment.
- **Devoid of Enduring Value:** Resolving an alert without improving service stability or permanently eliminating the bug.
- **Linearly Scalable:** Work that grows proportionally with traffic, users, or fleet size.

Google SRE caps operational toil at 50% of an engineer's time, dedicating the remaining >=50% to engineering permanent, systemic automation.

### Distributed Systems Scale Invariants

| Failure Domain | Fragile Anti-Pattern (Bandaid) | SRE Scale Invariant (Fix at Scale) |
| :--- | :--- | :--- |
| **Retries** | Blind retry in tight loop, flat sleep (`sleep(1)`) | Exponential backoff with Full Jitter, bounded max attempts, retry only on transient status codes (e.g., 429, 503). |
| **Thundering Herd** | Simultaneous retries across fleet upon service recovery | Random jitter interval added to backoff: `sleep = min(cap, base * 2^attempt) * random(0.5, 1.5)`. |
| **Cascading Failure** | Calling degraded downstream service continuously | Circuit Breaker (Closed -> Open on error threshold -> Half-Open probe) with rapid fail-fast. |
| **Resource Starvation** | Unbounded queue, `Promise.all` over unconstrained array | Bounded concurrency (Worker pools, Semaphore with timeout, Bulkhead isolation), explicit backpressure (`HTTP 429 / 503`). |
| **Race Conditions** | Ad-hoc `sleep(500)` hoping async task finishes | Deterministic synchronization: Promises, Condition Variables, Event Listeners, or polling with bounded timeout and backoff. |
| **State Mutation** | Retrying non-idempotent operations (`POST /transfers`) | Mandatory Idempotency Keys (`X-Idempotency-Key`) stored with transactional deduplication. |
| **Health Probes** | Static `200 OK` on `/health` while DB connection is dead | Dual health probes: Liveness (process responsive) vs Readiness (backing datastores and caches verified). |
| **Error Triage** | Empty `except: pass` or `catch (e) {}` swallowing exceptions | Structured telemetry: Log with error code, stack trace, and correlation ID (`trace_id`, `span_id`). |

---

## 5. SRE Operational Verification Matrix

Before any change is marked complete or merged, verify the SRE checklist:

```
[ ] KISS: Nesting depth <= 4 levels in all changed functions.
[ ] KISS: No trivial wrapper chains with zero data transformation or policy.
[ ] DRY: Zero copy-pasted logic blocks; domain invariants canonicalized.
[ ] YAGNI: Zero unreferenced parameters, unused config flags, or speculative hooks.
[ ] SCALE: All network/RPC retries implement exponential backoff + jitter.
[ ] SCALE: No sleep() used as a synchronization band-aid for async races.
[ ] SCALE: Concurrency is strictly bounded (pools, limits, semaphores).
[ ] SCALE: Mutations support idempotency tokens.
[ ] SCALE: Errors are structured with correlation IDs; no bare exception swallowing.
```
