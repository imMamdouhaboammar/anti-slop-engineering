---
name: observability-and-slo-architect
description: Transforms observability from passive logger.error statements into a Google Monarch & Dapper proactive telemetry architecture—mandating OpenTelemetry by default with unbroken W3C traceparent propagation across every I/O operation, RPC, message queue, and worker; emitting automated RED metrics for endpoints and USE metrics for resources without metric cardinality explosions; and gating production alerts on Google SRE Multi-Window Multi-Burn-Rate error budgets. Use when designing observability architectures, instrumenting APIs, background queues, outbox workers, or database drivers, adding Prometheus/OpenTelemetry/Monarch metrics, replacing high-cardinality metric labels (user_id in labels), defining SLIs/SLOs, or auditing code for broken trace contexts and alert noise.
license: MIT
metadata:
  version: "1.0.0"
  parent: anti-slop-engineering
---

# Observability & SLO Architect (Google Monarch & Dapper School)

> Telemetry without distributed context is blindness; high-cardinality identifiers in time-series metrics are a denial-of-service attack on your monitoring infrastructure; alerts not tied to user impact or error budget burn rate are operational noise. Transform observability into a proactive engineering contract: OpenTelemetry by default, automated RED and USE metrics, and Multi-Window Multi-Burn-Rate SLO alerts.

## Target Architecture: Google Monarch & Dapper Imprint

1. **Google Dapper (Distributed Tracing & Context Causality):**
   - **OpenTelemetry by Default:** Every I/O operation (HTTP, gRPC, database query, Redis command, message queue enqueue/dequeue, background worker) is bound to an active Span.
   - **Unbroken Context Propagation:** Pass W3C TraceContext (`traceparent: 00-<trace_id>-<span_id>-<flags>`, `tracestate`) and `x-correlation-id` across every network boundary, asynchronous queue, and database statement (via SQLcommenter).
   - **Forensic Isolation:** High-cardinality identifiers (`user_id`, `tenant_id`, `order_id`, `idempotency_key`, `request_id`) live exclusively within Span Attributes and structured JSON logs.

2. **Google Monarch (Planetary Low-Cardinality Metric Stream Engine):**
   - **Strict Low-Cardinality Metric Schemas:** Time-series metric dimensions use bounded allowlists ($\prod |L_i| \le 1,000$ per metric family). Dynamic identifiers in metric labels are strictly prohibited.
   - **404 Route Collapsing:** Unmatched URL paths collapse to `"__unmatched__"` to neutralize scanner-induced cardinality explosions.
   - **Histograms over Averages:** Durations are recorded exclusively in explicit-bucket Histograms to compute P50, P95, and P99 quantiles. Arithmetic averages and Gauge percentiles are mathematically invalid and prohibited.
   - **Trace Exemplars:** Span `trace_id` and `span_id` attach directly to Histogram bucket recordings, enabling 1-click jumps from latency spikes to causal traces.

3. **RED & USE Metric Instrumentation:**
   - **RED for Endpoints (Request-Driven Work):**
     - **Rate:** Throughput in requests/sec (`http.server.request.count`, `rpc.server.request.count`).
     - **Errors:** Failure rate (`http.server.error.count` partitioned by status class or error code).
     - **Duration:** Latency distribution recorded via explicit-bucket Histograms (`http.server.duration`).
   - **USE for Resources (Capacity & Hardware/Software Limits):**
     - **Utilization:** Fraction of time busy or capacity consumed ($0.0 \le U \le 1.0$) for CPU, Memory, DB Connection Pools, Worker Pools.
     - **Saturation:** Depth of queued work waiting for capacity (Queue backlog, connection waiters, event loop lag).
     - **Errors:** Count of resource-level failure events (pool checkout timeouts, worker OOMs, dropped messages).

4. **SLI/SLO-Driven Alerts (Google SRE Multi-Burn-Rate):**
   - **Ban Non-Impact Alerts:** No alert fires on raw resource thresholds (e.g. CPU > 80%) unless there is measurable user impact or Error Budget exhaustion.
   - **Multi-Window Multi-Burn-Rate Matrix:**
     - **14.4x Fast Burn (2% budget in 1 hour):** Long window = 1 hour, Short window = 5 minutes $\rightarrow$ Immediate PagerDuty page & automated canary rollback.
     - **6.0x Slow Burn (5% budget in 6 hours):** Long window = 6 hours, Short window = 30 minutes $\rightarrow$ Incident remediation ticket for next business day.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Instrumenting HTTP endpoints, gRPC handlers, or RPC clients | Emit RED metrics (Rate, Errors, Histogram Duration), bind to OpenTelemetry Server Spans, propagate W3C `traceparent` |
| Designing or instrumenting background queues, event buses, outbox workers, or DB queries | Inject `traceparent` and `correlation_id` on producer, extract on consumer, record USE metrics on workers and connection pools |
| Writing logging middleware or error handling layers | Ban raw `console.log` and `logger.error("...")`; emit structured JSON logs correlated with `trace_id`, `span_id`, and redacting secrets |
| Establishing alerting policies, service readiness checklists, or SLO gates | Enforce Multi-Window Multi-Burn-Rate alerts on availability and P95/P99 latency SLIs; reject static threshold alerts |
| Auditing existing services or PR diffs | Scan for cardinality leaks (`user_id` in labels), gauge-averaged latencies, broken async trace trees, and noisy threshold alerts |
| Static documentation edits, CSS token changes, or local offline scripts | Do not activate; use `anti-slop-engineering` |

