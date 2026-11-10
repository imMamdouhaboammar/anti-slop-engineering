# Google Dapper & OpenTelemetry End-to-End Context Propagation Playbook

## 1. The Unbroken Causal Chain Principle (Google Dapper School)

In the Google Dapper architecture, a distributed trace is a causal tree of timed spans sharing a single 128-bit `trace_id`, connected by `parent_span_id` edges and accompanied by a request-scoped `correlation_id`. If any single hop—an API gateway, an `AsyncLocalStorage` callback, a BullMQ/Kafka/SQS queue producer, a transactional outbox poller, or a database pool—drops the context carrier, the tree splits into disconnected orphan traces.

---

## 2. The Four Mandatory Propagation Seams

### Seam 1: Edge Ingress & Outbound HTTP/gRPC Calls
- **Ingress:** Extract `traceparent` (`00-<traceId>-<parentSpanId>-<flags>`), `tracestate`, and `x-correlation-id` from incoming headers. Validate hex lengths and reject all-zero trace/span IDs. Mint a child `SERVER` span and echo `x-correlation-id` + `traceparent` in response headers so frontend error boundaries can display the exact support `correlation_id`.
- **Egress:** Wrap `fetch` / gRPC clients so every outbound request starts a `CLIENT` span and injects `traceparent: 00-<traceId>-<clientSpanId>-<flags>` and `x-correlation-id`.

### Seam 2: Asynchronous Message Queues (Kafka, SQS, RabbitMQ, BullMQ, Redis Streams)
- **Producer:** Never publish a raw business payload alone. Wrap every payload in a `TracedAsyncEnvelope<T>` containing mandatory `traceparent` and `correlationId` fields populated from a `PRODUCER` child span.
- **Consumer:** Before running domain logic, parse `envelope.traceparent` and `envelope.correlationId` to start a `CONSUMER` child span with `traceId === envelope.traceId` and `parentSpanId === envelope.producerSpanId`.

### Seam 3: Transactional Outbox Tables
- When persisting domain events in a relational `outbox_events` table inside a database transaction, include explicit `traceparent VARCHAR(55) NOT NULL` and `correlation_id VARCHAR(64) NOT NULL` columns in the table schema.
- When the outbox relay worker polls and dispatches rows to the message broker, it extracts `row.traceparent` and `row.correlation_id` so the downstream consumer span links directly back to the originating HTTP transaction.

### Seam 4: Database Client Queries & SQLcommenter
- Wrap database query execution (`queryTraced`) to create a `CLIENT` span recording low-cardinality attributes (`db.system = "postgresql"`, `db.operation.name = "INSERT"`, `db.collection.name = "orders"`).
- Append a parameterized SQLcommenter suffix (`/*traceparent='00-<traceId>-<dbSpanId>-01',correlation_id='<corrId>'*/`) so DBAs and slow-query analyzers can map any lock contention or slow query back to the exact user trace without logging raw SQL parameter values (`$1, $2`).

---

## 3. Verification via In-Memory Span & Metric Exporters

Never trust that context propagation works by visual inspection alone. In automated tests:
1. Execute an end-to-end flow: `Frontend HTTP Request -> API Handler -> Queue/Outbox Producer -> Background Worker Consumer -> Database Query`.
2. Inspect the collected spans in `InMemorySpanExporter`:
   - Assert all 4 spans (`SERVER`, `PRODUCER`, `CONSUMER`, `CLIENT` DB) share the **exact same `traceId`** and `correlationId`.
   - Assert the parent-child chain holds: `PRODUCER.parentSpanId === SERVER.spanId`, `CONSUMER.parentSpanId === PRODUCER.spanId`, and `DB_CLIENT.parentSpanId === CONSUMER.spanId`.
   - Assert high-cardinality `app.user_id` and `app.order_id` exist on the Span attributes and JSON logs, while `InMemoryMetricReader` contains **zero** high-cardinality label keys.
