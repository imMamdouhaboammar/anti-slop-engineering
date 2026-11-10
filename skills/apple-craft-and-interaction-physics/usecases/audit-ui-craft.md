# Use Case: Audit UI Craft & Interaction Physics

## When to Use
Use when reviewing a pull request, auditing an existing interactive component, or troubleshooting visual jank, layout jumps (CLS > 0), keyboard traps, missing empty/error states, or sluggish non-interruptible animations.

---

## 4-Step Audit Procedure

### 1. State Matrix Audit
- Inspect the component state variables.
- Are there loose booleans (`isLoading`, `isError`, `isSuccess`)?
- Does the view explicitly handle all 8 states (`loading_skeleton`, `empty`, `partial_error`, `offline`, `optimistic_rollback`, `loaded_fresh`, `revalidating_stale`, `terminal_error`)?
- If a server mutation fails, does the component preserve the user's typed draft, or does it discard input?

### 2. Layout Stability (CLS) Audit
- Check bounding boxes of skeleton loaders versus loaded data. Are the dimensions identical?
- Are images declared with explicit `aspect-ratio` or `width`/`height`?
- Do form validation error messages pop in and push the form downward, or do they occupy a pre-reserved track?
- Is `scrollbar-gutter: stable` configured on scroll containers?

### 3. Interaction Physics Audit
- Check animated CSS properties: are there any instances of `transition: all`?
- Are non-compositor properties (`height`, `width`, `top`, `left`, `margin`, `padding`) being animated?
- Can animations be interrupted mid-flight by pointer down or swipe?
- Does the retargeted motion inherit instantaneous velocity ($v_0$) or does it snap?
- Is there an epsilon termination check ($\epsilon \le 10^{-4}$) on spring/rAF loops?

### 4. Keyboard & Screen Reader Audit
- Is there any bare `outline: none` without an accessible `:focus-visible` replacement?
- Does `:focus-visible` declare a 3:1 contrast ratio, 2px stroke, and 2px offset?
- In modals and drawers, is Tab focus trapped, and is focus restored to the trigger on Escape?
- Do composite widgets use Roving Tabindex?
- Are dynamic status changes announced via `aria-live="polite"`?

---

## Automated Guard Audit
Run the automated verification script:
```bash
npx anti-slop-engineering apple-craft audit <record.json> --source <component.ts> --json
```
