// SPDX-License-Identifier: MIT
// Example: Observability & SLO Gate — Low-Cardinality Metrics, P50/P95/P99 Histograms with Exemplars, W3C traceparent Propagation Across Async Queues/Workers/DB, and Multi-Burn-Rate SLO Evaluation

export class MetricCardinalityViolationError extends Error {
  readonly code = "METRIC_CARDINALITY_VIOLATION" as const;
  constructor(readonly labelKey: string, readonly reason: string) {
    super(`Metric cardinality violation on label '${labelKey}': ${reason}`);
  }
}

export class BrokenTraceContextError extends Error {
  readonly code = "BROKEN_TRACE_CONTEXT" as const;
  constructor(readonly boundary: string) {
    super(`Missing or invalid W3C traceparent/correlationId at boundary '${boundary}'`);
  }
}

// ---------------------------------------------------------------------------
// 1. W3C Trace Context (traceparent + correlation_id)
// ---------------------------------------------------------------------------

const W3C_TRACEPARENT_RE =
  /^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/;

export interface W3CTraceContext {
  readonly traceId: string;
  readonly spanId: string;
  readonly parentSpanId?: string;
  readonly traceFlags: "00" | "01";
  readonly correlationId: string;
  readonly tracestate?: string;
}

export class DeterministicTraceIdGenerator {
  private counter = 1;

  nextTraceId(): string {
    const hex = (this.counter++).toString(16).padStart(12, "0");
    return `4bf92f3577b34da6a3ce${hex}`;
  }

  nextSpanId(): string {
    const hex = (this.counter++).toString(16).padStart(16, "0");
    return hex;
  }
}

export function extractOrMintW3CContext(
  headers: Readonly<Record<string, string | undefined>>,
  idGen: DeterministicTraceIdGenerator
): W3CTraceContext {
  const rawTraceparent = headers["traceparent"]?.trim().toLowerCase();
  const rawCorrelationId = headers["x-correlation-id"]?.trim();
  const rawTracestate = headers["tracestate"]?.trim();

  if (rawTraceparent) {
    const match = W3C_TRACEPARENT_RE.exec(rawTraceparent);
    if (
      match &&
      match[1] !== "00000000000000000000000000000000" &&
      match[2] !== "0000000000000000"
    ) {
      return {
        traceId: match[1],
        parentSpanId: match[2],
        spanId: idGen.nextSpanId(),
        traceFlags: match[3] === "01" ? "01" : "00",
        correlationId:
          rawCorrelationId && rawCorrelationId.length > 0
            ? rawCorrelationId
            : match[1],
        tracestate: rawTracestate,
      };
    }
  }

  const rootTraceId = idGen.nextTraceId();
  return {
    traceId: rootTraceId,
    spanId: idGen.nextSpanId(),
    traceFlags: "01",
    correlationId:
      rawCorrelationId && rawCorrelationId.length > 0
        ? rawCorrelationId
        : rootTraceId,
    tracestate: rawTracestate,
  };
}

export function createChildContext(
  parent: W3CTraceContext,
  idGen: DeterministicTraceIdGenerator
): W3CTraceContext {
  return {
    traceId: parent.traceId,
    parentSpanId: parent.spanId,
    spanId: idGen.nextSpanId(),
    traceFlags: parent.traceFlags,
    correlationId: parent.correlationId,
    tracestate: parent.tracestate,
  };
}

export function formatW3CTraceparent(ctx: W3CTraceContext): string {
  return `00-${ctx.traceId}-${ctx.spanId}-${ctx.traceFlags}`;
}

// ---------------------------------------------------------------------------
// 2. Low-Cardinality Metric Firewall & Calibrated P50/P95/P99 Histogram
// ---------------------------------------------------------------------------

const ALLOWED_METRIC_LABEL_KEYS = new Set([
  "http.request.method",
  "http.route",
  "http.response.status_class",
  "error.code",
  "queue.name",
  "worker.outcome",
  "db.system",
  "db.operation.name",
]);

