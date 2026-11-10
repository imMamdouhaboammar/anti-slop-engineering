---
name: api-ergonomics-and-contract-governor
description: Enforces Microsoft TypeScript compiler-team ergonomic rigor and Stripe world-class API design standards for SDKs, CLIs, and internal modules. Use when designing public SDKs, library interfaces, CLI commands, or internal module boundaries; enforcing pit-of-success defaults, discriminated unions, branded nominal types, progressive disclosure, and RFC 9457 problem details — even if they don't explicitly say "api governor". Do NOT use for trivial internal variable renames, local loop optimizations, or simple non-contract utility functions.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: The API Ergonomics & Contract Governor (Microsoft TypeScript & Stripe DX)

> Design APIs where the easiest way to use them is also the correct, safe, and performant way.

## Why This Skill Is Needed & Target State

AI agents and hurried developers frequently produce clunky, brittle, and leaky interfaces: boolean traps (`foo(true, false, true)`), stringly-typed IDs (`userId: string` passed to `orgId`), exploding option bags requiring 10 mandatory parameters for simple operations, and ad-hoc string error throwing (`throw new Error("failed")`) lacking machine-actionable codes.

The target state is **architectural contract governance**: every SDK, CLI, and internal module exhibits Microsoft TypeScript compiler-team ergonomic rigor (zero `any`, branded nominal types, discriminated unions rendering illegal states unrepresentable, clean `.d.ts` hovers) and Stripe world-class developer experience (pit-of-success defaults, progressive disclosure from 1-line facades to advanced pipelines, and standardized RFC 9457 problem details).

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Designing a new public SDK, client library, or internal service boundary | Enforce Pit-of-Success defaults, 3-tier progressive disclosure, and branded types |
| Defining domain entities, request options, or status state machines | Model using Discriminated Unions; eliminate boolean flags and impossible states |
| Authoring CLI tools, commands, or developer toolkits | Enforce zero-config default execution, hierarchical subcommand discovery, and RFC 9457 error output |
| Modeling API errors, failure payloads, or exception classes | Implement RFC 9457 Problem Details with machine codes, retryability hints, and remediation actions |
| Auditing existing libraries or reviewing API PRs | Run adversarial ergonomics checks (Boolean trap audit, stringly-typed ID audit, option explosion audit) |
| Local loop optimizations, private helper refactors, or formatting | Do not activate; use Anti-Slop Engineering BUILD/FIX gates |

---

## The Four Absolute Pillars

1. **Pit of Success Defaults:** Every function, client, and CLI command must succeed with maximum safety and optimal performance out of the box without requiring callers to specify configuration bags. Safe timeouts (10s default via `AbortSignal.timeout`), automatic idempotent retries with exponential backoff and full jitter, TLS verification, and bounded pagination limits are pre-configured. Callers pass only what is unique to their intent.
2. **Illegal States Unrepresentable (Compile-Time Impossibility):** Eliminate boolean flags and loose primitive combinations that permit contradictory states (such as `{ status: "success", errorCode: "INVALID" }`). Utilize Discriminated Unions with tag discriminators, Nominal Branded Types (`CustomerId`, `InvoiceId`) to prevent parameter transposition, and exact exhaustiveness checking (`assertNever`).
3. **Progressive Disclosure:** Structure APIs in three distinct cognitive tiers:
   - *Tier 1 (One-Liner):* High-level, zero-friction entry-point solving the 80% use case in a single call.
   - *Tier 2 (Configured Options):* Explicit, type-safe options bag overriding defaults for specific operational requirements.
   - *Tier 3 (Escape Hatch & Advanced Engine):* Direct access to underlying protocol, raw request client, custom transport adapters, and streaming pipelines without leaky abstractions.
4. **RFC 9457 Problem Details:** Standardize all programmatic and network errors on the IETF RFC 9457 (RFC 7807) specification. Every error exposes a stable URI `type`, human-readable `title`, HTTP/CLI `status`, detailed `detail`, contextual `instance`, deterministic machine `code`, parameter-specific `invalid_params`, actionable `suggested_action`, and boolean `retryable` metadata.

---

## Invariant Rules

