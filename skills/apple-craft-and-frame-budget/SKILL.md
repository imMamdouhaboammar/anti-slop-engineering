---
name: apple-craft-and-frame-budget
description: Enforces Apple Human Interface Guidelines (HIG) craft and 60/120Hz Client Runtime Physics across web, mobile, and desktop interfaces. Use when building, refactoring, or auditing interactive UI components, animations, state management, optimistic mutations, skeleton loaders, scroll/gesture handlers, modals, or client rendering pipelines — even if the user doesn't explicitly say "Apple craft" or "frame budget". Do NOT use for headless backend-only services, SQL schema migrations, or non-interactive CLI scripts.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Apple Craft & Frame Budget (Apple HIG & 60/120Hz Client Runtime Physics)

> Anti-slop UI rules stop an interface from looking broken; Apple runtime physics make an interface feel alive, instantaneous, and physically Inevitable at 120Hz.

## Why This Skill Is Needed & Target State

Baseline UI hygiene in `anti-slop-engineering` prevents visual slop—stripping developer notes from the DOM, decluttering navbars, and banning patronizing microcopy. However, an interface can be visually clean and still feel sluggish, fragile, and amateurish in motion. AI coding agents routinely generate UI components that trigger forced synchronous reflows (Layout Thrashing), animate layout properties (`height`, `top`, `left`), freeze the main thread with synchronous `JSON.parse`/`localStorage` calls, block user clicks behind network spinners, shift layout geometry as payloads resolve (`CLS > 0`), and collapse into impossible states due to combinatorial "Boolean Soup" (`isLoading && !isError && isSubmitted`).

The target state is **Apple Human Interface Guidelines (HIG) Craft & 60/120Hz Client Runtime Physics**:
1. **Strict 16.6ms (60Hz) / 8.3ms (120Hz ProMotion) Frame Budgets:** Zero layout thrashing, GPU-compositor-only animations (`transform`, `opacity`), epsilon-terminated `requestAnimationFrame` loops, and zero main-thread blocking Tasks (`< 50ms` Long Task threshold, `< 4ms` per frame script budget).
2. **Sub-50ms Optimistic UI & Zero Cumulative Layout Shift (`CLS = 0.000`):** Instantaneous visual acknowledgment on every interaction with deterministic rollback snapshots on server failure, paired with pixel-exact skeleton and media geometry reservation.
3. **Explicit Discriminated-Union UI State Machines:** Complete elimination of Boolean Soup in favor of exhaustive state machines covering `Empty`, `Stale`, `Offline`, `Optimistic`, and `Partial Failure` states.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Building or refactoring interactive UI views, lists, forms, or dashboards | Enforce Discriminated Union State Machines, pixel-matched skeletons (`CLS = 0`), and sub-50ms Optimistic UI |
| Authoring animations, transitions, drag gestures, or scroll effects | Restrict to compositor properties (`transform`, `opacity`), enforce epsilon-terminated `rAF`, and gate scroll hijacking off touch devices |
| Handling large client datasets, local persistence, or real-time streams | Offload heavy parsing/filtering/storage off the Main Thread or yield via `< 4ms` frame slices |
| Building slide-out drawers, sheets, dialogs, or overlays | Enforce `role="dialog"`, `aria-modal="true"`, body scroll lock, Tab focus trap, and focus restoration |
| Auditing frontend PRs, Lighthouse/Performance traces, or janky interactions | Run the Frame Budget & State Machine Pre-Mortem and `scripts/frame_budget_guard.py` |
| Headless backend workers, database DDL migrations, or CLI batch scripts | Do not activate; route to `paranoid-principal-architect` or `zero-downtime-migration-gate` |

---

## The Five Absolute Laws

