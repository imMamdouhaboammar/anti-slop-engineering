# Workflow: Enforce Low-Cardinality Metrics & P50/P95/P99 Histograms

Use this workflow when adding Prometheus, OpenTelemetry, or Datadog metrics to HTTP routes, RPC services, message consumers, or database gateways, or when remediating a metric cardinality explosion.

## Step-by-Step Procedure

### 1. Audit & Strip High-Cardinality Metric Attributes
1. Inspect every `createCounter`, `createHistogram`, `createUpDownCounter`, and `Gauge` call site.
2. Immediately remove any dynamic or unbounded identifier from metric attributes: `user_id`, `tenant_id` (unless strictly capped to a tiny fixed enum), `request_id`, `trace_id`, `span_id`, `correlation_id`, `order_id`, `idempotency_key`, `email`, `ip_address`, `error.message`, or raw `req.url` / `req.path`.
3. Relocate those high-cardinality identifiers to OpenTelemetry Span Attributes (`span.setAttribute("app.user_id", userId)`) and Structured JSON Log fields.

### 2. Define a Compile-Time Bounded Metric Label Allowlist
1. Create a strict TypeScript/Python/Go/Rust type or validation wrapper for metric attributes (e.g., `BoundedHttpMetricAttributes` containing only `http.request.method`, parameterized `http.route`, `http.response.status_class`, and bounded `error.code`).
2. Normalize `http.route` to the router template (`/v1/orders/:orderId/capture`) rather than the raw request path. Map all unmatched `404` paths to `"__unmatched__"`.
3. Calculate the theoretical maximum cardinality product $\prod_{i} |L_i|$ across all labels on the metric family and verify $\prod_{i} |L_i| \le 1,000$.

### 3. Configure Calibrated Latency Histograms (P50 / P95 / P99)
1. Replace any `Gauge`-based latency tracking or arithmetic `sum/count` average calculation with a `Histogram` instrument (`http.server.request.duration`, `messaging.process.duration`, `db.client.operation.duration`).
2. Declare explicit bucket boundaries matched to the domain SLO (e.g., `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]` ms) so P50, P95, and P99 quantiles can be computed accurately across replicas.
3. Attach the active span's `trace_id` and `span_id` as an Exemplar on histogram recordings so high-latency bucket spikes link directly to distributed traces.

### 4. Verify with an In-Memory Metric Reader
1. In the test suite, collect emitted metric data points via an `InMemoryMetricReader`.
2. Assert that zero metric data points contain banned high-cardinality keys (`user_id`, `request_id`, `trace_id`, etc.) and that Histogram bucket counts and `sum`/`count` accurately reflect recorded latencies.
