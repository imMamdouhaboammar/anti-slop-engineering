---
name: chaos-and-degradation-choreographer
description: Plan and review graceful degradation and controlled fault tests for dependencies, worker pools, retries, circuit breakers, and recovery. Use when an optional dependency may fail, a critical outcome becomes uncertain, or recovery could overload a service.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Chaos and Degradation Choreographer

## Plan by dependency

1. Trace required and optional dependencies per operation. Record the customer-visible result for healthy, degraded, uncertain, overloaded, and recovered states. Mark irreversible effects and authorization checks as required.
2. Allocate an end-to-end deadline across calls, queueing, and retries. Give dependencies separate bounded capacity where one must not starve another. Specify when to reject excess work, who owns retries, and the total attempt budget. Classify errors before retrying. Release resources on cancellation and terminal failures.
3. Write the fallback's data value, age, authorization, validation, and observability contract. A nonessential cache may degrade to bounded origin reads. An uncertain payment stays pending until reconciled, using the same provider idempotency key only if its contract permits replay. Apply the same identity and data-validation checks to the fallback.
4. Define the circuit breaker's trigger, open behavior, half-open probe budget, and recovery condition. Design load shedding and recovery to avoid a surge from every queued client when the dependency becomes healthy.
5. Run the normal case first and change one fault at a time in an isolated test environment with fake credentials, bounded load, controlled clock, and disabled production access. Define the stop signal, deadline, and cleanup in advance. Record affected operations, baseline metrics, fault timing, fallback use, queue recovery, and the exact assertions and command.

## Schedules

| Fault | Evidence |
| --- | --- |
| Optional Redis cache unavailable | Unaffected path responds within the degraded budget. Origin traffic stays within its reserved capacity. Extra requests are shed after the cap. |
| Payment timeout after request submission | Return a pending state. Reconcile provider state before treating the attempt as definitively failed. At most one effect appears across retries. |
| Persistent transient errors | Requests end at the total attempt or time budget. Unrelated queues retain capacity. No dependency requires an unbounded backlog to recover. |
| Fallback data fails identity, freshness, or schema check | Withhold the fallback. Preserve a distinct invalid-data signal and avoid looking like a successful fresh response. |
| Dependency restored | Permit bounded probes, re-open on a failed probe, and restore traffic gradually on successful probes. Verify the queue drains and user-facing latency returns to its agreed interval. |

The [offline schedule fixture](examples/degradation_cases.py) exercises the decisions above using injected states and an integer budget. It runs without network, subprocesses, or real services. The fixture is a policy model. Verify latency, cancellation, failure isolation, and recovery on the real component in a disposable integration environment.

Catalog: [CON-09, CON-11, OPS-07, SRE-08](../../references/anti-pattern-catalog.md). See also [deterministic simulation](../deterministic-simulation-and-property-testing/SKILL.md).

References: [Google SRE on cascading failures](https://sre.google/sre-book/addressing-cascading-failures/), [AWS on timeouts, retries, and jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).
