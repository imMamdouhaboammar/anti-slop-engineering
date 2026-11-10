# Use Case: Implement Tainted PII Types

> Step-by-step implementation guide for sealing domain models against accidental log, telemetry, and error serialization leaks.

## Implementation Steps

1. **Define Nominal Branded Types:**
   Create opaque brands for sensitive fields:
   ```typescript
   declare const BrandSymbol: unique symbol;
   export type Branded<T, Brand extends string> = T & { readonly [BrandSymbol]: Brand };
   export type UserEmail = Branded<string, "UserEmail">;
   export type UserPhone = Branded<string, "UserPhone">;
   ```

2. **Implement the `Redacted<T>` Container:**
   Wrap all sensitive primitives in an immutable container that overrides `toString()`, `toJSON()`, and `[util.inspect.custom]` to emit `[REDACTED]`.

3. **Require Audit Context for Unwrapping:**
   Gate the underlying value behind an explicit unwrap method:
   ```typescript
   user.email.reveal({ actorId: "auth_service", reason: "send_verification_email", correlationId: ctx.id });
   ```

4. **Audit Call Sites with Static Analysis:**
   Run static lint checks or `scripts/privacy_guard.py --source <file>` to verify that no raw unredacted fields are passed to `console.log`, `logger.*`, or analytics SDKs.