const BANNED_HIGH_CARDINALITY_KEYS = new Set([
  "user_id",
  "userid",
  "customer_id",
  "account_id",
  "tenant_id",
  "request_id",
  "trace_id",
  "span_id",
  "correlation_id",
  "order_id",
  "idempotency_key",
  "session_id",
  "email",
  "ip",
  "ip_address",
  "url",
  "raw_url",
  "path",
  "error_message",
]);

const DYNAMIC_PATH_SEGMENT_RE =
  /\/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d{2,}|usr_[a-zA-Z0-9]+|ord_[a-zA-Z0-9]+|acc_[a-zA-Z0-9]+)(?=\/|$)/g;

export function normalizeRouteForMetrics(matchedRouteTemplate: string | undefined): string {
  if (!matchedRouteTemplate || matchedRouteTemplate.trim() === "") {
    return "__unmatched__";
  }
  const clean = matchedRouteTemplate.split("?")[0];
  return clean.replace(DYNAMIC_PATH_SEGMENT_RE, "/:id");
}

export function validateLowCardinalityLabels(
  labels: Readonly<Record<string, string>>
): void {
  for (const [key, value] of Object.entries(labels)) {
    const normalizedKey = key.toLowerCase().replace(/[.-]/g, "_");
    if (BANNED_HIGH_CARDINALITY_KEYS.has(normalizedKey)) {
      throw new MetricCardinalityViolationError(
        key,
        "High-cardinality identifier is strictly prohibited in metric labels; move to Span Attributes or Structured Logs"
      );
    }
    if (!ALLOWED_METRIC_LABEL_KEYS.has(key)) {
      throw new MetricCardinalityViolationError(
        key,
        "Label key is not in the compile-time bounded allowlist"
      );
    }
    if (key === "http.route") {
      DYNAMIC_PATH_SEGMENT_RE.lastIndex = 0;
      if (value.includes("?") || DYNAMIC_PATH_SEGMENT_RE.test(value)) {
        DYNAMIC_PATH_SEGMENT_RE.lastIndex = 0;
        throw new MetricCardinalityViolationError(
          key,
          `Unparameterized dynamic path '${value}' detected in http.route`
        );
      }
    }
  }
}

export interface TraceExemplar {
  readonly traceId: string;
  readonly spanId: string;
  readonly valueMs: number;
}

export interface HistogramSeriesSnapshot {
  readonly labels: Readonly<Record<string, string>>;
  readonly bucketBoundsMs: readonly number[];
  readonly bucketCounts: readonly number[];
  readonly count: number;
  readonly sumMs: number;
  readonly exemplars: readonly TraceExemplar[];
}

export class LowCardinalityHistogram {
  private readonly series = new Map<
    string,
    {
      labels: Readonly<Record<string, string>>;
      counts: number[];
      observations: number[];
      count: number;
      sumMs: number;
      exemplars: TraceExemplar[];
    }
  >();

  constructor(
    readonly name: string,
    readonly bucketBoundsMs: readonly number[] = [
      5, 10, 25, 50, 100, 150, 250, 400, 750, 1500, 3000, 7500,
    ]
  ) {}

  record(
    valueMs: number,
    labels: Readonly<Record<string, string>>,
    traceCtx?: W3CTraceContext
  ): void {
    validateLowCardinalityLabels(labels);
    const key = Object.entries(labels)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join("|");

    let entry = this.series.get(key);
    if (!entry) {
      if (this.series.size >= 1000) {
        throw new MetricCardinalityViolationError(
          this.name,
          "Exceeded hard 1,000 active time-series cardinality budget"
        );
      }
      entry = {
        labels: { ...labels },
        counts: new Array<number>(this.bucketBoundsMs.length + 1).fill(0),
        observations: [],
        count: 0,
        sumMs: 0,
        exemplars: [],
      };
      this.series.set(key, entry);
    }

    let placed = false;
    for (let i = 0; i < this.bucketBoundsMs.length; i++) {
      if (valueMs <= this.bucketBoundsMs[i]) {
        entry.counts[i] += 1;
        placed = true;
        break;
      }
    }
    if (!placed) {
      entry.counts[this.bucketBoundsMs.length] += 1;
    }

    entry.observations.push(valueMs);
    entry.count += 1;
    entry.sumMs += valueMs;

    if (traceCtx && traceCtx.traceFlags === "01") {
      entry.exemplars.push({
        traceId: traceCtx.traceId,
        spanId: traceCtx.spanId,
        valueMs,
      });
    }
  }

