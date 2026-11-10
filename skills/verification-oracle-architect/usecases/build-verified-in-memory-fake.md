# Workflow: Build a Verified In-Memory Fake & Shared Contract Suite

Use this workflow when replacing banned module mocks (`vi.mock`, `jest.mock`, `sinon.stub`, `unittest.mock.patch`) or when testing services that depend on databases, caches, queues, or external payment/RPC gateways.

## Step-by-Step Procedure

### 1. Delete Module Mocks & Extract a Narrow Port Interface
1. Remove every `vi.mock(...)`, `jest.mock(...)`, `unittest.mock.patch(...)`, and `.mockResolvedValue(...)` call from the test suite.
2. Define a narrow, domain-focused Port interface (e.g., `LedgerStoragePort`, `WebhookOutboxPort`) specifying exact input/output types and typed domain errors (`DuplicateIdempotencyKeyError`, `OptimisticConcurrencyError`).

### 2. Implement the Stateful In-Memory Fake
Build an `InMemory*` class implementing the Port interface with these mandatory rules:
1. **Boundary Clone Isolation:** Call `structuredClone(record)` on every write into internal `Map` storage and `structuredClone(stored)` on every read out of storage so external object mutations never leak.
2. **Real Constraint Enforcement:** Enforce composite unique indexes (`tenantId + idempotencyKey`), primary key collisions, and check constraints (`balanceCents >= 0`).
3. **Optimistic Locking (`version` CAS):** Verify `current.version === expectedVersion` before mutating; increment `version` on commit.
4. **Transactional Rollback Snapshots:** In `withTransaction(fn)`, snapshot all internal maps before calling `fn(this)`. If `fn` throws, restore the exact snapshot before rethrowing.

### 3. Bind Fake and Real Adapters with a Shared Contract Suite
1. Create a parameterized contract test runner:
   `export function runPortContractSuite(name: string, createAdapter: () => Promise<Port>)`
2. Assert roundtrip persistence, clone isolation, tenant boundary isolation, unique key rejection, CAS version conflict, and mid-transaction rollback restoration inside the shared suite.
3. Run the shared suite against both `InMemoryAdapter` and `RealDatabaseAdapter`.

### 4. Assert Observable Domain State in Service Tests
1. Inject `new InMemoryAdapter()` into the domain service under test.
2. Execute the domain command and assert the resulting state stored in the fake (`await fakeRepo.getAccount(...)`) rather than asserting internal method call counts (`toHaveBeenCalledWith`).
