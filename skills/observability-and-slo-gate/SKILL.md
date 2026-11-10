---
name: observability-and-slo-gate
description: Enforces Google Dapper and OpenTelemetry production observability architecture—strictly separating low-cardinality metrics (bounded label sets and P50/P95/P99 latency Histograms) from high-cardinality traces and structured logs, guaranteeing unbroken end-to-end W3C traceparent and correlation_id context propagation across HTTP, gRPC, message queues, outbox workers, and database queries, and gating releases with Multi-Window Burn-Rate SLOs. Use when instrumenting APIs, background jobs, queues, or database layers, adding Prometheus/OpenTelemetry/Datadog metrics, structured logging, distributed tracing, defining SLIs/SLOs, or auditing code for metric cardinality explosions (user_id in labels) and broken trace trees — even if the user doesn't explicitly say "observability gate". Do NOT use for purely static markdown formatting or offline one-off scripts with no runtime telemetry requirements.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Observability & SLO Gate (Google Dapper / OpenTelemetry & Multi-Burn-Rate SRE School)

> Production code that executes without telemetry is blind; production code that puts `user_id` into a Prometheus metric label is a financial time bomb. Enforce Low-Cardinality Metrics with P50/P95/P99 Histograms, High-Cardinality Traces/Logs, and Unbroken W3C `traceparent` Context Propagation from the first frontend click to the final database statement.

## Why This Skill Is Needed & Target State

AI-generated services typically pass local functional tests while introducing two catastrophic production observability failures:
1. **Metric Cardinality Explosion (The Datadog/Prometheus Bankruptcy Trap):** Agents routinely attach unbounded dynamic identifiers (`user_id`, `request_id`, `order_id`, `email`, `ip_address`, `trace_id`, or unrouted raw URLs like `/orders/9481-a8f2/pay`) as Prometheus or OpenTelemetry Metric labels/attributes. Because every unique label combination creates a new time-series in the TSDB, 100,000 active users across 10 routes and 5 status codes instantly spawn 5,000,000 active time-series—OOM-killing Prometheus collectors and exploding Datadog/CloudWatch custom metric bills.
2. **Broken Async Trace Causality & Blind Production Failures:** Agents emit unstructured `console.log("Failed", err)` or start HTTP spans that vanish the moment work is enqueued to Kafka, SQS, RabbitMQ, BullMQ, Redis Streams, an Outbox table, or a worker pool. Without explicit W3C `traceparent` and `correlation_id` injection and extraction across async boundaries, production incidents become impossible to trace from the user's frontend click down to the failing SQL query.

The target state is **Google Dapper & OpenTelemetry Grade Observability**:
1. **Strict Cardinality Split:** Metrics (`Counter`, `Histogram`, `UpDownCounter`) use strictly bounded, low-cardinality label sets ($\prod |L_i| \le 1,000$ per metric family) and record latency distributions via **Histograms** for accurate P50, P95, and P99 quantile calculation. All high-cardinality diagnostic identifiers (`user_id`, `tenant_id`, `order_id`, `idempotency_key`, `request_id`) live exclusively inside **Trace Span Attributes** and **Structured JSON Logs**.
2. **Unbroken End-to-End W3C Context Propagation:** Every synchronous RPC and asynchronous queue/outbox/worker hop propagates `traceparent` (`00-<trace_id>-<span_id>-<flags>`), `tracestate`, and `correlation_id`, maintaining a single causal trace tree from client UI to database query.
3. **Actionable SLIs & Multi-Window Burn-Rate SLOs:** Every critical service boundary defines latency (P95/P99) and availability SLIs backed by Google SRE Multi-Window, Multi-Burn-Rate error-budget alerts.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Adding Prometheus, OpenTelemetry, StatsD, or Datadog metrics to HTTP routes, RPC handlers, or workers | Enforce the Low-Cardinality Metric Law (allowlist bounded labels only; ban `user_id`/`request_id`/raw URLs) and use Histograms for latency |
| Implementing message producers/consumers (Kafka, SQS, BullMQ, RabbitMQ), transactional outboxes, or background workers | Require explicit W3C `traceparent` and `correlation_id` injection on publish/enqueue and extraction before worker execution |
| Authoring error handlers, logging middleware, or database query wrappers | Enforce structured JSON logs automatically correlated with `trace_id`, `span_id`, and `correlation_id`, with PII/secret redaction |
| Designing service readiness, production launch checklists, or alerting rules | Define Golden Signal SLIs (P50/P95/P99 Histogram quantiles + Error Rate) and Multi-Window Burn-Rate SLO gates |
| Auditing PR diffs or existing services for observability defects or metric cost spikes | Scan for high-cardinality metric labels, `console.log` noise, unpropagated async contexts, and gauge-averaged latencies |
| Purely static documentation edits, local one-off CLI formatting scripts, or CSS token tweaks | Do not activate; use `anti-slop-engineering` |

