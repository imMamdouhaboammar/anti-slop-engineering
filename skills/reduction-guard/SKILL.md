---
name: reduction-guard
description: Enforce the Musk 5-Step Reduction Algorithm and 10% Add-Back Ledger calibration gate. Question requirements, delete parts before optimizing, and track deletion calibration.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Reduction Governor & Add-Back Ledger Guard

> "Possibly the most common error of a smart engineer is to optimize a thing that should not exist." — Elon Musk

## Why This Skill Is Needed & Target State

AI code generators suffer from additive bias: they continuously add parameters, options, wrapper functions, and speculative configurations. When asked to optimize, they optimize dead branches rather than deleting them.

The target state is strict adherence to the 5-Step Algorithm in rigid order:
1. **Make requirements less dumb:** Question who set the requirement and why. Constraints imposed by physics or law are kept; constraints imposed by habit or tradition are challenged.
2. **Delete the part or process:** Remove unused parameters, dead wrappers, and speculative branches.
3. **Simplify or optimize:** Only after deleting non-essential parts, simplify the remaining core.
4. **Accelerate cycle time:** Reduce test and iteration overhead.
5. **Automate:** Automate the verified, simplified pipeline.

## The 10% Add-Back Ledger Invariant

Musk's Rule: *"If you're not adding things back 10% of the time, you're clearly not deleting enough."*
Every deletion and add-back is logged to `.anti-slop/add-back-ledger.jsonl`.
- **Target Add-Back Rate:** $10\% \le R \le 25\%$ (Aggressive, calibrated simplification).
- **Timid ($< 10\%$):** Deletions are too conservative.
- **Reckless ($> 35\%$):** Deletions are careless and breaking active contracts.

## CLI Usage

```bash
# Check current calibration status and add-back rate
bunx anti-slop-engineering reduction status --json

# Log an item removal
bunx anti-slop-engineering reduction log-remove --item "legacy_v1_router" --reason "Replaced by v2"

# Log an item reinstatement
bunx anti-slop-engineering reduction log-addback --item "legacy_v1_router" --reason "External webhook compatibility"
```
