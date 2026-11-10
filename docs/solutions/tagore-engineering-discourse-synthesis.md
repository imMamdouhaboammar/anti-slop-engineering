# Tagore Synthesis: Engineering Discourse Substance, Dual-Vector Slop Taxonomy, 8-Dimension Scoring Rubric & Repository Voice Calibration

## 1. Executive Summary & Forensic Discovery

Reverse engineering of `apurvrdx1/tagore` (MIT) revealed a profound, neglected truth in AI-assisted software engineering: **engineering discourse (PR descriptions, commit messages, ADRs, documentation, code comments, and agent reasoning traces) represents over 50% of an engineering repository's cognitive surface, yet remains the primary attack vector for AI slop**.

While code-level linters audit ASTs and type assertions, LLMs drafting technical prose consistently degenerate into two catastrophic failure modes:

1. **Inflated Engineering Slop (The Marketing Pitch):**
   Technical prose is infected by statistical predictability: significance inflation ("serves as an enduring testament", "marking a pivotal milestone"), copula avoidance ("boasts a comprehensive architecture that functions as"), superficial "-ing" participle chaining ("enhancing throughput while fostering developer joy and cultivating collaboration"), rule-of-three triads, breathless em-dash crutches, and hollow promotional buzzwords ("groundbreaking", "seamless").
2. **Flattened Soulless Slop (The Sterile Wire-Copy):**
   When instructed to be concise, models swing to the opposite extreme: passive voice ("the functions were updated by the system"), subjectless fragments, neutral wire-copy summarizing code without stating *engineering trade-offs*, zero operational stakes, zero empirical measurements, and metronomic sentence rhythm.

### The Tagore Philosophy in Software Engineering
Named in homage to Rabindranath Tagore—whose prose carried what frontier models reach for and miss: a point of view, specificity over abstraction, and restraint over puffery—this module elevates prose deslopping into a deterministic, high-performance engineering discipline within `anti-slop-engineering`.

---

## 2. Architectural Pillars

### Pillar A: Dual-Vector Slop Taxonomy

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

Tagore rejects the fallacy that removing tells is sufficient. Removing tells alone produces sterile, voiceless text; adding substance on top of slop merely buries the slop. Both vectors must be addressed simultaneously.

### Pillar B: 8-Dimension Scoring Rubric & Subtotal Floors

The rubric evaluates 5 Mechanics dimensions (50 pts, floor 35) and 3 Substance dimensions (30 pts, floor 21) with an overall pass threshold of 56/80:

$$\text{Total Score} \ge 56/80 \quad \land \quad \text{Mechanics} \ge 35/50 \quad \land \quad \text{Substance} \ge 21/30$$

| Category | Dimension | Max | Floor | Focus |
| :--- | :--- | :---: | :---: | :--- |
| **Mechanics** | Directness | 10 | — | Statements or announcements? Zero throat-clearing. |
| | Rhythm | 10 | — | Sentence length variance ($\sigma \ge 5.0$); zero em-dash crutches. |
| | Trust | 10 | — | Zero affordance narration, zero hand-holding, zero servile hedging. |
| | Authenticity | 10 | — | Free of AI buzzwords (`delve`, `tapestry`, `testament`), copula avoidance, and triads. |
| | Density | 10 | — | Free of filler phrases (`in order to`), bolding abuse, and passive clutter ($< 35\%$). |
| *Subtotal* | **Mechanics Floor** | **50** | **35** | *Must clear 35/50 to avoid `REVISE_MECHANICS`* |
| **Substance** | Specificity | 10 | — | Names exact numbers, files, commits, latencies, and memory deltas. |
| | Restraint | 10 | — | Achievements sized at actual technical magnitude; zero puffery. |
| | Technical Voice | 10 | — | Explicit trade-offs, concurrency race conditions, and failure modes. |
| *Subtotal* | **Substance Floor** | **30** | **21** | *Must clear 21/30 to avoid `REVISE_SUBSTANCE`* |
| **Total** | **Overall Pass Gate**| **80** | **56** | *Both floors + $\ge 56$ required for `PROCEED`* |

### Pillar C: The Slop-to-Substance Ratio (SSR)
Quantifies prose quality into an empirical metric:
$$\text{SSR} = \frac{\text{Tells Count} + (\text{Passive Ratio} \times \text{Lines})}{\text{Empirical Tokens} + \text{Stakes Keywords} + 1}$$
- $\text{SSR} \le 0.20$: Pristine engineering prose.
- $0.20 < \text{SSR} \le 0.50$: Acceptable technical discourse.
- $\text{SSR} > 1.00$: Slop dominant; rejected.

### Pillar D: Repository Voice Profiler
Calibrates AI output to the ground-truth human voice of the repository (measured from lead maintainer commits, ADRs, or READMEs) across 8 attributes:
- `mean_sentence_length` ($12.0 - 22.0$ words)
- `sentence_length_stddev` ($\sigma \ge 5.0$)
- `passive_voice_ratio` ($\le 15\%$)
- `empirical_token_ratio` ($\ge 3.5\%$)
- `dash_density_per_100w` ($\le 1.0$)
- `type_token_ratio` ($0.40 - 0.60$)

