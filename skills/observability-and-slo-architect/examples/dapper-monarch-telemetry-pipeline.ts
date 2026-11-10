// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
// Canonical Example: Google Monarch & Dapper Telemetry Pipeline
// Demonstrates OpenTelemetry by default, unbroken W3C traceparent context propagation,
// automated RED (Rate, Errors, Duration) metrics, USE (Utilization, Saturation, Errors) metrics,
// structured JSON logging with secret redaction, and Multi-Window Multi-Burn-Rate SLO evaluation.

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

// ============================================================================
// 1. Google Dapper: W3C TraceContext & Context Propagation
// ============================================================================

const W3C_TRACEPARENT_RE = /^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/;

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

export function formatW3CTraceparent(ctx: W3CTraceContext): string {
  return `00-${ctx.traceId}-${ctx.spanId}-${ctx.traceFlags}`;
}

// SQLcommenter database context propagation
export function appendSqlCommenter(sql: string, ctx: W3CTraceContext): string {
  const comment = `/*traceparent='${formatW3CTraceparent(ctx)}',correlation_id='${ctx.correlationId}'*/`;
  return `${sql.trim()} ${comment};`;
}

// ============================================================================
// 2. Google Monarch: Low-Cardinality Metric Governance & Histograms
// ============================================================================

const BANNED_HIGH_CARDINALITY_KEYS = new Set([
  "user_id",
  "userid",
  "app.user_id",
  "customer_id",
  "account_id",
  "request_id",
  "http.request_id",
  "trace_id",
  "span_id",
  "correlation_id",
  "order_id",
  "email",
  "ip",
  "ip_address",
  "raw_url",
  "req.url",
  "url",
]);

export interface MetricExemplar {
  readonly traceId: string;
  readonly spanId: string;
  readonly timestampMs: number;
}

export class BoundedMetricGuard {
  static validateAttributes(attributes: Readonly<Record<string, string | number | boolean>>): void {
    for (const key of Object.keys(attributes)) {
      const lower = key.toLowerCase();
      if (BANNED_HIGH_CARDINALITY_KEYS.has(lower)) {
        throw new MetricCardinalityViolationError(
          key,
          "High-cardinality dynamic identifier is prohibited in time-series metric labels."
        );
      }
    }
  }

  static collapseRoute(matchedRoute: string | undefined): string {
    if (!matchedRoute || matchedRoute.trim() === "") {
      return "__unmatched__";
    }
    // Collapse dynamic IDs if raw path leaked
    if (/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(matchedRoute)) {
      return "__unmatched__";
    }
    return matchedRoute;
  }
}

export interface ExplicitHistogramBucket {
  readonly leMs: number;
  count: number;
}

export class ExplicitBucketHistogram {
  readonly buckets: ExplicitHistogramBucket[];
  count = 0;
  sumMs = 0;
  readonly exemplars: MetricExemplar[] = [];

  constructor(
    readonly name: string,
    bucketBoundariesMs: readonly number[]
  ) {
    this.buckets = bucketBoundariesMs.map((boundary) => ({
      leMs: boundary,
      count: 0,
    }));
  }

  record(
    valueMs: number,
    attributes: Readonly<Record<string, string | number | boolean>>,
    exemplar?: MetricExemplar
  ): void {
    BoundedMetricGuard.validateAttributes(attributes);
    this.count++;
    this.sumMs += valueMs;

    for (const b of this.buckets) {
      if (valueMs <= b.leMs) {
        b.count++;
      }
    }

    if (exemplar) {
      this.exemplars.push(exemplar);
    }
  }

  estimateQuantile(quantile: 0.5 | 0.95 | 0.99): number {
    if (this.count === 0) return 0;
    const targetCount = this.count * quantile;

    let prevLe = 0;
    let prevCount = 0;

    for (const b of this.buckets) {
      if (b.count >= targetCount) {
        const bucketTotal = b.count - prevCount;
        if (bucketTotal === 0) return b.leMs;
        const fraction = (targetCount - prevCount) / bucketTotal;
        return prevLe + fraction * (b.leMs - prevLe);
      }
      prevLe = b.leMs;
      prevCount = b.count;
    }

    return this.buckets[this.buckets.length - 1].leMs;
  }
}

// ============================================================================
// 3. RED & USE Telemetry Architecture
// ============================================================================

export interface BoundedRedLabels {
  readonly "http.request.method": "GET" | "POST" | "PUT" | "DELETE";
  readonly "http.route": string;
  readonly "http.response.status_class": "2xx" | "3xx" | "4xx" | "5xx";
}

export class RedEndpointTelemetry {
  private requestCount = 0;
  private errorCount = 0;
  readonly durationHistogram: ExplicitBucketHistogram;

  constructor() {
    this.durationHistogram = new ExplicitBucketHistogram(
      "http.server.duration",
      [5, 10, 25, 50, 100, 150, 250, 400, 750, 1500, 3000, 7500]
    );
  }

  recordEndpointCall(
    method: "GET" | "POST" | "PUT" | "DELETE",
    route: string,
    statusCode: number,
    durationMs: number,
    exemplar?: MetricExemplar
  ): void {
    const statusClass =
      statusCode >= 500
        ? "5xx"
        : statusCode >= 400
        ? "4xx"
        : statusCode >= 300
        ? "3xx"
        : "2xx";

    const labels: BoundedRedLabels = {
      "http.request.method": method,
      "http.route": BoundedMetricGuard.collapseRoute(route),
      "http.response.status_class": statusClass,
    };

    BoundedMetricGuard.validateAttributes(labels);
    this.requestCount++;
    if (statusCode >= 400) {
      this.errorCount++;
    }

    this.durationHistogram.record(durationMs, labels, exemplar);
  }

