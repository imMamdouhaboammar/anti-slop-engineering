# Workflow: Author a Property-Based & Metamorphic Invariant Suite

Use this workflow when testing financial/billing arithmetic, fee/tax allocations, currency conversions, parsers, serializers, codecs, compilers, or stateful workflow engines.

## Step-by-Step Procedure

### 1. Identify Universal Domain Invariants (Not Static Examples)
Before writing any test code, list at least two universal properties that must hold for **all** valid inputs:
1. **Conservation Invariant:** Does the sum of output allocations plus fees equal the exact input principal ($\sum \text{parts} = \text{total}$)?
2. **Roundtrip Invertibility:** Does `decode(encode(x))` or `parse(format(x))` reconstruct `x` losslessly across arbitrary payloads?
3. **Idempotency / Algebraic Law:** Does applying an operation twice produce the same state as applying it once ($f(f(s, x)) \equiv f(s, x)$)?
4. **Metamorphic Relation:** If we permute, scale, or partition the input $x \to T(x)$, how must the output $f(T(x))$ relate to $f(x)$?
5. **State Machine Safety:** Across any sequence of valid or invalid commands $\vec{c}$, can a terminal state (`RELEASED`, `REFUNDED`, `CANCELLED`) ever transition backwards or violate balance conservation?

### 2. Build Adversarial Generators with Shrinking
1. Use `fast-check` (TypeScript/JS), `Hypothesis` (Python), `proptest` (Rust), or `rapid` (Go).
2. Configure generators to include adversarial boundary values: `0`, `1`, prime numbers, `MAX_SAFE_INTEGER`, skewed weights (`[1, 9999]`), empty collections, and multi-byte UTF-8/UTF-16 surrogate pairs.
3. Set `numRuns >= 200` (or `max_examples=200`) and keep shrinking enabled so any failing run reduces to the smallest counterexample.

### 3. Assert Independent Oracles (Never Duplicate Production Math)
1. Never copy the production implementation formula into the test assertion.
2. Assert the algebraic invariant (`sum === grossCents`), compare against a simpler reference model, or verify the inverse operation.
