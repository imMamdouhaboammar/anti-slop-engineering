---
name: chromatic-drift-guard
description: Quantify chromatic saturation drift, OKLCH color space adherence, and eliminate AI category reflex traps (cheerful drift, warm-cream bands, purple-blue gradient clichés, dark-mode inertia).
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Chromatic Saturation Drift & OKLCH Reflex Guard

> Quantify color space divergence, eliminate cheerful saturation drift, and break statistical AI color clichés using standard-library CIE OKLCH mathematics.

## Why This Skill Is Needed & Target State

Generative AI models suffer from persistent chromatic biases:
1. **Cheerful Saturation Drift**: Given a muted, analog, or near-monochrome brand direction, models subconsciously generate friendlier, bluer, oversaturated video-game pastels ($\text{Chroma} \gg \text{Target}$).
2. **The Dark-Mode Reflex**: Sliding into near-black backgrounds ($L \approx 0.12$) on 90% of designs without physical scene motivation.
3. **The Warm-Cream Band Trap**: Falling into the warm-cream default band ($L \in [0.84, 0.97], C < 0.06, H \in [40, 100]$) as an unargued reflex for "warmth".
4. **Purple-to-Blue Gradients**: Defaulting to gradients with multiple stops in the $H \in [250, 290]$ band.

The target state is mathematical color discipline: working in CIE OKLCH, adhering to committed background lightness $L_{\text{target}}$ and chroma $C_{\text{target}}$, and requiring written justification for aesthetic choices.

## Invariant Rules

1. **Cheerful Drift Bound:** Actual painted chroma must not exceed committed target chroma by more than $\Delta C = 0.03$ without explicit commit-sheet justification.
2. **Committed Lightness Anchor:** Theme and body background lightness must align with the committed target lightness $L_{\text{target}}$ within $\pm 0.12$ tolerance.
3. **Banned Category Reflex Bands:** Warm-cream default bands and purple-blue gradient defaults are strictly rejected unless accompanied by an explicit `/* auteur-allow: RULE -- reason */` comment.

## Color Math: CIE OKLCH Transformation

$$\text{sRGB} \xrightarrow{\text{Gamma Expansion}} \text{Linear RGB} \xrightarrow{M_1} \text{LMS} \xrightarrow{\sqrt[3]{\cdot}} \text{LMS}' \xrightarrow{M_2} \text{OKLab} \xrightarrow{\text{Polar}} \text{OKLCH}$$

Where Euclidean Chroma is:
$$C = \sqrt{a^2 + b^2}, \quad H = \text{atan2}(b, a) \pmod{360^\circ}$$

## CLI Usage

```bash
# Scan directory for chromatic drift and reflex band violations
bunx anti-slop-engineering chroma-drift --scan src/ --target-l 0.55 --target-c 0.04

# Evaluate single hex or oklch color string
bunx anti-slop-engineering chroma-drift --color "#7b6b63"

# Validate pre-existing chroma report JSON
bunx anti-slop-engineering chroma-drift --file .anti-slop/chroma.json --strict
```
