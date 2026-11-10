# Inter-Module Handoff Contracts

> Formal Handoff Protocols Between Tagore Guard and Existing Anti-Slop Modules.

---

## 1. Tagore ↔ Cognitive Bandwidth & Attention Economy Guard

### Contract Purpose
Cognitive Load & Attention Governor (`scripts/attention_guard.py`) regulates structural ergonomics: Time-to-Point ($TTP \le 20\text{w}$), Maximum Wall Length ($W_{max} \le 60\text{w}$), Anchor Density ($\ge 3.0/100\text{w}$), and Terminal Blocking Placement ($\mathcal{B}_{pos}$).
However, text can be structurally scannable while still being stuffed with AI significance puffery or copula avoidance.

### Execution Sequence
1. **Pre-Filter (Tagore Guard):**
   Tagore audits the raw text for lexical tells (29 catalog items), copula avoidance, and substance floors ($\text{Substance} \ge 21/30$).
   - If Tagore fails (`REVISE_MECHANICS` or `REVISE_SUBSTANCE`), execution halts immediately.
2. **Post-Filter (Attention Governor):**
   Once prose is linguistically clean and grounded, Attention Governor evaluates visual shape, bold anchor placement, and scannability.
3. **Payload Passing:**
   Tagore emits `metrics.discourse_vector = "clean"` in the TOON payload consumed by Attention Governor.

---

## 2. Tagore ↔ PR Boundary & Git Topology Guard

### Contract Purpose
PR Boundary Guard (`scripts/pr_boundary_guard.py`) verifies branch hygiene, commit subject length ($\le 100$ characters), and PR template radio-button state.
It does not deeply analyze whether the PR description or commit message body is bloated with chatbot fluff.

### Protocol
- **Trigger:** Pre-push or CI PR triage (`anti-slop pr-guard`).
- **Handoff:** PR Boundary Guard extracts the PR body (`PULL_REQUEST_TEMPLATE.md` or git log message body) and delegates prose analysis to Tagore:
  ```bash
  bunx anti-slop-engineering tagore --file .github/pull_request_body.md --json
  ```
- **Invariant:** A PR cannot be approved if PR Boundary Guard passes but Tagore returns `REVISE_MECHANICS` or `REVISE_SUBSTANCE`. Both gates must be GREEN.

---

## 3. Tagore ↔ Comment Budget & Syntactic Obviousness Guard

### Contract Purpose
Comment Budget Guard (`scripts/comment_budget_guard.py`) enforces Comment-to-Code Ratio ($\text{CCR} \le 0.35$) and bans syntax narration (e.g. `// increment i`, `// return result`).
It protects formal `// SAFETY:` invariants and JSDoc/TSDoc docstrings.

### Protocol
- When docstrings or multiline explanatory comments survive Comment Budget screening, Tagore audits their linguistic formulation:
  - Banning copula avoidance ("This function serves to validate..." $\to$ "Validates...")
  - Banning superficial participle chains ("Validates input, ensuring compliance and enhancing security")
  - Banning chatbot apologetics or unverified training disclaimers.

---

## 4. Tagore ↔ Re0 State-Note & Shower-Test Guard

### Contract Purpose
Re0 Handoff Guard (`scripts/re0_handoff_guard.py`) enforces NVIDIA's 1,500-token context reset discipline for agent handoffs.
State notes must pass the Cold-Read Shower Test.

### Protocol
- Tagore audits the `OBJECTIVE`, `PROVEN_INVARIANTS`, and `NEGATIVE_CORPUS` blocks in `.anti-slop/state-note.json`:
  - Enforces active subject agency (no passive drifting).
  - Enforces empirical metrics (exact test counts, memory usage, latency numbers).
  - Flags sterile bullet points that omit concrete technical trade-offs.

---

## 5. Tagore ↔ Repo Memory & Invariant Steward

### Contract Purpose
Repo Memory & Invariant Steward (`scripts/invariant_steward_guard.py`) synchronizes established architecture invariants (`.anti-slop/invariant-ledger.json` and `.toon`).

### Protocol
- When a new invariant or ADR is drafted, Tagore audits the rationale text.
- Prevents architectural records from being corrupted by marketing puffery or ungrounded speculative reasoning.
- Verifies that every proposed invariant cites empirical evidence and explicit trade-offs.

---

## 6. Tagore ↔ Get-Fable Lifecycle & Poteto Mode

### Contract Purpose
Get-Fable and Poteto Mode govern autonomous agent execution loops:
- "Substantial work requires passing completion evidence for the current generation."
- "Any prose surface $\to$ the unslop skill. Your reply is a prose surface."

### Protocol
- Before completing any agent turn or handoff:
  ```bash
  bunx anti-slop-engineering tagore --text "<deliverable-or-pr-body>" --toon
  ```
- If the TOON record reports `verdict: REVISE_*` or `verdict: REFUSE`, the agent must NOT declare the task done or ask the user for feedback. The agent must loop, apply the suggested replacements, inject empirical substance, and re-verify until `verdict: PROCEED`.
