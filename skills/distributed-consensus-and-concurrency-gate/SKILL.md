---
name: distributed-consensus-and-concurrency-gate
description: Review concurrent writes, optimistic concurrency, idempotent delivery, distributed leases, leader election, clock assumptions, and database transaction boundaries. Use when a stale reader, duplicate request, partition, or paused worker could violate a data invariant.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Distributed Consensus and Concurrency Gate

## Review

1. State the invariant, who may change it, the authoritative store, and when callers see success. Example: one inventory unit admits one committed reservation even if two callers read the same initial stock.
2. Follow every writer through its check, mutation, commit, and acknowledgment. Record the isolation level and unique constraints, or the compare-and-write condition and affected-row handling. Include jobs and retries that enter through a different route.
3. Replay one interleaving where both writers observe the same state. Add error schedules for a crash after commit before acknowledgment, a stale holder resuming after handover, and a partition during election when each applies.
4. Record the file or query, schedule, asserted result, and exact test command for each claim. Mark checks against a model as such. Use real sessions on the deployed database engine and the affected isolation level to verify storage behavior.

## Select controls by invariant

| Case | Evidence to require |
| --- | --- |
| Check-then-act or lost update | Protect the check and write in the authoritative store. Use atomic conditional updates or version compare-and-swap for a row invariant. For predicate or multi-row invariants, demonstrate a database constraint, appropriate locking, or serializable isolation with a bounded retry of the complete transaction. A lock on existing rows may leave a concurrent insert unprotected. |
| Optimistic concurrency | The update predicates on the previously observed revision and increments it atomically. Distinguish a zero-row conflict from success. Retry only safe operations after rereading, within a request deadline and attempt budget. |
| Duplicate delivery or lost acknowledgment | Bind the deduplication key to tenant, operation, and payload. A repeated key with identical input returns the original result, and conflicting input is rejected. Commit the dedupe record with the local effect, or use an outbox and verify downstream idempotency for external effects. Retain keys through the supported retry window. |
| Lease protects an external writer | Identify who grants ownership and which sink rejects stale epochs atomically with writes. Verify fencing at the sink with a durable high-water mark or authoritative epoch. A lease timeout makes failover possible. It cannot revoke a paused worker's already issued request. |
| Consensus or leader change | Identify the actual protocol, membership, quorum, allowed failures, and conditions for a committed acknowledgment. Pause the prior leader, isolate a minority, elect through a quorum, then heal. Assert preservation of acknowledged commits and rejection of unauthorized stale writes. Check liveness after quorum recovers separately. |
| Clock-dependent ordering | Specify which clocks supply elapsed durations and event order. Use a monotonic clock for local deadlines. Test measured offset assumptions or rely on a protocol-provided revision, log position, or causal relation with the scope the invariant needs. |

## Evidence fixtures

Run the [two-session reservation schedule](examples/reservation_schedule.py) directly with Python 3.9+. Both workers observe the same snapshot before either commits. The guarded writer rejects the second reservation. The unguarded control admits two reservations and leaves a plausible stock reading of zero. SQLite demonstrates the conditional write with a deterministic sequence. Verify transaction-level claims again on the target database.

| Schedule | Assertion |
| --- | --- |
| Worker A receives epoch 41 and stalls. Worker B receives 42, commits a write, and A resumes. | The sink rejects epoch 41 and retains B's value. |
| Caller sends one create request twice, with the first reply lost after commit. | One effect is visible. The retry returns the original result. Reusing that key with a different payload returns a conflict. |
| Two transactions see one free slot and each tries to insert a distinct reservation. | The invariant admits one reservation. If a transaction is retried, it repeats the original read and decision on fresh state. |
| A three-replica cluster loses connectivity between its leader and the other two replicas. | The isolated leader cannot acknowledge a new quorum-committed write. A new leader preserves previously acknowledged entries. |

Catalog: [CON-01, CON-12, DAT-12](../../references/anti-pattern-catalog.md). For larger schedules use [deterministic simulation](../deterministic-simulation-and-property-testing/SKILL.md).

Sources: [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html), [PostgreSQL serialization failure handling](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html), [etcd concurrency reference](https://etcd.io/docs/v3.4/dev-guide/api_concurrency_reference_v3/), [Raft paper](https://raft.github.io/raft.pdf).
