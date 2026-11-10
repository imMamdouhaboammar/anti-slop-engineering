---
name: cognitive-load-and-attention-governor
description: >
  Enforce cognitive bandwidth and attention economy invariants across AI agent outputs,
  human-in-the-loop interactions, pull request descriptions, standalone deliverables, and
  multi-agent swarm handoffs. Governs scannability metrics (time-to-point, max wall length,
  landing anchor density), terminal blocking-question placement, deliverable purity (zero
  opener/closer fluff), working memory list bounding (Miller's law <= 5), and non-regression
  constraint preservation.
compatibility: ">=1.0.0"
metadata:
  version: "1.0.0"
  author: "Mamdouh Aboammar"
  license: "MIT"
---

# Cognitive Bandwidth & Attention Economy Governor

> "Attention is the scarcest resource in this conversation, and you are spending it with every word."

The cognitive bandwidth invariant execution pipeline is:

$$\text{Raw Content} \xrightarrow{\text{Scannability Gate}} \mathcal{S} \xrightarrow{\text{Terminal Ask Check}} \mathcal{B}_{pos} \xrightarrow{\text{Deliverable Purity}} \mathcal{P}_{deliv} \xrightarrow{\text{Non-Regression Guard}} \text{Pure Payload}$$

---

## Why This Skill Is Needed & Target State

**The Problem:**
Most LLM agents suffer from communicative slop:
1. **The Buried Ask:** When an agent needs human confirmation before an irreversible action (e.g. database migration, git push, deleting files), it buries the question in paragraph 2 and follows it with three paragraphs of status updates. Busy or ADHD users skim past it and miss the pending decision.
2. **Deliverable Impurity:** When asked to write a commit message, PR description, or configuration block, agents wrap it in conversational framing ("Here is your commit message:", "I hope this helps! Let me know if you need anything else!"). This breaks automated CI pipelines and wastes reviewer focus.
3. **Impenetrable Prose Walls:** Text that scores well on traditional readability formulas (Flesch-Kincaid) often consists of dense, anchor-free paragraphs. Readers bounce off walls of text without absorbing the load-bearing facts.
4. **Agent-to-Agent Swarm Bloat:** In multi-agent systems (Fable, Jev, EGM goldfish reviews), verbose subagent status reports contaminate orchestrator context windows, leading to attention decay and missed failure conditions.

**Target State:**
Zero conversational wrappers on deliverables. Bottom-line on Line 1. High visual anchor density ($\ge 3.0$ anchors per 100 words). Maximum unbroken wall $\le 60$ words. All blocking questions positioned in the terminal block with Line 1 flagged. Working memory lists capped at 5 items. Zero dropped technical numbers, thresholds, or warnings.

---

## Core Invariants

### 1. The Terminal Blocking-Question Invariant ($\mathcal{B}_{pos}$)
- If the reply requires human confirmation or a decision before proceeding, the ask **MUST** sit in the **last non-empty block**, with zero substantive prose after it (only short options/yes-no affordances permitted).
- If the reply exceeds 40 words, **Line 1 MUST explicitly flag the ask** (e.g. `before I`, `need`, `confirm`, `sign-off`, `go-ahead`, `wait`, or a decisive verdict opener `No`, `Don't`, `Stop`, `Hold`).

### 2. Deliverable Purity Invariant ($\mathcal{P}_{deliv}$)
- When asked to produce a deliverable (code, commit message, PR body, README snippet, config, command):
  - **Zero Opener Wrappers:** Ban `Here is...`, `Below is...`, `Sure!`, `I've drafted...`
  - **Zero Closer Offers:** Ban `Let me know if...`, `Hope this helps!`, `Feel free to customize...`
  - **Zero Lead-in Preamble:** Ban transitional lines ending in `:` or `.` right before a fenced code or quote block.

### 3. Text Shape Scannability Invariant ($\mathcal{S}$)
- **Time-to-Point ($TTP \le 20$ words):** Distance to the first bold anchor or verdict.
- **Maximum Wall Length ($W_{max} \le 60$ words):** Longest paragraph without a bold word, bullet, or heading.
- **Anchor Density ($\rho_{anchor} \ge 3.0$ per 100w):** Visual anchors (`**...**`, `→`, `#`, `-`) every 30 words.
- **Answer-First ($\mathcal{A}_1 = 1$):** Non-empty Line 1 starts with a bold takeaway or direct verdict.

### 4. Working Memory & List Bounding ($\mathcal{M}_{cap}$)
- Flat lists must not exceed 5 items (Miller's Law).
- For broader surveys, enforce progressive disclosure: name the top 2-3 items in full, and name/offer the remainder.

### 5. The Non-Regression Invariant (Preserving Technical Rigor)
- Brevity must never drop:
  - Exact numbers, timeouts, durations, and byte limits.
  - Scoped conditions (e.g., "only workspaces < 14 days old").
  - Safety warnings, error codes, and operational caveats.
- A warning is the last word to cut, never the first.

---

## Execution Workflows

| Mode | Trigger Condition | Playbook | Output Style |
|:-----|:------------------|:---------|:-------------|
| **Attention-Kind** | Default interactive agent dialogue | `playbooks/human-agent-interaction.md#attention-kind` | Plain English, front-loaded, bold anchors |
| **Spartan** | Heads-down coding, critical commands | `playbooks/human-agent-interaction.md#spartan` | Blunt, imperative, arrow bullets (`→`), zero warmth |
| **Rundown** | Standups, phase reviews, status checks | `playbooks/human-agent-interaction.md#rundown` | TL;DR on line 1, checklist (`✅`,`🟡`,`⬜`,`❔`), `Your move:` |
| **Swarm TOON** | Subagent-to-orchestrator handoffs | `playbooks/agent-to-agent-swarm.md` | Compressed TOON payload, bounded state tokens |

---

## Mathematical Metrics & Reference

Detailed mathematical definitions, KaTeX formulas, and empirical verification bounds live in **`references/attention-metrics.md`**.

Formal inter-module handoff contracts with Fable, J-Space, OmniSkill, OpenReview, PR Boundary Guard, and Comment Budget Guard live in **`references/handoff-contracts.md`**.

---

## CLI & Verification Commands

```bash
# Audit markdown file for scannability and attention violations
bunx anti-slop-engineering attention --file docs/rfc.md --json

# Verify 100% deliverable purity on a generated artifact
bunx anti-slop-engineering attention --text "$COMMIT_MSG" --check-deliverable

# Audit git diff additions across documentation
bunx anti-slop-engineering attention --base HEAD
```
