---
name: ui-and-copy-discipline
description: "Frontend UI craftsmanship, typography, layout, copywriting, and WCAG 2.2 accessibility discipline. Enforces the 5 Craftsmanship Standards, Purpose Gates, and zero AI slop in web interfaces and marketing copy."
author: "Mamdouh Aboammar <mamdouhfces1997@gmail.com>"
license: "MIT"
metadata:
  version: "1.6.0"
  focus: "frontend-craftsmanship"
---

# UI & Copywriting Discipline

> Enforce the 5 Craftsmanship Standards, Purpose Gates, and human accessibility across all user interfaces, components, and marketing prose.

---

## 1. The Core Purpose Test

Before introducing any visual technique (gradient, backdrop-filter, border radius, box shadow, transition), answer:
**What specific user or hierarchy goal does this technique serve?**

If the answer is "it looks like an AI default", "it makes the hero pop", or "it feels safe", the technique MUST be rejected or rewritten.
If the answer identifies a distinct hierarchy elevation, interactive feedback, or content clarity, it stays.

---

## 2. The 5 Craftsmanship Standards (C-1 to C-5)

### C-1: Intentionality
Every visual and textual element must have a deliberate rationale. Never use default blue-to-purple gradients (`from-blue-500 to-purple-500`), ambient multi-layered blurred shadows, or generic hero radial glows without product design tokens.

### C-2: Functional Completeness
Every interactive element works or it does not exist. A button, dropdown, search bar, or tab that renders but cannot execute its action is a defect, not decoration. Never ship non-functional mock UI elements.

### C-3: Content-Driven Composition
Page layout and section order must flow directly from the product's actual domain data and user goals. Ban generic AI landing page templates: hero -> 3 uniform feature cards with icons -> fake testimonial carousel -> pricing grid -> FAQ accordion. Compose bespoke layouts that fit the data.

### C-4: Resilience & Accessibility (WCAG 2.2 AA)
- **Normal Text Contrast:** $\ge 4.5:1$ against adjacent backgrounds.
- **Large Text ($\ge 18\text{pt}$ or $\ge 14\text{pt}$ bold):** $\ge 3.0:1$.
- **UI Components & Graphical Edges:** $\ge 3.0:1$ (WCAG 1.4.11).
- **Touch Targets:** Minimum $44 \times 44\text{px}$ on touch devices.
- **Visible Focus States:** Focus rings must have $\ge 3.0:1$ contrast against both the component and background. Never set `outline: none` without providing an accessible `:focus-visible` replacement.

### C-5: Performance & Motion
- Animations must be hardware-accelerated (`transform`, `opacity` only). Never animate layout properties (`width`, `height`, `margin`, `padding`, `top`, `left`).
- Always respect `prefers-reduced-motion: reduce`.
- Zero unconstrained requestAnimationFrame loops; terminate loops when animation values stabilize within $\epsilon \le 10^{-4}$.

---

## 3. The Three Rule Tiers

### Tier 1: Hard Gates (Absolute Bans)
- **Banned:** Fake or unverified statistics in marketing copy ("Trusted by 10,000+ teams" when fictitious).
- **Banned:** AI buzzword inflation ("Unleash the power of AI", "Revolutionize your workflow", "Next-generation AI-powered platform").
- **Banned:** Unrequested placeholder image/asset creation.
- **Banned:** Decorative separator comments in source code (`// =======================`, `/* ---- ROUTES ---- */`).
- **Banned:** Low-contrast text failing WCAG 2.2 AA standards.
- **Banned:** Dev-notes or mock disclaimers in user-visible DOM/JSX (`"Note: in production this connects to backend"`).

### Tier 2: Purpose Gates (Permitted ONLY with Documented Justification)
- **Gradients:** Permitted only when establishing intentional hierarchy between primary and secondary surfaces.
- **Glassmorphism (`backdrop-filter: blur(...)`):** Dose cap of at most 1–2 elements per viewport (e.g. sticky navigation bar only).
- **Pill Border Radii (`rounded-full`):** Permitted on compact status chips and floating action buttons; banned on text inputs, textareas, and content cards.
- **Micro-Animations:** Permitted when communicating state changes, transitions, or feedback; banned as gratuitous perpetual distraction.

### Tier 3: Quality Locks (Responsive & Mobile Discipline)
- **Content-Driven Breakpoints:** Place responsive breakpoints where content naturally breaks or degrades readability, not based on arbitrary device spec sheets.
- **Mobile-First Layout:** Mobile viewports must be deliberately designed, not desktop layouts forcibly squeezed into narrow widths.
- **Safe Area Insets:** Support iOS/Android display cutouts (`env(safe-area-inset-top)`, `env(safe-area-inset-bottom)`).

---

## 4. Automated Verification Commands

```bash
# Verify color contrast pairing:
bunx anti-slop-engineering contrast "#FFFFFF" "#1E293B"

# Scan workspace stylesheets and components for contrast violations:
bunx anti-slop-engineering contrast --scan src/

# Run full Seven Gates & anti-slop diff check:
bunx anti-slop-engineering check --base HEAD

# Generate comprehensive numbered audit report:
bunx anti-slop-engineering audit
```
