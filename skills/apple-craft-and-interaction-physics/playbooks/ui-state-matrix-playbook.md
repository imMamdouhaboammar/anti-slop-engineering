# Playbook: Exhaustive UI State Matrix Implementation

## Objective
Convert any loose, fragile boolean-based UI component into a rock-solid, 8-state Discriminated Union state machine with compile-time exhaustiveness checking and optimistic draft preservation.

---

## The 5-Step Refactoring Sequence

### Step 1: Enumerate the Domain State Matrix
Define an explicit TypeScript discriminated union declaring all 8 operational states:
```typescript
export type DashboardState<T> =
  | { status: 'loading_skeleton'; skeletonRows: number }
  | { status: 'empty'; guidance: string; onAction: () => void }
  | { status: 'loaded_fresh'; data: T; syncedAt: number }
  | { status: 'revalidating_stale'; data: T; isBackground: true }
  | { status: 'partial_error'; data: T; failedWidget: string; onRetry: () => void }
  | { status: 'offline'; data: T | null; pendingChanges: number }
  | { status: 'optimistic_rollback'; draftText: string; error: string; onRetry: () => void }
  | { status: 'terminal_error'; incidentId: string; message: string; onReset: () => void };
```

### Step 2: Establish the Draft Preservation Store
Before any optimistic mutation is triggered, store the current user draft:
```typescript
// Snapshot capture
const draftSnapshot = composerInputText;
const previousDataSnapshot = structuredClone(currentData);

// Apply optimistic mutation immediately (< 50ms)
setOptimisticView();

try {
  await api.mutate(draftSnapshot, { signal: AbortSignal.timeout(5000) });
  // Success: clear draft
  clearComposerText();
} catch (err) {
  // Rollback: RESTORE DRAFT TEXT
  setState({
    status: 'optimistic_rollback',
    draftText: draftSnapshot,
    error: err instanceof Error ? err.message : 'Network error',
    onRetry: () => retryMutation(draftSnapshot)
  });
}
```

### Step 3: Implement Sub-Region Error Boundaries for `partial_error`
If an ancillary widget fails (e.g. comments list or recommended items), do not replace the entire screen with an error:
```typescript
{state.status === 'partial_error' && (
  <div className="sub-region-error-banner" role="alert">
    <span>Failed to load comments.</span>
    <button type="button" onClick={state.onRetry}>Retry</button>
  </div>
)}
```

### Step 4: Wire the Offline Event Listeners
Detect offline transitions and reflect them in the state machine:
```typescript
useEffect(() => {
  const onOffline = () => setState(prev => ({ status: 'offline', data: prev.data, pendingChanges: 0 }));
  const onOnline = () => refreshFreshData();

  window.addEventListener('offline', onOffline);
  window.addEventListener('online', onOnline);

  return () => {
    window.removeEventListener('offline', onOffline);
    window.removeEventListener('online', onOnline);
  };
}, []);
```

### Step 5: Implement Compile-Time Exhaustiveness Assertion
Wrap the view renderer in a switch statement with an `assertNever` default branch:
```typescript
function assertNever(x: never): never {
  throw new Error(`Unimplemented UI State: ${JSON.stringify(x)}`);
}

export function ViewRenderer({ state }: { state: DashboardState<any> }) {
  switch (state.status) {
    case 'loading_skeleton': return <SkeletonView />;
    case 'empty': return <EmptyView onAction={state.onAction} />;
    case 'loaded_fresh': return <DataView data={state.data} />;
    case 'revalidating_stale': return <DataView data={state.data} isRefreshing />;
    case 'partial_error': return <DataView data={state.data} errorWidget={state.failedWidget} />;
    case 'offline': return <OfflineDataView data={state.data} />;
    case 'optimistic_rollback': return <RollbackView draft={state.draftText} onRetry={state.onRetry} />;
    case 'terminal_error': return <TerminalErrorView message={state.message} onReset={state.onReset} />;
    default: return assertNever(state);
  }
}
```
