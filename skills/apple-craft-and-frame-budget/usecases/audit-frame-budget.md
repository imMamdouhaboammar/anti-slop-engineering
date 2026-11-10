# Workflow: Audit 60/120Hz Frame Budget & Eliminate Jank

Use this workflow when diagnosing dropped frames, scroll stutter, input lag (`INP > 50ms`), high CPU usage at idle, or jarring animations in web, mobile, or desktop UIs.

## Step-by-Step Procedure

### 1. Audit DOM Read/Write Interleaving (Layout Thrashing)
1. Search all event handlers (`scroll`, `pointermove`, `resize`), animation callbacks (`requestAnimationFrame`), and lifecycle hooks (`useLayoutEffect`) for layout-reading APIs:
   - `getBoundingClientRect()`, `offsetWidth`, `offsetHeight`, `clientWidth`, `clientHeight`, `scrollTop`, `getComputedStyle()`.
2. Verify that **zero DOM/style mutations** (`style.*`, `classList.*`, `appendChild`, `innerHTML`) occur *before* a layout read within the same synchronous turn or loop.
3. Refactor into strict two-phase execution:
   - **Phase 1 (Read):** Collect all geometric measurements into local variables or a `ResizeObserver` cache.
   - **Phase 2 (Write):** Schedule all `transform` and `opacity` writes inside a single `requestAnimationFrame` callback.

### 2. Purge Non-Compositor Animations & `transition: all`
1. Inspect CSS rules, Tailwind utilities, and JS animation keyframes.
2. Replace every `transition: all` with explicit `transition-property: transform, opacity`.
3. Replace any animation of `width`, `height`, `top`, `left`, `right`, `bottom`, `margin`, or `padding` with:
   - `transform: translate3d(x, y, 0)` for spatial movement.
   - `transform: scale3d(sx, sy, 1)` or the **FLIP** technique for sizing transitions.

### 3. Bound `requestAnimationFrame` Loops & Touch Scroll Physics
1. Inspect every `requestAnimationFrame` recursion. Ensure it terminates via `cancelAnimationFrame(handle)` when `Math.abs(target - current) < 1e-4 && Math.abs(velocity) < 1e-4`.
2. Ensure `scroll`, `wheel`, `touchstart`, and `touchmove` listeners are marked `{ passive: true }` unless actively trapping a horizontal swipe gesture.
3. Gate any custom momentum scroll engine behind `!window.matchMedia('(pointer: coarse)').matches && window.innerWidth >= 768`.

### 4. Evict Heavy Compute & Sync I/O from the Main Thread
1. Remove synchronous `localStorage.getItem`/`setItem` and `JSON.stringify` from render functions, input handlers, and scroll loops.
2. Offload dataset sorting, filtering (`> 500` items), and large JSON parsing to a **Web Worker** or slice into `< 4ms` increments with `scheduler.yield()`.
