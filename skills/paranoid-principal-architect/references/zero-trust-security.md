# Zero-Trust Security & Threat Defense

## 1. Zero-Trust Philosophy: The Battlefield Axiom

Every system connected to a network is under continuous hostile reconnaissance. Zero-Trust mandates that no entity—whether inside or outside the network boundary—is trusted by default:
- **Clients are Hostile:** The browser, mobile app, and API caller are completely controlled by potential adversaries. Never trust client-supplied user IDs, roles, balances, prices, or timestamps.
- **Networks are Hostile:** Packets can be intercepted, delayed, replayed, or spoofed. All transport must be encrypted (TLS 1.3), authenticated, and verified.
- **Inputs are Exploit Vectors:** Every byte received must be subjected to runtime schema validation and sanitization.

---

## 2. Boundary Validation: Parse, Don't Validate

Validation functions that return booleans (`isValid(input)`) leave untyped, unsanitized objects in circulation. The Paranoid Architect enforces **Parse, Don't Validate**: transform untrusted input at the perimeter into strictly typed, sanitized domain representations.

### Zod / Valibot Schema Invariants
1. **Strip Unknown Fields:** Reject or strip undeclared fields to defeat mass-assignment and prototype-pollution attacks:
   ```typescript
   import { z } from "zod";

   export const CreatePaymentSchema = z.object({
     idempotencyKey: z.string().uuid(),
     amountInCents: z.number().int().positive().max(10_000_000), // Max $100k
     currency: z.enum(["USD", "EUR", "GBP"]),
     recipientId: z.string().regex(/^usr_[a-zA-Z0-9]{24}$/)
   }).strict(); // Strip or reject extraneous attributes
   ```
2. **Bounds on All Strings and Arrays:** Every string must have a `.max(N)` length limit. Every array must have a `.max(N)` item count limit to prevent memory exhaustion.
3. **Parse Early:** Execute schema parsing at the earliest entry point (e.g., HTTP handler, queue worker, WebSocket frame processor). If parsing fails, terminate immediately with a deterministic `400 Bad Request` and sanitized error structure.

---

## 3. Data-Layer Authorization & Tenancy Enforcement

Relying on frontend checks or top-level route middleware (`isAdmin = true`) is an invitation to Broken Object-Level Authorization (BOLA / IDOR).

### The Invariant
Every database query, mutation, and cache lookup must scope access to the authenticated user and tenant within the SQL/ORM statement itself:

```sql
-- CORRECT: Ownership enforced at query layer
UPDATE documents
SET content = :content, updated_at = :now
WHERE id = :document_id
  AND tenant_id = :auth_tenant_id
  AND owner_id = :auth_user_id;

-- FATAL DEFECT (BOLA Vulnerability):
-- Finding the document first, then checking doc.ownerId in memory
SELECT * FROM documents WHERE id = :document_id;
-- If race condition or logic flaw occurs, unauthorized write executes!
```

---

## 4. Cryptographic Hygiene & Timing Defense

### Constant-Time Equality Comparisons
Never compare passwords, API keys, HMAC signatures, or session tokens using standard equality (`===` or `==`). Standard string equality short-circuits on the first mismatched byte, leaking secret length and content through sub-microsecond timing discrepancies.

```typescript
import { timingSafeEqual } from "node:crypto";

export function constantTimeStringCompare(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf-8");
  const bufB = Buffer.from(b, "utf-8");

  if (bufA.length !== bufB.length) {
    // Perform dummy comparison to equalize time profile
    timingSafeEqual(bufA, bufA);
    return false;
  }
  return timingSafeEqual(bufA, bufB);
}
```

### Cryptographically Secure Randomness
`Math.random()` uses pseudo-random number generators (like Xoroshiro128+) that are trivially predictable given a few generated values.
- **Allowed:** `crypto.randomUUID()`, `crypto.getRandomValues(new Uint8Array(N))`.
- **Prohibited:** `Math.random()`, predictable incrementing IDs for public resources.

### Fail-Fast Secret Hydration
All required environment variables (encryption keys, database URLs, signing secrets) must be validated on process initialization before opening network listeners:
```typescript
const EnvSchema = z.object({
  DATABASE_URL: z.string().url(),
  SESSION_SECRET: z.string().min(32),
  NODE_ENV: z.enum(["development", "test", "production"])
});

export const env = EnvSchema.parse(process.env);
```

---

## 5. Web Security Headers & DOM Safety

### DOM Injection Defense
Never use unsanitized HTML sinks:
- **Prohibited:** `element.innerHTML`, `element.outerHTML`, `document.write()`, `eval()`, `setTimeout(string)`, `dangerouslySetInnerHTML`.
- **Mandatory:** `element.textContent`, DOM node creation (`document.createElement()`), or sanitized output via Trusted Types.

### Modern Security Headers
Every HTTP response serving web content must include:
```http
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self';
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Cookie Hardening
Session tokens must be delivered exclusively in hardened cookies:
- `HttpOnly`: Prevents client-side script access (mitigating XSS theft).
- `Secure`: Enforces transmission exclusively over TLS.
- `SameSite=Strict` (or `Lax` for OAuth redirect targets): Mitigates Cross-Site Request Forgery (CSRF).

---

## 6. Economic Denial of Service (EDoS) & Resource Caps

Malicious actors or runaway bots can bankrupt infrastructure or exhaust memory by sending massive payloads or pathological requests:
1. **Body Size Limits:** Impose strict byte limits before parsing (e.g., max 100KB for JSON, max 5MB for multi-part file uploads).
2. **ReDoS Defense:** Never evaluate unbounded regular expressions with nested quantifiers (e.g. `/(a+)+$/`) against user input. Use Google RE2 or linear-time DFA regex engines.
3. **Expensive Compute Gating:** Hash computations (Argon2, bcrypt), image transformations, and LLM calls must be gated behind rate limiters (e.g., sliding window token buckets) and user authorization quotas.
