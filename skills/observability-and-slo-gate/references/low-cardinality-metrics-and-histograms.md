# Low-Cardinality Metrics & P50/P95/P99 Histograms Reference

## 1. The Mathematical Law of Metric Cardinality

In Time-Series Databases (Prometheus TSDB, VictoriaMetrics, Mimir, Datadog Metrics), every unique combination of metric name and label key-value pairs instantiates an independent time series in memory and index storage:

$$\text{Active Time Series}(M) = |B| \times \prod_{i=1}^{k} |L_i|$$

where $|B|$ is the number of histogram buckets (plus `_sum`, `_count`, `_created`) and $|L_i|$ is the number of distinct values for label $L_i$.

| Label Set Design | Cardinality Calculation | TSDB & Billing Impact | Verdict |
| --- | --- | --- | --- |
| `method` (5) $\times$ `http.route` (25) $\times$ `status_class` (4) $\times$ 12 buckets | $12 \times 5 \times 25 \times 4 = 6,000$ series ($500$ label combinations) | $\approx 12\text{ MB}$ RAM in Prometheus; negligible cost | **APPROVED** ($\prod |L_i| \le 1,000$) |
| Adding `user_id` ($250,000$ users) to the same Histogram | $6,000 \times 250,000 = 1,500,000,000$ series | Instant Prometheus OOM crash; $>\$100,000/\text{mo}$ Datadog custom metric overage | **FATAL DEFECT** |
| Recording raw `req.url` during a 404 vulnerability scan ($500,000$ random paths) | $12 \times 500,000 = 6,000,000$ series | External attacker triggers TSDB Denial of Service (Economic DoS) | **FATAL DEFECT** |

---

## 2. Strictly Banned vs. Approved Metric Attributes

| Dimension | Allowed in Metrics? | Allowed in Span Attributes & JSON Logs? | Rationale |
| --- | --- | --- | --- |
| `http.request.method` (`GET`, `POST`, `PUT`, `DELETE`, `OTHER`) | **YES** | **YES** | Bounded enum ($\le 8$ values) |
| `http.route` (`/v1/orders/:id`, `"__unmatched__"`) | **YES** | **YES** | Bounded by defined application router templates |
| `http.response.status_class` (`2xx`, `3xx`, `4xx`, `5xx`) or bounded status code | **YES** | **YES** | Bounded enum |
| `error.code` (`INSUFFICIENT_FUNDS`, `TIMEOUT`, `NONE`) | **YES** | **YES** | Bounded domain error catalog ($\le 50$ values) |
| `queue.name` / `worker.outcome` | **YES** | **YES** | Bounded infrastructure topology |
| `user_id`, `customer_id`, `account_id`, `actor_id` | **NEVER** | **YES** (`app.user_id`) | Unbounded per-user cardinality |
| `request_id`, `trace_id`, `span_id`, `correlation_id` | **NEVER** | **YES** (or via Histogram Exemplar) | Unique per request ($\infty$ cardinality) |
| `order_id`, `invoice_id`, `idempotency_key`, `session_id` | **NEVER** | **YES** (`app.order_id`) | Unique per transaction ($\infty$ cardinality) |
| `email`, `ip_address`, `user_agent` (raw) | **NEVER** | **REDACTED / HASHED** | High cardinality + PII compliance leak |
| Raw `req.url`, `req.originalUrl`, `req.path`, `error.message` | **NEVER** | **YES** (sanitized) | Dynamic path IDs and free-form strings explode series |

---

## 3. Compile-Time & Runtime Metric Attribute Allowlist Gate (TypeScript)

Never expose raw untyped `Record<string, string>` metric recording to application handlers. Enforce both a TypeScript compile-time type and a runtime allowlist guard:

```ts
const BANNED_METRIC_LABEL_KEYS = new Set([
  "user_id",
  "userid",
  "customer_id",
  "account_id",
  "tenant_id",
  "request_id",
  "requestid",
  "trace_id",
  "traceid",
  "span_id",
  "spanid",
  "correlation_id",
  "correlationid",
  "session_id",
  "order_id",
  "idempotency_key",
  "email",
  "ip",
  "ip_address",
  "url",
  "raw_url",
  "path",
  "error_message",
]);

export interface BoundedHttpMetricLabels {
  readonly "http.request.method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "OTHER";
  readonly "http.route": string; // Must be parameterized template e.g. "/v1/orders/:id" or "__unmatched__"
  readonly "http.response.status_class": "2xx" | "3xx" | "4xx" | "5xx";
  readonly "error.code": string; // Bounded domain enum e.g. "NONE" | "VALIDATION_ERROR" | "UPSTREAM_TIMEOUT"
}

const UUID_OR_NUMERIC_SEGMENT_RE =
  /\/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d{3,}|acc_[a-zA-Z0-9]+|ord_[a-zA-Z0-9]+)(?=\/|$)/g;

export function normalizeRouteTemplate(matchedRoute: string | undefined): string {
  if (!matchedRoute || matchedRoute.trim() === "") {
    return "__unmatched__";
  }
  const withoutQuery = matchedRoute.split("?")[0];
  return withoutQuery.replace(UUID_OR_NUMERIC_SEGMENT_RE, "/:id");
}

export function assertLowCardinalityLabels(labels: Record<string, string>): void {
  for (const [key, value] of Object.entries(labels)) {
    const normalizedKey = key.toLowerCase().replace(/\./g, "_");
    if (BANNED_METRIC_LABEL_KEYS.has(normalizedKey)) {
      throw new Error(
        `CardinalityGateViolation: High-cardinality attribute '${key}' is banned in metrics; attach to Span Attributes or Structured Logs instead.`
      );
    }
    if (key === "http.route" && (value.includes("?") || UUID_OR_NUMERIC_SEGMENT_RE.test(value))) {
      UUID_OR_NUMERIC_SEGMENT_RE.lastIndex = 0;
      throw new Error(
        `CardinalityGateViolation: Unnormalized dynamic route '${value}' in http.route metric label.`
      );
    }
  }
}
```

---

## 4. Histogram Bucket Calibration & Exemplars for P50 / P95 / P99

Never track latency with a `Gauge` or a bare `Counter`. Configure explicit Histogram buckets aligned with user-facing SLO thresholds and attach the active trace's `traceId` and `spanId` as an **Exemplar**:

```ts
export const HTTP_LATENCY_BUCKETS_MS = [
  5, 10, 25, 50, 100, 150, 250, 400, 750, 1500, 3000, 7500,
] as const;

export interface HistogramExemplar {
  readonly traceId: string;
  readonly spanId: string;
  readonly valueMs: number;
  readonly timestampMs: number;
}
```

In Prometheus / VictoriaMetrics / OpenTelemetry Collector, compute fleet-wide P50, P95, and P99 quantiles from the Histogram buckets:

```promql
# Fleet-wide P99 latency per parameterized route over 5m window
histogram_quantile(
  0.99,
  sum by (le, http_route) (
    rate(http_server_request_duration_ms_bucket[5m])
  )
)
```
