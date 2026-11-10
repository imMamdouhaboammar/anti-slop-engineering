# Attention Economy & Scannability Metrics Specification

This document formalizes the mathematical models and empirical thresholds for text shape, scannability, deliverable purity, and blocking-question placement.

---

## 1. Text Shape vs. Vocabulary Models

Traditional readability metrics (Flesch-Kincaid, Gunning Fog, SMOG) compute grades from word length and sentence syllable counts:

$$\text{FKGL} = 0.39 \left(\frac{\text{total words}}{\text{total sentences}}\right) + 11.8 \left(\frac{\text{total syllables}}{\text{total words}}\right) - 15.59$$

**The Fundamental Flaw:** An unbroken, 400-word paragraph composed of simple 4th-grade words scores as "Easy / 4th Grade" under FKGL, yet represents an impenetrable wall of text that readers with ADHD or high cognitive load immediately bounce off of.

Anti-Slop Cognitive Governance measures **Text Geometry & Spatial Anchor Distribution** ($\mathcal{S}$):

### Time-to-Point ($TTP$)
The word offset before the reader encounters the first bold or high-salience anchor:

$$TTP = |\text{words}(\text{text}[0:\text{pos}_{\text{first\_anchor}}])|$$

- **Target:** $TTP \le 20$ words
- **Failure:** $TTP > 40$ words indicates buried bottom-line.

### Maximum Wall Length ($W_{max}$)
The maximum continuous word run within a single paragraph that contains **zero** formatting anchors (no bolding, no list marks, no arrow markers `→`, no code spans):

$$W_{max} = \max_{p \in \text{paras}} \left( |\text{words}(p)| \cdot \mathbb{I}(\text{has\_anchor}(p) = 0) \right)$$

- **Target:** $W_{max} \le 60$ words
- **Blocker:** $W_{max} > 100$ words triggers `ERR_EXCESSIVE_WALL_OF_TEXT`.

### Anchor Density ($\rho_{anchor}$)
The density of visual landing elements per 100 words:

$$\rho_{anchor} = \frac{100 \times (N_{bold} + N_{anchored\_lines})}{N_{words}}$$

- **Target:** $\rho_{anchor} \ge 3.0$ anchors per 100 words.

### Wall Word Fraction ($F_{wall}$)
The proportion of total words located in anchor-free prose paragraphs:

$$F_{wall} = \frac{\sum_{p \in \text{paras}, \neg \text{has\_anchor}(p)} |\text{words}(p)|}{N_{words}}$$

- **Target:** $F_{wall} \le 0.20$ (at least 80% of words sit within anchored or list blocks).

---

## 2. Terminal Blocking-Question Placement Invariant

When an agent needs human confirmation ($Q_{block}$), the placement determines whether the question is seen:

$$\mathcal{B}_{pos} = \begin{cases}
1 & \text{if } Q_{block} \in \text{last\_paragraph}(\text{text}) \land \text{no\_trailing\_prose} \land (\text{flagged}(\text{line}_1) \lor N_{words} < 40) \\
0 & \text{otherwise}
\end{cases}$$

### The Skimmer Invariant:
If $N_{words} \ge 40$, Line 1 must contain a flag keyword matching:
$$\text{Regex}(\backslash b(\text{before I} \mid \text{need} \mid \text{confirm} \mid \text{sign-off} \mid \text{go-ahead} \mid \text{wait} \mid \text{your call})\backslash b) \lor \text{Verdict}(\text{No, Don't, Stop})$$

---

## 3. Deliverable Purity Index ($\mathcal{P}_{deliv}$)

A deliverable $D$ must satisfy:

$$\mathcal{P}_{deliv} = \mathbb{I}(\text{OpenerWrappers}(D) = \emptyset) \land \mathbb{I}(\text{CloserOffers}(D) = \emptyset) \land \mathbb{I}(\text{PreambleLeadIn}(D) = \emptyset)$$

Where:
- $\text{OpenerWrappers}$: `Here is...`, `Below is...`, `Sure!`, `I've drafted...`
- $\text{CloserOffers}$: `Let me know if...`, `Hope this helps!`, `Feel free to...`
- $\text{PreambleLeadIn}$: Lines ending with `:` or `.` immediately preceding markdown blocks.

---

## 4. Working Memory Bounding ($\mathcal{M}_{cap}$)

Based on Miller's Law ($7 \pm 2$ chunks, modern cognitive research: 4-5 chunks for technical working memory):

$$\forall L \in \text{Lists}(\text{text}), \quad |L| \le 5$$

If $|L| > 5$, the list must be decomposed into thematic sub-sections or utilize progressive disclosure.
