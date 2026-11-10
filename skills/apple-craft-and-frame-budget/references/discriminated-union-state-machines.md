# Discriminated Union UI State Machines Reference

Boolean flags (`isLoading`, `isError`, `isSuccess`, `isEmpty`, `isStale`, `isOffline`) must never be combined as independent state variables. Every interactive component must be governed by an explicit **Discriminated Union State Machine** with a pure reducer and compile-time exhaustiveness checking.

---

## 1. Boolean Soup vs. Discriminated Union Comparison

| Dimension | Boolean Soup (`isLoading && !isError && ...`) | Discriminated Union (`state.status`) |
| --- | --- | --- |
| **State Cardinality** | $2^N$ implicit combinations (e.g. $2^5 = 32$ states) | Exact $K$ valid domain states ($9$ states) |
| **Impossible States** | Frequent (`isLoading: true, isError: true`) | Unrepresentable at compile time |
| **Data Nullability** | Requires `!` assertions or defensive `data?.items` everywhere | Automatically narrowed by `switch (state.status)` |
| **Adding a New State** | Silently missed in `if / else` branches across JSX | Compiler fails at `assertNever(state)` until handled |

---

## 2. Canonical TypeScript State & Event Definitions

```typescript
export interface PanelError {
  readonly panelId: string;
  readonly code: string;
  readonly message: string;
  readonly retryable: boolean;
}

export interface QueuedMutation<TPayload> {
  readonly idempotencyKey: string;
  readonly payload: TPayload;
  readonly queuedAtMs: number;
}

export type ViewState<TData, TDraft = string, TMutationPayload = unknown> =
  | { readonly status: "idle" }
  | { readonly status: "loading_initial"; readonly startedAtMs: number }
  | { readonly status: "loaded_empty"; readonly lastSyncedAtMs: number }
  | { readonly status: "loaded_fresh"; readonly data: TData; readonly lastSyncedAtMs: number }
  | { readonly status: "revalidating_stale"; readonly data: TData; readonly lastSyncedAtMs: number }
  | {
      readonly status: "optimistic_mutating";
      readonly data: TData;
      readonly rollbackSnapshot: TData;
      readonly preservedDraft: TDraft;
      readonly idempotencyKey: string;
      readonly lastSyncedAtMs: number;
    }
  | {
      readonly status: "partial_failure";
      readonly data: TData;
      readonly failedPanels: readonly PanelError[];
      readonly lastSyncedAtMs: number;
    }
  | {
      readonly status: "offline_queued";
      readonly data: TData;
      readonly queuedMutations: readonly QueuedMutation<TMutationPayload>[];
      readonly lastSyncedAtMs: number;
    }
  | {
      readonly status: "terminal_error";
      readonly errorCode: string;
      readonly message: string;
      readonly restoredDraft?: TDraft;
      readonly retryable: boolean;
    };
```

---

## 3. Compile-Time Exhaustiveness Guard (`assertNever`)

Every view renderer or state selector must enforce exhaustiveness in its `default` branch:

```typescript
export function assertNever(unhandled: never): never {
  throw new Error(`Unhandled discriminated union state: ${JSON.stringify(unhandled)}`);
}
```

When rendering JSX/HTML from `ViewState`, use a `switch (state.status)` expression where every branch returns a geometry-locked layout container and `default: return assertNever(state);` guarantees 100% coverage.
