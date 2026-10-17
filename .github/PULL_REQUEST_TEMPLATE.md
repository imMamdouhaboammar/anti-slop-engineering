## What changed / why
<!-- Explain observable behavior and the simplest chosen approach. -->

## Scope & compatibility
- [ ] Change is one coherent review unit or larger scope is justified
- [ ] Existing consumers and old contracts assessed
- [ ] Unrelated refactors/dependency/config churn excluded or justified

## Tests and independent evidence
- [ ] Baseline test result captured (or reason not possible)
- [ ] Existing assertions/snapshots modified? If yes, old vs new contract and approval shown
- [ ] Reproduction test first for bug fixes where practical
- [ ] Negative / edge / integration paths tested as appropriate
- [ ] Exact test commands and results listed; no invented passes
- [ ] No test skips/coverage exclusions/policy suppression to make CI pass

## Engineering & safety
- [ ] Reviewed permissions, data consistency, retries, concurrency and cleanup where relevant
- [ ] Reviewed dependencies, migrations, compatibility, rollback and instrumentation where relevant
- [ ] Evidence-backed findings resolved or documented

## If adding or updating a "Noted Slop" / Anti-Pattern
- [ ] Pattern added to `references/anti-pattern-catalog.md` with unique ID and 5-part schema
- [ ] (If applicable) Agent directive added to `SKILL.md` and `AGENTS.md`
- [ ] (If applicable) Heuristic check added to `scripts/diff_guard.py` and unit test added to `tests/test_diff_guard.py`
- [ ] Catalog counter updated in `README.md` and change documented in `CHANGELOG.md`
- [ ] Ran `make check` and `bun ./bin/cli.js test` with clean pass

## Remaining uncertainty / reviewer guidance
<!-- Flag risks, unverified environment assumptions, and review hotspots. -->
