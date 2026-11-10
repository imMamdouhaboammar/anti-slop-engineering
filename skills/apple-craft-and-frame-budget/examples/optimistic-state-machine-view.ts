// SPDX-License-Identifier: MIT
// Example: Apple Craft & 120Hz Frame Budget — Discriminated Union State Machine, Sub-50ms Optimistic Rollback, Zero-CLS Geometry & Epsilon Spring Physics

export interface InvoiceItem {
  readonly id: string;
  readonly title: string;
  readonly amountCents: number;
  readonly archived: boolean;
  readonly syncState: "synced" | "optimistic_pending";
}

export interface SubPanelFailure {
  readonly panelId: string;
  readonly errorCode: string;
  readonly retryable: boolean;
}

export interface QueuedArchiveAction {
  readonly invoiceId: string;
  readonly idempotencyKey: string;
  readonly queuedAtMs: number;
}

export type InvoiceBoardState =
  | { readonly status: "idle" }
  | { readonly status: "loading_initial"; readonly reservedRowCount: number; readonly rowHeightPx: 72 }
  | { readonly status: "loaded_empty"; readonly minContainerHeightPx: 432 }
  | { readonly status: "loaded_fresh"; readonly items: readonly InvoiceItem[]; readonly draftNote: string }
  | { readonly status: "revalidating_stale"; readonly items: readonly InvoiceItem[]; readonly draftNote: string }
  | {
      readonly status: "optimistic_mutating";
      readonly items: readonly InvoiceItem[];
      readonly rollbackSnapshot: readonly InvoiceItem[];
      readonly preservedDraft: string;
      readonly idempotencyKey: string;
      readonly draftNote: string;
    }
  | {
      readonly status: "partial_failure";
      readonly items: readonly InvoiceItem[];
      readonly failedPanels: readonly SubPanelFailure[];
      readonly draftNote: string;
    }
  | {
      readonly status: "offline_queued";
      readonly items: readonly InvoiceItem[];
      readonly queuedActions: readonly QueuedArchiveAction[];
      readonly draftNote: string;
    }
  | {
      readonly status: "terminal_error";
      readonly errorCode: string;
      readonly message: string;
      readonly restoredDraft: string;
    };

export type InvoiceBoardEvent =
  | { readonly type: "LOAD_START"; readonly reservedRowCount: number }
  | { readonly type: "LOAD_SUCCESS"; readonly items: readonly InvoiceItem[] }
  | { readonly type: "REVALIDATE_START" }
  | {
      readonly type: "OPTIMISTIC_ARCHIVE_SUBMIT";
      readonly invoiceId: string;
      readonly submittedDraft: string;
      readonly idempotencyKey: string;
      readonly nowMs: number;
      readonly online: boolean;
    }
  | { readonly type: "MUTATION_COMMIT_SUCCESS"; readonly canonicalItems: readonly InvoiceItem[] }
  | { readonly type: "MUTATION_ROLLBACK_ERROR"; readonly errorCode: string }
  | { readonly type: "SUBPANEL_DEGRADED"; readonly failure: SubPanelFailure }
  | { readonly type: "LOAD_TERMINAL_ERROR"; readonly errorCode: string; readonly message: string };

export function assertNever(unhandled: never): never {
  throw new Error(`Unhandled discriminated union member: ${JSON.stringify(unhandled)}`);
}

function extractCurrentItems(state: InvoiceBoardState): readonly InvoiceItem[] | null {
  switch (state.status) {
    case "loaded_fresh":
    case "revalidating_stale":
    case "optimistic_mutating":
    case "partial_failure":
    case "offline_queued":
      return state.items;
    case "idle":
    case "loading_initial":
    case "loaded_empty":
    case "terminal_error":
      return null;
    default:
      return assertNever(state);
  }
}

export function transitionInvoiceBoard(
  state: InvoiceBoardState,
  event: InvoiceBoardEvent
): InvoiceBoardState {
  switch (event.type) {
    case "LOAD_START":
      return { status: "loading_initial", reservedRowCount: event.reservedRowCount, rowHeightPx: 72 };
    case "LOAD_SUCCESS":
      if (event.items.length === 0) {
        return { status: "loaded_empty", minContainerHeightPx: 432 };
      }
      return { status: "loaded_fresh", items: event.items, draftNote: "" };
    case "REVALIDATE_START": {
      const existing = extractCurrentItems(state);
      return existing
        ? { status: "revalidating_stale", items: existing, draftNote: "" }
        : state;
    }
    case "OPTIMISTIC_ARCHIVE_SUBMIT":
      return applyOptimisticArchive(state, event);
    case "MUTATION_COMMIT_SUCCESS":
      return { status: "loaded_fresh", items: event.canonicalItems, draftNote: "" };
    case "MUTATION_ROLLBACK_ERROR":
      if (state.status !== "optimistic_mutating") return state;
      return {
        status: "loaded_fresh",
        items: state.rollbackSnapshot,
        draftNote: state.preservedDraft,
      };
    case "SUBPANEL_DEGRADED": {
      const existing = extractCurrentItems(state);
      return existing
        ? { status: "partial_failure", items: existing, failedPanels: [event.failure], draftNote: "" }
        : state;
    }
    case "LOAD_TERMINAL_ERROR":
      return {
        status: "terminal_error",
        errorCode: event.errorCode,
        message: event.message,
        restoredDraft: state.status === "optimistic_mutating" ? state.preservedDraft : "",
      };
    default:
      return assertNever(event);
  }
}

function applyOptimisticArchive(
  state: InvoiceBoardState,
  event: Extract<InvoiceBoardEvent, { type: "OPTIMISTIC_ARCHIVE_SUBMIT" }>
): InvoiceBoardState {
  const snapshot = extractCurrentItems(state);
  if (!snapshot) return state;

  const optimisticItems = snapshot.map((item) =>
    item.id === event.invoiceId
      ? { ...item, archived: true, syncState: "optimistic_pending" as const }
      : item
  );

  if (!event.online) {
    return {
      status: "offline_queued",
      items: optimisticItems,
      queuedActions: [
        { invoiceId: event.invoiceId, idempotencyKey: event.idempotencyKey, queuedAtMs: event.nowMs },
      ],
      draftNote: "",
    };
  }

  return {
    status: "optimistic_mutating",
    items: optimisticItems,
    rollbackSnapshot: snapshot,
    preservedDraft: event.submittedDraft,
    idempotencyKey: event.idempotencyKey,
    draftNote: "",
  };
}

export function stepCompositorSpring(
  current: number,
  target: number,
  velocity: number,
  dtSeconds: number,
  epsilon = 1e-4
): { readonly position: number; readonly velocity: number; readonly settled: boolean; readonly transformCss: string } {
  const displacement = current - target;
  const acceleration = -280 * displacement - 26 * velocity;
  const nextVelocity = velocity + acceleration * dtSeconds;
  const nextPosition = current + nextVelocity * dtSeconds;

  if (Math.abs(target - nextPosition) < epsilon && Math.abs(nextVelocity) < epsilon) {
    return {
      position: target,
      velocity: 0,
      settled: true,
      transformCss: `translate3d(0px, ${target.toFixed(2)}px, 0px)`,
    };
  }
  return {
    position: nextPosition,
    velocity: nextVelocity,
    settled: false,
    transformCss: `translate3d(0px, ${nextPosition.toFixed(2)}px, 0px)`,
  };
}

export function canEnableDesktopMomentumScroll(
  isCoarsePointer: boolean,
  viewportWidthPx: number
): boolean {
  return !isCoarsePointer && viewportWidthPx >= 768;
}
