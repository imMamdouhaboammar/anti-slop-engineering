# Repository Voice Calibration & Ground-Truth Profiling

> Calibrating AI Discourse to the Authentic Human Voice of the Codebase Rather Than Generic Model Defaults.

---

## 1. The Voice Drift Problem

When different developers and AI assistants contribute to a codebase, documentation and PR descriptions drift into either:
1. Bland ChatGPT Corporate Tone (polite, padded, repetitive).
2. Fragmented Staccato (clipped, subjectless notes without context).

Real, mature open-source repositories have a distinct engineering voice:
- Senior engineers use direct subject-verb constructions ("We added X because Y failed under Z load").
- They state concrete file paths and benchmark numbers.
- They acknowledge trade-offs honestly without sales puffery.

Tagore Voice Calibration measures the authentic human voice of your repository and establishes a baseline profile against which future AI drafts are calibrated.

---

## 2. Statistical Voice Metrics

A repository Voice Profile measures 8 linguistic attributes:

| Metric | Target / Typical Senior Range | Description |
| :--- | :---: | :--- |
| `mean_sentence_length` | $12.0 - 22.0$ words | Prevents both breathless run-on sentences and overly fragmented telegraphic copy. |
| `sentence_length_stddev` | $\ge 5.0$ words | Measures rhythmic variety. A low standard deviation ($< 3.0$) indicates robotic, metronomic cadence. |
| `passive_voice_ratio` | $\le 15.0\%$ | Measures active subject agency. |
| `empirical_token_ratio` | $\ge 3.5\%$ | Density of concrete numbers, units, paths, and commit hashes. |
| `comma_density_per_100w` | $4.0 - 8.0$ | Natural clausal punctuation without comma splices. |
| `semicolon_density_per_100w` | $\le 1.0$ | Semicolons used sparingly for closely linked engineering clauses. |
| `dash_density_per_100w` | $\le 1.0$ | Strictly bounds em-dash and hyphen crutches. |
| `type_token_ratio` (TTR) | $0.40 - 0.60$ | Lexical diversity without artificial synonym cycling. |

---

## 3. The Voice Profile Record (`.anti-slop/voice-profile.json`)

```json
{
  "word_count": 3396,
  "mean_sentence_length": 18.5,
  "sentence_length_stddev": 7.42,
  "passive_voice_ratio": 0.082,
  "empirical_token_ratio": 0.048,
  "comma_density_per_100w": 6.12,
  "semicolon_density_per_100w": 0.25,
  "dash_density_per_100w": 0.65,
  "type_token_ratio": 0.514
}
```

---

## 4. Calibration Workflow

### Step 1: Select High-Signal Ground-Truth Source
Choose an authentic document written by the project lead or core maintainer:
- An approved, battle-tested ADR (`docs/adr/ADR-001.md`)
- The repository architectural manifesto or README (`README.md`)
- A curated collection of maintainer git commit messages

### Step 2: Run Calibration Command
```bash
bunx anti-slop-engineering tagore --calibrate docs/adr/ADR-001.md
```

### Step 3: Inspect Calibrated Baseline
```bash
bunx anti-slop-engineering tagore --profile
```

### Step 4: Audit Agent Deliverables Against Baseline
When evaluating PR descriptions, ADRs, or release notes, Tagore checks that the deliverable conforms to the calibrated sentence length distribution and empirical density:
```bash
bunx anti-slop-engineering tagore --file PR_DESCRIPTION.md --json
```