1. **The 16.6ms / 8.3ms Frame Budget Physics Law (60Hz / 120Hz ProMotion):** On a 120Hz ProMotion display, the browser has `8.33ms` per frame (`16.67ms` at 60Hz) to execute JavaScript, recalculate styles, compute layout, paint, and composite. To leave headroom for browser overhead, per-frame JavaScript work must remain under **`4ms`**.
   - **Zero Layout Thrashing:** Never interleave DOM style writes and layout geometry reads (`getBoundingClientRect()`, `offsetWidth`, `offsetHeight`, `clientHeight`, `scrollTop`, `getComputedStyle()`) within the same frame. Batch all geometry reads first (`FastDOM` read phase), then batch all style mutations (`requestAnimationFrame` write phase).
   - **Compositor-Only Motion:** Animate strictly `transform` (`translate3d`, `scale`, `rotate`) and `opacity`. Animating `width`, `height`, `top`, `left`, `margin`, `padding`, or `border-width` triggers full document reflow and paint on every frame and is strictly prohibited. Use FLIP (First, Last, Invert, Play) for layout transitions.
   - **Zero Main-Thread Blocking:** Never execute large `JSON.parse`/`JSON.stringify`, synchronous `localStorage`/`sessionStorage` I/O inside render/scroll/input paths, or $O(N)$ sorting/filtering over $>500$ items on the Main Thread. Offload to Web Workers, IndexedDB async transactions, or chunk work across frames with `scheduler.yield()`.
2. **The Sub-50ms Optimistic UI & Graceful Rollback Law:** Human perception registers delay above `50ms–100ms` as mechanical lag. Every discrete user action (button press, toggle, reorder, like, archive, inline edit) must:
   - Render physical press feedback (`transform: scale(0.97)` or active highlight) within **`< 16ms`** (1 frame).
   - Transition the UI state optimistically within **`< 50ms`** while capturing an immutable rollback snapshot (`previousStateSnapshot`) and attaching a deterministic `Idempotency-Key`.
   - Execute a smooth, non-destructive **Rollback Transition** that restores `previousStateSnapshot`, preserves any user-typed draft input, and surfaces an actionable inline recovery state (`Retry` / `Dismiss`) if the server rejects or times out.
3. **The Zero Cumulative Layout Shift Law (`CLS = 0.000`):** Content must never jump, shift, or push interactive targets while asynchronous data, images, or web fonts stream in.
   - Every async data boundary must render a **pixel-matched skeleton or reserved grid slot** whose outer dimensions (`min-height`, `height`, `aspect-ratio`, padding, border) identically match the resolved state.
   - Every `<img>`, `<video>`, `<canvas>`, and `<svg>` must declare explicit `width` and `height` attributes or CSS `aspect-ratio`.
   - Stale-while-revalidate refreshes and inline validation errors must overlay or occupy pre-allocated layout tracks—never injecting unreserved DOM banners that push the document down.
4. **The Explicit State Machine Law (Zero Boolean Soup):** Combinatorial boolean flags (`const [isLoading, setIsLoading] = useState(false); const [isError, setIsError] = useState(false); const [isSubmitted, setIsSubmitted] = useState(false);`) create $2^N$ implicit states, inevitably producing impossible UI states (e.g., spinner and error banner visible simultaneously, or blank white screens when `isLoading` is false but `data` is undefined).
   - Represent every view and async mutation as an explicit **Discriminated Union State Machine** (`status` tag) with exhaustive `switch (state.status)` rendering.
   - Explicitly model and design all real-world operational states: `idle`, `loading_initial`, `loaded_empty`, `loaded_fresh`, `revalidating_stale`, `optimistic_mutating`, `partial_failure`, `offline_queued`, and `terminal_error`.
5. **The Native Hardware & Accessibility Physics Law:**
   - **Epsilon-Terminated `requestAnimationFrame`:** Never leave continuous `requestAnimationFrame` loops running after spring/lerp physics settle. Define a strict convergence threshold ($\epsilon = 10^{-4}$) and call `cancelAnimationFrame(handle)` as soon as $|\text{current} - \text{target}| < \epsilon$ and $|\text{velocity}| < \epsilon$.
   - **Touch Device Native Inertia:** Never apply programmatic scroll hijacking or wheel-smoothing engines to touch devices. Gate all custom momentum scroll engines behind `!window.matchMedia('(pointer: coarse)').matches && window.innerWidth >= 768`.
   - **Modal & Drawer Dialog Physics:** All slide-out drawers, sheets, and modals must declare `role="dialog"` and `aria-modal="true"`, lock `document.body` scroll without horizontal scrollbar shift (`scrollbar-gutter: stable`), trap `Tab` / `Shift+Tab` focus inside the active container, and restore focus to the exact trigger element upon close (`Escape` or dismiss).

---

## Invariant Rules