---

## The Five Absolute Laws

1. **The Low-Cardinality Metrics & High-Cardinality Traces/Logs Split Law:**
   - **Never** place unbounded or high-cardinality values (`user_id`, `customer_id`, `account_id`, `request_id`, `trace_id`, `span_id`, `correlation_id`, `session_id`, `order_id`, `idempotency_key`, `email`, `ip_address`, `error.message`, or raw unparameterized URL paths like `req.url` / `req.path`) inside Metric labels/attributes.
   - Restrict Metric attributes to a compile-time bounded allowlist of low-cardinality dimensions (`http.request.method`, parameterized `http.route` like `/v1/orders/:id`, `http.response.status_code` or `status_class`, `rpc.system`, `error.code` enum, `queue.name`, `worker.outcome`). The Cartesian product of all label values for any single metric family must remain $\prod_{i} |L_i| \le 1,000$.
   - Attach high-cardinality forensic attributes (`app.user_id`, `app.tenant_id`, `app.order_id`, `app.idempotency_key`, `http.request_id`) **exclusively** to OpenTelemetry **Span Attributes** (`span.setAttribute(...)`) and **Structured JSON Log fields**.
2. **The Histogram Quantile Law (Measure P50 / P95 / P99, Never Averages):**
   - Arithmetic averages (`avg_latency_ms = total_ms / count`) hide tail-latency outages where 1%–5% of users experience 30-second timeouts. Pre-computed per-pod percentiles (`gauge.set(p99)`) are mathematically invalid because percentiles cannot be averaged or summed across horizontal replicas.
   - Record all request durations, queue dwell times, and database query latencies using **Histograms** (`Histogram` with explicit domain-calibrated bucket boundaries, e.g., `[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]` seconds, or native OpenTelemetry Exponential Histograms) so P50, P95, and P99 quantiles can be aggregated accurately across any fleet dimension.
3. **The Unbroken W3C Context Propagation Law (`traceparent` + `correlation_id`):**
   - Every request entering at the edge must extract or mint a W3C Trace Context (`traceparent: 00-<32-hex-trace-id>-<16-hex-span-id>-<2-hex-flags>`, `tracestate`) and a deterministic `correlation_id`.
   - Context must never drop across asynchronous boundaries:
     - **HTTP / gRPC Egress:** Inject `traceparent`, `tracestate`, and `x-correlation-id` headers into every outbound request.
     - **Queues, Event Buses & Transactional Outboxes:** Serialize `traceparent` and `correlation_id` into the message headers or outbox row columns at enqueue time (`propagation.inject`), and extract them inside the worker (`propagation.extract`) to start a child or linked `CONSUMER` span before executing business logic.
     - **Database Queries:** Propagate active context to the database driver and annotate query spans with low-cardinality operation names (`SELECT orders.by_id`) or SQLcommenter metadata (`/*traceparent='00-...'*/`) without leaking literal SQL parameter values.
4. **The Structured Log-Trace Correlation & Redaction Law:**
   - Unstructured `console.log`, `console.error`, `print()`, or `fmt.Println` calls in production service paths are prohibited.
   - Every log record must be emitted as structured JSON containing at minimum: `timestamp`, `level`, `message`, `service.name`, `trace_id`, `span_id`, `correlation_id`, and high-cardinality domain context (`user_id`, `order_id`, `error.code`), while enforcing deterministic redaction of credentials (`Authorization`, `cookie`, `password`, `secret`, `token`, `api_key`, full PAN/SSN) prior to serialization.
