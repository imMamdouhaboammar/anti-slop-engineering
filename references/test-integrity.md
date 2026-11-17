# Test Integrity Protocol: Protect the Oracle

A test is a fallible executable claim about a contract, not infallible truth. The risk is that the same agent both changes implementation and quietly redefines what counts as success.

## Required workflow

1. **Capture a baseline:** record target commit, current test outcome, relevant test names, affected assertions, fixtures, snapshots, feature flags, and public contract.
2. **State the oracle:** document *independently* expected behavior before changing implementation. Requirements, API contracts, examples, prior tests, and domain invariants are evidence. Implementation output alone is not.
3. **Red first for bugs:** demonstrate a real failure with an initially failing test where practical. Do not create tests that merely duplicate the implementation's branch logic.
4. **Green through production fixes:** first ask whether a failure indicates a regression. Investigate causal path; do not chase CI green by editing the oracle.
5. **When tests must change:** disclose every modified old assertion, deleted fixture, snapshot, skip/xfail, or test configuration difference in the PR. State who or what authorized behavior change.
6. **Independent validation:** where possible, have a separate reviewer, a contract/spec, or a higher-level test assess the changed behavior; reread old and new tests without trusting agent explanation.
7. **Additional confidence:** use property-based, metamorphic, fuzz, mutation, integration or end-to-end tests when these test a real risk. Avoid numeric coverage theater.

## Test change decision table

| Scenario | Allowed? | Required evidence |
|---|---|---|
| Feature adds new behavior; existing behavior intact | Add new tests; usually leave old tests | New expected outcomes and regression checks |
| Contract intentionally changes | Yes, update old tests | Approved change request, old-vs-new assertions, consumer impact |
| Old test was objectively wrong | Yes, correct test | Independent specification, failing counterexample, clear rationale |
| Refactor with unchanged behavior | Generally preserve assertions | Original test results and same behavior after refactor |
| Snapshot changed due to UI/API output | Review, never blind update | Human-readable semantic diff and approval |
| Flaky test caused by timing or shared state | Fix test determinism | Reproducer and proof behavior coverage remains |
| Agent code breaks old expected behavior | No, do not rebaseline | Fix implementation or escalate change contract |
| Test is skipped, removed or assertions weakened for green | Block by default | Exceptional, explicitly reviewed reason and compensating proof |

## Patterns that falsify confidence

- Replacing concrete expected values with the new return value or `toBeDefined()`.
- Hard-coding the desired answer in a mock rather than running the business logic.
- Disabling the one failing test or weakening its assertion to check only invocation.
- Regenerating giant snapshots without reviewing the observable behavior change.
- Updating fixtures to the accidentally altered serialization schema.
- Making a test pass via artificial sleeps, extra retries, altered timeouts, or test order dependence.
- Changing CI filters so failures stop running; excluding integration suites from required checks.
- Turning actual errors into expected success states.

## High-value techniques

- **Characterization tests** for fragile legacy behavior, with warnings if behavior is undocumented and arguably wrong.
- **Mutation testing** (e.g., PIT, Stryker) for critical rules; avoid treating a raw mutation score as universal quality.
- **Contract tests** for consumers across module/service boundaries.
- **Integration tests** for persistence, migrations, security boundaries, and event handoffs.
- **Stateful/property-based tests** for invariants such as accounting totals, authorization, idempotency, and serialization symmetry.
- **E2E evidence** for user-facing journeys, not as a replacement for every deterministic unit test.

The objective is independent test *signal*, not maximal test count. DAMP tests may repeat input setup for clarity; do not apply DRY dogmatically to tests.

## Isolated counterfactual test runs

Run `python3 scripts/verification_oracle_guard.py counterfactual --base <commit> --tests <path>` for a test command and checkout you trust. The command runs test code under your own account. Use an OS sandbox for untrusted code.

- Baseline files come from the selected Git commit with the selected tests copied on top. Current files come from the working tree, including staged and unstaged edits and untracked files Git does not ignore. Each invocation starts in a fresh temporary checkout without Git metadata. Dependencies or fixtures missing from the snapshots may make the result inconclusive.
- A verified result requires the selected test case to fail by assertion on the baseline and pass on the current snapshot. Default unittest, Go, and Bun runs attribute outcomes to the selected file. A missing dependency, no executed case, or a custom command without attributable evidence is inconclusive. Default unittest output cannot pair a failed subtest with a passing subtest. A test that already passes on the baseline has no red-state evidence.
- Use `--check-flaky` to compare two independent runs per snapshot. The snapshots are discarded on completion.

## Targeted Python mutation checks

Run from the checkout with a changed condition in the selected function.

~~~bash
python3 scripts/targeted_mutation.py --source scripts/rule_registry.py \
  --function finding_metadata --test tests/test_rule_registry.py --base HEAD --seed 17
~~~

The command negates up to four changed conditions from direct `if` statements. Pass `--operator flip_boolean_return` to flip changed `True` or `False` values in direct `return` statements. It runs a passing baseline and each mutant in fresh copies of tracked files. The score counts mutants that passed or failed assertions in the same test cases. Other results are reported separately. Select trusted offline unit tests. The child process has your account's permissions.
