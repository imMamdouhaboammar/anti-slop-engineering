# Wire Compatibility Matrix (Forward & Backward Compatibility)

## 1. Formal Definitions: Backward vs Forward Wire Compatibility

During a rolling deployment or multi-version client window, services communicate via serialized messages (JSON over HTTP, Protobuf over gRPC, GraphQL queries, or Kafka/PubSub events).

- **Backward Compatibility (New Reader $\leftarrow$ Old Writer):** Code Version $N$ can cleanly read and process payloads produced by Code Version $N-1$ (e.g., new backend server receiving requests from an old mobile app, or reading historical queue messages).
- **Forward Compatibility (Old Reader $\leftarrow$ New Writer):** Code Version $N-1$ can cleanly read and process payloads produced by Code Version $N$ (e.g., old mobile app receiving responses from a newly deployed backend server, or an $N-1$ worker pod consuming an event published by an $N$ pod).

**Postel's Robustness Principle (Hardened for Zero-Trust):**
- **Conservative Writer:** Never emit a field change that removes, renames, or alters the type/semantics of an attribute expected by Version $N-1$.
- **Tolerant Reader:** Parse known fields strictly at the boundary, ignore unrecognized additive fields (do not throw on unknown properties in client response parsers), and supply deterministic defaults when optional fields are absent.

---

## 2. REST / JSON Wire Compatibility Rules

| Change Type | Request Payload (Client $\rightarrow$ Server) | Response Payload (Server $\rightarrow$ Client) | Safe Zero-Downtime Mitigation |
| --- | --- | --- | --- |
| **Add optional field** | **SAFE** (if server provides default when $N-1$ omits it) | **SAFE** (if $N-1$ client ignores unknown keys) | Default to `undefined`/`null` on server; configure client parsers not to reject unknown response keys |
| **Add required field** | **BREAKING** ($N-1$ clients omit it $\rightarrow$ `400 Bad Request`) | **SAFE** (additive for $N-1$ clients) | Add as optional in Phase 1; synthesize default on server until $N-1$ clients reach 0% |
| **Remove or rename field** | **BREAKING** ($N-1$ clients still send old field if server `.strict()` rejects it) | **BREAKING** ($N-1$ clients crash reading `undefined` property) | Emit **both** old and new fields in response (Dual-Payload); accept both in request |
| **Change field type** (e.g. `number` $\rightarrow$ `string`, `object` $\rightarrow$ `array`) | **BREAKING** | **BREAKING** | Introduce a new field name (`amount_minor_units` alongside `amount`) or gate via Stripe-style API version header |
| **Tighten nullability** (`string \| null` $\rightarrow$ `string`) | **BREAKING** ($N-1$ sends `null`) | **SAFE** (subset of previous domain) | Coerce `null` to safe fallback on server request parser during transition |
| **Loosen nullability** (`string` $\rightarrow$ `string \| null`) | **SAFE** (superset of previous domain) | **BREAKING** ($N-1$ client calls `.trim()` on `null` $\rightarrow$ `TypeError`) | Never return `null` on a previously non-null response field; use empty value or new nullable field |
| **Add new Enum value** | **SAFE** (server accepts wider set) | **BREAKING** ($N-1$ client exhaustive `switch` throws on unknown enum) | Map new enum variant to safe legacy fallback for $N-1$ callers, or gate behind API version header |

---

## 3. Protocol Buffers (Protobuf v3 / gRPC) Compatibility Rules

Protobuf binary wire encoding relies entirely on **field tag numbers** (`1`, `2`, `3`...) and **wire types** (`VARINT`, `LEN`, `I64`, `I32`), not field names (unless JSON-encoded via `protojson`).

### Non-Negotiable Protobuf Invariants
1. **Never change a field's tag number.** Changing `string email = 2;` to `string email = 3;` destroys binary compatibility immediately.
2. **Never reuse a deleted tag number or field name.** When removing a field in Phase 3 (Contract), you MUST permanently reserve both the tag and the name (for `protojson` safety):
   ```protobuf
   message Invoice {
     reserved 4, 8 to 11;
     reserved "legacy_tax_rate", "old_customer_ref";

     string id = 1;
     int64 amount_cents = 2;
     string currency = 3;
     int32 tax_basis_points = 12; // New expanded field on fresh tag 12
   }
   ```
3. **Wire-compatible type promotions only:**
   - `int32`, `uint32`, `int64`, `uint64`, and `bool` are wire-compatible (`VARINT`), though truncation occurs if a 64-bit value is read by a 32-bit $N-1$ reader.
   - Changing `int32` to `sint32` is **BREAKING** (`sint32` uses ZigZag encoding).
   - Changing a scalar field to `repeated` or `map` is **BREAKING**.
4. **Always include an `UNSPECIFIED = 0` enum default:**
   ```protobuf
   enum PaymentStatus {
     PAYMENT_STATUS_UNSPECIFIED = 0;
     PAYMENT_STATUS_PENDING = 1;
     PAYMENT_STATUS_SUCCEEDED = 2;
     PAYMENT_STATUS_FAILED = 3;
   }
   ```
   In proto3, if an $N-1$ reader receives an unrecognized enum integer from a Version $N$ writer, it preserves the raw integer or falls back to `0` (`UNSPECIFIED`) instead of crashing—provided the application code handles `UNSPECIFIED` gracefully.

---

## 4. GraphQL Schema Evolution Rules

GraphQL lacks path-based `/v1`, `/v2` URL versioning by design; the schema must evolve continuously in place:

1. **Additive-Only Field Evolution:** Add new fields or types without altering existing field signatures.
2. **Never change an output field from Non-Null (`String!`) to Nullable (`String`)** without auditing client codegen—typed mobile clients (Apollo iOS / Kotlin) generate non-optional types for `!` fields and will fail decoding if `null` is returned.
3. **Never change an input argument from Nullable (`input: String`) to Non-Null (`input: String!`)**—existing client queries omitting that argument will fail GraphQL validation immediately (`400`).
4. **Formal Deprecation Lifecycle:**
   ```graphql
   type User {
     id: ID!
     "Deprecated: Use givenName and familyName instead. Scheduled for removal after 2027-02-01."
     fullName: String! @deprecated(reason: "Use givenName and familyName")
     givenName: String!
     familyName: String!
   }
   ```
   Track field-level resolver telemetry (`graphql_field_usage_total{type="User", field="fullName"}`) and execute Phase 3 removal only when 30-day usage equals `0`.

---

## 5. Stripe-Style Date-Pinned API Version Gates

When a structural contract break is unavoidable for external API consumers, implement **Stripe's Date-Pinned Version Transform Pipeline**:
1. Core domain services always execute against the **latest canonical schema (Version $N$)**.
2. Each API key or request declares its pinned version header (e.g. `X-API-Version: 2026-05-01`).
3. Incoming requests pass through an ordered chain of **Request Upcasters** ($2026\text{-}05\text{-}01 \rightarrow \text{Latest}$).
4. Outgoing responses pass through an ordered chain of **Response Downcasters** ($\text{Latest} \rightarrow 2026\text{-}05\text{-}01$) that synthesize legacy fields (e.g. computing `full_name` from `given_name + " " + family_name`) exclusively for older clients.
