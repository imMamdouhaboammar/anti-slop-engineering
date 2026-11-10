---
name: mandela-guard
description: Audit test suites, benchmarks, and evals for the 8 Mandela Leakage Patterns where tests confirm themselves, verifiers judge their own designs, or assertions are tautological.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Mandela Test-Oracle & Leakage Guard

> Eliminate test-oracle self-grading, tautological assertions, and circular mock confirmations.

## Why This Skill Is Needed & Target State

The "Mandela Effect" in LLM testing occurs when a test suite passes not because the code works, but because the test grades itself. Common failure modes:
1. **Tautological Assertions:** `assert True`, `expect(true).toBe(true)`, or self-comparisons `expect(val).toBe(val)`.
2. **Circular Mock Confirmation:** Mocking a return value `mock.return_value = 'x'` and immediately asserting `assert mock() == 'x'` without exercising real domain logic.
3. **Swallowed Test Failures:** `try: ... except AssertionError: pass` silently turning test breakages into passes.
4. **Frame-Injected Evals:** Prompt benchmarks where the prompt tells the evaluator to confirm success.

The target state is independent ground truth: every test assertion must be capable of failing when the implementation is broken (A/B/A falsification).

## Invariant Rules

1. **External Ground Truth:** Assertions must evaluate computed outputs against independent expected constants, not self-derived values.
2. **Zero Swallowed AssertionErrors:** Never catch `AssertionError` in tests unless specifically testing an assertion library via an inverted test runner.
3. **No Circular Mocking:** Mock only at system boundaries (I/O, network, clocks). Never mock the function under test.

## CLI Usage

```bash
# Scan test directory for Mandela leakage patterns
bunx anti-slop-engineering mandela tests/ --json

# Run in strict mode (fails on warnings)
bunx anti-slop-engineering mandela --strict
```
