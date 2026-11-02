---
name: future-scale-gate
description: Use before committing to hard-to-reverse foundations for a long-lived software product, language, runtime, data model, or platform; when current workload evidence is being used to dismiss credible growth requirements; or when a team wants to build for extreme future scale without proving which foundations matter. Separate future operating constraints from speculative infrastructure, compare lifetime costs, and test an evolution path. Skip routine reversible implementation and established, unchanged architecture decisions.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Future-Scale Gate

> Design for credible future change; implement only the capacity and foundations justified now.

## Own the right problem

This Skill owns **architectural evolution capacity**: whether today's structural choices prevent credible future workloads, users, deployment models, or extensions. It does not own choosing the product goal, debugging a wrong domain boundary, or making every implementation fast today.

- **[Decision Guard](../decision-guard/SKILL.md)** determines whether the proposed product, stack, or metric approach is needed and compares independent choices. Use it first if the basic direction is undecided.
- **[Root-Fix Gate](../root-fix-gate/SKILL.md)** traces the existing owner of a bug or scattered invariant. Use it for cross-layer fixes, not speculative redesign.
- **Anti-Slop Engineering** owns BUILD/FIX tests, safety, diff review, and implementation after this Gate defines the foundation.

## Activation and refusal

| Signal | Action |
| --- | --- |
| A language/runtime, persistence contract, core API, or irreversible data model is being established | Run an operating-envelope and reversal-cost assessment |
| “No performance problem today, so this cannot matter” dismisses a plausible future operating constraint | Separate *measuring a hotspot* from *designing capacity for future workloads* |
| “Plan for millions” is used to demand microservices, sharding, or distributed execution immediately | Demand a credible scenario, migration barrier, and bounded evolution proof |
| A later engine, tenant model, or deployment target might be blocked by a current design | Test the smallest representative evolution path before commitment |
| A localized feature is reversible within existing stable boundaries | Skip this Skill; use BUILD/FIX |
| A direct answer exists or the underlying solution is questionable | Route to Decision Guard before architecture work |

Do not block ordinary work with repeated future-proofing checklists. Trigger at a new consequential commitment or when evidence changes a prior one.

## Non-negotiable invariants

1. **Future scenarios are not predictions.** Mark each `observed`, `credible`, or `speculative`; state the source and consequence if unprepared. An inaccessible source is unknown, not absence of need.
2. **Future readiness and future implementation are different.** Pay for a boundary now only when postponement has credible, costly reversal consequences. Defer expensive capacity until its trigger.
3. **Reversibility sets the proof burden.** Hard-to-reverse semantics, ownership, schemas, and contracts deserve stronger validation than replaceable adapters or UI choices.
4. **No “future-proof” claims from interfaces alone.** Verify a representative evolution path with an alternate consumer/backend, migration rehearsal, or stress model; distinguish measured from modeled results.
5. **Compare lifecycle ownership, not just day-one LOC.** Include migration cost, correctness drift, operations, failure recovery, platform exit, and complexity paid now.
6. **No scale dogma.** Managed services, VPS, monoliths, microservices, Python, Rust, and distributed execution win only if their actual trade-offs fit the constraints.
7. **Protect user authority.** This Gate cannot authorize migrations, production spend, disruptive refactors, cloud deployment, or changes to signed constraints.
8. **Preserve semantics under evolution.** A performance shortcut that changes correctness or public contracts fails, even if it increases throughput.

## Execution router

| Evidence state | Decision | Handoff |
| --- | --- | --- |
| Credible future, expensive reversal, cheap foundation, feasible evolution test | `proceed` with foundation only | Anti-Slop BUILD; defer infrastructure with triggers |
| Credible future, reversal expensive, but necessary boundary/proof unknown | `pause` | Smallest source check or evolution spike; do not lock the design |
| Future only speculative and expensive to prepare for now | `stop` speculative investment | Maintain replaceable design and a revisit trigger |
| Scale is already failing under a proven workload | Route to performance diagnosis | Measure causes; protect architectural contracts while optimizing |
| Future demand requires a signed change of product scope or budget | `pause` for authority | Show choice, cost, and consequence without deploying |
| No consequential commitment or meaningful migration hazard | Return to BUILD/FIX | No record, no extra ceremony |

