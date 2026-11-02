# Review: verify evolution capacity in the actual change

1. Read the original operating envelope and decision record. Check if sources are still current; do not endorse a future forecast based on prose alone.
2. Follow the dependency direction in the implementation. Identify where a second consumer, alternate runtime or larger workload would attach and whether the promised boundary truly exists.
3. Inspect tests: are they independent contracts, or merely unit assertions over the chosen implementation? Require a representative migration/evolution exercise for a hard-to-reverse commitment.
4. Inspect the actual diff for prematurely shipped infrastructure, speculative options, duplicated adapters, and hidden ongoing toil. A justified wider change may be correct; line count alone proves neither waste nor readiness.
5. Confirm deferred work has objective revisit triggers and no silent production commitments. Check data/security/rollout authority separately.
6. Classify the result: **PASS** when the documented claim has observed evidence and no blocker; **REWORK** when the boundary is theatrical or migration impossible; **PAUSE** when critical source/proof/authority is unknown; **STOP** if the change is unnecessary.

Report: claimed future capacity, evidence/proof, actual implementation boundary, adversarial counterexample, future change path, deferred features/triggers, remaining risks, and explicit next action. Do not convert a structurally complete JSON result into an architecture guarantee.
