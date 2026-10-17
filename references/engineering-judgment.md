# Judgment, Trade-offs, and Legitimate Exceptions

## Avoid a new anti-slop slop

A huge mandatory checklist can itself cause excessive code, bureaucracy and agent confusion. The skill's core is workflow; the catalog is a selective diagnostic. Read only relevant sections on demand. Prefer precise corrective action to mechanically satisfying counts or scores.

## Trade-off rules

- A necessary authorization check, error handler, or transaction boundary is not overengineering even if it adds many lines.
- Extract shared code for *stable* duplication; tolerate short/local duplication when abstraction would couple unrelated future changes.
- Consistent framework boilerplate may be necessary; hand-rolling standard cryptography, parsing, auth, or date/time logic to save lines is dangerous.
- New dependencies are justified when their tested behavior meaningfully reduces risk/maintenance; don't reinvent complex libraries for a two-line LOC goal.
- Prefer readability to dense one-liners. A small function can be worse than a slightly longer clear function.
- Some comments are essential for non-obvious invariants, concurrency hazards, or business reasons. Banning all comments is counterproductive.
- Production logging must be structured and privacy-safe; having many necessary operational events is not 'console pollution'.
- Changing existing tests is valid when the approved contract changes; changing tests to fit a regression is not.
- Unit vs integration vs E2E should reflect system risk and cost; neither all-unit nor all-E2E is a universal rule.
- Rule thresholds (file length, diff size, number of files) are prompts for scrutiny, not blockers without measured harm.
- Version pinning must honor repository support policy; blindly choosing newest framework/toolchain is unsafe.

## How to classify a suspected smell

1. **Observed**: exact path, line or executable evidence.
2. **Invariant / cost**: what contract, trust boundary or maintenance burden might be affected?
3. **Counterexample**: could this be intentional and justified under this repo's requirements?
4. **Impact and confidence**: what breaks and how certain are we?
5. **Action**: smallest safe correction or documented exception.

If a finding fails steps 1 or 2, label it **unverified observation**, not a defect.
