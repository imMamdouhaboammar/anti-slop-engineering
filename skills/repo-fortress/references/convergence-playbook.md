# Zero-Rework Convergence Playbook (From 2,000+ Violations to PASS)

This playbook outlines the exact priority sequencing and architectural patterns required to bring massive linting and type errors down to zero without regressions.

---

## Convergence Workflow Overview

```
Total Errors (e.g. 2,000)
       │
       ▼
[Framework Alignment Pass] ──► Strip legacy false-positive rules (e.g. React 16 JSX scope)
       │ (e.g. leaves 800 real errors)
       ▼
[Priority P0: Async & Runtime] ──► no-floating-promises, await-thenable, no-base-to-string
       │ (leaves 500 errors)
       ▼
[Priority P1: Types & Casts] ──► no-unsafe-type-assertion, boundary decoders, typed ports
       │ (leaves 50 errors)
       ▼
[Priority P2: Dead Code & Chunks] ──► Knip triage, Vite/Rollup manual chunks
       │
       ▼
0 Errors, 0 Warnings (PASS)
```

---

## Priority P0: Async & Runtime Correctness

### 1. `no-floating-promises`
Unawaited promises cause hidden race conditions, missed database rollbacks, unhandled rejections, and silent socket leaks.
- **Rule**: If caller is `async` or teardown order matters, use `await`.
- **Background Dispatch**: If execution is intentionally non-blocking:
  ```typescript
  // Attach .catch() before marking with void
  void backgroundOperation().catch((err: unknown) => {
    logger.error("Background task encountered an error", {
      error: err instanceof Error ? err.message : String(err)
    });
  });
  ```

### 2. `await-thenable`
Avoid `await` on synchronous functions or plain objects.
- Inspect the function signature: did a previous refactor make it sync, or did someone forget `async` in the declaration?
- Remove redundant `await` only after confirming the function is genuinely synchronous.

### 3. `no-base-to-string`
String interpolation of objects (`${obj}`) results in `[object Object]` or unhelpful error summaries.
```typescript
// Type-safe stringifier helper
export function formatError(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}
```

---

## Priority P1: Type Soundness & Structural Boundaries

### 1. `no-unsafe-type-assertion`
Casting unvalidated data (`as User`, `as Record<string, unknown>`) creates invisible runtime crashes.

#### At Input/Output Boundaries (HTTP, Webhooks, DB):
Instead of raw assertions, use lightweight validator guards:
```typescript
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseIncomingWebhook(raw: unknown): WebhookPayload {
  if (!isRecord(raw)) throw new TypeError("Expected JSON object");
  if (typeof raw.event !== "string") throw new TypeError("Missing 'event' field");
  return { event: raw.event, data: raw.data };
}
```

#### In Test Fixtures:
Avoid casting partial doubles:
```typescript
// ❌ WRONG
const socket = { send: vi.fn() } as unknown as WebSocket;

// ✅ RIGHT: Narrow Port Interface & Factory
export interface SocketPort {
  send(data: string | Uint8Array): void;
}

export function createMockSocket(overrides: Partial<SocketPort> = {}): SocketPort {
  return {
    send: vi.fn(),
    ...overrides,
  };
}
```

---

## Priority P2: Dead Code & Asset Optimization

### 1. Knip Dead Code Triage
- Never delete exports blindly based on linter output.
- Check against:
  - Framework conventions (e.g. Next.js `page.tsx`, Vite `index.html`).
  - Dynamic imports (`import(...)`).
  - CLI bin entrypoints declared in `package.json`.
  - Starlark / BUCK / Bazel build rules.
- Whitelist dynamic entrypoints in `knip.json` before deleting true dead code.

### 2. Vite / Rollup Chunk Size Warnings
Large single-chunk bundles (>500kB) trigger CI warnings. Configure manual vendor chunks:
```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("react") || id.includes("react-dom")) return "vendor-react";
            if (id.includes("lucide") || id.includes("icons")) return "vendor-icons";
            return "vendor";
          }
        }
      }
    }
  }
});
```
