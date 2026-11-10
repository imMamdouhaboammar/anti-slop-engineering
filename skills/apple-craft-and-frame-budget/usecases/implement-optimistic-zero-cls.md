# Workflow: Implement Sub-50ms Optimistic UI & Zero-CLS Layout

Use this workflow when implementing user mutations (buttons, toggles, inline edits, form submissions, drag-and-drop reorders) and asynchronous data/media loading boundaries.

## Step-by-Step Procedure

### 1. Lock Layout Geometry for Zero CLS (`CLS = 0.000`)
1. **Measure Resolved Content Bounds:** Determine the exact outer height, grid template, padding, and aspect ratios of the populated component (`loaded_fresh`).
2. **Build Pixel-Matched Skeleton (`loading_initial`):** Construct a skeleton component that occupies the identical bounding box (`min-height`, `height`, `gap`, `border`) and animates shimmer strictly via compositor `opacity` or `transform: translate3d()`.
3. **Lock Media & Font Slots:** Add explicit `width`, `height`, and `aspect-ratio` to all `<img>`/`<video>` elements, pre-allocate a fixed `min-height` track for inline validation/error messages, and set `scrollbar-gutter: stable` on scroll containers.

### 2. Wire Sub-16ms Tactile Press & Sub-50ms Optimistic Projection
1. **Tactile Press (`< 16ms`):** Add pointer/active feedback (`active:scale-[0.97]` or `transform: scale3d(0.97, 0.97, 1)`) using compositor properties.
2. **Snapshot & Optimistic Transition (`< 50ms`):**
   - On action dispatch, synchronously capture `rollbackSnapshot = structuredClone(currentData)` and `preservedDraft = currentInputDraft`.
   - Generate `idempotencyKey = crypto.randomUUID()`.
   - Immediately dispatch `OPTIMISTIC_MUTATE` to update the UI before awaiting `fetch()`.

### 3. Implement Graceful Rollback & Draft Preservation
1. Bind an `AbortSignal.timeout(8000)` to the background network call and pass `Idempotency-Key: idempotencyKey` in the request headers.
2. **If the Server Commits (`2xx`):** Dispatch `MUTATION_COMMIT` with the canonical server record to transition to `loaded_fresh` with zero layout jump.
3. **If the Server Rejects (`4xx`/`5xx`) or Times Out:**
   - Dispatch `MUTATION_ROLLBACK`.
   - Restore `rollbackSnapshot` smoothly (using spring-damped compositor transition).
   - Restore `preservedDraft` back into the input/composer control so the user never re-types lost work.
   - Surface a non-shifting inline retry banner that replays the request with the preserved `idempotencyKey`.
