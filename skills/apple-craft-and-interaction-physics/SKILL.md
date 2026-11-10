---
name: apple-craft-and-interaction-physics
description: Enforces Apple Human Interface Guidelines (HIG) craft, Design Engineering, and 60/120Hz Interaction Physics across web, mobile, and desktop interfaces. Mandates Exhaustive UI State Matrices (loading skeleton, empty, partial error, offline, optimistic rollback), Zero Cumulative Layout Shift (CLS = 0.000 via strict geometry pre-reservation), Interruptible Spring Physics with velocity continuity, Keyboard and Focus Ring Mastery, and 120Hz compositor budgeting. Use when designing, building, refactoring, or auditing interactive UI components, animations, transitions, state machines, gesture handlers, modals, forms, or rendering pipelines — even if the user does not explicitly say "Apple HIG" or "interaction physics". Do NOT use for headless backend-only services, database DDL migrations, or non-interactive CLI batch scripts.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Apple Craft & Interaction Physics (Apple HIG & Design Engineering)

> Anti-slop engineering stops an interface from looking broken; Apple interaction physics and design engineering make an interface feel physical, inevitable, and effortlessly alive at 120Hz.

## Why This Skill Is Needed & Target State

Baseline UI hygiene prevents overt visual slop—stripping developer debug notes from the DOM, removing fake disclaimer banners, and decluttering crowded navbars. However, an interface can pass baseline linting and still feel sluggish, brittle, and amateurish in production. AI coding agents routinely generate UI code that suffers from five fatal interaction defects:
1. **Combinatorial Boolean Soup & State Amnesia:** Managing asynchronous states with loose booleans (`isLoading`, `isError`, `isSubmitted`) creating $2^N$ implicit states, crashing when offline, dropping typed input drafts on network failure, or presenting blank screens instead of actionable empty states.
2. **Cumulative Layout Shift (CLS > 0):** Injecting unreserved async DOM blocks, unsized images, and sudden error banners that violently jostle surrounding content and trigger mis-clicks.
3. **Locked-In, Non-Interruptible Animations:** Applying rigid duration-based transitions (`transition: all 400ms ease`) that lock the interface into canned playback, ignoring mid-flight pointer changes, freezing gestures, and lagging behind the user's intent.
4. **Keyboard & Focus Neglect:** Stripping focus rings with `outline: none`, creating keyboard traps, ignoring dialog focus trapping/restoration, and omitting ARIA live regions for screen readers.
5. **Frame Budget Thrashing:** Interleaving layout reads and DOM writes, animating reflow properties (`height`, `top`, `width`), and blocking the main thread with synchronous JSON parsing during active render frames.

The target state is **Apple HIG Craft & Design Engineering Physics**:
- **Exhaustive UI State Matrix:** Every view is an explicit Discriminated Union State Machine handling all 8 operational states (`loading_skeleton`, `empty`, `partial_error`, `offline`, `optimistic_rollback`, `loaded_fresh`, `revalidating_stale`, and `terminal_error`) with compile-time exhaustiveness.
- **Strict Zero Cumulative Layout Shift (`CLS = 0.000`):** Pixel-matched skeleton geometry, media `aspect-ratio` locks, reserved validation error tracks, and `scrollbar-gutter: stable`.
- **Interruptible Spring Physics:** Physically grounded mass-spring-damper motion ($F = -kx - cv$) with instantaneous gesture interruption, continuous velocity inheritance ($v_0$), compositor-only execution (`transform`, `opacity`), and epsilon-terminated convergence ($\epsilon \le 10^{-4}$).
- **Keyboard & Focus Mastery:** Flawless keyboard operability, high-contrast `:focus-visible` rings with offset, strict dialog focus trapping and return restoration, roving tabindex for composite controls, and polite ARIA announcements.
- **ProMotion 120Hz Frame Budget:** Sub-4ms JavaScript execution per frame, zero layout thrashing, and offloading heavy tasks off the main thread.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Building or refactoring interactive UI views, lists, forms, or dashboards | Enforce Discriminated Union State Machines, pixel-matched skeletons (`CLS = 0`), and sub-50ms Optimistic UI with rollback snapshots |
| Authoring animations, transitions, drag gestures, sheets, or scroll effects | Restrict to compositor properties (`transform`, `opacity`), enforce interruptible spring physics with velocity continuity, and epsilon-terminated `rAF` |
| Designing keyboard navigation, focus management, overlays, or modals | Enforce `:focus-visible` rings (never bare `outline: none`), `role="dialog"`, `aria-modal="true"`, focus trap, and focus restoration to trigger |
| Handling large client datasets, local persistence, or real-time streams | Offload heavy JSON parsing and filtering off the Main Thread via Web Workers or chunk with `scheduler.yield()` |
| Auditing frontend PRs, Lighthouse traces, or janky interactions | Run the Apple Craft Interrogation Matrix and `scripts/apple_craft_guard.py` |
| Headless backend workers, database DDL migrations, or CLI batch scripts | Do not activate; route to `paranoid-principal-architect` or `zero-downtime-migration-gate` |

