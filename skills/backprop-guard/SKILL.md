---
name: backprop-guard
description: Backpropagate downstream code failures, test rejections, and slop findings into upstream rules, invariants, and AGENTS.md rather than merely patching downstream symptoms.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Upstream Invariant & Rule Backpropagation Guard

> Feed errors from output back through the generative layers that produced them, updating upstream invariants so the failure can never recur.

## Why This Skill Is Needed & Target State

When an AI coding assistant introduces a bug or writes slop, standard workflows only fix the local file. The prompt, rules, constitution, or missing invariant that permitted the mistake remain untouched. Consequently, subsequent sessions repeat the exact same failure.

The target state is an error backpropagation pipeline:
1. **Identify the Symptom:** Map the failure to its error class (`DEMOCK`, `MANDELA`, `REDUCTION`, `AST_SLOP`, `SRE_KISS`).
2. **Question Upstream Requirements (Elon Step 1):** Challenge why the rule or gap existed.
3. **Pin the SSOT Owner:** Direct the invariant into `AGENTS.md`, `.anti-slop/invariant-ledger.json`, or a specific skill file.
4. **Atomically Apply:** Update the invariant ledger so all future agent turns ingest the new constraint at Gate 0.

## Invariant Rules

1. **Backprop Before Local Merge:** Significant downstream failures must emit an upstream invariant candidate before PR completion.
2. **One Canonical Owner:** Every backpropagated lesson belongs in exactly one Single Source of Truth (SSOT).
3. **Preserve Generalization:** Formulate rules as general behavioral constraints, not hyper-narrow one-off exceptions.

## CLI Usage

```bash
# Generate backprop record for an observed finding
bunx anti-slop-engineering backprop \
  --finding DEMOCK_SILENT_FALLBACK \
  --file "src/db/client.ts" \
  --line 42 \
  --excerpt "catch { return []; }" \
  --json

# Atomically commit invariant to .anti-slop/invariant-ledger.json
bunx anti-slop-engineering backprop \
  --finding DEMOCK_SILENT_FALLBACK \
  --file "src/db/client.ts" \
  --line 42 \
  --excerpt "catch { return []; }" \
  --apply
```
