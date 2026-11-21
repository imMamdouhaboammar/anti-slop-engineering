# Anti-Slop Engineering Rules for GitHub Copilot

Enforce 7 gates, Google SRE reliability principles, and AST-level slop elimination:
- **Gate 0 Preflight**: Infer domain intent autonomously; verify git remote sync before editing.
- **Google SRE**: KISS (nesting <= 4, function length <= 80 lines), DRY (single source of truth), YAGNI (no speculative parameters or empty TODOs), toil elimination (exponential backoff with full jitter).
- **Clean-Room Dev Ladder**: Use standard library built-ins first (`crypto.randomUUID()`, `structuredClone()`, `URLSearchParams`).
- **AST Slop Elimination**: Eliminate chained type assertions (`as unknown as T`), ungrounded casts without `// SAFETY:`, quadratic reducer copies, and conditional empty spreads.
- **Zero-Obviousness Comment Budget**: CCR <= 0.35, no syntax play-by-play comments.
- **Apple Craft & WCAG 2.2**: Zero CLS ($CLS = 0.000$); normal text contrast >= 4.5:1.
- **Zero-Trust**: Boundary schema parsing, distributed idempotency, constant-time crypto (`crypto.timingSafeEqual()`), RFC 9457 problem details.
- **Mandela Test Integrity**: Zero tautological assertions, zero swallowed errors, zero circular mocks.
