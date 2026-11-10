# Playbook 2: Sub-50ms Optimistic UI, Zero CLS & Discriminated Union State Machines

A 120Hz frame rate means nothing if clicking a button locks the user behind a 600ms spinner, if incoming data causes the screen to jump under their finger, or if contradictory boolean flags crash the view into an impossible state.

---

## 1. The Sub-50ms Optimistic UI & Deterministic Rollback Protocol

Human visual-tactile coupling expects immediate physical confirmation when touching or clicking a surface:
- **`0ms – 16ms` (Tactile Press Phase):** Active press physics (`:active` or pointer-down `transform: scale(0.97)`) must render on the very next frame.
- **`16ms – 50ms` (Optimistic Projection Phase):** Before the network packet even leaves the client's cell tower, transition the UI state machine into `optimistic_mutating` and render the expected outcome immediately.

### The Four-Step Optimistic Mutation Contract

1. **Capture Immutable Snapshot (`rollbackSnapshot`):** Before mutating local state, store a frozen copy of the authoritative state and the user's raw input draft (`draftInput`).
2. **Generate Client `Idempotency-Key`:** Mint a deterministic key (`crypto.randomUUID()`) so safe retries never duplicate server side effects.
3. **Apply Optimistic State Projection:** Render the updated item immediately with subtle pending metadata (e.g. `syncState: "pending"`).
4. **Reconcile or Roll Back:**
   - **On `2xx` Commit:** Replace the temporary client state with the server's canonical timestamp/version (`loaded_fresh`).
   - **On `4xx`/`5xx`/Timeout:** Transition cleanly back to `rollbackSnapshot`, restore `draftInput` into the composer/form so zero user work is lost, and expose a scoped inline `Retry` / `Dismiss` banner.

---

## 2. Zero Cumulative Layout Shift (`CLS = 0.000`) Geometry Discipline

Cumulative Layout Shift (`CLS`) measures unexpected movement of visible elements after initial render. In Apple-grade interfaces, **target `CLS` is strictly `0.000`**.

### Four Mandatory Geometry Locks

1. **Pixel-Matched Skeletons:** Never render a `24px` spinner in place of a `320px` card grid. The `loading_initial` skeleton must use the exact same CSS Grid/Flexbox container, row heights, gaps, and border widths as `loaded_fresh`.
2. **Intrinsic Media Dimensions:** Every `<img>`, `<video>`, and `<svg>` must specify explicit `width` and `height` HTML attributes or CSS `aspect-ratio: 16 / 9` so the browser allocates the exact bounding box before a single byte of media downloads.
3. **Metric-Matched Web Fonts:** Pair `font-display: optional` or `swap` with `@font-face` metric overrides (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) so fallback system fonts occupy the exact line height and character width of the custom font.
4. **Pre-Allocated Status & Validation Tracks:** Reserve fixed-height slots (`min-height: 1.25rem`) for form field error messages and use overlay/fixed toast tracks or reserved header slots for network status banners so error states never push buttons down the page.

---

## 3. Eliminating Boolean Soup via Discriminated Union State Machines

### Why Boolean Soup Fails

Consider a naive component with 5 boolean hooks:
`isLoading`, `isRefreshing`, `isError`, `isEmpty`, `isOffline`
Five booleans create $2^5 = 32$ possible state combinations, yet only `7–9` are physically valid. In production, race conditions inevitably leave `isLoading === true && isError === true` or `isEmpty === true && data.length > 0`, resulting in flickering skeletons, stacked error banners, or blank screens.

### The Canonical 9-State View Machine

Every data-driven view must be modeled as a single tagged union (`status` discriminator) where invalid field combinations are unrepresentable at the type level:

| State (`status`) | Data Present? | UI Representation |
| --- | --- | --- |
| `idle` | No | Initial Dormant Trigger / Search Prompt |
| `loading_initial` | No | Pixel-Matched Skeleton (`CLS = 0.000`, matches resolved layout geometry) |
| `loaded_empty` | Empty (`[]`) | Purposeful Zero-State with primary creation/filter-reset CTA (same container bounds) |
| `loaded_fresh` | Yes (`T`) | Interactive Primary View |
| `revalidating_stale` | Yes (`T` stale) | Keep `T` 100% visible and interactive; show subtle non-blocking sync indicator |
| `optimistic_mutating` | Yes (`T` optimistic + `rollbackSnapshot: T`) | Render optimistic state immediately (`< 50ms`); rollback cleanly on error |
| `partial_failure` | Yes (`T` primary + `failedPanels[]`) | Render primary `T` normally; show scoped inline retry inside failed sub-panel |
| `offline_queued` | Yes (`T` + `queuedOps[]`) | Render local state + offline badge; queue mutations for background replay |
| `terminal_error` | No | Actionable Error View with error code, correlation ID, and retry button |
