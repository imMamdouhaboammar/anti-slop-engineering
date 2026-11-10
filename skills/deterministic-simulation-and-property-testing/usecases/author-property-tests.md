# Usecase: Author Property-Based Tests

Step-by-step workflow for converting example-based test suites into generative property tests with automatic shrinking.

## When to Use
- Testing serialization/deserialization routines, codecs, and cryptographic primitives.
- Verifying financial transaction balances and double-entry accounting invariants.
- Testing data structures, search indexes, sorting routines, and query compilers.

## Workflow

### 1. Identify the Domain Invariant
Determine the algebraic property:
- **Round-Trip:** `decode(encode(obj)) == obj`
- **Idempotency:** `process(process(state)) == process(state)`
- **Conservation:** `sum(balances_after) == sum(balances_before)`
- **Metamorphic:** `sort(reverse(list)) == sort(list)`

### 2. Construct Generator Arbitraries
Define input generators covering edge cases:
```typescript
import fc from "fast-check";

const arbTransaction = fc.record({
  sourceAccount: fc.uuid(),
  destAccount: fc.uuid(),
  amountCents: fc.integer({ min: 1, max: 100_000_000 }),
});
```

### 3. Run Property Assertions
Execute across $\ge 1,000$ iterations:
```typescript
test("transfer conserves total ledger balance across 1000 random transactions", () => {
  fc.assert(
    fc.property(arbTransaction, (tx) => {
      const initialTotal = ledger.getTotalBalance();
      ledger.transfer(tx.sourceAccount, tx.destAccount, tx.amountCents);
      const finalTotal = ledger.getTotalBalance();
      expect(finalTotal).toEqual(initialTotal);
    }),
    { numRuns: 1000 }
  );
});
```

### 4. Verify Shrinking & Mutation Falsification
Introduce a deliberate defect (e.g. subtract a transaction fee without crediting a fee account). Run the test:
1. Verify the test fails.
2. Confirm the shrinking engine reduces the failure to a minimal counterexample.
3. Revert the defect and confirm the test returns to green.
