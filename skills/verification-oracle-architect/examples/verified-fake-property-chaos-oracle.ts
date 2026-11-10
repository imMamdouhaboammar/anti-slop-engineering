// SPDX-License-Identifier: MIT
// Example: Verification Oracle Architect — Contract-Verified In-Memory Fake, Property-Based & Metamorphic Oracles, and Seeded Deterministic Chaos Simulation

export class DuplicateIdempotencyKeyError extends Error {
  readonly code = "DUPLICATE_IDEMPOTENCY_KEY" as const;
  constructor(readonly tenantId: string, readonly idempotencyKey: string) {
    super(`Duplicate idempotency key '${idempotencyKey}' for tenant '${tenantId}'`);
  }
}

export class OptimisticConcurrencyError extends Error {
  readonly code = "OPTIMISTIC_CONCURRENCY_CONFLICT" as const;
  constructor(readonly entityId: string, readonly expectedVersion: number) {
    super(`Version conflict on '${entityId}' (expected v${expectedVersion})`);
  }
}

export class SimulatedChaosFaultError extends Error {
  readonly code = "SIMULATED_CHAOS_FAULT" as const;
  constructor(
    readonly faultMode: "pre_commit_connection_drop" | "post_commit_ack_drop",
    readonly seedHex: string
  ) {
    super(`Deterministic chaos fault '${faultMode}' triggered [seed=${seedHex}]`);
  }
}

export interface AccountRecord {
  readonly tenantId: string;
  readonly accountId: string;
  readonly balanceCents: number;
  readonly version: number;
}

export interface TransferReceipt {
  readonly tenantId: string;
  readonly idempotencyKey: string;
  readonly fromAccountId: string;
  readonly toAccountId: string;
  readonly amountCents: number;
  readonly executedAtMs: number;
}

export interface LedgerStoragePort {
  getAccount(tenantId: string, accountId: string): Promise<AccountRecord | null>;
  upsertAccount(account: AccountRecord, expectedVersion: number): Promise<AccountRecord>;
  findReceipt(tenantId: string, idempotencyKey: string): Promise<TransferReceipt | null>;
  saveReceipt(receipt: TransferReceipt): Promise<void>;
  withTransaction<T>(work: (tx: LedgerStoragePort) => Promise<T>): Promise<T>;
}

// ---------------------------------------------------------------------------
// 1. Stateful In-Memory Fake with structuredClone & Rollback Snapshots
// ---------------------------------------------------------------------------

export class InMemoryLedgerStorage implements LedgerStoragePort {
  private accounts = new Map<string, AccountRecord>();
  private receipts = new Map<string, TransferReceipt>();

  private accountKey(tenantId: string, accountId: string): string {
    return `${tenantId}::${accountId}`;
  }

  private receiptKey(tenantId: string, idempotencyKey: string): string {
    return `${tenantId}::${idempotencyKey}`;
  }

  async getAccount(tenantId: string, accountId: string): Promise<AccountRecord | null> {
    const found = this.accounts.get(this.accountKey(tenantId, accountId));
    return found ? structuredClone(found) : null;
  }

  async upsertAccount(account: AccountRecord, expectedVersion: number): Promise<AccountRecord> {
    const key = this.accountKey(account.tenantId, account.accountId);
    const current = this.accounts.get(key);
    const currentVersion = current ? current.version : 0;

    if (currentVersion !== expectedVersion) {
      throw new OptimisticConcurrencyError(account.accountId, expectedVersion);
    }
    if (account.balanceCents < 0) {
      throw new RangeError(`Account '${account.accountId}' balance cannot be negative`);
    }

    const updated: AccountRecord = {
      ...structuredClone(account),
      version: expectedVersion + 1,
    };
    this.accounts.set(key, updated);
    return structuredClone(updated);
  }

  async findReceipt(tenantId: string, idempotencyKey: string): Promise<TransferReceipt | null> {
    const found = this.receipts.get(this.receiptKey(tenantId, idempotencyKey));
    return found ? structuredClone(found) : null;
  }

