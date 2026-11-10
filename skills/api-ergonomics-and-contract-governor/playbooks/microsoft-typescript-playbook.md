# Playbook: Microsoft TypeScript Compiler-Team Ergonomic Rigor

> Model types so cleanly that the TypeScript compiler guides the developer into correct code before they even read documentation.

## 1. The Core Philosophy

The Microsoft TypeScript compiler team designs interfaces around three axioms:
1. **Predictable Autocomplete Over Clever Metaprogramming:** An API where Ctrl+Space suggests the exact property needed is infinitely superior to complex type-level template metaprogramming that slows down compiler language servers.
2. **Hover Readability (`.d.ts` Cleanliness):** When a developer hovers over a function or variable, the tooltip must render clean, recognizable type aliases (e.g. `PaymentIntent`), not a 400-character flattened mapped type with internal utility generics (`Omit<Pick<...>, ...>`).
3. **Soundness at the Seam:** External boundaries must validate payloads at runtime, but internal module types must be strict and nominal, making accidental parameter transposition impossible.

---

## 2. Strict Compiler Configuration Baseline

All modern TypeScript SDKs and internal modules must compile under this `tsconfig.json` baseline:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "strictBindCallApply": true,
    "strictPropertyInitialization": true,
    "noImplicitThis": true,
    "alwaysStrict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "declaration": true,
    "declarationMap": true
  }
}
```

---

## 3. Nominal Branded Types

To prevent swapping identically-typed primitives (e.g. passing a `userId` to a parameter expecting an `orgId`), enforce compile-time nominal branding:

```typescript
declare const BrandTag: unique symbol;

export type Nominal<T, Name extends string> = T & { readonly [BrandTag]: Name };

export type UserId = Nominal<string, "UserId">;
export type OrganizationId = Nominal<string, "OrganizationId">;
export type ApiKey = Nominal<string, "ApiKey">;

// Constructor functions with validation:
export function asUserId(value: string): UserId {
  if (!value.startsWith("usr_")) {
    throw new TypeError(`Invalid UserId format: ${value}`);
  }
  return value as UserId;
}

export function asOrganizationId(value: string): OrganizationId {
  if (!value.startsWith("org_")) {
    throw new TypeError(`Invalid OrganizationId format: ${value}`);
  }
  return value as OrganizationId;
}
```

---

## 4. Template Literal Types for Predictable Prefixes

Combine template literal types with nominal branding for self-documenting ID contracts:

```typescript
export type StripePrefixedId<Prefix extends string> = `${Prefix}_${string}`;

export type ChargeId = Nominal<StripePrefixedId<"ch">, "ChargeId">;
export type RefundId = Nominal<StripePrefixedId<"re">, "RefundId">;
```

---

## 5. Exhaustive Pattern Matching

Never leave switch statements or if-else cascades open to unhandled branches when consuming discriminated unions:

```typescript
export function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unhandled discriminated union member: ${JSON.stringify(value)}`);
}
```
