---
description: Audit TypeScript/JavaScript files for type assertions and AST-level slop
---

Inspect the specified TypeScript or JavaScript code for AST-level slop patterns:
1. Eliminate chained type assertions (`as unknown as T` or `as any as T`).
2. Eliminate ungrounded type assertions (`as T`) lacking nearby `// SAFETY:` justifications.
3. Eliminate quadratic reducer copies (`acc = { ...acc, [k]: v }` inside `.reduce()`).
4. Eliminate conditional empty spreads (`...(condition ? { key: value } : {})`).
5. Eliminate test-oracle erosion via module-level mocking (`vi.mock()`, `jest.mock()`).
$ARGUMENTS
