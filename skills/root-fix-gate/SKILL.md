---
name: root-fix-gate
description: Use when a coding agent is about to patch the same symptom across controllers, views, endpoints or files; a small behavior change causes a wide diff; a workaround may hide a wrong model, schema or domain boundary; or a user proposes a shortcut with uncertain downstream effects. Trace the causal owner and compare a coherent root correction against distributed patches before implementation or review. Skip narrow, localized fixes with an already established owner.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Root-Fix Gate

> Fix the right responsibility at the lowest coherent boundary; prove why the change surface exists.

## Why This Skill Is Needed & Target State

An agent can make every screen pass while leaving the invalid contract in place: hiding the same user email in twenty controllers instead of checking whether email belongs to identity or checkout. Correct-looking output, passing local tests, a smaller file count, and the user's suggested fix are each insufficient to prove a sound design.

The target is a causal ownership decision before code, followed by focused implementation and an independent diff-to-plan review. The outcome may be a one-boundary correction, a genuinely necessary multi-layer change, `pause` for missing evidence, or `stop` when no change is required.

## Activation and boundaries

| Signal | Action |
| --- | --- |
| Repeated filtering, masking, normalization, or validation across consumers | Trace where the rule should be owned before duplicating it |
| Small request produces a cross-layer or unexpectedly wide diff | Compare source-of-truth correction with distributed patches |
| Agent or user says “just change the model” without contract evidence | Examine actual boundaries and downstream dependencies |
| Old fixes keep returning as new symptoms | Reopen the causal hypothesis with failed-probe evidence |
| Owner known and change is narrow, reversible, fully specified | Use parent Anti-Slop BUILD/FIX directly; do not require a record |
| New stack, vendor, or long-term architecture is undecided | Route to `decision-guard` first, then return for implementation ownership |

Do not turn every CRUD edit into an architecture review. Do not insist that every rule belongs in an ORM model: ownership may be a domain service, schema constraint, serializer, policy layer, transport adapter, or the UI depending on the invariant.

## Invariant Rules

1. **Goal is not a patch instruction.** Restate observable behavior separately from the proposed code modification.
2. **Trace writes as well as reads.** A presentation symptom can originate from a data contract, mapping, default, workflow, or authorization rule.
3. **Owner before consumers.** Locate the component responsible for enforcing the invariant. Consumers may still need changes for compatibility.
4. **Falsify the elegant hypothesis.** Test whether a one-model fix breaks auth, persistence, backward compatibility, ordering, privacy, or another caller.
5. **No forced centralization.** Distinct domain contexts can intentionally own different email policies. A global interceptor is not automatically correct.
6. **Plan the causal diff.** Every changed path needs a reason: owner, consumer, test, migration, or integration. File count alone is never a blocker.
7. **Preserve authority and data.** Changing nullability does not authorize deleting existing emails, rewriting identities, or running migrations.
8. **Tests prove contracts, not formatting.** Regression evidence must protect the invariant and affected consumers; avoid tests that merely assert the workaround runs.
9. **Machine review is not an architecture judge.** Automated checks can identify missing evidence and unexpected paths, not certify causal truth.

## Execution Workflows

- **[Trace](usecases/trace.md):** Read in full when deciding which layer owns a repeated symptom or data rule, before editing.
- **[Review](usecases/review.md):** Read in full after implementation or when reviewing a wide diff, before declaring completion.

### Decision router

| Evidence | Decision | Next step |
| --- | --- | --- |
| Root boundary observed, no material dependent risk | `proceed` | Test that boundary; implement the smallest coherent change |
| Root boundary plausible but auth/data/consumer effects unknown | `pause` on risky mutation | Read callers, add characterization probes, ask only for inaccessible facts |
| Different contexts have distinct valid owners | `proceed` with scoped owners | Preserve separate invariants; reject a fake shared utility |
| Root correction changes an authorized contract | `pause` for authority | State old/new contract, migration impact and user decision needed |
| Original request is already satisfied by a source or standard capability | `stop` | Show evidence and avoid unnecessary code |
| Diff is wider than expected | `review`, not automatic rejection | Reconcile paths against evidence and the change plan |

### Mandatory checkpoints

**Before editing:** Name the symptom, the suspected cause, the responsible owner, source evidence, a plausible alternative (including local patches), invariants, and expected changed paths. For a narrow verified fix, a short note suffices. For consequential cross-layer work, use the [record contract](references/record-contract.md).

**At implementation:** Apply the parent BUILD/FIX red-green-refactor cycle. No schema migration, account-email deletion, external send, deployment, or destructive action without its separate authorization.

**After implementation:** Compare actual paths with the plan; inspect repeated transformations and whether the owner is still wrong. Reopen the hypothesis if the diff spreads without explanation or a regression reveals another owner.

## Domain References

- **[Ownership model](references/ownership-model.md):** Read in full for MVC, cross-cutting rules, legacy code, and identity-versus-order examples.
- **[Record contract](references/record-contract.md):** Read before saving or auditing an ownership decision packet.

For a persistent packet, run `python3 scripts/root_fix_guard.py audit <record.json> --json` from the Anti-Slop repository, or its package CLI equivalent `npx anti-slop-engineering root-fix audit <record.json> --json` **only in a release containing the command**. Add `--base <ref> --repo <project>` to compare a real working diff. A standalone copy of this Skill does not include the repository-level script: if unavailable, review manually and report `machine audit: NOT RUN`. Exit `0` means structurally complete, `2` incomplete, `1` invalid input or Git inspection; exit `0` never proves the root cause is correct.

## Failure taxonomy

| Failure | Signal | Recovery |
| --- | --- | --- |
| Symptom fan-out | Same transformation in many consumers | Trace upstream owner and test a single-boundary fix |
| Model magnetism | Every policy forced into an ORM entity | Check domain, adapter and identity boundaries independently |
| Domain conflation | Order contact email treated as login identity | Separate purposes and test migration/auth contracts |
| False minimalism | One-line change silently breaks dependent callers | Expand the **necessary** test/migration surface |
| Diff laundering | Unplanned paths explained after the fact | Compare original plan, sources and actual changes |
| Authority bypass | “Clean up” deletes historical user data | Pause, request explicit decision and recovery plan |
| Verification theater | Only UI-hidden symptom is tested | Test source invariant and dependent behaviors |

## Delegated Skills

- `anti-slop-engineering`: Own BUILD/FIX, test integrity, SRE and diff verification after ownership is identified.
- `decision-guard`: Own independent solution necessity and consequential architecture choices; this Skill owns implementation responsibility.
- `future-scale-gate`: Evaluate whether an architectural boundary redesign introduces irreversible evolution constraints.

## Completion and limits

Report the chosen owner with source, alternative rejected and why, planned versus actual paths, protected invariants and test evidence, outstanding uncertainty, and `proceed`/`pause`/`stop`. Do not promise that fewer files or a structural pass is a root-cause proof. Semantic scenarios in `evals/scenarios.json` are a test bank, not executed model-performance evidence.