1. **Ban `transition: all`.** Always enumerate explicit compositor properties (`transition: transform 200ms cubic-bezier(0.22, 1, 0.36, 1), opacity 150ms ease-out`). `transition: all` accidentally animates layout properties (`height`, `padding`, `margin`) during responsive resizes and state changes.
2. **Enforce Read-Before-Write DOM discipline.** If a component must measure DOM geometry (`getBoundingClientRect`, `offsetWidth`), perform all measurements before mutating `element.style`, `classList`, or DOM nodes, or isolate geometry tracking inside `ResizeObserver` / `IntersectionObserver` callbacks rather than `scroll` or `mousemove` listeners.
3. **Passive event listeners for scroll and touch.** All `scroll`, `wheel`, `touchstart`, and `touchmove` listeners that do not call `preventDefault()` must pass `{ passive: true }` so the browser compositor thread never blocks waiting on the JS main thread.
4. **Never wipe existing screen data during background revalidation.** Transitioning from `loaded_fresh` to `revalidating_stale` must keep the existing data interactive on screen while showing a subtle, non-blocking refresh indicator—never replacing already-loaded content with a full-screen spinner or skeleton.
5. **Preserve user drafts across optimistic rollbacks and network failures.** If a form submission or comment post fails, rolling back the optimistic item must restore the user's exact input text back into the composer field so zero keystrokes are lost.
6. **Degrade gracefully under `partial_failure`.** When a composite view fetches multiple data sources (e.g., primary document + activity sidebar + recommendations) and a secondary source fails, transition to `partial_failure`: render the primary content normally and isolate the retry affordance strictly inside the failed sub-region.
7. **Queue or guard mutations when `offline_queued`.** Listen to `navigator.onLine` / `online` / `offline` events and network transport errors; transition mutations to an explicit `offline_queued` state or disable destructive server-only actions with clear status rather than throwing unhandled promise rejections.
8. **Enforce exhaustiveness checking (`assertNever`) on UI state machines.** Every view state switch statement must include a `default` branch assigning `const _exhaustive: never = state;` so TypeScript fails compilation the instant a new state variant is added without a UI renderer.
9. **Honor `prefers-reduced-motion: reduce` and `44x44px` hit targets.** Every interactive control must maintain at least a `44x44px` (`2.75rem`) touch target area, and all spatial spring/slide animations must degrade to instant or opacity-only cross-fades when `@media (prefers-reduced-motion: reduce)` is active.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Auditing or fixing UI jank, frame drops, scroll stutter, or main-thread stalls | [Audit Frame Budget](usecases/audit-frame-budget.md) | [Compositor & Frame Budget Physics](references/compositor-and-frame-budget.md) |
| Implementing instant interactions, optimistic mutations, rollback paths, and zero-CLS skeletons | [Implement Optimistic & Zero-CLS UI](usecases/implement-optimistic-zero-cls.md) | [Optimistic UI & Zero CLS](references/optimistic-ui-and-zero-cls.md) |
| Replacing Boolean Soup with exhaustive Discriminated Union State Machines | [Architect UI State Machine](usecases/architect-ui-state-machine.md) | [Discriminated Union State Machines](references/discriminated-union-state-machines.md) |
| Durable frame-budget & UI craft assessment record generation & audit | [Record Contract](references/frame-budget-record-contract.md) | `scripts/frame_budget_guard.py` |

---

## Mandatory Pre-Render Interrogation Matrix

Before generating or approving any UI component, animation, or client state flow, interrogate the design against these five physical constraints:

