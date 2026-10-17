# Anti-Slop Engineering

[![CI](https://github.com/imMamdouhaboammar/anti-slop-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/imMamdouhaboammar/anti-slop-engineering/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Compliant-success.svg)](https://agentskills.io)
[![Author](https://img.shields.io/badge/author-Mamdouh%20Aboammar-blue)](https://github.com/imMamdouhaboammar)

**An Engineering Discipline Playbook, Agent Skill & Triage Guard for AI Coding Agents.**

> *"Write less unnecessary code. Preserve intended behavior. Protect the test oracle. Prove correctness. Leave the codebase healthier."*

---

A portable, provider-neutral **Agent Skill** and lightweight verification guard for planning changes, implementing features, reviewing pull requests, and auditing agent-generated code. It systematically addresses code bloat, architectural drift, superficial tests, test-oracle tampering, false confidence, security shortcuts, uncontrolled operational behavior, and degraded review hygiene.

This is **not** an "AI detection" tool or style linter. It critiques concrete engineering decisions using source evidence and behavioral contracts regardless of who wrote the code.

---

## Table of Contents

- [The Core Problem: AI Slop & Test Tampering](#the-core-problem-ai-slop--test-tampering)
- [Repository Contents](#repository-contents)
- [The Seven Gates](#the-seven-gates)
- [Heuristic Diff Guard](#heuristic-diff-guard)
- [Installation & Integration](#installation--integration)
  - [Claude Code](#claude-code)
  - [Antigravity / Gemini CLI](#antigravity--gemini-cli)
  - [Cursor / Windsurf / Copilot](#cursor--windsurf--copilot)
  - [CI / Local Pre-commit](#ci--local-pre-commit)
- [Anti-Pattern Catalog (186 Diagnostic Patterns)](#anti-pattern-catalog-186-diagnostic-patterns)
- [Design Commitments](#design-commitments)
- [Development & Testing](#development--testing)
- [Citation](#citation)
- [License & Copyright](#license--copyright)

---

## The Core Problem: AI Slop & Test Tampering

As AI coding agents take on complex multi-step tasks, common pathological failure modes emerge:
1. **Test-Oracle Tampering:** Changing existing test assertions, adding `@pytest.mark.skip`, or modifying golden snapshots merely to make a broken implementation look green.
2. **Needless Architecture & Layer Creep:** Introducing unnecessary micro-files, speculative interfaces, redundant wrappers, and complex factory patterns for simple one-line changes.
3. **Duplicate Business Rules:** Improvised helper functions scattered across the codebase that replicate existing domain logic with subtle discrepancies.
4. **Error Swallowing & Security Shortcuts:** Adding broad `except: pass`, `verify=False`, `@ts-ignore`, or disabling authentication gates to avoid errors.
5. **False Confidence & Hallucinated Passes:** Reporting tests or builds as successful without running or verifying the actual commands against source truth.

Anti-Slop Engineering enforces disciplined, evidence-based constraints to prevent these degradations.

---

## Repository Contents

```text
anti-slop-engineering/
├── SKILL.md                          # Compact, actionable 7-gate agent skill instructions
├── scripts/
│   └── diff_guard.py                 # Pure stdlib Python 3 read-only diff triage guard
├── tests/
│   └── test_diff_guard.py            # Unit tests for the heuristic diff guard
├── references/
│   ├── anti-pattern-catalog.md       # 186 diagnostic anti-patterns across 13 engineering domains
│   ├── test-integrity.md             # The Test Integrity Protocol: protecting test oracles
│   ├── pr-review.md                  # Evidence-first PR review protocol with severity scales
│   ├── security-and-operations.md    # Trust boundaries, injection resistance & operational safety
│   ├── engineering-judgment.md       # Legitimate exceptions vs checklist cargo-culting
│   ├── evidence-and-sources.md       # Empirical papers, research basis & methodology limitations
│   └── evaluation-cases.md           # 12 blinded evaluation benchmarks and scoring rubric
├── assets/
│   ├── PR_REVIEW_TEMPLATE.md         # Template for human & agent PR descriptions
│   └── RUN_REPORT_TEMPLATE.md        # Structured evidence report template for agent executions
├── .github/
│   ├── workflows/ci.yml              # CI testing across Python 3.9 through 3.13
│   ├── ISSUE_TEMPLATE/               # Bug reports & Anti-Pattern community proposals
│   └── PULL_REQUEST_TEMPLATE.md      # Pull request template enforcing gate verification
├── pyproject.toml                    # Standard Python packaging configuration
├── Makefile                          # Developer targets (make test, make guard, make check)
├── CITATION.cff                      # Machine-readable citation file
├── NOTICE                            # Copyright and author notice
├── AUTHORS.md                        # Author & contributor registry
├── CONTRIBUTING.md                   # Community contribution standards
└── LICENSE                           # MIT License
```

---

## The Seven Gates

When an agent operates in **BUILD**, **FIX**, **REVIEW**, or **CLEANUP** mode, it executes seven deterministic verification gates:

| Gate | Phase | Objective |
|---|---|---|
| **Gate 0** | **Discover** | Inspect root configs, lockfiles, conventions, and nearby implementations; never improvise repo habits. |
| **Gate 1** | **Contract** | Define explicitly: *what changes, what must not change, invariants, and rollback requirements*. |
| **Gate 2** | **Lock Oracle** | Baseline existing tests. Protect assertions. On fixes, write red-state repro before modifying production code. |
| **Gate 3** | **Implement** | Minimum justified complexity. Extend existing patterns; no duplicate layers or unnecessary dependencies. |
| **Gate 4** | **Verify** | Execute real tests beyond green badges. Test negative boundaries, concurrency, and contract seams. |
| **Gate 5** | **Audit Diff** | Run `diff_guard.py` as a skeptical reviewer. Scrutinize scope expansions, test modifications, and hidden leaks. |
| **Gate 6** | **Evidence** | Issue structured report: `BLOCK`, `REWORK`, `REVIEW`, or `PASS` with exact `file:line` citations and proof. |

---

## Heuristic Diff Guard

A zero-dependency, read-only Python 3 tool for fast pre-commit and PR diff triage:

```bash
# Compare staged + tracked changes against HEAD:
python3 scripts/diff_guard.py --base HEAD

# Compare PR branch against merge-base with main:
BASE="$(git merge-base HEAD origin/main)"
python3 scripts/diff_guard.py --repo . --base "$BASE"

# Output machine-readable JSON:
python3 scripts/diff_guard.py --base HEAD --json

# Strict gate: Exit code 2 if blocker patterns (e.g. skipped tests) are found:
python3 scripts/diff_guard.py --base HEAD --fail-on-blocker
```

### What `diff_guard.py` Checks
- **Modified Existing Tests:** Flags commits modifying existing test files (`TEST_CHANGE_REVIEW`) to enforce test-oracle review.
- **Skipped & Disabled Tests:** Catches `@pytest.mark.skip`, `it.skip`, `test.skip`, `@Disabled`, etc.
- **Weak Assertions:** Catches `assert True`, `expect(true).toBe(true)`, and empty assertion patterns.
- **Security Bypass Candidates:** Detects `verify=False`, `rejectUnauthorized: false`, `--no-verify`.
- **Error Swallowing:** Detects `except: pass`, empty `catch {}` blocks.
- **Type Suppression:** Detects `@ts-ignore`, `@ts-nocheck`, `type: ignore`.
- **Large Diff Scope:** Prompts review when added lines exceed threshold (default 400 lines).

---

## Installation & Integration

### As an Agent Skill (Recommended)

Copy the entire `anti-slop-engineering` directory into your agent's skills directory:

```bash
# Clone the repository:
git clone https://github.com/imMamdouhaboammar/anti-slop-engineering.git

# Example for Claude Code / Antigravity / Agent Skills location:
cp -r anti-slop-engineering ~/.gemini/config/skills/anti-slop-engineering
# or project-local:
cp -r anti-slop-engineering .agents/skills/anti-slop-engineering
```

### System Instruction / Prompt Prompting

If your AI host does not support automatic skill discovery, add the following directive to your project's `AGENTS.md`, `CLAUDE.md`, or system prompt:

```markdown
For any code implementation, bug fix, refactor, or pull request review, adhere strictly to
the Seven Gates in anti-slop-engineering/SKILL.md. Load relevant references on demand.
Never modify or delete existing test assertions to make an implementation pass without an
independently approved contract change. Always cite verbatim verification evidence.
```

---

## Anti-Pattern Catalog (186 Diagnostic Patterns)

The repository includes a detailed diagnostic catalog in [`references/anti-pattern-catalog.md`](references/anti-pattern-catalog.md) covering:

1. **Requirements & Scope:** Speculation, scope creep, imaginary requirements, incomplete migrations.
2. **Architecture & Abstractions:** Premature microservices, over-abstraction, god objects, wrapper explosion.
3. **Duplication & Code Organization:** Copy-paste business logic, shotgun surgery, shadow utility modules.
4. **Data, State & Persistence:** N+1 queries, unindexed queries, silent transaction rollbacks, leaky caches.
5. **Security & Boundaries:** Hardcoded credentials, prompt injection vulnerabilities, unsanitized inputs, SSRF, permissive CORS.
6. **Concurrency & Async:** Race conditions, thread leaks, unhandled task cancellation, un-fenced distributed jobs.
7. **APIs & Contracts:** Breaking public contracts, missing status codes, untyped responses, lack of pagination.
8. **Testing & Oracles:** Assert True theater, snapshot overwrite without review, mocking the unit under test, missing failure-path tests.
9. **Frontend & UI:** Scroll hijacking, accessibility violations, layout thrashing, un-memoized heavy computations.
10. **Operations & Reliability:** Missing graceful shutdown, unbounded retry storms, blind migrations, unmonitored queues.
11. **CI & Release:** Disabling lint rules, flaky test workarounds, missing build locks.
12. **Workflow & Review Hygiene:** Mega-PRs, unreviewable diffs, lack of test proof in review notes.
13. **Agent Autonomy:** Self-modifying safety boundaries, hallucinated test outputs, speculative code deletions.

---

## Development & Testing

```bash
# Run unit tests:
make test

# Run tests with verbose output:
make test-verbose

# Validate syntax across scripts and tests:
make lint

# Complete verification pass:
make check
```

---

## Citation

If you use Anti-Slop Engineering in academic research, agent evaluations, or software development benchmarks, please cite it using:

```bibtex
@software{aboammar2026antislop,
  author = {Aboammar, Mamdouh},
  title = {Anti-Slop Engineering: An Engineering Discipline Playbook and Guard System for AI Coding Agents},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/imMamdouhaboammar/anti-slop-engineering}
}
```

See [`CITATION.cff`](CITATION.cff) for CFF format.

---

## License & Copyright

- **Author & Maintainer:** [Mamdouh Aboammar](https://github.com/imMamdouhaboammar) (`mamdouhfces1997@gmail.com`)
- **License:** [MIT License](LICENSE)
- **Notice:** [NOTICE](NOTICE)

Copyright (c) 2026 Mamdouh Aboammar and contributors. All rights reserved.
