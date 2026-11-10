# Usecase: Enforce OpenTelemetry I/O Spans & W3C Trace Context

## Context
When microservices, background job workers, or database access layers are implemented without end-to-end distributed tracing, production debugging relies on guesswork and uncoordinated log timestamps.

## Objective
Enforce OpenTelemetry Spans across every network egress, database query, and message broker hop, propagating W3C `traceparent` (`00-<trace_id>-<span_id>-<flags>`) and maintaining a continuous causal DAG.

## Execution Steps

1. **Initialize OpenTelemetry Tracer:**
   Use the global tracer provider to acquire a tracer scoped to the current package.
2. **Wrap Remote I/O in CLIENT Spans:**
   Enclose all HTTP, gRPC, and DB calls inside an active span with canonical semantic attributes (`http.request.method`, `server.address`, `db.system`).
3. **Inject Context into Wire Headers:**
   Serialize `traceparent` and `x-correlation-id` into outbound HTTP request headers or message queue headers before dispatch.
4. **Extract Context in Consumer / Background Worker:**
   Before processing an incoming HTTP request or queue job, parse `traceparent` and start a `SERVER` or `CONSUMER` span linked to the parent.
5. **Attach SQLcommenter Comments to DB Statements:**
   Format SQL queries to include `/*traceparent='...'*/` for storage engine observability.
6. **Record Exceptions Explicitly:**
   In `catch` blocks, call `span.recordException(err)` and set `SpanStatusCode.ERROR` before rethrowing or translating domain errors.