  async saveReceipt(receipt: TransferReceipt): Promise<void> {
    const key = this.receiptKey(receipt.tenantId, receipt.idempotencyKey);
    if (this.receipts.has(key)) {
      throw new DuplicateIdempotencyKeyError(receipt.tenantId, receipt.idempotencyKey);
    }
    this.receipts.set(key, structuredClone(receipt));
  }

  async withTransaction<T>(work: (tx: LedgerStoragePort) => Promise<T>): Promise<T> {
    const accountsSnapshot = structuredClone(this.accounts);
    const receiptsSnapshot = structuredClone(this.receipts);
    try {
      return await work(this);
    } catch (error) {
      this.accounts = accountsSnapshot;
      this.receipts = receiptsSnapshot;
      throw error;
    }
  }
}

// ---------------------------------------------------------------------------
// 2. Parameterized Shared Contract Test Suite (Runs on Fake AND Real DB)
// ---------------------------------------------------------------------------

export async function verifyLedgerStorageContract(
  createAdapter: () => Promise<LedgerStoragePort>
): Promise<{ readonly passedContractGates: readonly string[] }> {
  const gates: string[] = [];

  // Gate 1: Persistence roundtrip & structuredClone reference isolation
  {
    const adapter = await createAdapter();
    const mutableInput = {
      tenantId: "tenant_a",
      accountId: "acc_1",
      balanceCents: 10_000,
      version: 0,
    };
    await adapter.upsertAccount(mutableInput, 0);
    mutableInput.balanceCents = 999_999; // Caller mutation must not corrupt storage
    const stored = await adapter.getAccount("tenant_a", "acc_1");
    if (!stored || stored.balanceCents !== 10_000 || stored.version !== 1) {
      throw new Error("Contract failure: structuredClone boundary isolation violated");
    }
    gates.push("structured_clone_boundary_isolation");
  }

  // Gate 2: Composite tenant isolation
  {
    const adapter = await createAdapter();
    await adapter.upsertAccount(
      { tenantId: "tenant_a", accountId: "shared", balanceCents: 500, version: 0 },
      0
    );
    const crossTenant = await adapter.getAccount("tenant_b", "shared");
    if (crossTenant !== null) {
      throw new Error("Contract failure: cross-tenant data leak");
    }
    gates.push("composite_tenant_isolation");
  }

  // Gate 3: Optimistic concurrency CAS version check
  {
    const adapter = await createAdapter();
    await adapter.upsertAccount(
      { tenantId: "tenant_a", accountId: "acc_cas", balanceCents: 1000, version: 0 },
      0
    );
    let threwCas = false;
    try {
      await adapter.upsertAccount(
        { tenantId: "tenant_a", accountId: "acc_cas", balanceCents: 800, version: 0 },
        0
      );
    } catch (err) {
      threwCas = err instanceof OptimisticConcurrencyError;
    }
    if (!threwCas) {
      throw new Error("Contract failure: stale expectedVersion was not rejected");
    }
    gates.push("optimistic_concurrency_version_cas");
  }

  // Gate 4: Atomic snapshot rollback on mid-transaction error
  {
    const adapter = await createAdapter();
    await adapter.upsertAccount(
      { tenantId: "tenant_a", accountId: "acc_rb", balanceCents: 4000, version: 0 },
      0
    );
    try {
      await adapter.withTransaction(async (tx) => {
        await tx.upsertAccount(
          { tenantId: "tenant_a", accountId: "acc_rb", balanceCents: 1000, version: 1 },
          1
        );
        throw new Error("Abort mid-transaction");
      });
    } catch {
      // Expected abort
    }
    const postRollback = await adapter.getAccount("tenant_a", "acc_rb");
    if (!postRollback || postRollback.balanceCents !== 4000 || postRollback.version !== 1) {
      throw new Error("Contract failure: transaction failed to rollback partial writes");
    }
    gates.push("transactional_snapshot_rollback");
  }

  return { passedContractGates: gates };
}

// ---------------------------------------------------------------------------
// 3. Property-Based & Metamorphic Oracle (Conservation + Invertibility)
// ---------------------------------------------------------------------------

