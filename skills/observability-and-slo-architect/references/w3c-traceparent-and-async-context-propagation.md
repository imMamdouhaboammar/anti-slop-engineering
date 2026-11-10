# W3C TraceContext & Async Context Propagation

Distributed causality breaks whenever context fails to cross asynchronous boundaries. In modern systems, this occurs predominantly across message brokers (Kafka, SQS, RabbitMQ, BullMQ), transactional outbox tables, worker thread pools, and database client queries.

---

## 1. W3C TraceContext Wire Format

The W3C TraceContext specification defines the canonical HTTP/RPC/message headers:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              ^  ^                                ^                ^
              |  |-- 32-hex trace ID              |-- 16-hex span  |-- 2-hex flags
              |-- version (always 00)                 ID               (01 = sampled)
```

Secondary correlation headers:
- `tracestate`: Opaque vendor-specific key-value pairs (e.g. `congo=t61rcWkgMzE,rojo=00f067a`).
- `x-correlation-id`: Durable business correlation token linking logs and traces across distinct systems.

---

## 2. Asynchronous Queue & Outbox Context Propagation

Every async producer must serialize active context into the message envelope. Every worker must extract this context before executing work.

### Producer Context Injection

```typescript
export interface MessageEnvelope<T> {
  readonly messageId: string;
  readonly traceparent: string;
  readonly correlationId: string;
  readonly tracestate?: string;
  readonly payload: T;
}

export function createMessageEnvelope<T>(
  payload: T,
  activeContext: W3CTraceContext
): MessageEnvelope<T> {
  return {
    messageId: crypto.randomUUID(),
    traceparent: `00-${activeContext.traceId}-${activeContext.spanId}-${activeContext.traceFlags}`,
    correlationId: activeContext.correlationId,
    tracestate: activeContext.tracestate,
    payload,
  };
}
```

### Consumer Context Extraction & Linked Spans

```typescript
export function processQueueMessage<T>(
  envelope: MessageEnvelope<T>,
  handler: (payload: T) => Promise<void>
): Promise<void> {
  const parentContext = parseW3CTraceparent(envelope.traceparent);
  
  // Start CONSUMER span parented or linked to the producer span
  return tracer.startActiveSpan(
    "queue.process_message",
    {
      kind: SpanKind.CONSUMER,
      parent: parentContext,
      attributes: {
        "messaging.system": "kafka",
        "messaging.message_id": envelope.messageId,
        "correlation_id": envelope.correlationId,
      },
    },
    async (span) => {
      try {
        await handler(envelope.payload);
        span.setStatus({ code: SpanStatusCode.OK });
      } catch (err: any) {
        span.recordException(err);
        span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
        throw err;
      } finally {
        span.end();
      }
    }
  );
}
```

---

## 3. Database Context Propagation: SQLcommenter

To correlate database slow query logs with application traces without modifying SQL query logic, inject W3C traceparent into the SQL query string using SQLcommenter syntax:

```typescript
export function formatSqlWithComment(sql: string, context: W3CTraceContext): string {
  const comment = `/*traceparent='00-${context.traceId}-${context.spanId}-${context.traceFlags}',correlation_id='${context.correlationId}'*/`;
  return `${sql.trim()} ${comment};`;
}
```

When query logs surface in PostgreSQL, MySQL, or Cloud Spanner, the `traceparent` comment allows immediate retrieval of the originating HTTP request trace in Google Cloud Trace or Jaeger.