1. **No boolean parameter traps.** Functions taking two or more boolean arguments are prohibited. Replace boolean flags with named union literals or discriminated option records (e.g. `mode: "sync" | "async"` instead of `isAsync: boolean`).
2. **Nominal branding for all domain identifiers.** Never pass raw unbranded `string` or `number` types for entity IDs across public module boundaries. Enforce branded types (e.g. `type AccountId = string & { readonly __brand: unique symbol }`) to prevent passing a user ID where an account ID is expected.
3. **Discriminated unions for multi-state entities.** State machines, lifecycle statuses, and polymorphic payloads must use a common discriminator key (`status`, `kind`, `type`). Never combine optional fields across incompatible states.
4. **Exhaustive pattern matching enforcement.** All consumers handling discriminated unions must enforce compile-time exhaustiveness via a dedicated `assertNever(x: never): never` utility or compiler-checked switch statements.
5. **Progressive disclosure in namespaces and classes.** High-level client instances must not pollute root autocompletion with 150 internal transport methods. Group methods by domain resource (e.g. `client.customers.create()`), leaving advanced transport customization to builder or client options.
6. **Built-in timeout and cancellation discipline.** Every network-bound method must accept an optional `AbortSignal`, defaulting to a safe built-in timeout (e.g. `AbortSignal.timeout(10_000)`). Hanging network calls by default are considered critical bugs.
7. **Safe-by-default retryability with idempotency.** Network clients must automatically generate or accept deterministic idempotency keys for state-mutating requests, coupled with automated retries for transient errors (HTTP 408, 429, 502, 503, 504) using exponential backoff with full jitter.
8. **Cursor-based pagination with bounded page sizes.** Collection-returning methods must default to cursor pagination (returning `has_more` and `next_cursor`), with a safe default limit (e.g. 20) and a hard-coded maximum ceiling (e.g. 100). Never allow unbounded fetch-all operations on public APIs.
9. **Standardized RFC 9457 error contracts.** Custom error classes must inherit from a canonical `ProblemDetailsError` containing standard fields (`type`, `title`, `status`, `detail`, `instance`, `code`, `retryable`, `invalid_params`, `suggested_action`). Raw `throw new Error("msg")` in public APIs is prohibited.
10. **Clean `.d.ts` hover readability.** Do not author type gymnastics that evaluate to massive, unreadable union expansions in IDE tooltips. Use clean interface aliases, exported types, and nominal brands to maintain high developer comprehension.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Authoring a new public SDK or client library | [Architect SDK](usecases/architect-sdk.md) | [Progressive Disclosure](references/progressive-disclosure-patterns.md) |
| Designing a developer-facing CLI tool | [Design CLI](usecases/design-cli.md) | [Pit of Success Defaults](references/pit-of-success-defaults.md) |
| Refactoring an internal module boundary | [Refactor Module Contract](usecases/refactor-module-contract.md) | [Illegal States Unrepresentable](references/illegal-states-unrepresentable.md) |
| Auditing API ergonomics or conducting PR review | [Audit API Ergonomics](usecases/audit-api-ergonomics.md) | [RFC 9457 Problem Details](references/rfc9457-problem-details-contract.md) |
| Validating an API contract record | [Record Contract](references/api-contract-record-contract.md) | `scripts/api_contract_guard.py` |

---

## Mandatory Pre-Execution Interrogation Matrix

Before emitting or approving an SDK, CLI, or module boundary, evaluate against this matrix:

- **The Caller Experience:** Can a first-time developer write a working call in under 10 seconds from IDE autocomplete alone? Does the 80% use case require importing more than 1 symbol?
- **The Failure Blast Radius:** If a developer makes a mistake, does it fail at compile time? Or does it fail silently at runtime after 3 hours of execution?
- **The Option Bag Density:** Does the function take more than 5 required parameters? If yes, refactor into an options object with sensible defaults.
- **The State Machine Integrity:** Can an entity simultaneously have `success = true` and `error = "Timeout"`? Can a cancelled job have an active worker ID? If yes, collapse into a discriminated union.
- **The Error Transparency:** When a network or domain call fails, can the consumer's automated remediation handler parse the exact machine code and parameter path without regex-matching error message strings?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **The Boolean Trap:** `function updateUser(id: string, true, false, true)` — consecutive or positional boolean flags that obfuscate caller intent.
2. **Stringly-Typed Identifiers:** `function transfer(from: string, to: string)` where `AccountId` and `UserId` can be accidentally reversed without compiler errors.
3. **Option Explosion Soup:** Forcing callers to provide 10 separate fields just to initialize a basic client or execute a default read.
4. **Throwing Bare Errors:** `throw new Error("Invalid request")` lacking machine-readable error codes, RFC 9457 problem details, or documentation links.
5. **Ambiguous Return Tuples/Objects:** Returning `{ data?: T; error?: E }` where both can be `undefined` or both can be present simultaneously.
6. **Unbounded Collections:** Returning raw unbounded arrays from service endpoints without cursor pagination and hard ceilings.
7. **Hanging Default Network Calls:** Creating `fetch()` or HTTP clients without an explicit timeout mechanism.