  quantile(q: 0.5 | 0.95 | 0.99, labels: Readonly<Record<string, string>>): number {
    const key = Object.entries(labels)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join("|");
    const entry = this.series.get(key);
    if (!entry || entry.observations.length === 0) return 0;
    const sorted = [...entry.observations].sort((a, b) => a - b);
    const idx = Math.min(
      sorted.length - 1,
      Math.max(0, Math.ceil(q * sorted.length) - 1)
    );
    return sorted[idx];
  }

  snapshots(): readonly HistogramSeriesSnapshot[] {
    return Array.from(this.series.values()).map((s) => ({
      labels: s.labels,
      bucketBoundsMs: this.bucketBoundsMs,
      bucketCounts: [...s.counts],
      count: s.count,
      sumMs: s.sumMs,
      exemplars: [...s.exemplars],
    }));
  }
}

// ---------------------------------------------------------------------------
// 3. High-Cardinality Dapper Spans & Redacted Structured JSON Logs
// ---------------------------------------------------------------------------

export interface RecordedSpan {
  readonly name: string;
  readonly kind: "SERVER" | "CLIENT" | "PRODUCER" | "CONSUMER";
  readonly traceId: string;
  readonly spanId: string;
  readonly parentSpanId?: string;
  readonly correlationId: string;
  readonly durationMs: number;
  readonly status: "OK" | "ERROR";
  readonly attributes: Readonly<Record<string, string | number | boolean>>;
}

const SENSITIVE_KEY_RE =
  /(?:authorization|cookie|password|passwd|secret|api[-_]?key|access[-_]?token|refresh[-_]?token|ssn|card[-_]?number)/i;

export function redactTelemetryAttributes(
  attrs: Readonly<Record<string, string | number | boolean>>
): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(attrs)) {
    if (SENSITIVE_KEY_RE.test(k)) {
      out[k] = "[REDACTED]";
    } else if (typeof v === "string" && /^Bearer\s+\S+/i.test(v)) {
      out[k] = "[REDACTED]";
    } else {
      out[k] = v;
    }
  }
  return out;
}

export class InMemoryTelemetrySink {
  readonly spans: RecordedSpan[] = [];
  readonly structuredLogs: string[] = [];

  recordSpan(span: RecordedSpan): void {
    this.spans.push({
      ...span,
      attributes: redactTelemetryAttributes(span.attributes),
    });
  }

  emitStructuredLog(
    level: "INFO" | "WARN" | "ERROR",
    message: string,
    ctx: W3CTraceContext,
    fields: Readonly<Record<string, string | number | boolean>>
  ): void {
    const payload = {
      timestamp: "2026-11-10T13:15:00.000Z",
      level,
      "service.name": "checkout-order-settlement-pipeline",
      message,
      trace_id: ctx.traceId,
      span_id: ctx.spanId,
      correlation_id: ctx.correlationId,
      ...redactTelemetryAttributes(fields),
    };
    this.structuredLogs.push(JSON.stringify(payload));
  }
}

// ---------------------------------------------------------------------------
// 4. End-to-End Pipeline: HTTP -> Outbox Queue -> Worker -> SQLcommenter DB
// ---------------------------------------------------------------------------

export interface TracedQueueMessage<TPayload> {
  readonly messageId: string;
  readonly queueName: string;
  readonly traceparent: string;
  readonly tracestate?: string;
  readonly correlationId: string;
  readonly payload: TPayload;
}

export interface OrderCapturePayload {
  readonly tenantId: string;
  readonly userId: string;
  readonly orderId: string;
  readonly idempotencyKey: string;
  readonly amountCents: number;
}

export function buildSqlCommenterQuery(
  parameterizedSql: string,
  ctx: W3CTraceContext
): string {
  const tp = formatW3CTraceparent(ctx);
  return `${parameterizedSql} /*traceparent='${tp}',correlation_id='${ctx.correlationId}'*/`;
}

