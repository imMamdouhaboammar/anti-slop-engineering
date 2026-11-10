# Inter-Module Handoff Contracts

This specification defines the explicit bidirectional handoff contracts between the Cognitive Bandwidth & Attention Economy Governor and existing agent engines and guard systems.

---

## 1. Handoff Contract: Attention Governor $\longleftrightarrow$ Fable Lifecycle (`get-fable`)

### Context:
Fable orchestrates complex autonomous engineering cycles (Discovery, Planning, Execution, Verification, Learning). Subagents reporting back to the coordinator emit verbose narrative tokens that inflate context windows and bury critical invariant failures.

### Ingress Contract (Subagent $\rightarrow$ Attention Governor):
When a Fable subagent finishes a task or hits a circuit breaker, its raw markdown report must pass through the Attention Governor filter before submission to the orchestrator:

```toon
[SubagentHandoffEnvelope] (version: 1.0)
fields: 5
  task_id: string
  execution_phase: enum(DISCOVERY|PLANNING|EXECUTION|VERIFICATION|LEARNING)
  status_checklist: list[4] (done, in_progress, not_started, unknown)
  blocking_decision: optional[BlockingAsk]
  state_payload: string
```

### Filtering Invariants:
1. **Rundown State Checklists:** State must be rendered strictly with 4 standard indicators:
   - `✅ <subject> <past-tense-verb>`
   - `🟡 <subject> <present-participle-verb>`
   - `⬜ <subject> not started`
   - `❔ <subject> unknown`
2. **Terminal Blocking Placement:** If `blocking_decision` is present, it MUST be positioned at the terminal block of the TOON envelope, and Line 1 must declare: `FLAG: Decision required before phase transition.`
3. **Purity Enforcement:** Zero transitional conversational filler ("I have completed the tasks you assigned me. Here is the summary...").

---

## 2. Handoff Contract: Attention Governor $\longleftrightarrow$ Latent Workspace (`j-space`)

### Context:
J-Space (Gurnee et al., Anthropic 2026) models the internal representations of concepts an agent is "poised to say". Unfiltered dumping of internal deliberations creates conversational slop.

### Egress Contract (J-Space $\rightarrow$ External Transcript):
1. **The Poised-to-Speak Filter:** Deep multi-turn internal reasoning, backtracking, and counterfactual proofs remain bounded inside J-Space internal memory.
2. **The Broadcast Gate:** When materializing tokens to the external conversation transcript:
   - Apply the **Bottom-Line Rule:** The single most decisive verdict or architectural conclusion occupies Line 1.
   - Apply **Anchor Injection:** Break homogeneous reasoning into blank-line-separated points with bold anchors (`**Takeaway.**`) or directional arrows (`→`).
   - Suppress Tangents: Speculative design musings that do not affect the immediate task are retained in J-Space rather than emitted.

---

## 3. Handoff Contract: Attention Governor $\longleftrightarrow$ Autonomous Review (`openreview` & `omni-skill`)

### Context:
OpenReview and OmniSkill post automated PR review comments, suggestions, and architectural triage reports across GitHub, GitLab, and local IDEs.

### Ingress & Egress Invariants:
1. **100% Deliverable Purity:**
   $$\mathcal{P}_{deliv} = 1.0$$
   Automated comments must never begin with "I noticed that..." or "Good job on this PR, however...".
2. **Direct Suggestion Format:**
   Reviews must lead immediately with the target file and line anchor:
   ```markdown
   **`src/auth.ts:42`** Replace deprecated token verification with crypto-safe validator.

   ```diff
   - const token = jwt.verify(raw);
   + const token = await safeVerifyToken(raw, { maxAge: 3600 });
   ```
   ```
3. **Miller's Law Review Cap:**
   A single review pass must present at most 5 top-priority findings per review comment. Additional findings must be grouped into expandable sections or deferred to subsequent triage passes.

---

## 4. Handoff Contract: Attention Governor $\longleftrightarrow$ PR Boundary & Comment Budget Guards

### Integration Matrix:

| Guard | Primary Domain | Attention Governor Cross-Validation |
|:------|:---------------|:------------------------------------|
| `pr-boundary-guard` | Git provenance, branch naming, template checkboxes, commit subjects | Audits the PR description body for Time-to-Point ($TTP \le 20$), Maximum Wall Words ($W_{max} \le 60$), and terminal question placement. |
| `comment_budget_guard` | Comment-to-Code Ratio ($\text{CCR} \le 0.35$), banning syntax play-by-play | Ensures retained comments are concise, load-bearing contracts with zero cognitive fluff. |
| `diff_guard` | Seven Gates, SRE rules, AST rules, sensitive secrets | Scans newly added markdown files, READMEs, and docstrings for opener wrappers and closer offers. |

---

## 5. Handoff Contract: Attention Governor $\longleftrightarrow$ Audit Runner (`scripts/audit_runner.py`)

### Execution Protocol:
During `bunx anti-slop-engineering check` or `bunx anti-slop-engineering audit`:
1. `attention_guard` executes against modified markdown files and PR diffs.
2. Any `blocker` finding (`COGNITIVE-BURIED-ASK`, `COGNITIVE-DELIVERABLE-IMPURITY`, `ERR_EXCESSIVE_WALL_OF_TEXT`) triggers exit code 2 and blocks CI / automated pull request merges.
3. Machine-readable findings are formatted as RFC 9457 Problem Details in the compiled audit report (`anti-slop/audit-NNN.md`).