---

## The Four Physical Pillars & Absolute Laws

### 1. The Exhaustive UI State Matrix Law (حظر تسليم أي شاشة بدون تغطية الحالات)
Never deliver any screen, async container, or interactive mutation without explicitly modeling and designing all required operational states:
- **`loading_skeleton`:** Render a pixel-matched skeleton whose outer dimensions, padding, and layout tracks match the resolved state to the exact pixel (`CLS = 0`).
- **`empty`:** A first-class zero-state with clear contextual guidance and a prominent, actionable CTA (never a blank void or generic "No items").
- **`partial_error`:** Isolate sub-region component failures with an inline retry affordance; secondary component failures must NEVER crash or blank the primary screen.
- **`offline`:** Surface a non-intrusive offline indicator, preserve cached content for reading, and queue non-destructive mutations locally.
- **`optimistic_rollback`:** Instantaneous visual feedback (< 16ms) and optimistic state transition (< 50ms) backed by an immutable rollback snapshot (`previousStateSnapshot`); if the server rejects, gracefully revert and restore the user's exact draft text into the active input.
- **`loaded_fresh`:** Canonical populated interactive state.
- **`revalidating_stale`:** Keep existing data fully interactive on screen while displaying a subtle, non-blocking refresh indicator (never flash full-screen loaders during background sync).
- **`terminal_error`:** Full-screen or modal failure with actionable recovery options, retry button, and clear incident correlation tokens.
- **Compile-Time Exhaustiveness:** Banish combinatorial booleans (`isLoading`, `isError`). Model states as a Discriminated Union with a tag (`status`). Enforce `assertNever(state)` in the default branch of every state switch.

### 2. The Zero Layout Shift Law (`CLS = 0.000` & Geometry Pre-Reservation)
Dynamic content, images, and streaming data must NEVER shift surrounding interactive elements:
- Pre-reserve geometry for all dynamic elements: declare explicit `aspect-ratio` or `width` and `height` attributes on all `<img>`, `<video>`, `<canvas>`, and `<svg>` elements.
- Pre-allocate dedicated layout tracks for validation error messages and status alerts so errors overlay or expand within reserved space without pushing form inputs downward.
- Enforce `scrollbar-gutter: stable` on scrollable containers to eliminate horizontal layout jarring when scrollbars appear or disappear.
- Prevent font-swap layout shift using `font-display: optional` or CSS font metric overrides (`size-adjust`, `ascent-override`, `descent-override`).

### 3. The Interruptible Physics & Velocity Continuity Law
Physical objects in the real world have mass and momentum—they do not reset to zero velocity or refuse new input while in motion:
- **Instant Interruption:** Every animation and transition must be immediately interruptible at any point in its timeline by user input (pointer down, swipe, click, key press). Never lock interaction behind animation duration queues.
- **Velocity Inheritance:** When a motion is interrupted mid-flight, the new trajectory must inherit the instantaneous velocity ($v_0$) of the interrupted motion ($F = -kx - cv$). Snapping to 0 velocity or jumping to target geometry is a physical defect.
- **Banning `transition: all`:** Explicitly declare animated compositor properties (`transition: transform ...`). Never use `transition: all`, which captures layout properties during responsive resizes.
- **Compositor-Only Properties:** Animate strictly GPU-composited properties: `transform` (`translate3d`, `scale`, `rotate`) and `opacity`. Animating `height`, `width`, `top`, `left`, `margin`, `padding`, or `border-width` triggers document reflow and is strictly prohibited.
- **Epsilon Convergence:** Spring calculations and `requestAnimationFrame` loops must check convergence ($\epsilon \le 10^{-4}$) and immediately call `cancelAnimationFrame(handle)` when $|\text{current} - \text{target}| < \epsilon$ and $|\text{velocity}| < \epsilon$.
- **Respect Motion Preferences:** Honor `@media (prefers-reduced-motion: reduce)` by immediately completing animations or degrading to instant opacity cross-fades.

