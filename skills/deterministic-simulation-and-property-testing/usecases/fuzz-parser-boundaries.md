# Usecase: Fuzz Parser & Boundary Deserializers

Step-by-step workflow for implementing structure-aware fuzzing on untrusted parsers, decoders, and API entry points.

## When to Use
- Implementing custom binary or text protocol parsers (RPC, JSON, YAML, Protobuf, CSV).
- Validating external webhooks, file upload parsers, and untrusted payload unpackers.
- Auditing against stack overflow (recursion depth) and memory exhaustion (allocation bombs).

## Workflow

### 1. Define Resource Boundaries
In the parser under test, enforce explicit bounds before parsing deep syntax:
```typescript
export function parseUntrusted(raw: string, maxBytes = 1048576, maxDepth = 16): ParsedData {
  if (raw.length > maxBytes) {
    throw new PayloadTooLargeError(`Payload length ${raw.length} exceeds ${maxBytes} byte limit`);
  }
  // Enforce recursion depth counter inside parse loop
}
```

### 2. Implement Grammar-Aware Mutator
Construct an arbitrary generator matching the schema grammar:
```typescript
import fc from "fast-check";

const arbGrammarToken = fc.oneof(
  fc.string(),
  fc.integer(),
  fc.boolean(),
  fc.constant(null),
  fc.unicodeString({ minLength: 0, maxLength: 500 })
);
```

### 3. Author Fuzz Harness
Assert crash-freedom and structured error rejection over $\ge 5,000$ iterations:
```typescript
test("untrusted parser survives 5000 structure-aware mutations without unhandled panics", () => {
  fc.assert(
    fc.property(arbGrammarTree, (tree) => {
      const serialized = serializeTree(tree);
      try {
        const result = parseUntrusted(serialized);
        expect(result).toBeDefined();
      } catch (err: unknown) {
        expect(err).toBeInstanceOf(DomainParseError);
      }
    }),
    { numRuns: 5000 }
  );
});
```

### 4. Verify Against Allocation Bombs
Generate deep nested payloads (e.g. 50 levels of nesting) and large repetitive arrays. Verify the parser rejects them with a clean `RecursionDepthExceededError` in under $10\text{ms}$ without spiking heap allocations or exhausting the call stack.
