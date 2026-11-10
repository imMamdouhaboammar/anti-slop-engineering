# Deterministic Chaos & Fault Injection Reference

## 1. Seeded PRNG (`Mulberry32`) & Virtual Clock

Never use `Math.random()` or `setTimeout` inside verification suites. Use a deterministic 32-bit PRNG and an explicit Virtual Clock:

```ts
export class SeededPrng {
  private state: number;

  constructor(readonly initialSeed: number) {
    this.state = initialSeed >>> 0;
  }

  nextFloat(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(this.state ^ (this.state >>> 15), 1 | this.state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  nextInt(minInclusive: number, maxInclusive: number): number {
    return minInclusive + Math.floor(this.nextFloat() * (maxInclusive - minInclusive + 1));
  }
}

export class DeterministicVirtualClock {
  private currentMs: number;

  constructor(initialEpochMs = 1_700_000_000_000) {
    this.currentMs = initialEpochMs;
  }

  nowMs(): number {
    return this.currentMs;
  }

  advanceMs(deltaMs: number): void {
    if (deltaMs < 0) {
      throw new RangeError("VirtualClock cannot move backwards unless testing clock skew");
    }
    this.currentMs += deltaMs;
  }
}
```

---

## 2. Deterministic Chaos Storage Proxy (Pre-Commit vs. Post-Commit Faults)

Wrap the Contract-Verified `InMemoryLedgerStorage` in a deterministic chaos interceptor that injects faults according to the seeded PRNG:
- **`pre_commit_abort`:** Fails *inside* `withTransaction` before completion, testing that the fake's snapshot rollback restores `100%` of prior state.
- **`post_commit_ack_drop`:** Allows `withTransaction` to commit durable state inside the storage engine, then throws `SimulatedPostCommitAckDropError` before returning to the caller. When the caller retries with the same `Idempotency-Key`, the service must detect the already-saved `TransferReceipt` and return it without executing a second debit/credit!

```ts
export class SimulatedNetworkDropError extends Error {
  readonly code = "SIMULATED_NETWORK_DROP" as const;
  constructor(readonly phase: "pre_commit" | "post_commit_ack_drop", readonly seed: number) {
    super(`Chaos network drop during ${phase} (seed=0x${seed.toString(16)})`);
  }
}

export interface ChaosFaultConfig {
  readonly preCommitDropProbability: number;
  readonly postCommitAckDropProbability: number;
  readonly simulatedJitterMaxMs: number;
}
```

---

## 3. Deterministic Retry & Saga Verification Pattern

```ts
export async function executeIdempotentTransferWithRetry(
  storage: LedgerStoragePort,
  clock: DeterministicVirtualClock,
  prng: SeededPrng,
  request: {
    readonly tenantId: string;
    readonly idempotencyKey: string;
    readonly fromAccountId: string;
    readonly toAccountId: string;
    readonly amountCents: number;
  },
  maxAttempts = 5
): Promise<TransferReceipt> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await storage.withTransaction(async (tx) => {
        const existingReceipt = await tx.findReceipt(request.tenantId, request.idempotencyKey);
        if (existingReceipt) {
          return existingReceipt;
        }

        const sender = await tx.getAccount(request.tenantId, request.fromAccountId);
        const receiver = await tx.getAccount(request.tenantId, request.toAccountId);
        if (!sender || !receiver) {
          throw new Error("Account not found");
        }

        await tx.upsertAccount(
          { ...sender, balanceCents: sender.balanceCents - request.amountCents },
          sender.version
        );
        await tx.upsertAccount(
          { ...receiver, balanceCents: receiver.balanceCents + request.amountCents },
          receiver.version
        );

        const receipt: TransferReceipt = {
          tenantId: request.tenantId,
          idempotencyKey: request.idempotencyKey,
          fromAccountId: request.fromAccountId,
          toAccountId: request.toAccountId,
          amountCents: request.amountCents,
          executedAtMs: clock.nowMs(),
        };
        await tx.saveReceipt(receipt);
        return receipt;
      });
    } catch (error) {
      if (attempt === maxAttempts) {
        throw error;
      }
      const baseBackoffMs = 50 * Math.pow(2, attempt - 1);
      const jitterMs = prng.nextInt(0, baseBackoffMs);
      clock.advanceMs(jitterMs);
    }
  }
  throw new Error("Unreachable");
}
```