### 4. The Keyboard & Focus Mastery Law (لوحة المفاتيح والـ Screen Readers)
An interface is incomplete until it can be driven swiftly and cleanly with a keyboard alone:
- **Focus Ring Discipline:** Never suppress focus outlines (`outline: none`, `outline: 0`) without providing an explicit, high-contrast replacement. Enforce `:focus-visible` styling with a minimum 3:1 contrast ratio against the background, at least a 2px stroke, and `outline-offset: 2px` so the ring is never clipped.
- **Modal & Drawer Focus Trapping & Restoration:** Every slide-out drawer, bottom sheet, and modal dialog must declare `role="dialog"` and `aria-modal="true"`, trap `Tab` and `Shift+Tab` cycles inside the container, and programmatically restore focus to the trigger element that opened it upon dismissal (`Escape` or close button).
- **Roving Tabindex for Composite Controls:** Composite widgets (toolbars, segmented controls, tablists, menus, data grids) must implement the Roving Tabindex pattern (`tabIndex={isActive ? 0 : -1}`) with Arrow-key navigation to eliminate tab-stop exhaustion.
- **Screen Reader Semantics & ARIA Live Regions:** Surface dynamic state changes and toast notifications via `aria-live="polite"` or `role="status"`. Declare `aria-busy="true"` on containers undergoing async updates. Provide explicit accessible names (`aria-label` or visually hidden text) for all icon buttons.

### 5. The ProMotion 120Hz Frame Budget Law (8.33ms Physics)
- On a 120Hz display, each frame must complete within `8.33ms` (`16.67ms` at 60Hz). JavaScript execution must consume **`< 4ms`** per frame to reserve headroom for browser styling, layout, and compositing.
- **Zero Layout Thrashing:** Never interleave DOM style mutations and layout reads (`getBoundingClientRect()`, `offsetWidth`, `offsetHeight`, `scrollTop`). Batch all layout reads first, then execute style mutations in `requestAnimationFrame`.
- **Zero Main-Thread Blocking:** Never execute synchronous `JSON.parse`/`JSON.stringify`, `localStorage` I/O, or heavy sorting over large arrays inside input, render, or scroll handlers. Offload to Web Workers or slice with `scheduler.yield()`.
- **Touch Device Native Inertia:** Never apply programmatic scroll hijacking or custom wheel smoothing to touch devices. Gate momentum scroll engines behind `!window.matchMedia('(pointer: coarse)').matches && window.innerWidth >= 768`.

---

## Invariant Rules

1. **Ban bare `outline: none`.** Any removal of default focus outlines must be accompanied by an explicit, accessible `:focus-visible` ring declaring `outline: 2px solid <color>` and `outline-offset: 2px`.
2. **Ban `transition: all`.** Explicitly enumerate animated compositor properties (`transform`, `opacity`).
3. **No unreserved dynamic DOM injection.** All async containers, skeletons, dynamic images, and error slots must declare reserved bounding boxes matching their resolved dimensions.
4. **Preserve user drafts across optimistic rollbacks.** If a server mutation fails, restoring the prior state snapshot MUST retain the user's typed input inside the composer or form field.
5. **Passive event listeners for scroll and touch.** Listeners for `scroll`, `wheel`, `touchstart`, and `touchmove` that do not invoke `preventDefault()` must specify `{ passive: true }`.
6. **Zero synchronous layout thrashing.** Read all geometry before writing styles. Use `FastDOM` patterns or `ResizeObserver`/`IntersectionObserver` for geometric tracking.
7. **Cancelable physics loops.** Every physics animation loop must be cancelable on pointerdown/drag and must terminate with $\epsilon \le 10^{-4}$.
8. **Enforce compile-time exhaustiveness checking.** All UI state switches must include `const _exhaustive: never = state;`.
9. **Minimum 44x44px touch targets.** All interactive controls must provide at least a `44x44px` hit target area.
10. **Zero Dev-Notes Leakage in user-facing DOM.** Never render internal debugging strings or placeholder banners into the UI.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Auditing existing UI for jank, layout shift, keyboard traps, or state gaps | [Audit UI Craft](usecases/audit-ui-craft.md) | [Apple Craft Record Contract](references/apple-craft-record-contract.md) |
| Architecting interaction physics, spring transitions, and gestures | [Architect Interaction Physics](usecases/architect-interaction-physics.md) | [Interruptible Spring Physics](references/interruptible-spring-physics.md) |
| Implementing exhaustive state views, zero-CLS skeletons, and rollback | [Implement Exhaustive State View](usecases/implement-exhaustive-state-view.md) | [Exhaustive UI State Matrix](references/exhaustive-ui-state-matrix.md) |
| Mastering keyboard navigation, focus rings, roving tabindex, and ARIA | [Keyboard Focus Mastery](playbooks/keyboard-focus-mastery-playbook.md) | [Keyboard & Focus Mastery](references/keyboard-and-focus-mastery.md) |
| Durable assessment record generation & automated guard execution | [Record Contract](references/apple-craft-record-contract.md) | `scripts/apple_craft_guard.py` |

