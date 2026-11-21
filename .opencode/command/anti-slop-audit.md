---
description: Comprehensive anti-slop audit across all codebase files and diffs
---

Execute a comprehensive anti-slop audit across the target files or staged changes.
Scan for:
1. Diff bloat and unverified edits.
2. SRE violations (excessive nesting, overly long functions, toil, missing backoff).
3. Type-level & AST slop (chained assertions, ungrounded casts, quadratic copies).
4. Comment bloat (CCR > 0.35, syntax narration).
5. WCAG 2.2 contrast failures.
6. Mandela test oracle leakage (tautological asserts, swallowed errors, circular mocks).
Report findings grouped by Must fix / Should fix / Optimization opportunities.
$ARGUMENTS
