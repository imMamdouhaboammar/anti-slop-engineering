# Reference: Wire Compatibility & $N-1 \leftrightarrow N+1$ Coexistence

> Fleet deployments are asynchronous and staggered; production is permanently heterogeneous.

## The Coexistence Invariant

In high-scale engineering organizations (Meta, Google, Amazon), code deployments across thousands of containers, regions, and availability zones take minutes to hours. Simultaneously, native mobile clients (iOS, Android) remain in the wild running software versions released weeks, months, or years prior.

$$\text{Fleet Version } N \quad \text{and} \quad \text{Fleet Version } N+1 \quad \text{coexist on the same wire}$$

Any deployment where version $N+1$ cannot parse data produced by version $N$, or where version $N$ crashes upon receiving data produced by version $N+1$, is a severe deployment defect.

---

## The Four Wire Compatibility Axioms

1. **Additive-Only Evolution:** You may add new fields, new endpoints, and new optional parameters. You may never remove fields, change field types, or rename fields in a single step.
2. **The Tolerant Reader Mandate:** Every service must parse only the fields it requires and silently ignore unknown fields. Deserializers configured to reject unexpected keys (e.g. `failOnUnknownProperties = true` in Jackson, or unstripped schemas) are strictly prohibited on shared network boundaries.
3. **Safe Defaulting for Missing Fields:** When a new pod ($N+1$) reads a payload produced by an older pod ($N$), any newly added fields will be absent. The code in $N+1$ must gracefully supply safe, deterministic default values without throwing null pointer or missing property errors.
4. **Permanent Tag Immutability (Protobuf & Thrift):** Field index tags and IDs must never be renumbered, reassigned, or reused. Once tag `4` is assigned to `string user_email`, tag `4` is permanently bound to that conceptual type even after retirement.

---

## Wire Protocol Matrices

### 1. Protocol Buffers (proto3) & gRPC

| Action | Safety Status | Rule |
| --- | --- | --- |
| Adding an optional scalar field | Safe | Assign new, unused tag number. Never reuse deleted tag numbers. |
| Removing an active field | **Fatal in single PR** | Mark field as `reserved <tag_number>, "<field_name>";`. Keep reading in application code until older fleet versions are decommissioned. |
| Changing field type | **Fatal** | Even `int32` to `int64` is wire-incompatible in varint encoding. Add a new field with a new tag number instead. |
| Adding an enum variant | Caution | Unknown enum variants decode to 0 or numeric value in proto3. Older readers must handle unrecognized enum integers without crashing. |
| Renaming a field | Safe on wire, risky in JSON | Wire format uses tag numbers; however, JSON mapping uses field names. Do not rename if JSON gateway is in use. |

### 2. JSON / REST APIs

| Action | Safety Status | Rule |
| --- | --- | --- |
| Adding a key to JSON response | Safe (with Tolerant Reader) | All consumers must ignore unexpected keys. Verify client libraries do not enforce strict closed-shape parsing. |
| Removing a key from JSON response | **Fatal in single PR** | Requires Expand-Contract deprecation. Dual-emit for at least one full deployment cycle and verify zero client access via access logs. |
| Changing value type (e.g. string to array) | **Fatal** | Add a new key (e.g. `tags` alongside deprecated `tag`). Client parsers will throw unhandled type casting errors otherwise. |
| Adding required request body field | **Fatal to $N-1$ clients** | Any new request attribute must be optional with a server-side default. Old mobile apps cannot send fields they do not know exist. |

### 3. Apache Thrift (Meta Legacy & Internal RPC)

- Field IDs must be strictly positive and unique.
- Field types must match binary protocol signatures.
- Deprecated fields must be annotated as `// deprecated` and retained in `.thrift` definitions until all upstream services upgrade.

---

## The Four-Stage Expand-Contract Deprecation Cycle

When an API field, RPC parameter, or schema column must be renamed or retired, follow this four-stage deployment cycle:

```
Stage 1: EXPAND
  - Introduce new field alongside existing field.
  - Server writes to both fields; reads from legacy field.
  - Verification: N-1 and N+1 both receive necessary data.

Stage 2: DUAL-READ & SHADOW
  - Server reads from new field if present, falling back to legacy field.
  - Clients updated to send and read new field.
  - Verification: Telemetry confirms >99.99% of traffic utilizes new field.

Stage 3: CONTRACT (READ-ONLY LEGACY)
  - Mark legacy field as deprecated in schema and documentation.
  - Server ceases writing to legacy field if safe, or writes dummy compatibility value.
  - Verification: Zero errors reported across fleet for 14 continuous days.

Stage 4: DECOMMISSION
  - Delete legacy field from schema definitions.
  - Mark tag or field name as reserved in schema definitions.
```

---

## Pre-Release Wire Verification Checklist

- [ ] Does every newly added field declare an explicit fallback default?
- [ ] Are JSON deserializers configured to ignore unknown properties (`passthrough` or `strip`)?
- [ ] Are Protobuf/Thrift tags verified against the historical schema repository to guarantee zero tag collision?
- [ ] Does any existing mobile client version ($N-1 \dots N-k$) still consume any field scheduled for deletion?
- [ ] Have integration tests executed with $N$ sending to $N+1$, and $N+1$ sending to $N$?
