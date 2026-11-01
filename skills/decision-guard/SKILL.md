---
name: decision-guard
description: Use when an AI agent is deriving metrics or complex explanations while a direct answer may exist, choosing a software architecture or technology stack, or making consequential technical decisions with long-term operational costs and uncertain assumptions. Do not use for narrow, fully specified implementation or routine bug fixes.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Decision Guard

> Find the direct answer, challenge the premise, then defend the smallest credible decision over its useful lifetime.

## Why This Skill Is Needed & Target State

Agents can execute a flawed plan with impressive local correctness: derive a value already exposed directly, accept the user's solution as the problem, or default to a familiar framework-host-database bundle without examining operational consequences. Repeated agreement and earlier investment do not establish that the premise is sound.

The target is an interruption-capable decision process grounded in checked sources, independent alternatives, explicit reversibility, and conditional recommendations. It may conclude that no new implementation is needed. It must never imply that a completed checklist proves the choice is correct.

## Activation and boundaries

| Situation | Behavior |
| --- | --- |
| Complex inference, simulation, or metric derivation | Run the direct-observation path before constructing a proxy |
| Framework, infrastructure, database, vendor, or data-boundary selection | Compare independent architectural axes and future stress conditions |
| Long-running project reveals evidence that undermines its original premise | Reopen the decision; do not defend sunk cost |
| Existing, approved implementation and no new material evidence | Continue normal execution; avoid recurring decision theater |
| Small bug, agreed specification, or reversible local refactor | Do not activate; use Anti-Slop Engineering BUILD/FIX gates |

Do not use this Skill to override a signed constraint, silently change an authorized roadmap, or block routine work with speculative hypotheticals. If a consequential recommendation conflicts with user authority, report the evidence and seek a decision rather than changing course unilaterally.

## Invariant Rules

1. **Goal before method.** Restate the wanted result separately from the user's proposed technique.
2. **Observed before derived.** Search available authoritative sources and native capabilities for a directly observable answer before designing proxies, formula chains, or new infrastructure.
3. **Evidence types stay distinct.** Label observed, derived, inferred, and unavailable claims. An inaccessible source is not a negative finding.
4. **No default-stack bundles.** Evaluate rendering, runtime/jobs, hosting, persistence, and operations separately when they are material. No framework mandates its most-associated host.
5. **No reverse dogma.** Neither popular managed platforms nor VPS/self-hosting win by default. Compare total ownership burden and credible future states.
6. **Future is a scenario, not a fact.** Test migration, failure, growth, maintainability, exit cost and recovery conditions without invented forecasts.
7. **Interrupt on material discovery.** If a verified direct answer or decision-changing constraint appears, stop unnecessary work and show the evidence, even after substantial prior investment.
8. **Protect authority.** A recommendation is not an authorization to deploy, migrate data, buy services, or alter protected decisions.
9. **No mechanical truth claims.** `decision_guard.py` verifies record completeness only; independent source review and domain tests remain mandatory.

## Decision router

| Evidence state | Required action | Exit condition |
| --- | --- | --- |
| Direct answer found and semantics verified | Recommend direct use; identify redundant work | User accepts the revised plan or retains the old one explicitly |
| Potential direct source not inspected | Inspect it using available read/search/query tools | Evidence found, disproved, or marked unavailable |
| Source unavailable or conflicting | Record unknown, competing hypotheses, next probe | Pause consequential commitment; do not manufacture certainty |
| Architecture options materially differ | Decompose axes and compare two serious choices | Trade-offs, constraints, reversal and future stress are visible |
| Strong contract or regulation excludes a candidate | Eliminate that candidate, explain the authority | Remaining candidates satisfy hard constraints |
| No meaningful choice or only routine reversible work | Hand back to parent BUILD/FIX | No unnecessary decision packet |

## Execution Workflows

- **[Investigate](usecases/investigate.md)** for direct answers, metrics, hidden data, assumptions and path dependence.
- **[Architect](usecases/architect.md)** for tech-stack, vendor, infrastructure and multi-year lifecycle decisions.

At the start of either workflow, inspect the repository or data inventory, the user goal and the decision authority. Use tools available in the host; do not assume browsers, credentials, or remote environments exist.

### Mandatory reassessment triggers

Reopen only when new evidence changes a critical assumption, a credible simpler option appears, a target constraint changes, an option fails a critical proof, or a project's operating conditions cross the recorded revisit trigger. Do not ask for repeated reevaluation on every ordinary edit.

### Output and verification

Present the decision in this order:

1. **Goal and current recommendation**: one sentence each, including `proceed`, `pause`, or `stop`.
2. **Direct-path result**: observed finding and source, or exact unknown and next probe.
3. **Options**: viable alternatives and meaningful differences; separate architecture axes when relevant.
4. **Reasoning boundary**: facts, assumptions, operational owner, downside, reversibility, stress/revisit trigger.
5. **Handoff**: what can execute, what requires user authority, and what evidence remains unverified.

When the decision is consequential or likely to be revisited, save a JSON decision record following [record contract](references/decision-record.md). Audit it with `python3 scripts/decision_guard.py audit <record.json> --json` from the repository root (or the installed module's equivalent root). Exit 0 means structurally complete, exit 2 means incomplete; neither proves the underlying recommendation. Do not create a record for trivial tasks.

## Domain References

- **[Decision method](references/decision-method.md)**: Read in full before architecture comparisons or conflicting evidence classification.
- **[Decision record](references/decision-record.md)**: Read in full before writing or validating a persistent decision.

## Failure taxonomy

| Failure | Observable signal | Recovery |
| --- | --- | --- |
| Premise capture | Plan accepted as the goal | Reframe objective, try direct observation |
| Source omission | Derived claim without source inventory | Check source/tool/schema/documentation |
| Context momentum | Sunk cost cited to preserve redundant work | Compare forward costs only |
| Default bundle bias | Framework, host and DB decided as one brand bundle | Split selection axes and trace constraints |
| Reverse bias | VPS/self-host or new framework assumed inherently superior | Compare ops owner, backups, support and reversibility |
| Forecast theater | Exact future pricing/load presented without evidence | Replace with scenario ranges and measurement plan |
| Ritualistic skepticism | Endless options and objections after evidence is sufficient | Decide, record invalidation triggers, resume delivery |

## Delegated Skills

- `anti-slop-engineering`: Resume BUILD/FIX/REVIEW and the Seven Gates after the choice is established.
- `fable-research` or a host-equivalent research capability: Resolve source or vendor claims whose current truth changes the decision.
- `fable-verify` or a host-equivalent verification capability: Test concrete technical feasibility and performance claims, not merely the prose.

## Completion and limits

Finish when the direct route has been checked or honestly marked unknown, consequential alternatives and constraints have been compared, the user can understand what would invalidate the recommendation, and the next permitted action is explicit. A decision can validly end in `pause` or `stop`. Behavioral evaluation scenarios live in `evals/scenarios.json`; they are test cases, not claims of live-model results.