  getRate(): number {
    return this.requestCount;
  }

  getErrorRate(): number {
    return this.requestCount > 0 ? this.errorCount / this.requestCount : 0;
  }
}

export interface ResourceUseMetrics {
  readonly resourceName: string;
  readonly utilization: number; // 0.0 to 1.0
  readonly saturationWaiters: number;
  readonly errorCount: number;
}

export class MockDbConnectionPoolUseCollector {
  private totalErrors = 0;

  constructor(
    private readonly activeConnections: number,
    private readonly maxConnections: number,
    private readonly pendingWaiters: number
  ) {}

  collect(): ResourceUseMetrics {
    const utilization =
      this.maxConnections > 0
        ? Math.min(1.0, this.activeConnections / this.maxConnections)
        : 0;

    return {
      resourceName: "db_connection_pool",
      utilization,
      saturationWaiters: this.pendingWaiters,
      errorCount: this.totalErrors,
    };
  }

  recordTimeout(): void {
    this.totalErrors++;
  }
}

// ============================================================================
// 4. Structured JSON Logging with Deterministic Secret Redaction
// ============================================================================

const SENSITIVE_KEY_PATTERNS = [
  /password/i,
  /secret/i,
  /token/i,
  /api[_-]?key/i,
  /authorization/i,
  /cookie/i,
  /access[_-]?token/i,
];

export function redactSensitiveKeys(
  obj: Readonly<Record<string, any>>
): Record<string, any> {
  const result: Record<string, any> = {};
  for (const [key, val] of Object.entries(obj)) {
    const isSensitive = SENSITIVE_KEY_PATTERNS.some((pattern) => pattern.test(key));
    if (isSensitive) {
      result[key] = "[REDACTED]";
    } else if (val && typeof val === "object" && !Array.isArray(val)) {
      result[key] = redactSensitiveKeys(val);
    } else {
      result[key] = val;
    }
  }
  return result;
}

export interface StructuredLogRecord {
  readonly timestamp: string;
  readonly level: "info" | "warn" | "error";
  readonly message: string;
  readonly serviceName: string;
  readonly traceId: string;
  readonly spanId: string;
  readonly correlationId: string;
  readonly context: Record<string, any>;
}

export class StructuredJsonLogger {
  readonly logs: StructuredLogRecord[] = [];

  log(
    level: "info" | "warn" | "error",
    message: string,
    ctx: W3CTraceContext,
    extra: Record<string, any> = {}
  ): StructuredLogRecord {
    const record: StructuredLogRecord = {
      timestamp: new Date().toISOString(),
      level,
      message,
      serviceName: "checkout-settlement-engine",
      traceId: ctx.traceId,
      spanId: ctx.spanId,
      correlationId: ctx.correlationId,
      context: redactSensitiveKeys(extra),
    };

    this.logs.push(record);
    return record;
  }
}

// ============================================================================
// 5. Google SRE Multi-Window Multi-Burn-Rate SLO Evaluator
// ============================================================================

export interface MultiWindowBurnRateAlert {
  readonly alertName: string;
  readonly severity: "page" | "ticket";
  readonly burnRateMultiplier: number;
  readonly longWindow: string;
  readonly shortWindow: string;
  readonly fired: boolean;
  readonly action: string;
}

export class SloMultiBurnRateEvaluator {
  constructor(
    readonly availabilityTarget: number = 0.999 // 99.9%
  ) {}

  evaluate(
    errorRatio1h: number,
    errorRatio5m: number,
    errorRatio6h: number,
    errorRatio30m: number
  ): MultiWindowBurnRateAlert[] {
    const errorBudget = 1.0 - this.availabilityTarget; // 0.001
    const fastBurnThreshold = 14.4 * errorBudget; // 0.0144
    const slowBurnThreshold = 6.0 * errorBudget; // 0.006

    const fastBurnFired =
      errorRatio1h > fastBurnThreshold && errorRatio5m > fastBurnThreshold;
    const slowBurnFired =
      errorRatio6h > slowBurnThreshold && errorRatio30m > slowBurnThreshold;

    return [
      {
        alertName: "CheckoutFastErrorBudgetBurn1hAnd5m",
        severity: "page",
        burnRateMultiplier: 14.4,
        longWindow: "1h",
        shortWindow: "5m",
        fired: fastBurnFired,
        action: fastBurnFired ? "page_and_halt_rollout" : "none",
      },
      {
        alertName: "CheckoutSlowErrorBudgetBurn6hAnd30m",
        severity: "ticket",
        burnRateMultiplier: 6.0,
        longWindow: "6h",
        shortWindow: "30m",
        fired: slowBurnFired,
        action: slowBurnFired ? "open_remediation_ticket" : "none",
      },
    ];
  }
}

// ============================================================================
// 6. Asynchronous Queue Envelope with W3C Context Propagation
// ============================================================================

export interface QueueMessageEnvelope<T> {
  readonly messageId: string;
  readonly traceparent: string;
  readonly correlationId: string;
  readonly payload: T;
}

export function createQueueMessage<T>(
  payload: T,
  ctx: W3CTraceContext
): QueueMessageEnvelope<T> {
  return {
    messageId: `msg_${Math.random().toString(36).substring(2, 10)}`,
    traceparent: formatW3CTraceparent(ctx),
    correlationId: ctx.correlationId,
    payload,
  };
}

export function extractQueueContext(
  envelope: QueueMessageEnvelope<any>,
  idGen: DeterministicTraceIdGenerator
): W3CTraceContext {
  return extractOrMintW3CContext(
    {
      traceparent: envelope.traceparent,
      "x-correlation-id": envelope.correlationId,
    },
    idGen
  );
}
