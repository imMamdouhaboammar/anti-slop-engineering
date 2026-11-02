# Architect: credible future before hard-to-reverse commitment

Read [foundation method](../references/foundation-method.md) and [record contract](../references/record-contract.md) before creating a persistent decision.

1. **Reframe the objective.** Distinguish desired product capability from a proposed implementation (e.g. “support future programs” versus “rewrite in Rust”). If the goal itself is uncertain, route to Decision Guard.
2. **Collect sources.** Read design constraints, public contracts, current code and owner plans; independently seek a credible future operating envelope. Mark inaccessible evidence unknown and explicitly flag speculative cases.
3. **Identify dependency traps.** Draw the dependency direction for semantics, state, persistence, integration, configuration and runtime. Name a future consumer that today's design might block. Do not insist on replacing code just because a dependency exists.
4. **Compare forward costs.** For viable designs, record cost now, cost of being wrong, migration/exit path, ongoing operational owner and failure recovery. If an explicit hard constraint leaves one design, record its source rather than fabricating an alternative. Do not bundle unrelated architecture axes into one vendor choice.
5. **Choose foundation and deferral separately.** Justify the boundary now by irreversible risk; define a concrete activation trigger for each deferred costly capability.
6. **Falsify.** Execute the smallest real alternate consumer, compatibility fixture or migration rehearsal that could disprove the boundary. Avoid theoretical “supports X” claims based on interfaces and mock unit tests alone.
7. **Decide.** `proceed` only with sufficient evidence and a passing evolution proof; `pause` if key evidence/proof/authority is missing; `stop` if the proposed foundation is unnecessary or speculative.

The work output should allow a different engineer to challenge the scenario source and reproduce the proof. If a complete record is warranted, audit it with `future_scale_guard.py`, then hand off to Anti-Slop BUILD/FIX. The machine check does not supply missing evidence.
