# Property-Based Testing & Automated Shrinking

Principles and patterns for replacing example-based tests with generative invariant verification.

## The Flaw of Example-Based Testing

Example-based tests test point values:
```typescript
test("adds items", () => {
  expect(addToCart(cart, item, 2)).toEqual({ count: 2, total: 20 });
});
```
This tests one path through the code. In real production workloads, edge cases hide in integer overflows, negative quantities, Unicode homoglyphs, empty collections, zero division, and extreme combinations of valid inputs.

Property-based testing (PBT) tests algebraic laws and invariants across thousands of pseudo-randomly generated inputs:

$$\forall x \in \text{Domain}, \quad \text{Invariant}(f(x)) = \text{true}$$

## The Five Canonical Invariant Categories

| Invariant Category | Mathematical Formulation | Practical System Example |
| --- | --- | --- |
| **Round-Trip Invertibility** | $\text{decode}(\text{encode}(x)) \equiv x$ | Serialization/deserialization, compression, encryption, tokenization |
| **Idempotency** | $f(f(x)) \equiv f(x)$ | Payment processing, cache warming, state-machine synchronization, deletion |
| **Metamorphic Relations** | $f(T(x)) \equiv T'(f(x))$ | Query optimization, search filters, sorting, coordinate transformations |
| **Model Equivalence** | $f_{\text{system}}(x) \equiv f_{\text{oracle}}(x)$ | High-performance optimized implementation compared against simple reference model |
| **Conservation Laws** | $\sum \text{State}_{\text{before}} \equiv \sum \text{State}_{\text{after}}$ | Double-entry ledgers, mass/energy conservation, token balance transfer |

## Automated Shrinking

When a property test fails on a complex input (e.g. an array of 500 random elements), raw counterexamples are unreadable.

**Shrinking** is the deterministic process of recursively reducing the failing input to its minimal reproducible form:

```
Initial Failing Input:
[492, -1829, 0, 12, 99999, -1, 42, 888, 301, ...] (length 256)
  ↓ Shrink step 1 (halve array)
[492, -1, 42, ...] (length 16)
  ↓ Shrink step 2 (reduce numbers toward 0)
[-1]
Minimal Counterexample: [-1] (Root cause: negative integer unhandled)
```

### Shrinking Guidelines
1. **Never disable shrinking:** Fast execution is useless if root-cause debugging requires hours of manual minimization.
2. **Deterministic shrinking paths:** Ensure shrinks are reproducible; shrinking algorithms must not rely on unseeded randomness.
3. **Bounded shrinking depth:** Prevent infinite shrinking loops by ensuring shrink candidates strictly decrease in complexity.

## Frameworks Matrix

| Language | Primary Framework | Key Feature |
| --- | --- | --- |
| TypeScript / JavaScript | `fast-check` | Synchronous & asynchronous arbitraries, model-based commands, full shrink tree |
| Python | `Hypothesis` | Conjectural engine, database of previous failures, deep AST-level integration |
| Rust | `proptest` / `quickcheck` | Macro-based arbitrary generation, deterministic seeds, integration with cargo test |
| Go | `pgregory.net/rapid` | Zero-reflection fast generator, model-based state machine runner |

## Red-Green Mutation Falsification

A property test is unverified until shown to fail when a deliberate bug is introduced:
1. **Inject Mutation:** Change `<=` to `<` in boundary condition, or delete an idempotency check.
2. **Observe Red Failure:** The property runner must fail, report the failing seed, and shrink the input to the exact counterexample.
3. **Restore Green Implementation:** Restore correct code; property test must pass across $\ge 1,000$ iterations.
