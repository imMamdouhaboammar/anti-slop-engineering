# Architectural foresight without capacity theater

## Separate four kinds of investment

| Investment | Example | Typical timing |
| --- | --- | --- |
| **Invariant** | Deterministic event ordering, tenant isolation, public API semantics | Before depending code/data uses the contract |
| **Boundary** | Stable IR between language semantics and execution engine | When reversing the dependency later would require a public rewrite |
| **Capacity** | More workers, indexes, caches, native engine, partitioning | When credible demand or bounded experiment justifies it |
| **Operations** | Monitoring, replay, rollback, migration rehearsals | As needed to make the chosen boundary safe and verifiable |

Do not treat every early abstraction as a foundation. A named interface is useful only when it expresses a stable, testable responsibility across plausible consumers. A speculative adapter with no actual second use or representative spike can increase rather than reduce lifetime cost.

## Build the future operating envelope

For each materially different scenario, record:

- **Stress axis:** programs per tenant, event volume, concurrency, data retention, correctness, geographic locality, extensibility, or recovery.
- **Basis:** observed demand, credible product/domain trajectory, or speculative possibility.
- **Source:** product requirements, current code/contract, comparable system evidence, domain constraint, or an explicit stakeholder assumption; distinguish inference from direct observation.
- **Failure if unprepared:** which specific contract, owner, or migration path would be difficult to change.
- **Revisit event:** evidence that should cause expansion or reversal; prefer observable events over arbitrary calendar dates.

The envelope needs *multiple stress axes*, not arbitrary perfect-future throughput forecasts. A high-traffic scenario that adds no new architectural constraint should not automatically cause new services. A small but fundamental compatibility scenario can justify a stronger boundary even with negligible present traffic.

## Reversibility and option value

Assess each commitment independently:

| Reversal | Signals | Evidence burden |
| --- | --- | --- |
| Low | One isolated adapter or UI component; no persistent format/public consumer | Local regression plus documented replacement path |
| Medium | Multiple components, operational migration, limited downstream users | Representative integration/migration exercise |
| High | Persistent schema, language semantics, protocol, identity boundary or unversioned external contract | Counterfactual implementation, compatibility proof, and authority checks |

Evaluate the **cost of being wrong**, not how impressive an architecture sounds. Include upgrade downtime, data conversion, auth/security surface, operational owner, vendor exit, test and tooling migration, and failure modes. Do not invent precise dollar totals when price and staffing data are unknown. A range or qualitative ordering with assumptions is acceptable.

## Bounded fitness proof

Specify a *falsifiable* capability before building the full production version:

1. Name the future consumer or stress and its invariant.
2. Identify the minimal source/fixture/prototype needed to exercise the boundary.
3. State the expected observation and failure criteria.
4. Run the experiment; record command/artifact/result and environmental limits.
5. If `failed` or `not_run`, pause an irreversible commitment or explicitly narrow the claim. Do not relabel an unrun proposal as a passing proof.

Good proofs: alternate interpreter executes a golden semantic trace; a migrated schema reopens old data; tenant-isolation tests span another tenant; an event queue reschedules without changing deterministic order; a server adapter runs behind the same request contract. A diagram, interface declaration, high code coverage, or speculative benchmark alone is not proof.

## Worked case: a simulation language

**Goal:** Support a language today with a Python reference interpreter, while preserving a future native backend and larger programs.

**Failure:** Evaluating only current 10-user runs leads to embedding parse semantics, mutable simulation state, scheduling, and output format directly in CPython implementation objects. Rewriting those semantics later can break user programs.

**Credible envelope:** (1) heterogeneous user-authored programs with substantially more events, (2) alternative execution environments with the same externally observable semantics. Neither scenario justifies assuming a million concurrent customers tomorrow.

**Two designs:**

- Direct Python AST-to-loop: minimum current code, but potentially high semantic coupling and a costly migration.
- Stable semantic IR/event contracts with a Python reference engine: modest present contract/test cost, continued interpreter simplicity, and a path to another executor.

**Foundation now:** versioned semantic representation, deterministic seed/event ordering contract, conformance fixtures, and a small alternate backend spike. **Defer:** distributed scheduler, auto-scaling fleet, full Rust rewrite, and production sharding until specific program profiles or deployment demand justify them.

**Falsification:** If the alternate backend cannot reproduce golden behavior without importing Python-only semantics, the foundation is not ready. A project may choose to accept this limitation, but it must be explicit.

## Counterexample: speculative global database partitioning

An internal application has no observed multi-region requirement, no jurisdictional mandate, and no product plan for geographic partitioning. A consultant proposes sharding on day one “because millions might arrive.” The extra transaction, query, and incident-management complexity is certain; the scenario is speculative. The justified early action may be canonical tenant IDs, controlled schema migrations and backup/restore tests; postpone sharding with an explicit data-volume/latency trigger. If a signed data-residency rule emerges later, reopen the decision with real jurisdictional evidence.

## Counterexample: future requirement is already a contract

A library's public format must support forward-compatible readers from its first release. Waiting for an observed compatibility bug is wrong: released artifacts cannot be retroactively rewritten. Define explicit schema versions, unknown-field semantics, and migration fixtures early. This is foundation work, even when today's only consumer is the producer.