5. **The Golden Signals & Multi-Window Multi-Burn-Rate SLO Law:**
   - Every critical path must define quantitative Service Level Indicators (SLIs) covering Latency (Histogram P95 and P99), Availability (non-5xx / valid outcome ratio), and Saturation (queue depth / connection pool utilization / consumer lag).
   - Gate production operations on an explicit Error Budget ($1 - \text{SLO}$) using Google SRE **Multi-Window, Multi-Burn-Rate Alerts** (e.g., Fast Burn `14.4x` over `1h` + `5m` consuming 2% budget -> Page; Slow Burn `6x` over `6h` + `30m` consuming 5% budget -> Ticket).

---

## Invariant Rules

1. **Enforce a Metric Attribute Allowlist Decorator/Wrapper.** Wrap metric recorders (`counter.add`, `histogram.record`) in a strongly typed helper that accepts only compile-time bounded attribute keys and strips or rejects forbidden high-cardinality keys (`user_id`, `request_id`, `trace_id`, `email`, `ip`, `url`).
2. **Always normalize HTTP routes before recording metrics.** Use the matched router template (`/api/v1/accounts/:accountId/transfers`) for `http.route`—never the raw request URL (`/api/v1/accounts/acc_991823/transfers`). If a request hits an unmatched `404` path, map `http.route` to the constant `"__unmatched__"` to prevent 404 scanner attacks from exploding metric cardinality.
3. **Require `traceparent` and `correlation_id` fields in every Queue/Outbox envelope schema.** Define async job/event TypeScript/Pydantic/Protobuf schemas with mandatory `traceparent: string` and `correlationId: string` metadata fields so a producer cannot compile without passing trace context.
4. **Bind OpenTelemetry Exemplars to Histogram recordings.** When recording a Histogram measurement inside an active sampled span, attach the span's `trace_id` and `span_id` as a Metric Exemplar so engineers can jump directly from a P99 latency spike on a Grafana histogram bucket to the exact offending Dapper trace.
5. **Record exceptions on the active span before rethrowing or mapping.** Whenever an operation catches an error, call `span.recordException(err)` and `span.setStatus({ code: SpanStatusCode.ERROR, message: err.code })` so trace trees surface the exact failure boundary.
6. **Verify telemetry in unit/integration tests with In-Memory Exporters.** Test suites for instrumented services must assert against an `InMemorySpanExporter` and `InMemoryMetricReader` that (a) zero banned high-cardinality keys appear in emitted metric attributes, and (b) producer and consumer spans share the exact same `traceId` across async queue/outbox hops.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Instrumenting metrics, replacing high-cardinality labels, or configuring P50/P95/P99 latency Histograms | [Enforce Low-Cardinality Metrics & Histograms](usecases/enforce-low-cardinality-metrics-and-histograms.md) | [Low-Cardinality Metrics & Histograms](references/low-cardinality-metrics-and-histograms.md) |
| Instrumenting HTTP/gRPC boundaries, background workers, message queues, outboxes, and DB spans | [Propagate W3C Trace Context End-to-End](usecases/propagate-w3c-trace-context-across-queues-and-workers.md) | [W3C `traceparent` & Async Context Propagation](references/w3c-traceparent-and-async-context-propagation.md) |
| Setting up structured trace-correlated logging, Golden Signal SLIs, and Multi-Burn-Rate SLOs | [Define Golden Signals & Burn-Rate SLOs](usecases/define-golden-signals-and-burn-rate-slos.md) | [Structured Logs, SLIs & Burn-Rate SLOs](references/structured-logs-slis-and-burn-rate-slos.md) |
| Durable observability & SLO assessment record generation and source hazard audit | [Record Contract](references/observability-slo-record-contract.md) | `scripts/observability_guard.py` |

---

## Mandatory Pre-Instrumentation Interrogation Matrix

Before adding a metric, span, log line, or background job handler, answer these five questions:

