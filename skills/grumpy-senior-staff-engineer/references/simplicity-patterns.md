# Simplicity Patterns: Structural Discipline for Readable, Maintainable Code

## 1. Data Structures Over Class Hierarchies

Prefer plain, immutable data structures and pure functions over deep OOP inheritance trees.

**Avoid:**
```typescript
abstract class Shape {
  abstract area(): number;
}
class Circle extends Shape {
  constructor(private radius: number) { super(); }
  area() { return Math.PI * this.radius ** 2; }
}
class Rectangle extends Shape {
  constructor(private w: number, private h: number) { super(); }
  area() { return this.w * this.h; }
}
```

**Prefer (discriminated union + function):**
```typescript
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "rectangle"; width: number; height: number };

function area(shape: Shape): number {
  switch (shape.kind) {
    case "circle": return Math.PI * shape.radius ** 2;
    case "rectangle": return shape.width * shape.height;
  }
}
```

Adding a new shape in the class hierarchy requires a new file, a new subclass, and spreading logic across the codebase. Adding it to the discriminated union + function is a 2-line change in one file.

---

## 2. Flat Control Flow (Early Return & Guard Clauses)

Deep nesting is a maintenance tax paid by every engineer who reads the code.

**Avoid:**
```typescript
function processOrder(order: Order | null): Result {
  if (order) {
    if (order.status === "pending") {
      if (order.items.length > 0) {
        // actual work buried at nesting level 3
        return { success: true };
      } else {
        return { success: false, error: "empty_order" };
      }
    } else {
      return { success: false, error: "invalid_status" };
    }
  } else {
    return { success: false, error: "not_found" };
  }
}
```

**Prefer (early returns flatten the control flow):**
```typescript
function processOrder(order: Order | null): Result {
  if (!order) return { success: false, error: "not_found" };
  if (order.status !== "pending") return { success: false, error: "invalid_status" };
  if (order.items.length === 0) return { success: false, error: "empty_order" };

  // actual work at top level — readable, debuggable, greppable
  return { success: true };
}
```

---

## 3. The 3-Point DRY Barrier

Do not abstract a pattern until all three conditions are true:
1. At least **two real, existing** call sites use the same logic.
2. Both call sites require **identical** mutation semantics going forward.
3. The abstraction has a **clean, non-conjunction name** (not `UserOrOrgProcessor`).

If any condition is not met, tolerate the duplication. The wrong abstraction is more expensive than the right duplication.

---

## 4. Single Responsibility (The One Thing Rule)

A function has one responsibility if its name can be completed with a single verb and noun:
- `createOrder` ✓
- `validateAndCreateOrderAndSendNotification` ✗ (three responsibilities)

If a function's name requires "and" or "or," decompose it.

---

## 5. Explicit Over Implicit

Reject:
- Magic decorators that hide control flow (`@Transactional`, `@Cacheable`)
- Global singletons accessed without injection
- Monkey-patching or prototype mutation at module initialization
- Implicit event buses where `publish(event)` causes invisible side effects

Prefer code where "Go to Definition" traces every side effect to its source.

---

## 6. Strict Types Without Type Gymnastics

Use TypeScript's type system to prevent invalid states from compiling. Stop before the generics become a Turing-complete riddle.

**Useful:**
```typescript
type UserId = string & { readonly brand: "UserId" };
type OrgId = string & { readonly brand: "OrgId" };
// Now you cannot accidentally pass an OrgId where a UserId is required.
```

**Type gymnastics (delete this):**
```typescript
type DeepPartial<T> = T extends object
  ? { [P in keyof T]?: DeepPartial<T[P]> }
  : T;
// If you need this, your data model has a problem.
```

**Rules:**
- Ban `any` and `@ts-ignore` — if the type system cannot express it, the design is wrong
- Use `unknown` with explicit narrowing instead of `any` for untrusted input
- Use discriminated unions instead of optional fields that signal internal state
