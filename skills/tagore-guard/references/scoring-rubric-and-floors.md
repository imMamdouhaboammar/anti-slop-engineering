# Tagore Scoring Rubric & Subtotal Floors

> Mathematical Specification and Diagnostic Criteria for the 8-Dimension Discourse Scoring Matrix.

---

## The 8 Dimensions

Every piece of engineering prose (PR description, commit body, ADR, docstring, or state note) is evaluated on 8 distinct dimensions (1–10 points each).

$$\text{Total Score} = \sum_{i=1}^{5} \text{Mechanics}_i + \sum_{j=1}^{3} \text{Substance}_j$$

$$\text{Pass Condition} = (\text{Total Score} \ge 56) \land (\text{Mechanics} \ge 35) \land (\text{Substance} \ge 21)$$

---

## 1. Mechanics Dimensions (Max: 50, Floor: 35)

### M1: Directness (1–10)
- **Question:** Does the text state facts directly, or does it announce them?
- **Penalties:** Chatbot preambles (-3), signposting announcements (-2), persuasive authority tropes (-2), fragmented warmup headers (-2).
- **Target:** 10 = Zero announcements; immediate technical payload.

### M2: Rhythm & Cadence (1–10)
- **Question:** Does sentence length vary naturally, or is it metronomic?
- **Formula:**
  $$\text{Score} = \begin{cases}
  10 & \text{if } \sigma_{\text{len}} \ge 7.0 \\
  8  & \text{if } 5.0 \le \sigma_{\text{len}} < 7.0 \\
  6  & \text{if } 3.5 \le \sigma_{\text{len}} < 5.0 \\
  \max(2, \lfloor 1.5 \cdot \sigma_{\text{len}} \rfloor) & \text{otherwise}
  \end{cases}$$
- **Penalties:** Em-dash overuse (-2).

### M3: Trust & Non-Affordance (1–10)
- **Question:** Does the text respect reader intelligence without hand-holding or hedge defensiveness?
- **Penalties:** Knowledge-cutoff disclaimers (-3), sycophantic cheering (-3), excessive hedging (-2).

### M4: Authenticity & Lexical Purity (1–10)
- **Question:** Is the vocabulary genuine engineering discourse, or statistical AI buzzwords?
- **Penalties:** AI favorite tokens (`delve`, `tapestry`, `beacon`, `testament`, `pivotal`) (-2 each), copula avoidance (`serves as`, `boasts`) (-2 each), rule-of-three triads (-2), curly quotes (-1).

### M5: Density & Conciseness (1–10)
- **Question:** Is every word carrying load, or is there filler fluff?
- **Penalties:** Bloated filler phrases (`in order to`, `due to the fact that`) (-2 each), boldface overuse (-2), inline vertical lists (-2), emojis (-2), passive voice ratio $> 35\%$ (-2).

---

## 2. Substance Dimensions (Max: 30, Floor: 21)

### S1: Empirical Specificity (1–10)
- **Question:** Does the text name concrete numbers, metrics, versions, commit SHAs, or exact file paths?
- **Formula:**
  $$\text{Density} = \frac{\text{Count}(\text{Empirical Tokens})}{\text{Total Words}} \times 100$$
  $$\text{Score} = \begin{cases}
  10 & \text{if Density} \ge 4.0\% \\
  8  & \text{if } 2.5\% \le \text{Density} < 4.0\% \\
  6  & \text{if } 1.0\% \le \text{Density} < 2.5\% \\
  \max(1, \lfloor 4.0 \cdot \text{Density} \rfloor) & \text{otherwise}
  \end{cases}$$
- **Penalties:** Vague attributions ("studies show", "experts agree") (-3).

### S2: Restraint & Sizing (1–10)
- **Question:** Are achievements sized at their actual technical magnitude, or puffed up?
- **Penalties:** Significance inflation (`enduring testament`, `pivotal milestone`) (-3 each), notability puffery (-3), promotional marketing vocabulary (`groundbreaking`, `game-changer`, `seamless`) (-3 each), generic upbeat conclusions (-2).

### S3: Technical Voice & Operational Stakes (1–10)
- **Question:** Does the text articulate an active point of view on failure modes, trade-offs, and breaking boundaries?
- **Criteria:** Presence of explicit technical stakes keywords (`trade-off`, `latency`, `throughput`, `concurrency`, `race`, `memory leak`, `bottleneck`, `rollback`, `breaking`, `timeout`, `retry`, `idempotency`).
  - $\ge 4$ stakes keywords: 10
  - $2-3$ stakes keywords: 8
  - $1$ stakes keyword: 6
  - $0$ stakes keywords: 4
- **Penalties:** Formulaic "Challenges and Outlook" corporate section (-2).

---

## 3. Slop-to-Substance Ratio (SSR)

$$\text{SSR} = \frac{\text{Tells Count} + (\text{Passive Ratio} \times \text{Lines})}{\text{Empirical Tokens} + \text{Stakes Keywords} + 1}$$

- $\text{SSR} \le 0.20$: Pristine engineering prose.
- $0.20 < \text{SSR} \le 0.50$: Acceptable technical discourse.
- $0.50 < \text{SSR} \le 1.00$: Borderline; requires targeted cleanup.
- $\text{SSR} > 1.00$: Slop dominant; rejected.

---

## 4. Diagnostic State Matrix

| Mechanics | Substance | Vector | Verdict | Action Required |
| :---: | :---: | :--- | :---: | :--- |
| $\ge 35$ | $\ge 21$ | `clean` | **`PROCEED`** | None. Text meets all substance and mechanics invariants. |
| $\ge 35$ | $< 21$ | `flattened` | **`REVISE_SUBSTANCE`** | Clean but soulless. Inject empirical measurements, commit SHAs, and operational trade-offs. |
| $< 35$ | $\ge 21$ | `inflated` | **`REVISE_MECHANICS`** | Substance present but slop-shaped. Scrub catalog tells, eliminate copula avoidance, and break participle chains. |
| $< 35$ | $< 21$ | `mixed` | **`REFUSE`** | Both mechanics and substance failed. Clean-room rewrite required. |
