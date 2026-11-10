# Playbook 2: OpenTelemetry I/O Spans & W3C TraceContext Propagation

This playbook details how to instrument distributed services following the Google Dapper and OpenTelemetry specifications: ensuring every I/O operation is enclosed in a standard Span, passing W3C TraceContext across async boundaries, and propagating context into database queries and structured logs.

---

## 1. Wrap Every I/O Boundary in a Standard Span

Every network egress, database query, cache lookup, or file I/O must execute within an active OpenTelemetry Span.

### Pattern: Outbound HTTP Request Wrapper

```typescript
import { trace, SpanKind, SpanStatusCode } from "@opentelemetry/api";

const tracer = trace.getTracer("checkout-service");

export async function tracedFetch(url: string, init?: RequestInit): Promise<Response> {
  const parsedUrl = new URL(url);
  const route = `${parsedUrl.origin}${parsedUrl.pathname}`;

  return tracer.startActiveSpan(
    `HTTP ${init?.method ?? "GET"} ${parsedUrl.hostname}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "http.request.method": init?.method ?? "GET",
        "url.full": route,
        "server.address": parsedUrl.hostname,
      },
    },
    async (span) => {
      const headers = new Headers(init?.headers);
      
      // Inject active W3C traceparent and correlation ID into outbound headers
      const activeSpanContext = span.spanContext();
      headers.set(
        "traceparent",
        `00-${activeSpanContext.traceId}-${activeSpanContext.spanId}-${activeSpanContext.traceFlags.toString(16).padStart(2, "0")}`
      );

      try {
        const res = await fetch(url, { ...init, headers });
        span.setAttribute("http.response.status_code", res.status);
        if (res.status >= 500) {
          span.setStatus({ code: SpanStatusCode.ERROR, message: `HTTP ${res.status}` });
        } else {
          span.setStatus({ code: SpanStatusCode.OK });
        }
        return res;
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

## 2. Propagate Context Across Message Queues & Transactional Outbox

When a service enqueues a message or writes to a transactional outbox table, the active trace context must be stored in the payload metadata.

### Producer Injection (Kafka / SQS / BullMQ / Outbox)

```typescript
export interface OutboxRecord<T> {
  id: string;
  aggregateType: string;
  aggregateId: string;
  eventType: string;
  traceparent: string;
  correlationId: string;
  payload: T;
  createdAt: Date;
}

export function createOutboxRecord<T>(
  aggregateType: string,
  aggregateId: string,
  eventType: string,
  payload: T,
  activeContext: W3CTraceContext
): OutboxRecord<T> {
  return {
    id: crypto.randomUUID(),
    aggregateType,
    aggregateId,
    eventType,
    traceparent: `00-${activeContext.traceId}-${activeContext.spanId}-${activeContext.traceFlags}`,
    correlationId: activeContext.correlationId,
    payload,
    createdAt: new Date(),
  };
}
```

### Worker Consumer Extraction

```typescript
export async function consumeOutboxJob<T>(
  record: OutboxRecord<T>,
  handler: (payload: T) => Promise<void>
): Promise<void> {
  const remoteContext = parseW3CTraceparent(record.traceparent);

  // Resume trace tree under original parent
  await tracer.startActiveSpan(
    `worker.process ${record.eventType}`,
    {
      kind: SpanKind.CONSUMER,
      parent: remoteContext,
      attributes: {
        "messaging.system": "transactional_outbox",
        "messaging.destination": record.aggregateType,
        "app.aggregate_id": record.aggregateId,
        "correlation_id": record.correlationId,
      },
    },
    async (span) => {
      try {
        await handler(record.payload);
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

## 3. Correlated Structured JSON Logging

Never emit unstructured text strings or raw `console.log` statements. Every log must be emitted as structured JSON automatically enriched with active tracing metadata:

```typescript
export function logStructured(
  level: "info" | "warn" | "error",
  message: string,
  context: W3CTraceContext,
  extra: Record<string, any> = {}
): void {
  const sanitizedExtra = sanitizeSecrets(extra);

  const entry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    service: "checkout-order-pipeline",
    trace_id: context.traceId,
    span_id: context.spanId,
    correlation_id: context.correlationId,
    ...sanitizedExtra,
  };

  process.stdout.write(JSON.stringify(entry) + "\n");
}
```