export function executeEndToEndTracedOrderPipeline(params: {
  readonly incomingHeaders: Readonly<Record<string, string | undefined>>;
  readonly matchedRouteTemplate: string | undefined;
  readonly payload: OrderCapturePayload;
  readonly simulatedHttpLatencyMs: number;
  readonly simulatedWorkerLatencyMs: number;
  readonly simulatedDbLatencyMs: number;
  readonly idGen: DeterministicTraceIdGenerator;
  readonly sink: InMemoryTelemetrySink;
  readonly httpDurationHistogram: LowCardinalityHistogram;
  readonly workerDurationHistogram: LowCardinalityHistogram;
  readonly dbDurationHistogram: LowCardinalityHistogram;
}): {
  readonly rootTraceId: string;
  readonly correlationId: string;
  readonly executedSqlWithTraceComment: string;
} {
  const {
    incomingHeaders,
    matchedRouteTemplate,
    payload,
    simulatedHttpLatencyMs,
    simulatedWorkerLatencyMs,
    simulatedDbLatencyMs,
    idGen,
    sink,
    httpDurationHistogram,
    workerDurationHistogram,
    dbDurationHistogram,
  } = params;

  // Step 1: HTTP Ingress Span (extracts or mints W3C traceparent + correlation_id)
  const serverCtx = extractOrMintW3CContext(incomingHeaders, idGen);
  const safeRoute = normalizeRouteForMetrics(matchedRouteTemplate);

  // High-cardinality IDs go to Span Attributes & Structured JSON Logs ONLY
  sink.recordSpan({
    name: `POST ${safeRoute}`,
    kind: "SERVER",
    traceId: serverCtx.traceId,
    spanId: serverCtx.spanId,
    parentSpanId: serverCtx.parentSpanId,
    correlationId: serverCtx.correlationId,
    durationMs: simulatedHttpLatencyMs,
    status: "OK",
    attributes: {
      "http.request.method": "POST",
      "http.route": safeRoute,
      "app.user_id": payload.userId,
      "app.tenant_id": payload.tenantId,
      "app.order_id": payload.orderId,
      "app.idempotency_key": payload.idempotencyKey,
      authorization: incomingHeaders["authorization"] ?? "",
    },
  });

  // Low-cardinality labels ONLY on the HTTP Histogram
  httpDurationHistogram.record(
    simulatedHttpLatencyMs,
    {
      "http.request.method": "POST",
      "http.route": safeRoute,
      "http.response.status_class": "2xx",
      "error.code": "NONE",
    },
    serverCtx
  );

  // Step 2: Enqueue into Async Outbox / Queue with Producer Span & Injected traceparent
  const producerCtx = createChildContext(serverCtx, idGen);
  const envelope: TracedQueueMessage<OrderCapturePayload> = {
    messageId: `msg_${payload.orderId}`,
    queueName: "orders.settlement.v1",
    traceparent: formatW3CTraceparent(producerCtx),
    tracestate: producerCtx.tracestate,
    correlationId: producerCtx.correlationId,
    payload,
  };

  sink.recordSpan({
    name: "publish orders.settlement.v1",
    kind: "PRODUCER",
    traceId: producerCtx.traceId,
    spanId: producerCtx.spanId,
    parentSpanId: producerCtx.parentSpanId,
    correlationId: producerCtx.correlationId,
    durationMs: 2,
    status: "OK",
    attributes: {
      "queue.name": envelope.queueName,
      "messaging.message.id": envelope.messageId,
      "app.order_id": payload.orderId,
    },
  });

  // Step 3: Background Worker extracts W3C traceparent + correlationId from envelope
  if (!envelope.traceparent || !envelope.correlationId) {
    throw new BrokenTraceContextError("orders.settlement.v1 consumer");
  }
  const consumerCtx = extractOrMintW3CContext(
    {
      traceparent: envelope.traceparent,
      tracestate: envelope.tracestate,
      "x-correlation-id": envelope.correlationId,
    },
    idGen
  );

  sink.recordSpan({
    name: "process orders.settlement.v1",
    kind: "CONSUMER",
    traceId: consumerCtx.traceId,
    spanId: consumerCtx.spanId,
    parentSpanId: consumerCtx.parentSpanId,
    correlationId: consumerCtx.correlationId,
    durationMs: simulatedWorkerLatencyMs,
    status: "OK",
    attributes: {
      "queue.name": envelope.queueName,
      "app.user_id": envelope.payload.userId,
      "app.order_id": envelope.payload.orderId,
    },
  });

  workerDurationHistogram.record(
    simulatedWorkerLatencyMs,
    {
      "queue.name": envelope.queueName,
      "worker.outcome": "SUCCESS",
    },
    consumerCtx
  );

  // Step 4: Database Client Span inside Worker Context + SQLcommenter
  const dbCtx = createChildContext(consumerCtx, idGen);
  const parameterizedSql =
    "INSERT INTO ledger_settlements (tenant_id, order_id, amount_cents) VALUES ($1, $2, $3)";
  const executedSql = buildSqlCommenterQuery(parameterizedSql, dbCtx);

  sink.recordSpan({
    name: "INSERT ledger_settlements",
    kind: "CLIENT",
    traceId: dbCtx.traceId,
    spanId: dbCtx.spanId,
    parentSpanId: dbCtx.parentSpanId,
    correlationId: dbCtx.correlationId,
    durationMs: simulatedDbLatencyMs,
    status: "OK",
    attributes: {
      "db.system": "postgresql",
      "db.operation.name": "INSERT",
      "app.order_id": envelope.payload.orderId,
    },
  });

  dbDurationHistogram.record(
    simulatedDbLatencyMs,
    {
      "db.system": "postgresql",
      "db.operation.name": "INSERT",
    },
    dbCtx
  );

  sink.emitStructuredLog("INFO", "Order settlement committed", dbCtx, {
    "app.user_id": envelope.payload.userId,
    "app.order_id": envelope.payload.orderId,
    "error.code": "NONE",
    authorization: incomingHeaders["authorization"] ?? "",
  });

  return {
    rootTraceId: serverCtx.traceId,
    correlationId: serverCtx.correlationId,
    executedSqlWithTraceComment: executedSql,
  };
}

