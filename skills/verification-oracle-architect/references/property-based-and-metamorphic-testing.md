# Property-Based & Metamorphic Testing Reference

## 1. Framework Selection by Language

| Ecosystem | Canonical Property Library | Stateful Model Runner |
| --- | --- | --- |
| TypeScript / JavaScript (Bun / Vitest) | `fast-check` (`fc.assert(fc.property(...))`) | `fc.commands()` / `fc.modelRun()` |
| Python (`pytest` / `unittest`) | `hypothesis` (`@given(st.integers(), ...)`) | `RuleBasedStateMachine` |
| Rust (`cargo test`) | `proptest` (`proptest! { ... }`) | `proptest-state-machine` |
| Go (`go test`) | `pgregory.net/rapid` (`rapid.Check(t, ...)`) | `rapid.StateMachine` |

---

## 2. Financial Allocation Conservation & Metamorphic Invariants

Consider a multi-recipient basis-point fee and payout allocator using Largest Remainder Method (Hamilton's method) so not a single cent is ever lost or invented:

```ts
export interface AllocationResult {
  readonly feeCents: number;
  readonly payoutsCents: readonly number[];
}

export function allocatePayoutsExactCents(
  grossCents: number,
  weightsBps: readonly number[],
  platformFeeBps: number
): AllocationResult {
  if (!Number.isSafeInteger(grossCents) || grossCents < 0) {
    throw new RangeError("grossCents must be a non-negative safe integer");
  }
  if (platformFeeBps < 0 || platformFeeBps > 10_000) {
    throw new RangeError("platformFeeBps must be between 0 and 10000");
  }
  const weightSum = weightsBps.reduce((a, b) => a + b, 0);
  if (weightsBps.length === 0 || weightSum <= 0) {
    throw new RangeError("weightsBps must contain positive weights");
  }

  const feeCents = Math.floor((grossCents * platformFeeBps) / 10_000);
  const distributableCents = grossCents - feeCents;

  const floors = new Array<number>(weightsBps.length);
  const remainders = new Array<{ index: number; rem: number }>(weightsBps.length);
  let allocatedSum = 0;

  for (let i = 0; i < weightsBps.length; i++) {
    const numerator = distributableCents * weightsBps[i];
    const floored = Math.floor(numerator / weightSum);
    floors[i] = floored;
    allocatedSum += floored;
    remainders[i] = { index: i, rem: numerator % weightSum };
  }

  let leftoverCents = distributableCents - allocatedSum;
  remainders.sort((a, b) => (b.rem !== a.rem ? b.rem - a.rem : a.index - b.index));

  for (let i = 0; i < leftoverCents; i++) {
    floors[remainders[i].index] += 1;
  }

  return { feeCents, payoutsCents: floors };
}
```

### Property & Metamorphic Verification Oracle

Verify universal properties across hundreds of generated inputs without duplicating the Hamilton remainder loop in the test:

1. **Conservation of Money Invariant:**
   $$\text{feeCents} + \sum_{i} \text{payoutsCents}[i] = \text{grossCents}$$
2. **Fairness / Bounded Error Invariant:**
   For every recipient $i$ with exact rational entitlement $q_i = \frac{(\text{grossCents} - \text{feeCents}) \cdot w_i}{\sum w}$,
   $$\lfloor q_i \rfloor \le \text{payoutsCents}[i] \le \lceil q_i \rceil$$
3. **Metamorphic Permutation Invariance:**
   Reversing or permuting `weightsBps` produces the exact same `feeCents` and the exact same sorted multiset of `payoutsCents`.
4. **Metamorphic Monotonic Scaling:**
   Increasing `grossCents` to `grossCents + delta` ($\text{delta} > 0$) while keeping weights and fee rate constant never decreases total distributed payouts.

---

## 3. Parser & Serializer Invertibility (Roundtrip Oracle)

Whenever testing a parser, codec, cursor serializer, or wire protocol:

```ts
// Universal Roundtrip Property: decode(encode(msg)) === msg
for (let run = 0; run < 250; run++) {
  const generatedReceipt = generateArbitraryReceipt(prng, run);
  const wireBytes = encodeTransferReceiptBinary(generatedReceipt);
  const decoded = decodeTransferReceiptBinary(wireBytes);

  if (
    decoded.tenantId !== generatedReceipt.tenantId ||
    decoded.idempotencyKey !== generatedReceipt.idempotencyKey ||
    decoded.amountCents !== generatedReceipt.amountCents ||
    decoded.executedAtMs !== generatedReceipt.executedAtMs
  ) {
    throw new Error(`Roundtrip invertibility failed on run ${run}`);
  }
}
```