## Workflows

### Before commitment: [Architect](usecases/architect.md)

1. Identify the product's expected lifetime and *types* of future users, workloads, growth, failure, and extension; do not invent exact growth forecasts.
2. Classify evidence. Define a **future operating envelope** across materially different stresses when relevant; one grounded irreversible requirement is sufficient without inventing another. Name the failure mode if unprepared.
3. Name hard-to-reverse choices. For each, state why reversal is costly and how exit/migration could work.
4. Compare credible designs across current complexity, lifecycle cost, failure/recovery, and exit cost. If a hard constraint leaves only one viable option, cite it instead of inventing a fake alternative. Separate framework, hosting, persistence, and execution axes when they differ.
5. Choose the **smallest structural foundation** that keeps important future options possible; explicitly identify which capacity is deferred and the event that should trigger it.
6. Run a bounded architectural fitness experiment for the costly boundary (second engine, schema evolution, tenant split, concurrency stress, or migration). A passing checklist is not that experiment.
7. `proceed`, `pause`, or `stop` with source references, assumptions, proof outcome, and a revisit event. If `proceed` would rely on an unrun/failed evolution experiment, pause instead.

For trade-off methods and concrete non-happy-path examples, read [foundation method](references/foundation-method.md) before committing to an expensive boundary.

### After implementation: [Review](usecases/review.md)

Trace whether the foundation is actually present, whether deferred work accidentally shipped, and whether a future consumer can use the contract without a rewrite. Compare the real diff, tests and operational changes to the record. Reopen the design if implementation invalidates its assumptions.

## Record and machine audit

For consequential choices, record the decision using [record contract](references/record-contract.md); include a concrete evolution proof and deferred-work trigger. Example: [runtime envelope](examples/runtime-envelope-record.json).

```bash
python3 scripts/future_scale_guard.py audit path/to/record.json --json
# Or, when the package CLI is available:
node bin/cli.js future-scale audit path/to/record.json --json
```

The checker validates structure and referenced evidence *statuses*, not scenario plausibility, independent proof truth, expected load, or architecture quality. `0` = structurally complete, `2` = incomplete, `1` = invalid input. For `pause` and `stop`, record honest uncertainty without manufacturing a completed proceed packet.

## Failure taxonomy

| Failure | Observable signal | Recovery |
| --- | --- | --- |
| Present-only optimization | “No bottleneck today” used to dismiss irreversible runtime coupling | Identify future operating envelope and reversal cost |
| Capacity theater | Cluster or distributed stack before a supported use case | Separate stable boundary from deferred scale implementation |
| Interface theater | “It is modular” but second consumer cannot run unchanged semantics | Build the smallest alternate consumer/proof |
| Forecast theater | Exact loads/costs invented to justify a decision | Use explicit qualitative scenarios and measurements |
| Foundation laundering | Expensive abstraction with no credible scenario or exit risk | Remove it or supply a falsifiable scenario and proof |
| Sunk-cost defense | Prior implementation effort used to dismiss contrary evidence | Compare forward costs and revisit the commitment |
| Premature permanence | Database/schema/IR choice locks the public contract by accident | Version, migrate, and test compatibility before hardening |

## Completion

Hand off: long-term goal, evidence-ranked future envelope, consequential choices and reversal cost, competing options, chosen foundation versus deferred capacity, evolution proof evidence, test changes, unresolved unknowns, authority boundary and revisit triggers. Treat [evaluation scenarios](evals/scenarios.json) as proposed tests, **not** as verified model performance.
