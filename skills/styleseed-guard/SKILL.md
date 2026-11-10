---
name: styleseed-guard
description: Enforce StyleSeed Cognitive Job Output Grammars, 4-tier token canon DAG, 18-role semantic graph completeness, 11 pairwise contrast gates, 6-role spatial rhythm hierarchy, and S1 multi-screen longitudinal drift bounds.
license: MIT
metadata:
  version: "1.0.0"
  parent: anti-slop-engineering
---

# StyleSeed Synthesis: Cognitive Grammar, Token Canon DAG & Spatial Rhythm Guard

> Enforce Cognitive Job Output Grammars, 4-Tier Token Layering (Primitive -> Semantic -> Spatial/Type -> Component), 6-Role Spatial Rhythm Hierarchy, and S1 Multi-Screen Longitudinal Drift bounds across AI-generated UI systems.

## Why This Skill Is Needed & Target State

Standard aesthetic linters apply one monolithic standard to every interface, ignoring the **user's cognitive job**:
- In an **Operations Console** (`operations-console`), large decorative margins, hero cards, and oversized pill buttons are visual slop; 100% information density, tabular rows, compact monospace readouts, and immediate alert triage are essential.
- In **Editorial Reading** (`editorial-reading`), dense dashboards and noisy badges are slop; typographic hierarchy, optical baselines, and generous margins are essential.
- In **Technical Instruments** (`technical-instrument`), rounded cartoon buttons and gradient borders are slop; deterministic controls, explicit units, and zero layout shift are essential.

Furthermore, AI models generate **Token Spaghetti** and **Spatial Slop**:
1. **Primitive Token Leakage:** Hardcoded hex codes (`#2563EB`) or raw primitives (`colors.blue.600`) directly injected into leaf components, bypassing semantic themes.
2. **Circular and Upward Aliasing:** Primitives referencing primitives or semantic tokens aliasing component tokens.
3. **Contrast Deficits:** Defining `primary` without verifying mathematical contrast against `primaryForeground` across 11 canonical pairs.
4. **Spatial Inversion Anomalies:** Elements inside a card (`stackGap`) spaced further apart than the gap between independent sections (`sectionGap`).
5. **S1 Fifth-Screen Longitudinal Drift:** Diverging across screens 2..N away from baseline Screen 1 geometry, radii, and color.
6. **Decision Amnesia:** Re-inventing button heights and tokens across sessions without an auditable decisions/exceptions ledger.

The target state is a mathematically anchored, job-calibrated, token-layered design system with zero primitive leakage, strict spatial hierarchy, bounded longitudinal drift, and immutable invariants.

---

## The Non-Negotiable Invariants

1. **Anti-Leakage Token DAG (No Primitive Leakage in Components):** Component code (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`) must NEVER consume Tier 1 primitive literals or colors directly. Components consume Tier 2 Semantic tokens or Tier 4 Component tokens only.
2. **Pairwise Contrast Gates (11 Deterministic Pairs):** Semantic token pairs must satisfy WCAG 2.2 AA contrast ratios ($4.5:1$ for foreground/background/chrome/status pairs, $3.0:1$ for focus rings against surfaces).
3. **Spatial Rhythm Hierarchy (No Inversion Anomalies):** Inner sibling spacing (`stackGap`) must never exceed outer group spacing (`groupGap`) or section spacing (`sectionGap`):
   $$\text{stackGap} \le \text{groupGap} \le \text{sectionGap} \le \text{pageInset}$$
4. **Exceptions Cannot Waive Invariants:** A project decisions ledger (`.anti-slop/design-decisions.json` or `.styleseed/project.json`) may grant scoped exceptions to `default` craft rules, but **no exception can ever waive an invariant (`INV-*`)**. Invariant waiver attempts fail closed.
5. **S1 Longitudinal Drift Bound ($S_1 \le 0.25$):** Screens 2..N must not drift from baseline Screen 1 by more than $\Delta S_1 = 0.25$ across color, border radius, typography, and control heights.

---

## Mathematical Formulation

### 1. S1 Longitudinal Multi-Screen Drift Metric ($\Delta S_1$)

$$\Delta S_1 = \omega_c \cdot \Delta E(c_1, c_i) + \omega_r \cdot \frac{|r_1 - r_i|}{24} + \omega_f \cdot \delta_f(f_1, f_i) + \omega_h \cdot \frac{|h_1 - h_i|}{20}$$

Where:
- $\omega_c = 0.40, \omega_r = 0.20, \omega_f = 0.20, \omega_h = 0.20$
- $\Delta E(c_1, c_i)$ is normalized Euclidean color distance in sRGB / OKLab space.
- $r_1, r_i$ are observed border radii in pixels.
- $\delta_f$ is typographic font divergence ($0.0$ if matching family, $0.5$ if mismatched).
- $h_1, h_i$ are observed control heights in pixels.

### 2. Relative Luminance & Pairwise Contrast ($C_r$)

$$L = 0.2126 R_{\text{lin}} + 0.7152 G_{\text{lin}} + 0.0722 B_{\text{lin}}$$

$$C_r = \frac{L_{\text{lighter}} + 0.05}{L_{\text{darker}} + 0.05} \ge 4.5:1$$

---

## 4-Tier Token Layering Architecture

```
Tier 1: Primitives      [ #0F172A, #2563EB, 8px, 16px, 24px ]
      │ (alias only)
      ▼
Tier 2: Semantics       [ bg-surface, fg-default, border-subtle, primary, accent ]
      │ (alias only)
      ▼
Tier 3: Spatial & Type  [ pageInset, sectionGap, stackGap, display, body, mono ]
      │ (alias only)
      ▼
Tier 4: Components      [ button-primary-bg, card-elevation-border, input-height ]
```

---

## CLI Usage

```bash
# Scan repository for StyleSeed token leakage and spatial slop
bunx anti-slop-engineering styleseed --scan src/

# Audit against a specific tokens file and output grammar
bunx anti-slop-engineering styleseed --scan src/ --tokens tokens.json --grammar operations-console

# Validate spatial rhythm contract and decisions ledger
bunx anti-slop-engineering styleseed --spacing spacing.json --decisions decisions.json --strict

# Calculate S1 multi-screen drift index from probe measurements
bunx anti-slop-engineering styleseed --screens screens.json --json

# Inter-agent TOON protocol payload for get-fable / Poteto handoff
bunx anti-slop-engineering styleseed --scan src/ --toon
```

---

## Inter-Agent Handoff Contract (TOON Protocol)

When passing StyleSeed audit results between autonomous subagents, emit the formal TOON block:

```toon
styleseed-audit[v1.0.0]:
  verdict: PROCEED
  grammar: operations-console (density: compact)
  token-layers: { primitive: 32, semantic: 18, contrast-deficits: 0, leakage: 0 }
  spatial-rhythm: { roles: 6, inversions: 0, ad-hoc: 0 }
  s1-drift: { status: ANCHORED, max-dist: 0.04 }
  decisions-ledger: { decisions: 3, approved-exceptions: 1, invalid-exceptions: 0 }
  findings-count: [0]
```
