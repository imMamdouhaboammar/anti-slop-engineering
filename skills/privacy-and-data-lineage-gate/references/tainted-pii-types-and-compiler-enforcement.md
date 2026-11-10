# Tainted PII Types & Compiler-Enforced Boundary Sealing

> Protecting user data from the system itself through nominal typing, opaque wrappers, and unredacted serialization bans.

## The Core Hazard: Accidental Internal Leaks

External attackers exploit missing authorization or SQL injection. But 90% of privacy breaches originate from **internal code**:
1. Engineers passing entire `user` objects to `logger.info("User logged in", { user })`, dumping plaintext email, phone, and password hashes into Datadog, CloudWatch, or Sentry.
2. Analytics instrumentation calling `mixpanel.track("checkout_completed", { email: user.email })`, transmitting raw PII to third-party ad networks.
3. Unhandled exception stack traces formatting request bodies containing plaintext credit cards or social security numbers.
4. Developers concatenating raw strings: `` `Processing payment for ${user.email}` `` inside debugging prints.

Relying on human code reviews or regex scrubber proxies at the logging agent layer fails. High-volume systems require **compile-time type separation and opaque wrappers**.

---

## Nominal & Branded Types (Taint Tracking)

In standard TypeScript or Go, `string` represents anything: a SQL query, a UUID, an HTML snippet, or a user's private medical condition. When PII is stored as a raw `string`, the compiler cannot stop an engineer from passing it to an unredacted log statement.

Branded types create distinct, incompatible nominal types on top of primitive strings:

```typescript
declare const BrandSymbol: unique symbol;

export type Branded<T, Brand extends string> = T & { readonly [BrandSymbol]: Brand };

export type UserEmail = Branded<string, "UserEmail">;
export type PhoneNumber = Branded<string, "PhoneNumber">;
export type NationalId = Branded<string, "NationalId">;
export type PlaintextPassword = Branded<string, "PlaintextPassword">;
```

A function accepting `string` or `UserEmail` cannot accidentally receive an arbitrary unverified string without an explicit parsing constructor.

---

## The `Redacted<T>` Opaque Wrapper Pattern

All sensitive domain entities must store PII fields wrapped in a `Redacted<T>` container:

```typescript
import { inspect } from "node:util";

export class Redacted<T> {
  private readonly value: T;
  private readonly brand: string;

  constructor(value: T, brand = "PII") {
    this.value = Object.freeze(value);
    this.brand = brand;
  }

  // 1. String coercion returns constant placeholder
  public toString(): string {
    return `[REDACTED:${this.brand}]`;
  }

  // 2. JSON serialization masks the payload by default
  public toJSON(): string {
    return `[REDACTED:${this.brand}]`;
  }

  // 3. Node.js console.log / util.inspect returns opaque brand indicator
  public [inspect.custom](): string {
    return `[Redacted<${this.brand}>]`;
  }

  // 4. Boundary unwrapping requires explicit, auditable business justification
  public reveal(context: { actorId: string; reason: string; correlationId: string }): T {
    if (!context.actorId || !context.reason) {
      throw new Error("SECURITY_ERROR: Cannot reveal redacted PII without auditable context");
    }
    return this.value;
  }
}
```

### Compiler Invariants

1. **No Implicit Printing:** `console.log("Customer:", user.email)` prints `Customer: [Redacted<Email>]`.
2. **No Implicit Serialization:** `JSON.stringify(user)` outputs `{"id": "123", "email": "[REDACTED:Email]"}`.
3. **No Direct Assignment to Raw Sinks:** Passing `user.email` to `logger.info("msg", { target: user.email })` passes the `Redacted` instance, preventing plaintext leakage.
4. **Controlled Egress Points:** The only way to access the underlying string is calling `.reveal(auditContext)`, which creates an immutable audit trail entry.

---

## Rust Zero-Cost Tainted Types

In Rust microservices, the same guarantee is achieved at zero runtime cost using private fields and custom `Display` / `Debug` implementations:

```rust
use std::fmt;

#[derive(Clone)]
pub struct Redacted<T>(T);

impl<T> Redacted<T> {
    pub fn new(val: T) -> Self {
        Self(val)
    }

    pub fn reveal<'a>(&'a self, _audit: &AuditContext) -> &'a T {
        &self.0
    }
}

impl<T> fmt::Display for Redacted<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[REDACTED]")
    }
}

impl<T> fmt::Debug for Redacted<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Redacted {{ *** }}")
    }
}
```

Deriving standard `Debug` or `Display` on raw structs containing PII is strictly prohibited.
