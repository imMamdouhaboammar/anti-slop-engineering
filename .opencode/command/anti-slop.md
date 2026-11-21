---
description: Run anti-slop preflight triage and verify gates
---

Analyze this task and workspace through the Anti-Slop Engineering framework.
Check:
1. Gate 0 Preflight & Invariant Inversion: Infer domain requirements, name tools briefly, and verify git remote sync.
2. SRE Mandate: KISS (nesting <= 4, length <= 80 lines), DRY (deduplicate patterns), YAGNI (prune speculative code), Toil elimination (exponential backoff with jitter).
3. Clean-Room Dev Ladder: Use stdlib built-ins first.
4. Eliminate AST slop: chained assertions, ungrounded casts, quadratic reducer copies.
5. Zero-Obviousness & Comment Budget: CCR <= 0.35, no syntax narration.
$ARGUMENTS