---

## The Six Absolute Laws

1. **The OpenTelemetry by Default Law:**
   Every network call, database query, cache access, and queue message must execute within an active OpenTelemetry Span. Handlers must never catch errors without recording the exception (`span.recordException(err)`) and setting error status (`span.setStatus({ code: SpanStatusCode.ERROR, message: err.code })`).

2. **The Unbroken W3C Context Propagation Law:**
   Context must never drop across synchronous or asynchronous boundaries. Message payloads (Kafka, SQS, RabbitMQ, BullMQ) and Transactional Outbox rows must contain explicit `traceparent` and `correlation_id` headers. Workers must extract parent context before executing task logic.

3. **The Google Monarch Low-Cardinality Law:**
   Never attach dynamic or unbounded values (`user_id`, `request_id`, `order_id`, `email`, `ip_address`, raw URL paths) to metric attributes. Label products must remain $\prod |L_i| \le 1,000$. Unmatched 404 paths must be collapsed into `"__unmatched__"`.

4. **The RED & USE Dual-Matrix Law:**
   Endpoints must expose Rate, Errors, and Duration (RED) via Histograms. Resources (CPU, Memory, DB Connection Pools, Thread Pools, Worker Queues) must expose Utilization, Saturation, and Errors (USE).

5. **The Histogram Quantile Law:**
   Measure durations and payload sizes exclusively with Histograms configured with explicit, domain-calibrated bucket boundaries (e.g. `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]` ms). Never average latencies across horizontal instances. Attach Trace Exemplars to bucket observations.

6. **The Multi-Window Multi-Burn-Rate Alerting Law:**
   Ban alerts on non-user-impacting symptoms. Alerting must be driven by Error Budget Burn Rate evaluated simultaneously across long and short lookback windows (14.4x 1h/5m for paging; 6.0x 6h/30m for ticketing).

---

## Invariant Rules

1. **Mandatory Envelope Schema:** Async message schemas must define mandatory `traceparent: string` and `correlationId: string` metadata.
2. **Exemplar Binding:** When recording latency Histograms in sampled spans, attach the active `trace_id` and `span_id` as a Metric Exemplar.
3. **Deterministic Log Redaction:** Structured logs must automatically sanitize fields matching `authorization`, `cookie`, `password`, `secret`, `token`, and `api_key`.
4. **Pre-Enqueuing Resource Backpressure:** Check resource Saturation before enqueuing or accepting new transactions.
5. **In-Memory Verification Tests:** Automated test suites must verify telemetry using in-memory exporters, asserting zero cardinality leaks and unbroken trace trees across queue boundaries.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Instrumenting HTTP/gRPC endpoints with RED metrics & OTel spans | [Emit RED & USE Metrics](usecases/emit-red-and-use-metrics.md) | [RED & USE Metrics Matrix](references/red-and-use-metrics-matrix.md) |
| Propagating W3C context across queues, outboxes, workers & DB | [Enforce OpenTelemetry I/O Spans](usecases/enforce-opentelemetry-io-spans.md) | [W3C `traceparent` & Async Context](references/w3c-traceparent-and-async-context-propagation.md) |
| Formulating SLIs, SLOs & Multi-Burn-Rate alerting policies | [Define SLO Burn-Rate Alerts](usecases/define-slo-burn-rate-alerts.md) | [SLI/SLO & Multi-Burn Alerting](references/sli-slo-and-multi-burn-rate-alerting.md) |
| Auditing records and source code with automated guard | Record validation and source scan | `scripts/observability_guard.py` |

---

## Pre-Instrumentation Interrogation Matrix

- **Cardinality Audit:** What is the maximum cardinality product of all labels on this metric family? Could any tenant or user input explode the TSDB?
- **Causality Audit:** When this message is published to the queue, how does the background consumer retrieve the parent `traceId`?
- **Resource Saturation Audit:** What happens when the connection pool or queue saturates? Does USE metric instrumentation surface saturation before requests fail?
- **Burn-Rate Audit:** Does this alert page on a temporary 10-second blip, or does it require sustained budget consumption across both 1-hour and 5-minute windows?
- **Exemplar Linkage:** Can an operator click from the 99th-percentile latency bucket in Grafana directly to the offending Dapper trace?

---

## Prohibited Anti-Patterns

1. **Dynamic Identifiers in Metric Labels:** Passing `user_id`, `userId`, `account_id`, `order_id`, `email`, `ip`, or `req.url` into Prometheus/OTel metric attributes.
2. **Unstructured `logger.error` / `console.log`:** Emitting string-interpolated logs without structured JSON fields and trace correlation.
3. **Gauge Latency Averages:** Recording latency averages or percentiles using a Gauge instead of a Histogram.
4. **Context Dropping in Queues:** Enqueuing tasks to Kafka/SQS/BullMQ/Outbox without injecting `traceparent`.
5. **Noisy Single-Threshold Alerts:** Paging on-call when CPU > 80% without user-facing latency or error rate degradation.