export interface PayoutSplitResult {
  readonly feeCents: number;
  readonly payoutsCents: readonly number[];
}

export function allocatePayoutsExactCents(
  grossCents: number,
  weightsBps: readonly number[],
  platformFeeBps: number
): PayoutSplitResult {
  if (!Number.isSafeInteger(grossCents) || grossCents < 0) {
    throw new RangeError("grossCents must be a non-negative safe integer");
  }
  const weightSum = weightsBps.reduce((acc, w) => acc + w, 0);
  if (weightsBps.length === 0 || weightSum <= 0) {
    throw new RangeError("weightsBps must have a positive sum");
  }

  const feeCents = Math.floor((grossCents * platformFeeBps) / 10_000);
  const netPool = grossCents - feeCents;
  const payouts = new Array<number>(weightsBps.length);
  const remainders = new Array<{ index: number; rem: number }>(weightsBps.length);
  let distributed = 0;

  for (let i = 0; i < weightsBps.length; i++) {
    const prod = netPool * weightsBps[i];
    const whole = Math.floor(prod / weightSum);
    payouts[i] = whole;
    distributed += whole;
    remainders[i] = { index: i, rem: prod % weightSum };
  }

  const remainderCents = netPool - distributed;
  remainders.sort((a, b) => (b.rem !== a.rem ? b.rem - a.rem : a.index - b.index));
  for (let i = 0; i < remainderCents; i++) {
    payouts[remainders[i].index] += 1;
  }

  return { feeCents, payoutsCents: payouts };
}

// ---------------------------------------------------------------------------
// 4. Seeded Deterministic Chaos Harness (Mulberry32 PRNG + VirtualClock)
// ---------------------------------------------------------------------------

export class Mulberry32Prng {
  private state: number;

  constructor(readonly seed: number) {
    this.state = seed >>> 0;
  }

  seedHex(): string {
    return `0x${(this.seed >>> 0).toString(16).toUpperCase()}`;
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
  private epochMs: number;

  constructor(initialEpochMs = 1_700_000_000_000) {
    this.epochMs = initialEpochMs;
  }

  nowMs(): number {
    return this.epochMs;
  }

  advanceMs(deltaMs: number): void {
    this.epochMs += Math.max(0, deltaMs);
  }
}

export class DeterministicChaosLedgerProxy implements LedgerStoragePort {
  constructor(
    private readonly inner: LedgerStoragePort,
    private readonly prng: Mulberry32Prng,
    private readonly preCommitDropRate: number,
    private readonly postCommitAckDropRate: number
  ) {}

  getAccount(tenantId: string, accountId: string): Promise<AccountRecord | null> {
    return this.inner.getAccount(tenantId, accountId);
  }

  upsertAccount(account: AccountRecord, expectedVersion: number): Promise<AccountRecord> {
    return this.inner.upsertAccount(account, expectedVersion);
  }

  findReceipt(tenantId: string, idempotencyKey: string): Promise<TransferReceipt | null> {
    return this.inner.findReceipt(tenantId, idempotencyKey);
  }

  saveReceipt(receipt: TransferReceipt): Promise<void> {
    return this.inner.saveReceipt(receipt);
  }

