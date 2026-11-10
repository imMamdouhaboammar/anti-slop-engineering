---
name: comment-budget-guard
description: Enforce Comment-to-Code Ratios (CCR) and eliminate syntax play-by-play narration comments while strictly preserving formal safety contracts, JSDoc/TSDoc docstrings, and license headers.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Comment Budget & Obviousness Guard

> Enforce the Zero-Obviousness & Anti-Truism Doctrine by bounding Comment-to-Code Ratios (CCR) and eliminating syntax play-by-play comments without penalizing docstrings or safety invariants.

## Why This Skill Is Needed & Target State

AI code generators suffer from pervasive comment slop: narrating obvious syntax line-by-line (`// increment counter`, `// return result`, `// check if null`). Naive counters (e.g. `max-added-comments: 10`) break on large, well-documented pull requests while letting micro-PRs with 9 trivial comments slip through.

The target state is a metric-driven Comment-to-Code Ratio (CCR) engine that:
1. Calculates $\text{CCR} = \frac{\text{added\_comments}}{\max(1, \text{added\_code})}$.
2. Enforces an activation floor ($\ge 20$ added comments) before ratio warnings trigger.
3. Automatically exempts markdown docs, configuration files, SQL migrations, and SPDX license blocks.
4. Detects and blocks syntax narration slop while strictly safeguarding `// SAFETY:` contracts, `///` Rust doc comments, and `/** ... */` docstrings.

## Invariant Rules

1. **Silence over noise:** If a line of code is obvious to a competent engineer, narrating it with comments is banned.
2. **Contract preservation:** Never strip or discourage `// SAFETY:` proof annotations, formal docstrings, or license headers.
3. **Proportional budget:** High CCR on its own is classified as `review`; it is upgraded to `blocker` only when confirmed syntax play-by-play narration patterns are detected.

## CLI Usage

```bash
# Check git diff against base commit
bunx anti-slop-engineering comment-guard --base HEAD

# Audit unified diff patch file directly with custom threshold
bunx anti-slop-engineering comment-guard \
  --diff-file diff.patch \
  --threshold 0.35 \
  --min-floor 20 \
  --json
```
