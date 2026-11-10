---
name: house-tell-guard
description: Enforce the physical Gate 0 commit-sheet, break agent internal house tells, and mandate category reflex inversion before any code generation.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Agent House-Tell & Triple-Reflex Inversion Guard

> Require physical commit-sheet contracts on disk before code generation, eliminating category clichés and agent self-referential design habits.

## Why This Skill Is Needed & Target State

Slop is not ugliness; it is predictability. Generative models operate at three altitudes of reflex:
1. **First-Order Reflex**: What generic AI does for the category (e.g. AI tool = dark mode + neon blue glow + terminal mono).
2. **Second-Order Reflex**: What an AI trying to avoid the first order does (e.g. editorial serif on off-white "anti-SaaS" cliché).
3. **Third-Order Reflex (The House Tells)**: The subconscious habits of the agent or framework itself across unrelated projects (near-black background, mono corner labels, glowing borders, identical 3-card bento grids, decorative comment banners).

The target state is a physical, signed Gate 0 Pre-Commit Sheet (`.anti-slop/commit-sheet.json` or `design/COMMIT-SHEET.md`) that contractually breaks at least two house tells and commits non-default architectural decisions before code generation begins.

## Invariant Rules

1. **Gate 0 Physical Deliverable:** Zero code modification is permitted before `.anti-slop/commit-sheet.json` or `design/COMMIT-SHEET.md` exists and passes validation.
2. **The Seven Commitments:** The commit-sheet must provide non-generic, substantive answers for:
   - Peak / Signature Element (one sentence).
   - Color Strategy & Numeric Lightness ($L_{\text{target}}$).
   - Typographic Contrast Axis (rejecting Inter/Space Grotesk defaults).
   - Grid / Structure Break (concrete asymmetry or overlap).
   - Motion Budget ($\le 3$ scroll pattern families).
   - Category Reflex Check (1st order, 2nd order, and argued departure).
   - **House Tells Broken:** Minimum 2 habits of the agent itself contractually barred with explicit replacements.
3. **Anti-Truism Filter:** Generic marketing statements ("clean, modern look", "user-friendly design", "beautiful animations throughout") are rejected with exit code 2.

## CLI Usage

```bash
# Initialize a starter commit sheet template
bunx anti-slop-engineering house-tell --init-template

# Validate active commit sheet
bunx anti-slop-engineering house-tell --file .anti-slop/commit-sheet.json

# Validate markdown commit sheet with JSON output
bunx anti-slop-engineering house-tell --file design/COMMIT-SHEET.md --json --strict
```