// ---------------------------------------------------------------------------
// 5. Google SRE Multi-Window, Multi-Burn-Rate SLO Evaluator
// ---------------------------------------------------------------------------

export interface MultiWindowBurnRateEvaluation {
  readonly sloTarget: number;
  readonly errorBudgetRatio: number;
  readonly burnRate1h: number;
  readonly burnRate5m: number;
  readonly burnRate6h: number;
  readonly burnRate30m: number;
  readonly alertState: "PAGE_FAST_BURN" | "TICKET_SLOW_BURN" | "WITHIN_BUDGET";
}

export function evaluateMultiWindowBurnRateSlo(params: {
  readonly sloTarget: number; // e.g. 0.999 for 99.9%
  readonly errorRate1h: number;
  readonly errorRate5m: number;
  readonly errorRate6h: number;
  readonly errorRate30m: number;
}): MultiWindowBurnRateEvaluation {
  const errorBudgetRatio = 1 - params.sloTarget;
  const burnRate1h = params.errorRate1h / errorBudgetRatio;
  const burnRate5m = params.errorRate5m / errorBudgetRatio;
  const burnRate6h = params.errorRate6h / errorBudgetRatio;
  const burnRate30m = params.errorRate30m / errorBudgetRatio;

  if (burnRate1h >= 14.4 && burnRate5m >= 14.4) {
    return {
      sloTarget: params.sloTarget,
      errorBudgetRatio,
      burnRate1h,
      burnRate5m,
      burnRate6h,
      burnRate30m,
      alertState: "PAGE_FAST_BURN",
    };
  }

  if (burnRate6h >= 6.0 && burnRate30m >= 6.0) {
    return {
      sloTarget: params.sloTarget,
      errorBudgetRatio,
      burnRate1h,
      burnRate5m,
      burnRate6h,
      burnRate30m,
      alertState: "TICKET_SLOW_BURN",
    };
  }

  return {
    sloTarget: params.sloTarget,
    errorBudgetRatio,
    burnRate1h,
    burnRate5m,
    burnRate6h,
    burnRate30m,
    alertState: "WITHIN_BUDGET",
  };
}