- **The Cardinality Bomb Check:** What is the maximum number of unique values for *every* attribute on this metric? Could `user_id`, `tenant_id`, `order_id`, `request_id`, `email`, `ip`, `error.message`, or an unparameterized URL (`req.url`) ever enter this label? What happens to the TSDB if 1,000,000 malicious 404 requests hit random URLs?
- **The Quantile Aggregation Check:** Am I measuring latency or payload size with a `Histogram` configured with explicit buckets (to compute P50, P95, P99 across pods), or did I mistakenly emit a `Gauge` of averages/percentiles that cannot be aggregated horizontally?
- **The Async Context Hop Check:** When this HTTP handler inserts a job into a queue, Redis stream, or transactional outbox table, where are `traceparent` and `correlation_id` serialized? When the worker wakes up 10 seconds later in another process, how does it extract `traceparent` so its database span appears under the original frontend trace?
- **The 3:00 AM On-Call Correlation Check:** If thisP99 latency SLO alert fires at 3:00 AM, can the on-call engineer go from the Histogram Exemplar -> to the exact `trace_id` -> to all structured JSON logs across the API gateway, queue worker, and DB layer using a single `trace_id` or `correlation_id` query?
- **The Secret & PII Redaction Check:** Could any span attribute or structured log field inadvertently capture an `Authorization` header, session token, webhook signature, password, or unmasked customer PII?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **High-Cardinality Identifiers in Metric Labels:** Passing `user_id`, `userId`, `customer_id`, `request_id`, `trace_id`, `span_id`, `correlation_id`, `order_id`, `session_id`, `email`, `ip`, or `error.message` into Prometheus/OpenTelemetry metric attributes (`counter.add(1, { user_id })`).
2. **Unnormalized `req.url` / `req.originalUrl` / `req.path` in Metric Labels:** Recording raw URL strings containing path parameters or query strings in metrics instead of parameterized route templates (`http.route = "/v1/orders/:id"`) and `"__unmatched__"` for 404s.
3. **Fire-and-Forget Async Enqueue Without Context Injection:** Pushing payloads to queues, worker pools, `setImmediate`, or outbox tables without injecting W3C `traceparent` and `correlation_id` into the envelope and extracting them on the consumer side.
4. **Gauge-Averaged Latency or Pre-Aggregated Pod Percentiles:** Tracking latency by writing `latencyGauge.set(durationMs)` or computing `sum/count` averages without a `Histogram` supporting P50/P95/P99 bucket quantiles.
5. **Unstructured `console.log` / `print` in Production Paths:** Emitting raw text logs lacking `trace_id`, `span_id`, and `correlation_id` JSON fields, or logging raw error/request objects without PII/secret redaction.
6. **Silent Span Error Swallowing:** Catching an exception inside a traced block without calling `span.recordException(err)` and setting `SpanStatusCode.ERROR`.

---

## Required Output & Review Workflow

Structure all observability implementations, telemetry refactors, and production readiness audits through this 4-phase discipline:

1. **Cardinality Budget & Telemetry Contract:** List every metric family, its instrument type (`counter`, `histogram`, `up_down_counter`), its bounded label allowlist, and the mathematical upper bound of its label cardinality ($\prod |L_i| \le 1,000$). Map all high-cardinality identifiers to Trace Span Attributes and Structured Log fields.
2. **End-to-End W3C Context Propagation Wiring:** Implement W3C `traceparent` (`00-<traceId>-<spanId>-<flags>`), `tracestate`, and `correlation_id` extraction at ingress, propagation through `AsyncLocalStorage`/Context, header injection into queues/outboxes/HTTP clients, and extraction in background workers down to database query spans.
3. **Histogram SLIs & Multi-Burn-Rate SLO Gate:** Configure latency Histograms with explicit bucket boundaries for P50/P95/P99 computation, bind trace Exemplars, wire structured JSON logging with secret redaction, and specify the Multi-Window Burn-Rate SLO alerts (`14.4x` fast burn / `6x` slow burn).
4. **In-Memory Telemetry Verification & Guard Audit:** Verify in tests that emitted metrics contain zero high-cardinality labels and that `traceId` is preserved across async producer->consumer hops, then audit the record and source code with `scripts/observability_guard.py`.

When a durable observability and SLO assessment record is warranted, save a JSON assessment following the [Observability & SLO Record Contract](references/observability-slo-record-contract.md) and audit it with:
```bash
npx anti-slop-engineering observability audit <record.json> --json
# or: python3 scripts/observability_guard.py audit <record.json> [--source <instrumented_file.ts>] --json
```

---

## Domain References

