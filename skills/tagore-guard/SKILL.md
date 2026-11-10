---
name: tagore-guard
description: Eliminate AI prose tells, significance inflation, copula avoidance, and soulless flattening across PR descriptions, commit messages, ADRs, documentation, and agent reasoning traces. Inspired by Rabindranath Tagore's philosophy of literary restraint, empirical specificity, and authentic voice over statistical predictability. Enforces a dual-direction attack (removing inflated tells + adding empirical stakes), an 8-dimension scoring rubric with non-negotiable mechanics (>=35/50) and substance (>=21/30) floors (pass >= 56/80), and repository voice calibration.
license: MIT
metadata:
  version: "1.0.0"
  parent: anti-slop-engineering
  focus: engineering-discourse-and-substance
  author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
---

# Tagore Engineering Discourse & Substance Guard

> *"The butterfly counts not months but moments, and has time enough."* — Rabindranath Tagore

## Why This Skill Is Needed & Target State

Frontier LLMs operate on statistical likelihood, predicting the most probable tokens for broad audiences. In software engineering, this produces two devastating modes of discourse slop:

1. **Inflated Slop (The Marketing Pitch):**
   PR descriptions, ADRs, commit messages, and docstrings get bloated with significance inflation ("serves as an enduring testament", "marking a pivotal milestone"), copula avoidance ("boasts a comprehensive architecture that functions as"), superficial "-ing" participle chains ("enhancing throughput, ensuring resilience, and cultivating alignment"), rule-of-three triads, breathless em dashes, and marketing buzzwords ("groundbreaking", "seamless").
2. **Flattened Slop (The Sterile Wire-Copy):**
   When instructed to be objective or concise, models swing to the opposite extreme: passive voice ("the functions were updated by the system"), subjectless fragments, neutral reporting with zero technical conviction, zero empirical metrics, and zero mention of operational trade-offs, breaking risks, or failure modes.

**The Target State:**
Engineering discourse that carries what frontier models reach for and miss:
- **Active Technical Agency:** Engineers and systems do things; concepts don't "emerge".
- **Empirical Grounding:** Concrete numbers, percentages, milliseconds, memory deltas, commit SHAs, and file paths.
- **Operational Stakes & Conviction:** Explicit technical trade-offs, failure modes, and breaking boundaries.
- **Linguistic Restraint:** Sizing achievements at their actual technical magnitude with zero promotional puffery.
- **Varied Rhythm:** Sentence lengths differ naturally rather than marching in metronomic cadence.

---

## The Dual-Vector Slop Taxonomy

```
                          SUBSTANCE (30 pts, floor >= 21)
                                      ▲
                                      │
                   FLATTENED SLOP     │      CLEAN PROSE
             (High Mechanics, Low Sub)│    (Tagore Gate Passed)
             - Sterile wire-copy      │    - Empirical metrics
             - Passive voice          │    - Explicit trade-offs
             - Zero empirical numbers │    - Varied cadence
             - Zero operational stakes│    - Direct copulas
                                      │
  ────────────────────────────────────┼────────────────────────────────────► MECHANICS
                                      │                              (50 pts, floor >= 35)
                     REFUSE           │    INFLATED SLOP
             (Fails Both Dimensions)  │  (High Sub, Low Mech)
             - Chatbot preambles      │  - Significance puffery
             - Filler phrases         │  - Copula avoidance
             - Tautological truisms   │  - Superficial -ing chains
             - Metronomic cadence     │  - Rule-of-three triads
                                      │  - Breathless em dashes
```

---

## Invariant Rules

1. **The Dual Subtotal Floor Invariant:**
   A deliverable must score $\ge 56/80$ overall AND meet BOTH subtotal floors:
   $$\text{Mechanics} \ge 35/50 \quad \land \quad \text{Substance} \ge 21/30$$
   Passing mechanics while failing substance is rejected as `REVISE_SUBSTANCE` ("Clean but soulless"). Passing substance while failing mechanics is rejected as `REVISE_MECHANICS` ("Slop-shaped").
2. **The Direct Copula Rule:**
   Never substitute elaborate copula avoidance ("serves as a robust solution", "functions as a primary engine") for simple copula verbs ("is", "are", "has", "contains").
3. **The Anti-Participle Chaining Invariant:**
   Never tack trailing present participles (", enhancing X while fostering Y and ensuring Z") onto sentences to fake architectural depth. Break into active, declarative sentences naming the concrete mechanism.
4. **The Empirical Grounding Mandate:**
   Every technical PR description, ADR, or performance claim must cite at least one empirical token (benchmark delta, latency percentage, memory allocation, commit SHA, or exact file line).
5. **The Operational Stakes Invariant:**
   Engineering prose must state what can go wrong: failure modes, concurrency race conditions, memory limits, or trade-offs. Neutral summaries without trade-offs are flagged.
6. **The Direct Payload & Zero Affordance Mandate:**
   Transition directly from headings to technical content. Never write conversational preambles ("Here is an overview...", "I hope this helps!"), signposting ("Let's dive into..."), or affordance narration ("click to expand").

---

## The 5-Stage Execution Pipeline

