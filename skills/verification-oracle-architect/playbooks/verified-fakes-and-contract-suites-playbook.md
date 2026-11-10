# Playbook 1: Verified In-Memory Fakes & Shared Contract Test Suites

## 1. Why Module Mocking Fails in Production

When `anti-slop/no-module-mocking` blocks `vi.mock()` or `jest.mock()`, it prevents a systemic class of production incidents: **Mock-Reality Divergence**.
- A mock (`repo.save.mockResolvedValue({ id: '1' })`) encodes the test author's *assumptions* about a dependency, not how PostgreSQL, Redis, S3, or Stripe actually behave.
- Mocks ignore unique key collisions (`23505`), foreign key violations, composite tenant scoping (`WHERE tenant_id = $1`), optimistic concurrency version increments (`WHERE version = $2`), cursor sort stability, and transaction rollbacks.
- Worse, spy assertions (`expect(repo.save).toHaveBeenCalledWith(...)`) lock tests to internal call mechanics, breaking on benign refactors while staying green when state is corrupted.

---

## 2. The Port & Verified Fake Architecture

Replace module mocks with a 3-part hexagonal verification seam:

1. **Narrow Domain Port (`LedgerRepositoryPort`):** Define only the operations and error contracts the domain service requires.
2. **Stateful In-Memory Fake (`InMemoryLedgerRepository`):** A real, deterministic in-memory implementation backed by `Map`/`Set` structures that enforces every domain invariant in RAM (`0.05ms` per test).
3. **Parameterized Shared Contract Test Suite (`runLedgerRepositoryContractSuite`):** A single test suite parameterized by an adapter factory `() => Promise<LedgerRepositoryPort>` that runs against **both** `InMemoryLedgerRepository` (on every local test run) and `PostgresLedgerRepository` (against a real test DB/container in CI).

---

## 3. Five Mandatory Mechanics of a Verified In-Memory Fake

An in-memory fake is **not** a dummy stub returning constants. It must enforce these five mechanics:

### 3.1 Boundary Clone Isolation (`structuredClone`)
Never store or return raw object references passed by the caller. If caller code mutates an entity object after calling `await repo.findById(id)` without calling `await repo.save(entity)`, a naive `Map` fake silently mutates "persisted" state, whereas a real database does not.
- Clone every record on insert/update (`structuredClone(entity)`) and clone every record on read (`structuredClone(stored)`).

### 3.2 Constraint & Uniqueness Enforcement
Enforce primary key uniqueness, composite unique indexes (e.g., `(tenantId, idempotencyKey)`), and non-negative balance check constraints inside the fake, throwing the exact same typed domain errors (`DuplicateKeyError`, `ConcurrencyConflictError`, `InsufficientFundsError`) as the production adapter.

### 3.3 Optimistic Concurrency Control (CAS Versioning)
Every mutable aggregate stored in the fake must track its `version: number`. On update:
```ts
if (existing.version !== expectedVersion) {
  throw new ConcurrencyConflictError(entity.id, expectedVersion, existing.version);
}
```

### 3.4 Atomic Transaction Rollback Snapshots (`withTransaction`)
When a service executes multi-step mutations inside `repo.withTransaction(async (tx) => { ... })`, the fake must capture a full deep snapshot of its internal maps before invoking the callback. If the callback throws an exception (or a chaos fault fires mid-transaction), the fake restores the pre-transaction snapshot atomically:
```ts
async withTransaction<T>(fn: (tx: LedgerRepositoryPort) => Promise<T>): Promise<T> {
  const snapshot = this.captureSnapshot();
  try {
    return await fn(this);
  } catch (err) {
    this.restoreSnapshot(snapshot);
    throw err;
  }
}
```

### 3.5 Deterministic Cursor Pagination & Sorting
Implement exact tie-breaker sorting (`ORDER BY created_at DESC, id DESC`) in the fake's query methods so keyset pagination bugs are caught in unit tests.

---

## 4. The Shared Contract Test Suite Pattern

A fake without a contract suite inevitably drifts from the real database. Bind them together with a shared contract suite:

```ts
export function defineLedgerRepositoryContractSuite(
  adapterName: string,
  createHarness: () => Promise<{
    repo: LedgerRepositoryPort;
    cleanup: () => Promise<void>;
  }>
): void {
  describe(`LedgerRepositoryPort Contract [${adapterName}]`, () => {
    // 1. Roundtrip persistence & clone isolation
    // 2. Composite tenant isolation (Tenant A cannot read/mutate Tenant B)
    // 3. Unique (tenantId, idempotencyKey) conflict rejection
    // 4. Optimistic locking CAS version conflict on concurrent update
    // 5. Atomic rollback of all partial writes when withTransaction throws
    // 6. Deterministic cursor pagination ordering
  });
}
```

Execute the exact same suite in two places:
- `inMemoryLedgerRepo.contract.test.ts` -> `defineLedgerRepositoryContractSuite("InMemory", ...)`
- `postgresLedgerRepo.contract.test.ts` -> `defineLedgerRepositoryContractSuite("PostgreSQL", ...)`

If a developer changes `PostgresLedgerRepository` behavior (or adds a new port invariant), both contract runs must pass before merge.