---

## Required Output & Review Workflow

Structure all contract implementations, designs, and reviews through this 3-phase discipline:

1. **Ergonomics & Contract Pre-Mortem:** Identify the top 3 developer pain points, boolean traps, state contradiction risks, or error ambiguities in the proposed boundary.
2. **Hardened Contract Implementation:** Emit clean, production-grade TypeScript/CLI code with branded types, discriminated unions, safe defaults, and RFC 9457 errors from line one.
3. **Type & DX Verification:** Supply or execute compile-time and runtime tests: type assertions proving illegal states fail compilation, exhaustiveness tests, and automated error-handling verification.

When a durable architectural record is warranted, save a JSON assessment following the [API Contract Record Contract](references/api-contract-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering contract audit <record.json> --json
# or: python3 scripts/api_contract_guard.py audit <record.json> --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central index for ergonomic contract governance.
- **[Microsoft TypeScript Playbook](playbooks/microsoft-typescript-playbook.md)**: Compiler-team standards, branded types, `.d.ts` hygiene, and autocomplete optimization.
- **[Stripe DX Playbook](playbooks/stripe-dx-playbook.md)**: Idempotency keys, resource structures, cursor pagination, and predictable error handling.
- **[API Booby-Trap Catalog](playbooks/references/api-booby-traps.md)**: Forensic analysis of boolean traps, stringly types, and leaky abstractions.
- **[Pit of Success Defaults](references/pit-of-success-defaults.md)**: Zero-config execution, safe timeouts, and automatic jittered retries.
- **[Illegal States Unrepresentable](references/illegal-states-unrepresentable.md)**: Discriminated unions, nominal brands, and exhaustive pattern matching.
- **[Progressive Disclosure Patterns](references/progressive-disclosure-patterns.md)**: 3-tier API architectures from one-liners to power builders.
- **[RFC 9457 Problem Details Contract](references/rfc9457-problem-details-contract.md)**: Machine-readable error schema, remediation actions, and HTTP/CLI mapping.
- **[API Contract Record Contract](references/api-contract-record-contract.md)**: Schema for persistent API contract assessment records.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Boolean trap | `fn(id, true, false)` with positional booleans | Refactor to named option object with discriminated union literals |
| Transposed ID bug | Passing `orgId` into `userId` parameter | Wrap raw strings in nominal Branded Types |
| State contradiction | Object containing both `data` and `error` or incompatible fields | Model states as a tagged Discriminated Union |
| Cognitive overload | Requiring 10 parameters to execute a basic operation | Introduce 1-liner progressive disclosure facade with safe defaults |
| Opaque error handling | Callers scraping string messages with regex | Implement RFC 9457 Problem Details with machine codes |
| Network hang | Client stalls indefinitely during upstream network degradation | Bind `AbortSignal.timeout(10_000)` by default |

---

## Delegated Skills

- `anti-slop-engineering`: Follow BUILD/FIX gates and clean-room engineering standards once the contract is established.
- `paranoid-principal-architect`: Enforce 10M scale, zero-trust boundary parsing, and data-layer authorization.
- `safe-evolution-and-rollout-choreographer`: Verify additive schema evolution and N-1/N+1 wire compatibility when updating existing contracts.

---

## Completion and Limits

The task is complete when the API contract compiles with zero `any`, renders illegal states unrepresentable via discriminated unions and branded types, offers safe-by-default progressive disclosure from 1-line operations to advanced engines, and surfaces all errors through RFC 9457 problem details with verified machine codes. An ergonomics audit may validly output `refuse` or `pause` if a contract forces boolean traps, option explosion, or untyped error handling.