- **[Observability & SLO Gate Playbook Suite](playbooks/README.md)**: Central orchestration index for Google Dapper distributed tracing, OpenTelemetry semantic conventions, cardinality control, and SRE SLO alerting.
- **[Low-Cardinality Metrics, Histograms & Multi-Burn-Rate SLOs Playbook](playbooks/low-cardinality-metrics-and-slo-histograms-playbook.md)**: Cardinality math, compile-time attribute allowlists, Histogram bucket design for P50/P95/P99, Exemplars, and Google SRE Multi-Window Burn-Rate formulas.
- **[Google Dapper & OpenTelemetry End-to-End Context Propagation Playbook](playbooks/dapper-opentelemetry-context-propagation-playbook.md)**: W3C `traceparent` wire format, HTTP/gRPC/Queue/Outbox producer-consumer injection and extraction, database SQLcommenter spans, and trace-correlated structured JSON logging.
- **[Low-Cardinality Metrics & Histograms Reference](references/low-cardinality-metrics-and-histograms.md)**: Production TypeScript, Python, Go, and Rust patterns for type-safe metric wrappers, route normalization, and Histogram buckets.
- **[W3C `traceparent` & Async Context Propagation Reference](references/w3c-traceparent-and-async-context-propagation.md)**: End-to-end context carrier propagation across HTTP, BullMQ/Kafka/SQS queues, transactional outboxes, and database queries.
- **[Structured Logs, SLIs & Burn-Rate SLOs Reference](references/structured-logs-slis-and-burn-rate-slos.md)**: Trace-correlated JSON log serializers with secret redaction, Golden Signals, and PromQL/OTel Multi-Window Burn-Rate alert specifications.
- **[Observability & SLO Record Contract](references/observability-slo-record-contract.md)**: JSON schema and automated verification rules for `scripts/observability_guard.py`.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Metric cardinality explosion | Prometheus OOM or massive Datadog custom metrics bill; `user_id`, `request_id`, or `req.url` in metric labels | Strip high-cardinality keys from metrics via compile-time allowlist; move `user_id`/`request_id` to Span Attributes and Structured Logs |
| 404 scanner cardinality attack | Millions of unique `http.route` time-series from bots probing random URLs | Record matched route template (`/v1/items/:id`) only; collapse all unmatched routes to `"__unmatched__"` |
| Orphaned worker spans | Queue consumer or cron worker starts a brand-new root trace disconnected from the API request | Inject `traceparent` and `correlation_id` into the job/outbox payload on publish and extract parent context before starting the worker span |
| Blind tail-latency outages | Dashboard shows `avg_latency = 45ms` while P99 users time out at `15,000ms` | Replace average/gauge latency metrics with a bucketed `Histogram` and alert on P95/P99 quantiles |
| Uncorrelated log grep | Production error logged via `console.error(err)` with no `trace_id` or `correlation_id` | Emit structured JSON logs enriched automatically from active span context (`trace_id`, `span_id`, `correlation_id`) |
| Telemetry secret leak | Raw headers or payloads logged into span attributes or JSON logs | Enforce a deterministic field redaction allowlist/blocklist (`[REDACTED]`) before log/span emission |

---

## Delegated Skills

- `anti-slop-engineering`: Enforce core SRE discipline (KISS, DRY, YAGNI, Fix Issues at Scale) alongside telemetry instrumentation.
- `paranoid-principal-architect`: Pair W3C `correlation_id` and `traceparent` propagation with idempotency keys, boundary schema validation, and deterministic error codes.
- `mechanical-sympathy-profiler`: Pair P50/P95/P99 Histogram latency telemetry with pprof/FlameGraph profiling to eliminate tail-latency CPU/allocation bottlenecks.
- `scientific-fault-isolation`: Use distributed traces, span events, and trace-correlated structured logs as primary diagnostic evidence during bug reproduction.
- `verification-oracle-architect`: Verify telemetry exporters (`InMemorySpanExporter`, `InMemoryMetricReader`) using deterministic contract assertions without module mocks.

---

## Completion and Limits

The task is complete when all emitted metrics enforce a strict low-cardinality attribute allowlist ($\prod |L_i| \le 1,000$ with zero dynamic IDs or raw URLs), latency distributions are captured via explicit Histograms supporting P50/P95/P99 quantiles with Exemplars, W3C `traceparent` and `correlation_id` propagate unbroken across HTTP, async queues/outboxes, background workers, and database spans, structured JSON logs correlate with `trace_id`/`span_id` and redact secrets, Multi-Window Burn-Rate SLOs are defined, and `scripts/observability_guard.py` reports zero findings. A review may validly output `refuse` or `pause` if code injects high-cardinality IDs into metric labels or drops trace context across async worker hops.