### Stage 0: Voice Calibration (Optional Ground Truth)
Extract repository voice metrics from authentic maintainer commits or ADRs:
```bash
bunx anti-slop-engineering tagore --calibrate README.md
```
Matches sentence length distribution, empirical token density, and punctuation cadence.

### Stage 1: Draft Rewrite (Dual-Pass Scrub)
- **Pass 1a:** Scrub 29 cataloged tells (significance inflation, marketing hype, rule-of-three, em-dash, copula avoidance).
- **Pass 1b:** Inject technical substance (active human subjects, empirical metrics, operational trade-offs).

### Stage 2: Mechanical Pre-Delivery Checklist
Run 12 mechanical checks:
1. Adverbs? Kill them.
2. Passive voice? Find the actor, make them the subject.
3. Inanimate thing doing human verb ("the decision emerges")? Name the engineer/system.
4. "Here is..." or conversational throat-clearing? Delete.
5. "Not X, it's Y" negative parallelism? State Y directly.
6. Three consecutive sentences match length? Vary cadence.
7. Em dashes? Replace with commas, parentheses, or periods.
8. Vague declarative ("implications are significant")? State the exact delta.
9. Rule-of-three list? Cut to the primary one or two.
10. Copula avoidance ("serves as")? Replace with "is" or "has".
11. Emojis in technical prose? Remove.
12. Trailing -ing chains? Split into active clauses.

### Stage 3: 8-Dimension Scoring Matrix

| Category | Dimension | Max | Floor | Diagnostic Question |
| :--- | :--- | :---: | :---: | :--- |
| **Mechanics** | Directness | 10 | — | Statements or announcements? Zero throat-clearing. |
| | Rhythm | 10 | — | Varied cadence ($\text{stddev} \ge 5.0$) or metronomic? |
| | Trust | 10 | — | Zero affordance narration, zero hand-holding. |
| | Authenticity | 10 | — | Free of AI vocabulary, sycophancy, and copula avoidance. |
| | Density | 10 | — | Free of filler phrases, passive clutter, and bolding abuse. |
| *Subtotal* | **Mechanics Floor** | **50** | **35** | *Must clear 35/50 to avoid REVISE_MECHANICS* |
| **Substance** | Specificity | 10 | — | Names exact numbers, files, commits, and metrics. |
| | Restraint | 10 | — | Sizes achievements at actual scale; zero puffery. |
| | Technical Voice | 10 | — | Explicit trade-offs, failure modes, and operational stakes. |
| *Subtotal* | **Substance Floor** | **30** | **21** | *Must clear 21/30 to avoid REVISE_SUBSTANCE* |
| **Total** | **Overall Pass Gate**| **80** | **56** | *Both floors + $\ge 56$ required for PROCEED* |

### Stage 4: Self-Audit Reflection
Run the critical self-audit query:
> *"What makes this still obviously AI generated?"*
Check for late-surviving tells: overly tidy symmetric paragraphs, plausible-but-made-up placeholder numbers, slogan-y closing statements. Address before final release.

### Stage 5: Final Deliverable Contract
Emit clean deliverable with score breakdown, findings, and TOON status payload.

---

## Inter-Skill Handoff Contracts

| Partner Skill | Input Handoff to Tagore | Output Handoff from Tagore |
| :--- | :--- | :--- |
| **`cognitive-load-and-attention-governor`** | Provides scannability bounds ($TTP \le 20\text{w}$, $W_{max} \le 60\text{w}$, $\mathcal{B}_{pos}$ terminal). | Tagore guarantees lexical authenticity, substance floors, and zero copula avoidance before structural layout. |
| **`pr-boundary-guard`** | Provides git topology, commit message length caps, and checkbox contracts. | Tagore audits PR description body and commit bodies for AI tells, significance puffery, and missing operational stakes. |
| **`comment-budget-guard`** | Enforces Comment-to-Code Ratio ($\text{CCR} \le 0.35$) and bans syntax narration. | Tagore audits remaining docstrings and comments for direct copulas, active verbs, and zero -ing chains. |
| **`re0-handoff-guard`** | Mandates 1,500-token ceiling and cold-read Shower Test for State Notes. | Tagore ensures State Notes do not degenerate into sterile bullet points, preserving empirical metrics and trade-offs. |
| **`repo-memory-and-invariant-steward`** | Supplies established architectural invariants and ADR backlog. | Tagore audits new ADR proposals and invariant rationale for technical restraint and empirical proof. |
| **`get-fable` & `Poteto Mode`** | Fable lifecycle requires unslop prose before completing turn. | Tagore provides deterministic verification gate (`anti-slop tagore`) certifying prose quality before final response. |

---

## CLI Usage

```bash
# Audit inline text with suggested deslopping rewrites
bunx anti-slop-engineering tagore --text "This PR serves as an enduring testament..." --suggest

# Audit a PR description or ADR file
bunx anti-slop-engineering tagore --file docs/ADR-007.md --json

# Audit added prose from Git diff against base
bunx anti-slop-engineering tagore --base origin/main

# Output compact TOON format for agent handoffs
bunx anti-slop-engineering tagore --file PR_DESCRIPTION.md --toon

# Calibrate repository voice profile against maintainer docs
bunx anti-slop-engineering tagore --calibrate README.md
```
