# StyleSeed Synthesis: Cognitive Job Output Grammars, 4-Tier Token Canon DAG, 6-Role Spatial Rhythm & S1 Longitudinal Multi-Screen Drift Guard

## 1. Executive Summary & Forensic Discovery

Reverse engineering of `bitjaru/styleseed` (v5.0.0, MIT) revealed that aesthetic failures in AI-assisted UI generation do not stem from a lack of visual "taste" or missing prompt instructions; they stem from **architectural amnesia, uncalibrated cognitive job models, token leakage, and spatial disorder**:

1. **Monolithic Linter Fallacy:** Conventional linters enforce a single monolithic aesthetic standard across all screens. An **Operations Console** requiring 100% density, monospace numerical tabular alignment, and zero decorative cards is penalized as "harsh", while a marketing landing page is permitted to generate fluffy, uninformative cards. In reality, design quality is strictly relative to the user's **cognitive job**.
2. **Token Spaghetti & Primitive Leakage:** AI code generators inject raw hex codes (`#2563EB`) or raw primitive Tailwind classes (`bg-blue-600`) directly into leaf components, bypassing semantic themes and breaking dark-mode and white-label adaptation.
3. **Spatial Slop & Inversion Anomalies:** AI generators randomly guess paddings (`p-3`, `px-5`, `my-7`, `gap-2.5`) without an underlying spatial hierarchy, frequently producing inversion anomalies where internal element spacing (`stackGap`) exceeds outer section separation (`sectionGap`).
4. **$S_1$ Multi-Screen Longitudinal Drift:** Over a 5-screen generation trajectory, AI agents drift dramatically in color Euclidean distance ($\Delta E$), button heights (from 40px to 64px), and border radii (from 6px to 28px).
5. **Decisions Amnesia & Invariant Erosion:** Multi-turn sessions repeatedly re-derive design choices from statistical memory rather than binding to an audited decisions ledger, or attempt to waive non-negotiable accessibility invariants.

To resolve these failure modes, we synthesized and integrated the **StyleSeed Guard** (`styleseed-guard`) directly into `anti-slop-engineering`.

---

## 2. Architectural Pillars

### Pillar A: 12-Axis Cognitive Job Output Grammars
The engine defines 7 canonical cognitive output grammars with tailored density, containment, and control bounds:

| Grammar | Cognitive Job | Density | Containment | Dominance | Allowed Control Heights | Max Radius |
|---|---|---|---|---|---|---|
| `operations-console` | Real-time monitoring & triage | Compact | Bordered | Peer | 28px, 32px, 36px | 6px |
| `technical-instrument` | High-precision scientific parameter control | Compact | Flat | Subordinate | 28px, 32px | 4px |
| `editorial-reading` | Long-form reading & cognitive absorption | Spacious | Flat | Subordinate | 40px, 48px | 8px |
| `commerce-conversion` | Transactional checkout & catalog exploration | Balanced | Raised | Singular | 44px, 48px, 56px | 12px |
| `consumer-service` | Everyday task completion & workflow navigation | Balanced | Raised | Singular | 36px, 40px, 44px | 16px |
| `institutional-service` | Citizen self-service & statutory compliance | Balanced | Bordered | Singular | 40px, 44px, 48px | 8px |
| `expressive-marketing` | Brand storytelling & product launch engagement | Spacious | Raised | Singular | 44px, 52px, 60px | 24px |

### Pillar B: 4-Tier Token Layering DAG & Anti-Leakage Engine
Tokens are strictly structured as a 4-tier directed acyclic graph:
- **Tier 1 (Primitives):** Holds raw literal color/scale values (`#0F172A`, `#2563EB`, `8px`). Never consumed directly by UI components.
- **Tier 2 (Semantics):** 18 canonical roles (`background`, `surface`, `chrome`, `foreground`, `mutedForeground`, `chromeForeground`, `border`, `primary`, `primaryForeground`, `accent`, `accentForeground`, `focus`, `success`, `successForeground`, `warning`, `warningForeground`, `danger`, `dangerForeground`).
- **Tier 3 (Spatial & Typographic Roles):** 6 spatial rhythm roles + typography scales.
- **Tier 4 (Components):** Scoped to specific UI elements, referencing semantic tokens only.

