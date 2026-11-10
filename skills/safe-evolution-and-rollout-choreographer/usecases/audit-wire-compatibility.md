# Audit Wire Compatibility: $N-1 \leftrightarrow N+1$ Schema Review

Use this workflow when auditing pull requests, updating serialization schemas (Protobuf, Thrift, JSON, Avro, GraphQL), or reviewing network boundary contracts.

## Step-by-Step Audit Procedure

### 1. Enforce Additive-Only Modification
1. Check the diff for any deleted fields, renamed properties, or altered data types.
2. If an existing field was removed or renamed in a single pull request:
   - **Immediately reject the PR.**
   - Enforce the 4-stage Expand-Contract deprecation cycle.
3. Verify that all newly added fields are optional and supply deterministic fallback defaults.

### 2. Verify Tolerant Reader Deserialization
1. Audit deserializer configuration in both consumer and producer codebases:
   - In JSON (Java/Jackson): Verify `DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES` is set to `false`.
   - In TypeScript/Zod: Ensure schemas use `.passthrough()` or `.strip()`, never `.strict()` on shared wire payloads.
   - In Protobuf: Verify unknown fields are preserved in raw byte buffers rather than discarded or rejected.

### 3. Audit Protocol-Specific Wire Invariants
- **Protobuf (proto3):**
  - Verify new fields use new, strictly increasing tag numbers.
  - Check that no deleted tags are reused; ensure retired tags are declared in `reserved <tag_num>;`.
  - Confirm numeric types have not changed (e.g. `int32` to `int64` is wire-incompatible).
- **Apache Thrift:**
  - Verify field IDs are unique, positive integers.
  - Verify deprecated fields retain `// deprecated` annotations.
- **REST / JSON:**
  - Verify response shapes do not convert single values into arrays or objects without a new property name.

### 4. Verify Backward and Forward Tolerance
1. Construct a matrix test case:
   - Serializer $N$ $\rightarrow$ Deserializer $N+1$: must parse without errors and apply defaults for missing new fields.
   - Serializer $N+1$ $\rightarrow$ Deserializer $N$: must parse without errors and ignore unfamiliar new fields.
2. Confirm that legacy mobile clients ($N-1 \dots N-k$) continue to function cleanly.

### 5. Automated Static Audit
Run the rollout guard against the pull request diff:
```bash
python3 scripts/rollout_guard.py scan --base HEAD --json
```
Verify zero blocker findings before approving the pull request.
