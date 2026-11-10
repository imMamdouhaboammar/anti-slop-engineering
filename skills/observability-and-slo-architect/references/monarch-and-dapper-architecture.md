# Google Monarch & Dapper Telemetry Architecture

The Monarch & Dapper paradigm defines production observability at planetary scale. It enforces strict separation between bounded, streaming time-series metrics (Google Monarch) and high-cardinality, causal distributed traces (Google Dapper).

---

## 1. Google Monarch: In-Memory Metric Stream Model

Google Monarch is a multi-tenant, globally distributed, in-memory time-series monitoring system. Unlike conventional TSDBs that allow arbitrary key-value pairs, Monarch models metrics as strongly typed, schema-governed streams.

### Core Architectural Axioms of Monarch

1. **Target-Stream Schema:**
   Every metric family is bound to a defined `Target` (e.g. `service`, `cluster`, `zone`, `pod`) and a fixed set of low-cardinality stream field labels.
2. **The Cardinality Ceiling ($\prod |L_i| \le 1,000$):**
   The Cartesian product of all possible label combinations for any metric family must remain strictly bounded:
   $$\prod_{i=1}^{k} |L_i| \le 1,000$$
   Attaching dynamic runtime IDs (`user_id`, `request_id`, `order_id`, `ip_address`, `email`, raw URLs) into metric labels creates time-series combinatorial explosion, exhausting TSDB memory and crashing query engines.
3. **Stream Pre-Aggregation:**
   Monarch aggregates metrics at ingest time. Arithmetic averages of latencies across distributed machines are mathematically invalid (averages cannot be aggregated across nodes with unequal request counts). All latencies must be recorded as **Histograms** with explicit bucket boundaries.
4. **404 Route Collapsing:**
   Unmatched URL paths must be normalized to `"__unmatched__"`. If raw URLs like `/users/4a7f/profile` enter metric labels, a single malicious web crawler hitting 100,000 random URLs will spawn 100,000 unique metric streams, causing immediate TSDB denial-of-service.
5. **Trace Exemplars:**
   Monarch bridges metrics and traces by attaching Exemplars (`trace_id`, `span_id`, timestamp, latency) to Histogram bucket observations. An operator seeing an elevation in the 99th-percentile bucket can immediately click through to the exact Dapper trace responsible for the tail latency.

---

## 2. Google Dapper: Distributed Tracing & Causal Trees

Google Dapper provides end-to-end causal path tracing across distributed microservices, message queues, and storage backends.

### Core Architectural Axioms of Dapper

1. **OpenTelemetry by Default:**
   Every I/O operation (HTTP request, gRPC invocation, database query, cache fetch, message queue publish/consume) must occur within an active Span.
2. **W3C TraceContext Wire Standard:**
   Context crosses network and process boundaries using standard headers:
   - `traceparent`: `00-<32-hex-trace-id>-<16-hex-span-id>-<2-hex-flags>`
   - `tracestate`: vendor/environment routing data
   - `x-correlation-id`: stable business transaction identifier
3. **Forensic Attribute Placement:**
   All high-cardinality diagnostic data (`user_id`, `order_id`, `cart_id`, `idempotency_key`, `error.message`) must be attached exclusively as **Span Attributes** (`span.setAttribute(...)`) or structured JSON log properties—never as metric labels.
4. **SQLcommenter for Database Spans:**
   Database drivers must propagate active trace context directly into SQL statements using SQLcommenter syntax:
   ```sql
   SELECT id, balance FROM accounts WHERE id = ? /*traceparent='00-4bf92f3577b34da6a3ce000000000001-0000000000000002-01'*/;
   ```
   This links slow database query logs directly to the user's initial HTTP request.
5. **Deterministic Error Recording:**
   When an operation fails, the span must record the exception and set the canonical error status:
   ```typescript
   span.recordException(err);
   span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
   ```

---

## 3. Monarch vs Dapper Telemetry Decision Matrix

| Data Type | System | Allowed Identifiers | Prohibited Identifiers | Aggregation Mechanism |
| --- | --- | --- | --- | --- |
| **Metrics** | Google Monarch | `http.method`, `http.route`, `http.status_class`, `db.system`, `queue.name` | `user_id`, `request_id`, `order_id`, `email`, `ip`, raw URLs | Explicit-bucket Histograms, Sum counters |
| **Traces** | Google Dapper | `user_id`, `tenant_id`, `order_id`, `idempotency_key`, stack traces | None (unbounded attributes permitted) | Causal DAG, Span waterfall, Flame graphs |
| **Logs** | Structured Logger | `trace_id`, `span_id`, `correlation_id`, `user_id`, redacted parameters | Unmasked secrets, passwords, tokens, full PAN/SSN | Trace-correlated JSON search indices |
