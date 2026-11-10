---
name: design-system-drift-guard
description: Audit multi-surface applications for cross-route design system drift, unpoliced component variant explosions, orphaned single-route tokens, and keyboard focus-ring accessibility suppression.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Design System Drift & Variant-Budget Guard

> Prevent multi-route component proliferation, unpoliced variant explosions, and keyboard focus ring suppression across shipping applications.

## Why This Skill Is Needed & Target State

Single-file linters and isolated component tests miss the primary failure mode of evolving applications: **cross-route design drift**.
- Screen 1 declares 3 button variants (`primary`, `secondary`, `outline`). Screen 7 invents a 4th variant (`ghost` with slightly different padding or opacity) because the author lacked global visibility.
- Interactive controls (`button`, `a`, `input`, `select`) suppress outline focus rings via `outline: none` or Tailwind `focus:outline-none` without providing an explicit `:focus-visible` replacement, breaking WCAG 2.4.7 keyboard accessibility.
- Ad-hoc design tokens are created and used on exactly one route, inflating theme entropy.

The target state is a governed, bounded design system with explicit variant budgets per control kind, 100% visible keyboard focus indicators, and minimal token entropy.

## Invariant Rules

1. **Variant Budget Enforcement:** Each control kind (`button`, `input`, `select`, `card`, `badge`) must strictly adhere to its declared variant budget (default: 4 for button/card, 2 for select/input).
2. **Keyboard Focus Ring Protection:** Interactive elements must never suppress outline (`outline: none`, `focus:outline-none`) without an accompanying visible replacement (`:focus-visible:ring-2`, `box-shadow`).
3. **Zero Orphaned Tokens:** Design tokens used on exactly one route in multi-route products must be promoted to the canonical global theme or consolidated.

## Mathematical Formulation: Design System Entropy Index ($DSEI$)

$$DSEI = \sum_{k \in \text{Kinds}} \max\left(0, \frac{V_k - B_k}{B_k}\right) + \omega_{\text{focus}} \cdot F_{\text{missing}} + \omega_{\text{orphan}} \cdot T_{\text{orphan}}$$

Where:
- $V_k$ is the observed variant count for control family $k$.
- $B_k$ is the declared budget limit.
- $F_{\text{missing}}$ is the count of interactive elements missing keyboard focus rings.
- $T_{\text{orphan}}$ is the count of single-route design tokens.

## CLI Usage

```bash
# Scan source tree for variant budgets and focus ring suppression
bunx anti-slop-engineering system-drift --scan src/

# Specify per-kind variant budgets
bunx anti-slop-engineering system-drift --scan src/ --max-variants button=4,select=1,card=3 --json

# Validate pre-existing system drift record
bunx anti-slop-engineering system-drift --file .anti-slop/system-drift.json --strict
```
