# Workflow: Architect Explicit Discriminated-Union UI State Machine

Use this workflow whenever building a new stateful screen, data view, form, or interactive widget, or when refactoring legacy components suffering from "Boolean Soup" (`isLoading`, `isError`, `isSuccess`, `isEmpty`).

## Step-by-Step Procedure

### 1. Delete All Loose Status Booleans
1. Identify and remove independent boolean flags (`isLoading`, `isFetching`, `isError`, `isSubmitted`, `isEmpty`, `isOffline`).
2. Never allow a component to hold `data: T | null` alongside `error: Error | null` and `loading: boolean` as separate unconstricted fields.

### 2. Define the Exhaustive Discriminated Union (`status`)
Define a single `ViewState<TData, TDraft>` union that explicitly accounts for every operational horizon:
1. `idle`: Before initial trigger.
2. `loading_initial`: First load with zero cached data $\implies$ renders pixel-matched skeleton (`CLS = 0.000`).
3. `loaded_empty`: Query succeeded with 0 items $\implies$ renders actionable empty state inside the exact same layout dimensions.
4. `loaded_fresh`: Authoritative data loaded and interactive.
5. `revalidating_stale`: Background refresh in flight $\implies$ keeps `data` visible and interactive on screen while displaying a non-blocking refresh indicator.
6. `optimistic_mutating`: User mutation applied in `< 50ms` $\implies$ carries `data` (optimistic), `rollbackSnapshot` (prior state), `preservedDraft`, and `idempotencyKey`.
7. `partial_failure`: Primary `data` succeeded, but one or more secondary sub-panels failed $\implies$ renders primary `data` plus scoped inline retry on the failed sub-panel.
8. `offline_queued`: Client lost connectivity $\implies$ keeps `data` interactive and queues mutations with an explicit offline indicator.
9. `terminal_error`: Initial load failed with no cached fallback $\implies$ renders structured error code, message, and retry trigger.

### 3. Implement a Pure Deterministic Transition Reducer
1. Model all state changes as explicit events (`FETCH_START`, `FETCH_SUCCESS`, `FETCH_EMPTY`, `REVALIDATE_START`, `OPTIMISTIC_MUTATE`, `MUTATION_COMMIT`, `MUTATION_ROLLBACK`, `PARTIAL_PANEL_ERROR`, `NETWORK_OFFLINE`, `FETCH_ERROR`).
2. Write a pure function `transitionViewState(state, event): ViewState` with zero side effects so every state transition can be unit-tested in `< 1ms`.

### 4. Enforce `assertNever` in the View Switch
In the UI rendering layer, switch on `state.status` and place `assertNever(state)` in the `default` branch so any future state addition fails TypeScript compilation until rendered.