  async withTransaction<T>(work: (tx: LedgerStoragePort) => Promise<T>): Promise<T> {
    const committedResult = await this.inner.withTransaction(async (tx) => {
      const res = await work(tx);
      if (this.prng.nextFloat() < this.preCommitDropRate) {
        throw new SimulatedChaosFaultError("pre_commit_connection_drop", this.prng.seedHex());
      }
      return res;
    });

    if (this.prng.nextFloat() < this.postCommitAckDropRate) {
      throw new SimulatedChaosFaultError("post_commit_ack_drop", this.prng.seedHex());
    }

    return committedResult;
  }
}

export async function runPropertyAndChaosVerificationSuite(
  seeds: readonly number[] = [0x5eed1001, 0x5eed1002, 0x5eed1003, 0x9f4a2c01]
): Promise<{ readonly propertyRuns: number; readonly chaosSeedsVerified: number }> {
  let propertyRuns = 0;

  for (let s = 0; s < seeds.length; s++) {
    const prng = new Mulberry32Prng(seeds[s]);

    // Property & Metamorphic Oracle: 250 generated runs across seeds
    for (let i = 0; i < 65; i++) {
      const grossCents = prng.nextInt(0, 5_000_000);
      const recipientCount = prng.nextInt(1, 7);
      const weights: number[] = [];
      for (let w = 0; w < recipientCount; w++) {
        weights.push(prng.nextInt(1, 10_000));
      }
      const feeBps = prng.nextInt(0, 2500);

      const split = allocatePayoutsExactCents(grossCents, weights, feeBps);
      const sumPayouts = split.payoutsCents.reduce((a, b) => a + b, 0);

      // Invariant 1: Exact Conservation of Money
      if (split.feeCents + sumPayouts !== grossCents) {
        throw new Error(
          `Conservation law violated [seed=${prng.seedHex()}]: ${split.feeCents} + ${sumPayouts} !== ${grossCents}`
        );
      }

      // Invariant 2: Metamorphic Permutation Invariance
      const reversedWeights = [...weights].reverse();
      const reversedSplit = allocatePayoutsExactCents(grossCents, reversedWeights, feeBps);
      const sortedA = [...split.payoutsCents].sort((a, b) => a - b);
      const sortedB = [...reversedSplit.payoutsCents].sort((a, b) => a - b);
      for (let k = 0; k < sortedA.length; k++) {
        if (sortedA[k] !== sortedB[k]) {
          throw new Error(`Metamorphic permutation invariance violated [seed=${prng.seedHex()}]`);
        }
      }
      propertyRuns += 1;
    }

    // Deterministic Chaos Simulation: Pre-Commit Rollback + Post-Commit Idempotent Replay
    const baseStorage = new InMemoryLedgerStorage();
    const clock = new DeterministicVirtualClock();
    const chaosStorage = new DeterministicChaosLedgerProxy(baseStorage, prng, 0.25, 0.25);

    await baseStorage.upsertAccount(
      { tenantId: "t_chaos", accountId: "sender", balanceCents: 100_000, version: 0 },
      0
    );
    await baseStorage.upsertAccount(
      { tenantId: "t_chaos", accountId: "receiver", balanceCents: 0, version: 0 },
      0
    );

    let settledReceipt: TransferReceipt | null = null;
    for (let attempt = 1; attempt <= 25 && !settledReceipt; attempt++) {
      try {
        settledReceipt = await chaosStorage.withTransaction(async (tx) => {
          const existing = await tx.findReceipt("t_chaos", "idem_tx_01");
          if (existing) return existing;

          const sender = await tx.getAccount("t_chaos", "sender");
          const receiver = await tx.getAccount("t_chaos", "receiver");
          if (!sender || !receiver) throw new Error("Missing accounts");

          await tx.upsertAccount(
            { ...sender, balanceCents: sender.balanceCents - 25_000 },
            sender.version
          );
          await tx.upsertAccount(
            { ...receiver, balanceCents: receiver.balanceCents + 25_000 },
            receiver.version
          );

          const receipt: TransferReceipt = {
            tenantId: "t_chaos",
            idempotencyKey: "idem_tx_01",
            fromAccountId: "sender",
            toAccountId: "receiver",
            amountCents: 25_000,
            executedAtMs: clock.nowMs(),
          };
          await tx.saveReceipt(receipt);
          return receipt;
        });
      } catch {
        clock.advanceMs(50 * attempt);
      }
    }

    const finalSender = await baseStorage.getAccount("t_chaos", "sender");
    const finalReceiver = await baseStorage.getAccount("t_chaos", "receiver");
    if (
      !settledReceipt ||
      !finalSender ||
      !finalReceiver ||
      finalSender.balanceCents !== 75_000 ||
      finalReceiver.balanceCents !== 25_000
    ) {
      throw new Error(
        `Chaos idempotency/rollback invariant failed [seed=${prng.seedHex()}]`
      );
    }
  }

  return { propertyRuns, chaosSeedsVerified: seeds.length };
}