- **The 120Hz Compositor Check (`8.3ms` Budget):** Does this interaction read any layout metric (`offsetWidth`, `getBoundingClientRect`, `scrollTop`) after mutating the DOM? Does any CSS transition touch a non-compositor property (`height`, `width`, `top`, `left`, `margin`, `filter: blur()` without layer bounds)? Does any `requestAnimationFrame` loop lack an epsilon ($\epsilon = 10^{-4}$) termination check?
- **The Main-Thread Stall Check:** What happens if the payload contains 5,000 rows or a 2MB JSON blob? Are we running `.filter().sort()`, `JSON.parse()`, or `localStorage.setItem()` synchronously during user input or scroll frames instead of debouncing, virtualizing, or offloading to a Web Worker?
- **The Sub-50ms Optimistic & Rollback Check:** When the user clicks this button on a 400ms 3G connection, what happens in the first `16ms` and the first `50ms`? If the server returns `HTTP 409` or `HTTP 500` 600ms later, do we have the exact prior state snapshot to roll back cleanly without losing the user's draft input?
- **The Zero-CLS Geometry Check (`CLS = 0.000`):** Compare the bounding-box height and width of the `loading_initial` skeleton, the `loaded_empty` zero-state, the `loaded_fresh` populated view, and any inline error banner. Does any transition shift surrounding siblings by even `1px`?
- **The State Machine Exhaustiveness Check:** Have we eliminated all loose boolean flags (`isLoading`, `isError`, `isSuccess`)? How does the discriminated union explicitly render `loaded_empty`, `revalidating_stale`, `partial_failure`, and `offline_queued`?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Boolean Soup State Modeling:** Using 2 or more independent boolean state flags (`isLoading`, `isError`, `isSuccess`, `isFetching`, `isSubmitted`) to control view rendering instead of a discriminated union `status` field.
2. **Layout Thrashing (Interleaved DOM Write -> Read):** Mutating `el.style.*` or `classList` and subsequently reading `el.offsetHeight`, `el.offsetWidth`, `el.getBoundingClientRect()`, or `window.scrollY` inside a loop or synchronous frame handler.
3. **Non-Compositor CSS Animations & `transition: all`:** Using `transition: all` or animating `width`, `height`, `top`, `left`, `right`, `bottom`, `margin`, or `padding` on interactive elements.
4. **Infinite Unterminated `requestAnimationFrame` Loops:** Scheduling `requestAnimationFrame(tick)` unconditionally without checking whether $|\text{current} - \text{target}| < \epsilon$ (`1e-4`) and canceling the animation handle.
5. **Unreserved Async Geometry (`CLS > 0`):** Rendering `if (loading) return <Spinner />` with a `24px` spinner that jumps to a `640px` table on resolve, or rendering `<img>` tags without explicit `width`/`height` or `aspect-ratio`.
6. **Pessimistic Blocking Mutations Without Rollback:** Freezing a form or toggle behind a blocking spinner for a routine mutation without optimistic projection, or mutating optimistic state without storing a rollback snapshot (`previousSnapshot`) for error recovery.
7. **Touch Scroll Hijacking:** Running custom wheel/momentum scroll jacking on mobile/touch viewports without gating behind `!window.matchMedia('(pointer: coarse)').matches && window.innerWidth >= 768`.
8. **Inaccessible Modals/Drawers:** Rendering custom modals or slide-over drawers lacking `role="dialog"`, `aria-modal="true"`, body scroll lock, Tab focus trapping, or focus return on close.

---

## Required Output & Review Workflow

Structure all UI architecture designs, component implementations, and frontend performance reviews through this 4-phase discipline:

1. **Frame-Budget & CLS Pre-Mortem:** Audit the target interaction against the `8.3ms` (120Hz) / `16.6ms` (60Hz) frame budget, identifying potential layout-thrashing read/write cycles, main-thread blocking calls, and layout shift vectors (`CLS`).
2. **Explicit Discriminated-Union State Machine Definition:** Define the complete TypeScript discriminated union (`State`) and event union (`Event`), explicitly covering `idle`, `loading_initial`, `loaded_empty`, `loaded_fresh`, `revalidating_stale`, `optimistic_mutating` (with `rollbackSnapshot`), `partial_failure`, `offline_queued`, and `terminal_error`.
3. **Apple-Craft Implementation (Compositor Motion + Optimistic UI + Zero-CLS):** Emit clean, standards-compliant code with GPU-compositor transitions (`transform`, `opacity`), epsilon-gated `rAF` loops, touch-safe scroll gates, accessible dialog focus traps, and pixel-matched skeleton geometry.
4. **Runtime Physics & Falsification Verification:** Verify that every state transition is deterministic, server rejection cleanly restores the rollback snapshot without data loss, exhaustive switch checking holds, and `scripts/frame_budget_guard.py` reports zero findings.

