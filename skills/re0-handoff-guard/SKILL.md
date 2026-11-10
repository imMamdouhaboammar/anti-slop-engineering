---
name: re0-handoff-guard
description: Enforce NVIDIA Belcak et al. (2026) RSI Discovery & Paperthin Re0-Handoff contract. Compile dense, zero-slop State Notes (<=1500 tokens) and audit cold-read readiness via the Shower Test.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Re0 State-Note & Shower-Test Guard

> "You don't need long context; you need dense state notes and recursive resets." — NVIDIA Discovery (Belcak et al., 2026)

## Why This Skill Is Needed & Target State

Long context windows (>50K tokens) degrade agent reasoning via attention diffusion, hallucination debt, and conversational pollution. Belcak et al. proved on SWE-bench Verified that agents with 16K-token short state notes match or exceed 200K-token runs while serving 7x faster.

The target state is a structured context-reset protocol:
1. **1,500 Token Budget:** Dense, zero-fluff summary of objective, proven facts, and negative corpus.
2. **Shower Test (Cold-Read Audit):** Verifies that a subagent with zero prior conversational history can deterministically execute the next step.
3. **No Ungrounded Pronouns:** Banning ambiguous relative references ("this file", "the bug", "it") without explicit file paths or identifiers.
4. **Preserved Negative Corpus:** Keeping records of discarded hypotheses and dead ends so future cycles never repeat them.

## Invariant Rules

1. **Strict Token Ceiling:** State-notes must never exceed 1,500 tokens.
2. **Falsifiable Invariants:** Every entry in `PROVEN_INVARIANTS` must cite an executable verification command and digest.
3. **Discrete Single Action:** `NEXT_SINGLE_ACTION` must specify exactly one concrete file and verification command, not a multi-step speculative plan.

## CLI Usage

```bash
# Compile a new Re0 State-Note
bunx anti-slop-engineering re0-handoff compile \
  --goal "Upgrade database layer to fail closed" \
  --action "Remove sqlite fallback" \
  --target "src/db.ts" \
  --verify-cmd "bun test tests/db.test.ts"

# Run the Cold-Read Shower Test
bunx anti-slop-engineering re0-handoff shower-test --file .anti-slop/state-note.json
```
