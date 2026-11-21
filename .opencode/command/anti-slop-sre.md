---
description: Verify Google SRE invariants (KISS, DRY, YAGNI, toil elimination)
---

Audit this codebase or diff strictly against Google SRE principles:
1. KISS: Control-flow nesting depth must be <= 4 levels. Functions > 80 lines must be decomposed.
2. DRY: Single source of truth. Deduplicate duplicate blocks >= 4 lines.
3. YAGNI: Remove speculative parameters, dead branches, and empty placeholder comments.
4. Toil Elimination: Enforce exponential backoff with full jitter on retries, bound concurrency, and eliminate silent exception swallowing.
$ARGUMENTS