When a durable UI craft and frame-budget record is warranted, save a JSON assessment following the [Frame Budget Record Contract](references/frame-budget-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering frame-budget audit <record.json> --json
# or: python3 scripts/frame_budget_guard.py audit <record.json> [--source <component.tsx>] --json
```

---

## Domain References

- **[Apple Craft & Frame Budget Playbook Suite](playbooks/README.md)**: Central orchestration index for 60/120Hz runtime physics, optimistic UI, and state-machine architecture.
- **[60/120Hz Frame Budget & Compositor Physics Playbook](playbooks/frame-budget-physics-playbook.md)**: Browser rendering pipeline mechanics, FastDOM read/write batching, FLIP layout animations, epsilon-terminated springs, touch inertia gates, and Web Worker offloading.
- **[Optimistic UI, Zero-CLS & Discriminated State Machines Playbook](playbooks/optimistic-state-machine-playbook.md)**: Sub-50ms optimistic mutations, rollback snapshot choreography, pixel-exact skeleton reservation, and exhaustive union reducers.
- **[Compositor & Frame Budget Reference](references/compositor-and-frame-budget.md)**: Exact 16.6ms/8.3ms budget breakdowns, DOM properties that trigger layout/paint vs compositor, and main-thread time-slicing patterns.
- **[Optimistic UI & Zero-CLS Reference](references/optimistic-ui-and-zero-cls.md)**: Snapshot-mutate-reconcile-rollback patterns, idempotency keys, skeleton geometry parity, and font/image CLS locks.
- **[Discriminated Union State Machines Reference](references/discriminated-union-state-machines.md)**: TypeScript state machine templates replacing Boolean Soup across data fetching, forms, offline queues, and partial failures.
- **[Frame Budget Record Contract](references/frame-budget-record-contract.md)**: JSON schema and verification rules for `scripts/frame_budget_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Layout thrashing jank | Frame drops (`> 16.6ms`) during scroll, resize, or list animation | Separate all `getBoundingClientRect`/`offset*` reads before any `style`/`classList` writes; use `transform` |
| Paint storm on animation | High GPU/CPU paint time while animating drawer or accordion | Replace `height`/`left`/`margin` transitions with `transform: translate3d()` / `scaleY()` or FLIP |
| Runaway `rAF` battery drain | CPU stays at 15–30% when UI appears completely stationary | Add epsilon convergence check (`Math.abs(target - current) < 1e-4`) and call `cancelAnimationFrame` |
| Jarring screen jump (`CLS > 0`) | Buttons or text jump downward when API response or image loads | Reserve exact pixel dimensions via `aspect-ratio`, explicit `width`/`height`, and geometry-matched skeletons |
| Dead click / pessimistic lag | User clicks action button and nothing visually happens for 300ms | Add `< 16ms` active press transform and `< 50ms` optimistic state projection with rollback snapshot |
| Destructive rollback amnesia | Failed post/edit rolls back UI and deletes the text the user typed | Restore failed mutation payload directly into the draft input state on rollback |
| Boolean Soup impossible state | Spinner and error message (or empty state and data list) render at once | Refactor loose `isLoading`/`isError` booleans into a single discriminated union `status` switch |
| Touch scroll hijacking | Mobile Safari/Chrome scrolling feels sticky, delayed, or unnatural | Gate custom smooth-scroll engines behind `!window.matchMedia('(pointer: coarse)').matches && window.innerWidth >= 768` |

---

## Delegated Skills

- `anti-slop-engineering`: Enforce parent UI hygiene (zero dev-notes leakage in DOM, visual restraint, zero patronizing microcopy, and Direct Payload Invariant).
- `paranoid-principal-architect`: Pair optimistic UI mutations with server-side `Idempotency-Key` deduplication, `AbortSignal.timeout()`, and data-layer authorization checks.
- `scientific-fault-isolation`: Use deterministic barrier latches and virtualized clocks when testing out-of-order optimistic mutation responses and race rollbacks.

---

## Completion and Limits

The task is complete when all animations and frame loops respect the 16.6ms/8.3ms compositor budget without layout thrashing, continuous `rAF` loops terminate at epsilon (`1e-4`), touch devices retain native scroll inertia, modals enforce dialog ARIA and focus physics, interactive mutations provide sub-50ms optimistic feedback with verified rollback snapshots, async boundaries reserve exact pixel geometry (`CLS = 0.000`), and UI state is modeled as an exhaustive discriminated union with zero Boolean Soup. A review may validly output `refuse` or `pause` if a proposed UI implementation relies on layout-thrashing animations, unreserved layout shifts, or unguarded boolean state flags.
