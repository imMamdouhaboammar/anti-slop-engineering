---
name: finops-and-unit-economics-governor
description: Review cost per request, job, or tenant across cloud egress, API fan-out, retries, GPU usage, and model tokens. Use when an input or dependency failure can multiply paid work or when a proposed change cites cost savings.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# FinOps and Unit Economics Governor

## Review a billable unit

1. Select the outcome to count, such as a completed export. Count accepted, failed, and cancelled work separately. Record the observation window, region, provider, unit of measure, and workload segment.
2. Trace the request through billable fan-out, dependency retries, queue redelivery, egress, GPU duration, and model input/output/cache units. Include failed and speculative attempts when billable. Reconcile the trace with billing export or provider usage records.
3. Build base and bounded stress worksheets. For each meter record quantity per accepted request, worst permitted quantity, rate, currency, billing unit, source, and effective date. Keep provider-specific rates outside the shared example. Convert bytes, milliseconds, and token blocks before multiplying, respecting rounding and minimums. Missing rates remain unknown.
4. Bound work at admission and before each paid downstream call. Verify per-tenant and shared limits, total attempt budget including the first call, queues or semaphore, request deadline, and cancellation. Determine who can raise caps. Replays should reuse the underlying result where the paid side effect can be deduplicated. A concurrency limit controls how rapidly work starts. A bound on units or attempts controls how much work one request can generate.
5. Compare budgets against measured spend per outcome and per tenant. Record window or rate limits, billing lag, and behavior when the meter is unavailable. Before changing paid controls, test a safe rejection or lower-cost fallback and confirm the user-visible result.

| Evidence | What to measure |
| --- | --- |
| API fan-out | Calls per request by dependency and attempt number, context propagation, caller deadlines, and tail distribution |
| Network | Bytes by source/destination and region or zone, cache hit/miss, retries, and provider billing unit |
| Model or GPU | Uncached input, cached input, output units, billed cancellations, GPU seconds, concurrent slots |
| Retry and failure | Number of paid attempts before a terminal outcome, queue age, deduplicated effects, and user-visible outcomes |

## Worksheet and fixtures

For each meter, multiply billable units by the applicable rate. When relevant, add fixed charges with an explicit allocation period and denominator. Sum only after normalizing units and currency. Label an estimate from a run with missing prices as incomplete, even when a partial total is known.

The [offline cost cases](examples/cost_cases.py) use synthetic USD rates. They distinguish a bounded fan-out and retry budget, observed work without an upper bound, and an unavailable price. The fixture consumes billable counts already obtained from a trace. It does not query a provider or forecast spend.

Catalog: [CON-09, OPS-07, SRE-08](../anti-slop-engineering/references/anti-pattern-catalog.md).

References: [FinOps unit economics](https://www.finops.org/framework/capabilities/unit-economics/), [FOCUS specification](https://focus.finops.org/focus-specification/), [Google SRE on managing overload](https://sre.google/sre-book/handling-overload/).
