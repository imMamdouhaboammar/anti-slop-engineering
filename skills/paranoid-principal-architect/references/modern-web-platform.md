# Modern Web Platform Standards & Clean Architecture

## 1. Native Web Platform Primitives (TC39, WHATWG, W3C)

Legacy utility libraries (lodash, moment, axios, deep-clone, querystring) add bundle bloat, security audit overhead, and supply chain exposure. The Paranoid Architect prioritizes native standards:

| Legacy / Bloated Pattern | Native Platform Standard | Advantage |
| --- | --- | --- |
| `axios.get(url, { timeout: 3000 })` | `fetch(url, { signal: AbortSignal.timeout(3000) })` | Zero dependencies, native stream cancellation |
| `lodash.cloneDeep(obj)` | `structuredClone(obj)` | Native C++ memory cloning, handles circular references |
| `lodash.groupBy(arr, fn)` | `Object.groupBy(arr, fn)` | Native ECMAScript standard (TC39 Stage 4) |
| `moment(d).format(...)` | `new Intl.DateTimeFormat(locale, options).format(d)` | Native browser/engine i18n, zero bundle impact |
| `querystring.parse(str)` | `new URLSearchParams(str)` | Spec-compliant WHATWG URL encoding and parsing |
| Hand-rolled chunked reader | `ReadableStream` / `TransformStream` | Native Web Streams with automatic backpressure |

---

## 2. Modern Semantic HTML5 & Accessible UI

High-scale web frontends must be universally accessible, resilient, and lightweight:

### Modal Architecture: Native `<dialog>`
Never hand-roll div-based modals with synthetic event listeners and fragile focus loops:
```html
<dialog id="confirm-modal" aria-labelledby="modal-title">
  <form method="dialog">
    <h2 id="modal-title">Confirm Deletion</h2>
    <p>This action is irreversible.</p>
    <button type="submit" value="cancel">Cancel</button>
    <button type="submit" value="confirm" autofocus>Confirm</button>
  </form>
</dialog>
```
- Invoking `dialogElement.showModal()` automatically locks interaction to the top layer, traps Tab focus within the dialog, prevents background scroll, and closes on `Escape`.
- Returns user choice natively through `dialogElement.addEventListener('close', ...)`.

### Semantic Controls
- **Buttons:** Always declare explicit `type="button"` on interactive controls inside forms that are not submit triggers, preventing unintended form submissions.
- **Collapsible Regions:** Use native `<details>` and `<summary>` instead of synthetic toggle div hierarchies.

### Modern CSS Invariants
- Use `:has()` parent-selectors and Container Queries (`@container`) for modular, component-driven layouts.
- Always respect user accessibility preferences:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, ::before, ::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```

---

## 3. Strict Type Discipline & Type Branding

TypeScript is not documentation; it is a structural proof system. Loose typing breeds silent runtime corruption.

### Prohibitions
- **Ban `any`:** `any` disables type checking across all downstream consumers.
- **Ban `@ts-ignore` / `@ts-nocheck`:** Never suppress the compiler.
- **Ban blind assertions (`input as TargetType`):** Type assertions mask upstream schema mismatches. Use runtime type guards or Zod schema parsers.

### Branded Types for Domain Identifiers
Prevent accidental parameter transposition (e.g. passing an `orgId` where a `userId` is required):
```typescript
declare const __brand: unique symbol;
export type Brand<T, B> = T & { readonly [__brand]: B };

export type UserId = Brand<string, "UserId">;
export type OrganizationId = Brand<string, "OrganizationId">;
export type Cents = Brand<number, "Cents">;

export function createUserId(raw: string): UserId {
  if (!/^usr_[a-zA-Z0-9]{24}$/.test(raw)) {
    throw new TypeError(`Invalid UserId format: ${raw}`);
  }
  return raw as UserId;
}
```

### Discriminated Unions for State
Model domain states as exhaustive discriminated unions:
```typescript
export type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; code: string; message: string };
```

---

## 4. Structured Error Handling & Zero Meta-Leakage

### The Empty Catch Prohibition
Never swallow exceptions:
```typescript
// FATAL DEFECT: Swallowing errors masks silent failures and data corruption
try {
  await persistRecord();
} catch (e) {}
```

### Deterministic Error Mapping & Correlation IDs
Every operational error must map to a standardized machine-readable envelope without leaking database schemas, server paths, or stack traces:
```typescript
export interface ApiErrorEnvelope {
  correlationId: string;
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export function handleControllerError(err: unknown, correlationId: string): Response {
  // 1. Log full internal stack trace securely to private logging pipeline
  logger.error({ correlationId, error: err }, "Unhandled request error");

  // 2. Return clean, unslop, non-leaking payload to the caller
  const envelope: ApiErrorEnvelope = {
    correlationId,
    code: err instanceof DomainError ? err.code : "INTERNAL_SERVER_ERROR",
    message: err instanceof DomainError ? err.message : "An unexpected error occurred."
  };

  const status = err instanceof DomainError ? err.httpStatus : 500;
  return new Response(JSON.stringify(envelope), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
```
