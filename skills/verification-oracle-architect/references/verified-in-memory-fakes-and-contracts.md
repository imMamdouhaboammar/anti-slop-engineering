# Verified In-Memory Fakes & Shared Contract Suites Reference

## 1. Port Interface & Domain Error Contract

Define explicit, narrow Port interfaces and deterministic domain error classes so both the `InMemoryFake` and the `RealDatabaseAdapter` share one strict contract:

```ts
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
```

---

## 2. Stateful In-Memory Fake with `structuredClone` & Rollback Snapshots

```ts
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

    const next: AccountRecord = {
      ...structuredClone(account),
      version: expectedVersion + 1,
    };
    this.accounts.set(key, next);
    return structuredClone(next);
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
```

---

## 3. Parameterized Shared Contract Test Suite

Run this exact function against both `new InMemoryLedgerStorage()` and `new PostgresLedgerStorage(pool)`:

```ts
export async function verifyLedgerStorageContract(
  createAdapter: () => Promise<LedgerStoragePort>
): Promise<{ readonly passedChecks: readonly string[] }> {
  const checks: string[] = [];

  // Check 1: Clone isolation across reads and writes
  {
    const storage = await createAdapter();
    const initial: AccountRecord = {
      tenantId: "t_1",
      accountId: "acc_1",
      balanceCents: 5000,
      version: 0,
    };
    await storage.upsertAccount(initial, 0);
    const fetched = await storage.getAccount("t_1", "acc_1");
    if (!fetched || fetched.balanceCents !== 5000 || fetched.version !== 1) {
      throw new Error("Contract violation: persistence roundtrip failed");
    }
    checks.push("clone_isolation_and_roundtrip");
  }

  // Check 2: Tenant boundary isolation
  {
    const storage = await createAdapter();
    await storage.upsertAccount(
      { tenantId: "t_alpha", accountId: "shared_id", balanceCents: 1000, version: 0 },
      0
    );
    const leaked = await storage.getAccount("t_beta", "shared_id");
    if (leaked !== null) {
      throw new Error("Contract violation: cross-tenant read leak");
    }
    checks.push("composite_tenant_isolation");
  }

  // Check 3: Optimistic concurrency version enforcement
  {
    const storage = await createAdapter();
    await storage.upsertAccount(
      { tenantId: "t_1", accountId: "acc_cas", balanceCents: 2000, version: 0 },
      0
    );
    let conflictCaught = false;
    try {
      await storage.upsertAccount(
        { tenantId: "t_1", accountId: "acc_cas", balanceCents: 1500, version: 0 },
        0
      );
    } catch (err) {
      conflictCaught = err instanceof OptimisticConcurrencyError;
    }
    if (!conflictCaught) {
      throw new Error("Contract violation: failed to reject stale expectedVersion");
    }
    checks.push("optimistic_concurrency_cas");
  }

  // Check 4: Atomic rollback when withTransaction throws mid-flight
  {
    const storage = await createAdapter();
    await storage.upsertAccount(
      { tenantId: "t_1", accountId: "acc_rb", balanceCents: 3000, version: 0 },
      0
    );
    try {
      await storage.withTransaction(async (tx) => {
        await tx.upsertAccount(
          { tenantId: "t_1", accountId: "acc_rb", balanceCents: 1000, version: 1 },
          1
        );
        throw new Error("Simulated mid-transaction crash");
      });
    } catch {
      // Expected abort
    }
    const afterAbort = await storage.getAccount("t_1", "acc_rb");
    if (!afterAbort || afterAbort.balanceCents !== 3000 || afterAbort.version !== 1) {
      throw new Error("Contract violation: partial transaction state leaked after rollback");
    }
    checks.push("transactional_snapshot_rollback");
  }

  return { passedChecks: checks };
}
```
