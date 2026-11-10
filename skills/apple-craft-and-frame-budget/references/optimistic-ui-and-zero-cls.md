# Optimistic UI, Rollback Physics & Zero-CLS Reference

---

## 1. Optimistic Mutation Lifecycle & Latency Thresholds

| Phase | Elapsed Window | Mandatory Client Behavior |
| --- | --- | --- |
| **1. Tactile Press** | `0ms – 16ms` | Apply GPU-composited press state (`transform: scale(0.97)` or active surface highlight) |
| **2. Optimistic Commit** | `16ms – 50ms` | Freeze `rollbackSnapshot`, mint `idempotencyKey`, transition state machine to `optimistic_mutating`, clear composer UI while retaining `draftBackup` in state |
| **3. Server Reconcile (`2xx`)** | `50ms – 2000ms` | Replace optimistic entity ID/version with canonical server response (`loaded_fresh`) without layout shift |
| **4. Server Reject / Timeout** | `50ms – 5000ms` | Restore `rollbackSnapshot`, repopulate composer input from `draftBackup`, transition to inline recoverable error banner with one-click retry |

---

## 2. Deterministic Optimistic Rollback Pattern

Never mutate client arrays in place before a network request completes. Maintain an immutable `rollbackSnapshot`:

```typescript
export interface OptimisticMutationEnvelope<TData, TDraft> {
  readonly mutationId: string;
  readonly idempotencyKey: string;
  readonly startedAtMs: number;
  readonly optimisticData: TData;
  readonly rollbackSnapshot: TData;
  readonly preservedDraft: TDraft;
}
```

### Rollback Invariants
1. **Zero Data Loss on Failure:** If a user types a 300-word comment and hits Send, the comment immediately appears in the thread (`< 50ms`) and the textarea clears. If the network request fails 2 seconds later, rolling back the thread item **must** simultaneously restore the 300-word draft into the textarea (or offer an inline "Failed to send — Retry / Restore to editor" control on the item itself).
2. **Idempotent Retry:** Clicking `Retry` on a failed optimistic mutation must reuse the exact same `idempotencyKey` (`Idempotency-Key` HTTP header) so a dropped network response never creates duplicate server records.
3. **Out-of-Order Mutation Guard:** Track a monotonically increasing `mutationSeq`. If the user toggles a setting `ON -> OFF` rapidly and the older `ON` request fails or resolves after `OFF`, ignore or reconcile by sequence number rather than clobbering the newer state.

---

## 3. Zero Cumulative Layout Shift (`CLS = 0.000`) Checklist

| Element Category | CLS Failure Mode | Mandatory Geometry Lock |
| --- | --- | --- |
| **Async Data Lists / Cards** | `24px` spinner expands into `600px` list | Render `N` skeleton rows with exact matching `height`, `padding`, `gap`, and `border` (`min-height` locked) |
| **Images & Video** | Image loads and pushes text down by `300px` | Set explicit `width` & `height` attributes AND CSS `aspect-ratio: <w> / <h>; width: 100%; height: auto;` |
| **Web Fonts** | Fallback font swaps to web font and reflows line wraps | Define `@font-face` with `size-adjust`, `ascent-override`, and `descent-override` matching fallback metrics |
| **Inline Form Errors** | Validation error inserts `<p>` that shifts Submit button down | Pre-allocate a fixed error track (`min-height: 1.25rem`) below inputs or use anchored popover overlays |
| **Stale Revalidation** | Refreshing data replaces table with skeleton | Keep existing data table mounted (`revalidating_stale`); animate a `2px` top progress bar or header badge via `opacity`/`scaleX` |
| **Modal Scroll Lock** | `body { overflow: hidden }` removes `15px` scrollbar and shifts page horizontally | Apply `html { scrollbar-gutter: stable; }` or compensate `padding-right` by `window.innerWidth - document.documentElement.clientWidth` |