---

## Mandatory Pre-Render Interrogation Matrix

Before generating or approving any UI component, interaction, or client state flow, interrogate the implementation against these five physical constraints:

- **The State Matrix Completeness Check:** What does this view render in `loading_skeleton`, `empty`, `partial_error`, `offline`, and `optimistic_rollback`? Is state modeled as a Discriminated Union with compile-time exhaustiveness?
- **The Zero-CLS Geometry Check (`CLS = 0.000`):** Do the skeleton dimensions, image aspect ratios, and error message slots match their resolved geometry to the pixel? Does any transition push surrounding siblings by even 1px?
- **The Interruptible Physics Check:** If the user taps, swipes, or presses Escape while this drawer/modal/card is mid-animation, does it respond instantly, or does it finish playing a locked CSS transition? Does the retargeted motion inherit existing velocity ($v_0$)?
- **The Keyboard & Focus Check:** Can this component be operated end-to-end using only `Tab`, Arrow keys, `Enter`, `Space`, and `Escape`? Is there a visible 3:1 contrast focus ring on `:focus-visible`? Is focus trapped and properly restored upon close?
- **The 120Hz Compositor Check (`8.3ms` Budget):** Does any transition touch a layout property (`height`, `width`, `top`, `left`, `margin`)? Is there any synchronous DOM read following a style write? Are all spring physics loops terminated with $\epsilon \le 10^{-4}$?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **`transition: all` or `transition-all` utility classes:** Animates unintended layout properties and causes reflow during responsive resizing.
2. **Bare `outline: none` or `outline: 0`:** Silently strips keyboard focus indicators and leaves keyboard and screen reader users stranded.
3. **Boolean Soup State Management (`isLoading && !isError`):** Independent booleans producing impossible states and white screens.
4. **Non-Compositor Animations:** Animating `height`, `width`, `top`, `left`, `margin`, or `padding` instead of `transform` and `opacity`.
5. **Unreserved Dynamic DOM Injection:** Inserting elements into the flow without allocated slots, causing Cumulative Layout Shift.
6. **Non-Interruptible Canned Transitions:** CSS transitions with fixed duration that ignore user clicks or gesture interruptions.
7. **Synchronous Main-Thread JSON/Storage I/O:** Calling `localStorage.setItem(..., JSON.stringify(...))` inside input or animation loops.
8. **Scroll Hijacking on Touch Devices:** Overriding native iOS/Android momentum scrolling with custom wheel-smoothing scripts.
9. **Modal Without Focus Trap & Restoration:** Dialogs that allow Tab focus to escape into the background and fail to return focus to the trigger element on close.
10. **Full-Screen Loaders on Background Refresh:** Wiping existing visible data when refreshing stale content.

---

## Required Output & Review Workflow

Structure all UI architectural designs, implementations, and reviews through this 3-phase discipline:

1. **Physical & State Pre-Mortem:** Enumerate the 8 UI states, specify the exact geometry reservation locks for Zero CLS, define the interruptible spring parameters ($k, c, m$), and detail the keyboard focus path.
2. **Hardened Implementation:** Emit clean, production-grade, standards-compliant TypeScript/CSS with discriminated unions, compositor-only motion, high-contrast `:focus-visible` rings, dialog focus trapping, and draft preservation.
3. **Physical Verification:** Verify zero layout thrashing, confirm CLS is strictly 0.000, verify keyboard navigation and focus restoration, and test immediate interruption under rapid user interactions.

