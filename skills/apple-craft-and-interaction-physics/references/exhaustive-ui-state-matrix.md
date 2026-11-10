# Exhaustive UI State Matrix Reference

> Banish Boolean Soup. Replace combinatorial flags with mathematically exhaustive Discriminated Union state machines.

## Why Boolean Soup Fails

AI code generators frequently produce asynchronous state handling using independent boolean flags:
```typescript
// ANTI-PATTERN: Combinatorial Boolean Soup
const [isLoading, setIsLoading] = useState(false);
const [isError, setIsError] = useState(false);
const [isEmpty, setIsEmpty] = useState(false);
const [isOffline, setIsOffline] = useState(false);
const [data, setData] = useState<Item[] | null>(null);
```
With 4 boolean flags, there are $2^4 = 16$ possible permutations. Inevitably, the application encounters illegal combinations:
- `isLoading === true` and `isError === true`: Both the spinner and error banner render, overlapping in the layout.
- `isLoading === false`, `isError === false`, `data === null`: A blank white screen renders because no branch matches.
- Network fails during mutation: The optimistic item disappears, and the user's typed input is lost forever.

---

## The Eight Canonical Operational States

Every production-grade view or async container must implement an explicit Discriminated Union with tag `status`:

```typescript
export type ViewState<T> =
  | { status: 'loading_skeleton'; reservedHeightPx: number }
  | { status: 'empty'; guidanceTitle: string; callToAction: () => void }
  | { status: 'loaded_fresh'; data: T; updatedAt: number }
  | { status: 'revalidating_stale'; data: T; lastSyncAt: number }
  | { status: 'partial_error'; data: T; failedRegionId: string; retryRegion: () => void }
  | { status: 'offline'; data: T | null; pendingMutationsCount: number }
  | { status: 'optimistic_rollback'; draftPayload: string; errorReason: string; retryMutation: () => void }
  | { status: 'terminal_error'; incidentId: string; errorMessage: string; retryAll: () => void };
```

### 1. `loading_skeleton`
- **Behavior:** Renders a reserved layout skeleton that identically matches the outer bounding box, padding, line heights, and margins of the resolved content.
- **Physical Invariant:** Outer container dimension must be fixed so `CLS = 0.000` when transitioning to `loaded_fresh`.

### 2. `empty`
- **Behavior:** A first-class zero-state view. It must never be an empty void or generic text.
- **Design Invariant:** Includes clear educational copy explaining why it is empty, an icon or illustration, and a primary CTA that enables the user to create or import the first item.

### 3. `loaded_fresh`
- **Behavior:** The canonical populated state. All controls are interactive, and fresh data is rendered.

### 4. `revalidating_stale`
- **Behavior:** Triggered during background SWR (Stale-While-Revalidate) sync or polling.
- **Physical Invariant:** Existing screen content MUST remain completely interactive. Never replace active content with a full-screen skeleton or spinner. Render a subtle, non-blocking indicator (e.g., a quiet 2px progress pulse in the top corner).

### 5. `partial_error`
- **Behavior:** In composite dashboards (e.g. main document + activity stream + comments), if the comments endpoint fails with HTTP 500, the main document and activity stream must remain intact.
- **Fault Boundary:** Isolate the failure strictly to the comments container with an inline "Retry comments" CTA.

### 6. `offline`
- **Behavior:** Triggered by `navigator.onLine === false` or network transport aborts.
- **Persistence:** Render cached content from IndexedDB/storage. Disable destructive mutations with clear tooltips. Queue harmless local actions in an offline mutation queue.

### 7. `optimistic_rollback`
- **Behavior:** User submits an action (e.g., submits a comment or toggles a status). The UI updates within `< 50ms` optimistically.
- **Failure Recovery:** If the server returns 400/409/500:
  1. Capture `previousStateSnapshot` before mutating.
  2. Smoothly revert the optimistic DOM update.
  3. **Preserve User Draft:** Restore the user's typed text back into the composer/input field. Never clear the field until the server has acknowledged success or durable local persistence is committed.
  4. Surface an inline recovery badge: `[Failed to post. Tap to retry]`.

### 8. `terminal_error`
- **Behavior:** High-level catastrophic failure where core dependencies are unreachable.
- **Recovery Invariant:** Clear diagnostic incident correlation ID, human-readable error description, and a deterministic "Reload Application" or "Retry Connection" action.

---

## Compile-Time Exhaustiveness Checking

Every state rendering pipeline must enforce strict TypeScript compiler checks:

```typescript
function assertNever(value: never): never {
  throw new Error(`Unhandled UI State Variant: ${JSON.stringify(value)}`);
}

export function renderView<T>(state: ViewState<T>): JSX.Element {
  switch (state.status) {
    case 'loading_skeleton':
      return <LoadingSkeleton reservedHeight={state.reservedHeightPx} />;
    case 'empty':
      return <EmptyGuidance title={state.guidanceTitle} onAction={state.callToAction} />;
    case 'loaded_fresh':
      return <CanonicalContent data={state.data} />;
    case 'revalidating_stale':
      return <CanonicalContent data={state.data} isRefreshing={true} />;
    case 'partial_error':
      return <CompositeWithFailedRegion data={state.data} region={state.failedRegionId} onRetry={state.retryRegion} />;
    case 'offline':
      return <OfflineView data={state.data} pendingCount={state.pendingMutationsCount} />;
    case 'optimistic_rollback':
      return <ComposerWithRestoredDraft draft={state.draftPayload} error={state.errorReason} onRetry={state.retryMutation} />;
    case 'terminal_error':
      return <TerminalErrorScreen incidentId={state.incidentId} message={state.errorMessage} onRetry={state.retryAll} />;
    default:
      return assertNever(state);
  }
}
```

If an engineer or agent adds a new state variant to `ViewState` without adding a corresponding case branch in `renderView`, TypeScript will refuse to compile (`Type 'new_state' is not assignable to type 'never'`).