**Enforced Anti-Leakage Invariants:**
- `PRIMITIVE_TOKEN_LEAKAGE`: Leaf components consuming raw hex literals or primitive tokens directly.
- `UPWARD_CIRCULAR_ALIAS`: Primitives referencing primitives, or semantic tokens referencing component tokens.
- `PAIRWISE_CONTRAST_DEFICIT`: 11 deterministic pairwise contrast gates evaluated across semantic role pairs (WCAG 2.2 AA $\ge 4.5:1$ for text/status; $\ge 3.0:1$ for focus rings).

### Pillar C: 6-Role Spatial Rhythm Contract
Whitespace is partitioned into 6 distinct architectural roles:
1. `pageInset`: Viewport boundary to layout container.
2. `sectionGap`: Gap between independent functional sections.
3. `groupGap`: Gap between card clusters or fieldsets.
4. `stackGap`: Vertical spacing between immediate sibling elements.
5. `inlineGap`: Horizontal spacing between inline controls or chips.
6. `componentInset`: Internal padding of a container/card.

**Inversion Invariant:** Inner sibling spacing must never exceed outer grouping:
$$\text{stackGap} \le \text{groupGap} \le \text{sectionGap} \le \text{pageInset}$$

### Pillar D: $S_1$ Longitudinal Multi-Screen Drift Metric
Screen 1 serves as the ground-truth baseline ($S_1$). For subsequent screens $S_2 \dots S_N$, the longitudinal drift index is computed as:
$$\Delta S_1 = \omega_c \cdot \Delta E(c_1, c_i) + \omega_r \cdot \frac{|r_1 - r_i|}{24} + \omega_f \cdot \delta_f(f_1, f_i) + \omega_h \cdot \frac{|h_1 - h_i|}{20}$$
Where $\omega_c = 0.40, \omega_r = 0.20, \omega_f = 0.20, \omega_h = 0.20$. If $\Delta S_1 > 0.25$, the build is rejected for unanchored longitudinal drift.

### Pillar E: Project Decisions & Approved Exceptions Ledger
- `decision`: Establishes allowed values for an axis (`controlHeights: [36, 44]`), outranking defaults.
- `exception`: Adds an allowed value scoped to specific screens (`scope: { screens: ["orders"] }`).
- **Non-Negotiable Invariant:** Exceptions can **NEVER** waive an invariant (`INV-*`). Any attempt to waive accessibility or safety invariants fails closed with `ILLEGAL_INVARIANT_WAIVER`.

---

## 3. Polyglot Architecture & Handoff Contracts

| Component | Path | Technology | Purpose |
|---|---|---|---|
| **Python Guard** | `scripts/styleseed_guard.py` | Python 3.9+ (Stdlib zero-dependency) | Full offline audit, contrast math, S1 drift calculation, JSON/TOON serialization |
| **Rust Engine** | `services/anti-slop-rust/src/styleseed_auditor.rs` | Rust 2024 / native binary | High-throughput sub-millisecond triage in git diff pipeline |
| **CLI Dispatcher** | `bin/cli.js` | Bun / Node.js | Subcommand routing (`bunx anti-slop-engineering styleseed`) |
| **JSON Schema** | `schemas/styleseed_record.json` | Draft-07 JSON Schema | Strict validation contract for audit reports |
| **Agent Skill** | `skills/styleseed-guard/SKILL.md` | AgentSkills.io v1 / Poteto Mode | Directives, mathematical formulas, and CLI recipes for coding agents |
| **Invariant Ledger** | `.anti-slop/invariant-ledger.json` | JSON & TOON | Durable record of `INV-STYLESEED-TOKEN-DAG-AND-SPATIAL-RHYTHM` |

---

## 4. Verification & Polyglot Test Suite Results

All tests across all runtimes passed with zero failures:
1. **Python Unit Tests:** 438 existing tests + 13 new StyleSeed tests = **451 tests passing** (`python3 -m unittest discover -s tests -v`).
2. **Rust Engine Tests:** 11 unit tests + 4 interceptor tests + 3 ladder tests = **18 tests passing** (`cargo test --manifest-path services/anti-slop-rust/Cargo.toml`).
3. **Go Microservice Tests:** 17 tests passing (`(cd services/toil-guard-go && go test -v ./...)`).
4. **Node/Bun CLI Tests:** 42 CLI integration tests passing (`node --test tests/test_cli.mjs`).
5. **Invariant Steward Audit:** 8 invariants verified with `record_status: "complete"`.
