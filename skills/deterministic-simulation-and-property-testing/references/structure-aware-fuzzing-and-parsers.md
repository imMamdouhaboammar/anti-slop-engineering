# Structure-Aware Fuzzing & Untrusted Parsers

Methodology for fuzzing parsers, deserializers, and network protocol decoders.

## Dumb Fuzzing vs Structure-Aware Fuzzing

Dumb fuzzing flips arbitrary bytes at random offsets in a byte buffer:
```
Raw bytes: [0x7B, 0x22, 0x61, 0x22, 0x3A, 0x31, 0x7D]  // {"a":1}
Mutated:   [0x7B, 0xFF, 0x61, 0x22, 0x3A, 0x31, 0x7D]  // {a":1} -> Syntax Error
```
In structured protocols (JSON, Protobuf, YAML, SQL, HTTP/2, GraphQL), dumb mutations are rejected immediately by the lexical tokenizer. The deep semantic logic—deserialization, type casting, validation guards, and object construction—remains unexercised.

**Structure-Aware Fuzzing** generates and mutates valid or near-valid syntax trees based on the formal grammar:
- Modifies tree nodes (e.g. replaces an integer with `Number.MAX_SAFE_INTEGER + 1`).
- Duplicates fields (testing duplicate key handling and prototype pollution).
- Deepens nesting depth up to and beyond the recursion limit.
- Injects Unicode boundary strings (RTL overrides, null bytes, zero-width spaces).

## The Four Parser Invariants

Every parser or deserializer accepting untrusted input must prove four invariants:

| Invariant | Threat Vector | Defense Mechanism |
| --- | --- | --- |
| **Crash Freedom** | Unhandled panics, segfaults, uncaught exceptions | Comprehensive error mapping returning structured rejection objects |
| **Bounded Recursion Depth** | Stack overflow via deeply nested arrays/objects (`[[[[...]]]]`) | Explicit depth counter; reject when `depth > MAX_DEPTH` (e.g. 16) |
| **Bounded Memory Allocation** | Decompression bombs, allocation amplification ($O(N^2)$) | Explicit payload byte cap (e.g. $\le 10\text{MB}$); streaming chunk limits |
| **Algorithmic Complexity (ReDoS)** | Catastrophic regex backtracking or hash-table collision bombs | Linear-time regex engines (RE2/Rust `regex`), siphash/seeded hashers |

## Fuzzing Engine Matrix

| Ecosystem | Engine | Integration Pattern |
| --- | --- | --- |
| C / C++ / Native | `libFuzzer` / `AFL++` | `LLVMFuzzerTestOneInput` with `LLVMFuzzerCustomMutator` |
| Rust | `cargo-fuzz` / `arbitrary` | `fuzz_target!(|data: StructuredInput| { ... })` |
| Go | Native Fuzzing (`testing.F`) | `f.Fuzz(func(t *testing.T, payload []byte) { ... })` |
| Python | `Atheris` / `Hypothesis` | `@given(from_schema(MySchema)) def test_parse(payload): ...` |
| TypeScript / Node.js | `fast-check` / `jazzer.js` | `fc.assert(fc.property(arbStructuredPayload, (p) => { ... }))` |

## Writing a Structure-Aware Fuzz Target

```typescript
import fc from "fast-check";

const arbJsonLeaf = fc.oneof(
  fc.string(),
  fc.double(),
  fc.integer(),
  fc.boolean(),
  fc.constant(null)
);

const arbJsonTree = fc.letrec((tie) => ({
  tree: fc.oneof(
    { depthSize: "small" },
    arbJsonLeaf,
    fc.array(tie("tree")),
    fc.dictionary(fc.string(), tie("tree"))
  ),
})).tree;

test("parser proves crash-freedom and memory bounds under structured fuzzing", () => {
  fc.assert(
    fc.property(arbJsonTree, (data) => {
      const raw = JSON.stringify(data);
      try {
        const result = parseUntrustedPayload(raw, 65536, 16);
        expect(result).toBeDefined();
      } catch (err: unknown) {
        // Must reject gracefully with a typed DomainError, never an uncaught crash
        expect(err).toBeInstanceOf(Error);
      }
    }),
    { numRuns: 5000 }
  );
});
```