When a durable architectural record is warranted, save a JSON assessment following the [Apple Craft Record Contract](references/apple-craft-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering apple-craft audit <record.json> --source <component.ts> --json
# or: python3 scripts/apple_craft_guard.py audit <record.json> --source <component.ts> --json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Master index for UI craft, interruptible physics, and state architecture.
- **[Interaction Physics Playbook](playbooks/interaction-physics-playbook.md)**: Mass-spring-damper equations, velocity continuity, and gesture interruption.
- **[UI State Matrix Playbook](playbooks/ui-state-matrix-playbook.md)**: Discriminated unions, optimistic rollback snapshots, and draft preservation.
- **[Zero-CLS Geometry Playbook](playbooks/zero-cls-geometry-playbook.md)**: Skeleton bounding box matching, media aspect ratios, and stable gutters.
- **[Keyboard & Focus Mastery Playbook](playbooks/keyboard-focus-mastery-playbook.md)**: Focus rings, focus trapping, roving tabindex, and ARIA live regions.
- **[Apple Craft Record Contract](references/apple-craft-record-contract.md)**: Schema for persistent assessment records.
- **[Exhaustive UI State Matrix Reference](references/exhaustive-ui-state-matrix.md)**: Comprehensive breakdown of all 8 operational states.
- **[Zero-CLS Geometry Reservation](references/zero-cls-geometry-reservation.md)**: Layout stability formulas and reservation mechanisms.
- **[Interruptible Spring Physics Reference](references/interruptible-spring-physics.md)**: Physics equations and animation cancellation architecture.
- **[Keyboard & Focus Mastery Reference](references/keyboard-and-focus-mastery.md)**: WCAG 2.2 focus appearance, modal trapping, and screen reader tree semantics.
- **[Compositor & Frame Budget Reference](references/frame-budget-and-compositor.md)**: 120Hz/60Hz budgets, FastDOM read/write batching, and Web Worker offloading.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Boolean Soup | Multiple flags (`isLoading`, `isError`); spinner and error show together | Migrate to Discriminated Union with tag `status` and `assertNever` |
| Layout Shift (CLS) | Content jumps when image or error message loads | Add explicit `aspect-ratio` and pre-allocate layout slot |
| Canned Animation Lock | Element continues playing animation after user swipes or taps away | Replace with interruptible spring physics and inherit velocity $v_0$ |
| Focus Ring Erasure | `outline: none` makes active keyboard focus invisible | Apply `:focus-visible` with 3:1 contrast, 2px stroke, and 2px offset |
| Focus Escape | Pressing Tab inside modal moves focus to background page | Wrap in focus trap, lock body scroll, restore focus on dismiss |
| Layout Thrashing | Janky scroll or frame drop; `style.top` followed by `offsetHeight` | Separate reads and writes: read geometry first, mutate via `rAF` |
| Draft Amnesia | User typed long comment; network error empties composer | Preserve draft buffer on rollback; surface localized retry CTA |
| Background Wipeout | Screen goes white or shows full spinner on background refresh | Keep stale data visible interactively; render subtle inline indicator |

---

## Delegated Skills

- `anti-slop-engineering`: Follow core anti-slop guidelines and clean-code principles.
- `mechanical-sympathy-and-perf-gate`: Profile CPU cache lines, memory allocations, and high-throughput execution paths.
- `privacy-and-data-lineage-gate`: Ensure client-side caching and drafts adhere to crypto-shredding and PII data boundaries.
- `api-ergonomics-and-contract-governor`: Align client-side state models with RFC 9457 Problem Details and idempotent API endpoints.

---

## Completion and Limits

The task is complete when:
1. Every screen explicitly models and renders all 8 states in the UI State Matrix.
2. Geometry pre-reservation guarantees Cumulative Layout Shift is strictly 0.000.
3. All animations are interruptible spring physics with continuous velocity inheritance and epsilon termination.
4. The interface is fully navigable via keyboard with compliant `:focus-visible` rings and modal focus trapping/restoration.
5. All transitions execute on the GPU compositor (`transform`, `opacity`) within the 120Hz/60Hz frame budget.
An audit may validly output `refuse` or `pause` if critical interaction physics or accessibility invariants are violated.
