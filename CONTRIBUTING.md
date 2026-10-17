# Contributing to Anti-Slop Engineering

Thank you for your interest in improving **Anti-Slop Engineering**! We welcome contributions that uphold genuine engineering discipline, test integrity, and clear evidence over speculative abstractions.

## Principles for Contributions

1. **Evidence Over Vibes:** When adding or updating patterns in the [anti-pattern catalog](references/anti-pattern-catalog.md), provide concrete examples, rationale, context caveats, and remediation guidance.
2. **Protect the Test Oracle:** Any modification to existing tests must be justified with an explicit change contract and independent authority.
3. **Minimal Justified Complexity:** Keep additions lean and focused. Avoid unnecessary dependencies or over-engineered scaffolding.
4. **Stdlib-First for Tooling:** The diff guard (`scripts/diff_guard.py`) must remain pure standard-library Python (>=3.9) with zero external dependencies.

## Developing & Testing

### Running Tests

Run the bundled test suite using Python 3:

```bash
python3 -m unittest discover -s tests -v
```

Or using the Makefile:

```bash
make test
```

### Self-Guard Verification

Run the diff guard against your current changes:

```bash
python3 scripts/diff_guard.py --base HEAD
```

Or:

```bash
make guard
```

## Pull Request Checklist

Before submitting a PR, ensure:

- [ ] All tests pass (`make test`).
- [ ] Self-diff check passes without unintended blockers (`make guard`).
- [ ] No temporary files or credentials are committed.
- [ ] PR description includes rationale, before/after examples, and test evidence.
- [ ] Use the PR template provided in [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

## Submitting New Anti-Patterns

When proposing a new anti-pattern for `references/anti-pattern-catalog.md`:
1. Use the [Anti-Pattern Proposal issue template](.github/ISSUE_TEMPLATE/anti_pattern_proposal.md).
2. Clearly distinguish between *actual defects* and *legitimate contextual trade-offs*.
3. Include detection guidance and minimal refactoring steps.
