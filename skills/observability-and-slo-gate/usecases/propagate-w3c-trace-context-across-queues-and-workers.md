# Workflow: Propagate W3C Trace Context Across Queues, Workers & Databases

Use this workflow when instrumenting HTTP/gRPC endpoints that enqueue background jobs, publish events to Kafka/SQS/RabbitMQ/BullMQ/Redis Streams, write to a transactional outbox table, or execute database queries.

## Step-by-Step Procedure

### 1. Extract or Mint W3C `traceparent` & `correlation_id` at Ingress
1. At the HTTP/gRPC ingress boundary, parse the incoming W3C `traceparent` header (`00-<32-hex-trace-id>-<16-hex-parent-span-id>-<2-hex-trace-flags>`) and `tracestate` header.
2. If no valid `traceparent` is present (e.g., an uninstrumented external client), generate a new root 128-bit `traceId` and 64-bit `spanId`.
3. Extract `x-correlation-id` (or default to the root `traceId` if absent), validate its format, and echo `x-correlation-id` and `traceparent` on the HTTP response headers.

### 2. Inject Context into Every Async Queue & Outbox Envelope
1. Require `traceparent: string`, `tracestate?: string`, and `correlationId: string` in the schema of every queue message, event payload, and `outbox_events` database table.
2. Before publishing to a broker or inserting an outbox row, start a `PRODUCER` child span and serialize the active context (`traceparent`, `tracestate`, `correlationId`) into the message headers/columns using `propagation.inject()`.

### 3. Extract Context in Background Workers & Outbox Relays
1. When a worker or queue consumer receives a message, validate and extract `traceparent` and `correlationId` from the envelope via `propagation.extract()`.
2. Start a `CONSUMER` span whose `traceId` matches the extracted `traceparent` and whose `parentSpanId` references the producer span.
3. Attach high-cardinality business identifiers (`app.user_id`, `app.tenant_id`, `app.order_id`, `messaging.message.id`) to the consumer span attributes—never to worker metric labels.

### 4. Propagate Context Down to Database Spans
1. Execute every database query inside the active worker/request context so the database span inherits the same `traceId`.
2. Record low-cardinality span attributes (`db.system`, `db.operation.name`, parameterized `db.query.summary` like `INSERT ledger_entries`) and optionally append W3C SQLcommenter comments (`/*traceparent='00-...'*/`) for database slow-query log correlation without leaking raw SQL parameter literals.