---

## 3. Polyglot Architecture & Implementation

The module is implemented across the repository's three standard architectural tiers:

1. **Zero-Dependency Python Guard (`scripts/tagore_guard.py`):**
   - Compatible with Python >= 3.9 standard library only (`argparse`, `json`, `math`, `os`, `re`, `subprocess`, `sys`).
   - Implements regex scanning of the 29 cataloged tells + engineering extensions.
   - Computes the full 8-dimension scoring matrix, subtotal floors, SSR, and discourse vectors.
   - Supports `--file`, `--text`, `--base`, `--json`, `--toon`, `--suggest`, and `--calibrate`.
2. **High-Performance Streaming Rust Engine (`services/anti-slop-rust/src/tagore_auditor.rs`):**
   - Implemented in Rust with zero-allocation regex sets.
   - Audits streaming git diffs during pre-commit hooks and CI pipelines for `TAGORE-INFLATION-01`, `TAGORE-COPULA-02`, `TAGORE-PARTICIPLE-03`, `TAGORE-HYPE-04`, and `TAGORE-SYCOPHANCY-05`.
   - Integrated into `triage_diff` in `services/anti-slop-rust/src/lib.rs`.
3. **Multi-Agent CLI Integration (`bin/cli.js`):**
   - Exposes `tagore`, `tagore-guard`, `discourse`, `deslop-prose`, and `humanize` commands.
   - Supports both machine-readable JSON (RFC 9457) and compact TOON formats for agent handoffs.
4. **RFC 9457 JSON Schema (`schemas/tagore_record.json`):**
   - Standardized Problem Details schema with explicit metrics, findings, and remediation actions.
5. **Living Invariant Ledger Integration (`.anti-slop/invariant-ledger.json` & `.toon`):**
   - Added `INV-TAGORE-ENGINEERING-DISCOURSE-AND-SUBSTANCE` indexed and verified by `scripts/invariant_steward_guard.py`.

---

## 4. Inter-Module Handoff Contracts

| Module | Input Contract to Tagore | Output Contract from Tagore |
| :--- | :--- | :--- |
| **`cognitive-load-and-attention-governor`** | Provides structural scannability limits ($TTP \le 20\text{w}$, $W_{max} \le 60\text{w}$). | Tagore certifies lexical purity, substance floors, and zero copula avoidance before structural layout. |
| **`pr-boundary-guard`** | Supplies git topology, branch hygiene, and commit subject length ($\le 100$ chars). | Tagore audits PR description bodies and commit message bodies for significance puffery and missing operational stakes. |
| **`comment-budget-guard`** | Enforces Comment-to-Code Ratio ($\text{CCR} \le 0.35$) and bans syntax play-by-play narration. | Tagore audits surviving docstrings and comments for direct copulas, active verbs, and zero participle chains. |
| **`re0-handoff-guard`** | Mandates 1,500-token ceiling and cold-read Shower Test for State Notes. | Tagore ensures State Notes do not degenerate into sterile bullet points, preserving empirical metrics and trade-offs. |
| **`repo-memory-and-invariant-steward`** | Supplies established architectural invariants and ADR backlog. | Tagore audits new ADR proposals and invariant rationale for technical restraint and empirical proof. |
| **`get-fable` & `Poteto Mode`** | Requires unslop prose before completing autonomous agent turns. | Tagore provides deterministic verification gate (`anti-slop tagore`) certifying prose quality before final response. |

---

## 5. Verification & Test Evidence

All tiers of the test suite were executed and verified with 100% green status:

1. **Python Unit Suite (`python3 -m unittest discover -s tests -v`):**
   - Ran **458 tests** across all guards in 27.9s $\to$ **OK (0 failures)**.
   - `tests/test_tagore_guard.py`: 7 dedicated test cases verifying clean prose pass, inflated slop detection, flattened soulless slop detection, subtotal floor enforcement, voice calibration computation, CLI selftest, and JSON/TOON output.
2. **Rust Engine Suite (`cargo test`):**
   - Ran **14 tests** in `services/anti-slop-rust` $\to$ **14 passed; 0 failed**.
   - Verified `test_detects_significance_inflation`, `test_detects_copula_avoidance`, and `test_detects_promotional_hype`.
3. **CLI Integration Suite (`node tests/test_cli.mjs`):**
   - Ran **43 tests** across CLI dispatch and subcommands $\to$ **43 passed; 0 failed**.
   - Verified `tagore command routes to the Tagore engineering discourse & substance guard`.
4. **Invariant Steward Audit (`python3 scripts/invariant_steward_guard.py audit`):**
   - Verified that all 7 active invariants (including `INV-TAGORE-ENGINEERING-DISCOURSE-AND-SUBSTANCE`) pass schema validation and hash integrity.
5. **Self-Diff Verification (`python3 scripts/diff_guard.py --base HEAD` & `scripts/sre_guard.py --base HEAD`):**
   - **0 Blockers** across both guards.
