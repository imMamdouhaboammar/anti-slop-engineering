# Use Case: Refactor an Internal Module Contract

> Step-by-step workflow for eliminating boolean traps, stringly-typed IDs, and unstructured error throwing in existing modules.

## Step 1: Detect Contract Smells

Audit module export signatures for:
1. Two or more consecutive boolean parameters (`(a, true, false)`).
2. Raw `string` parameters representing different domain entities (`(userId: string, orgId: string)`).
3. Generic `throw new Error(...)` statements.
4. Giant option bags with >7 required fields.

---

## Step 2: Introduce Nominal Branded Types

1. Create branded types for each domain entity:
   ```typescript
   export type TenantId = Brand<string, "TenantId">;
   export type DocumentId = Brand<string, "DocumentId">;
   ```
2. Wrap external inputs at the parsing boundary (e.g. Zod `.transform(asTenantId)`).

---

## Step 3: Collapse Boolean Traps into Named Unions

Replace positional boolean flags with explicit union literals:
```typescript
// Before:
function queryLogs(tenantId: string, isRealtime: boolean, includeAudit: boolean, descending: boolean)

// After:
interface LogQueryOptions {
  readonly streamingMode?: "batch" | "realtime";
  readonly scope?: "application_only" | "include_audit";
  readonly sortDirection?: "asc" | "desc";
}
function queryLogs(tenantId: TenantId, options?: LogQueryOptions)
```

---

## Step 4: Model State as Discriminated Unions

Convert flat optional structs into tagged discriminated unions with an `assertNever` exhaustiveness guard.

---

## Step 5: Replace Bare Throws with RFC 9457 Errors

Ensure all exceptions thrown across the module boundary instantiate `ProblemDetailsError`.
