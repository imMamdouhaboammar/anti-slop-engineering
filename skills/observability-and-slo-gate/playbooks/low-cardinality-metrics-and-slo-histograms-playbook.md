# Low-Cardinality Metrics, P50/P95/P99 Histograms & Multi-Burn-Rate SLOs Playbook

## 1. The Cardinality Firewall: Why Metrics and Traces Have Opposite Laws

Metrics and Traces serve fundamentally different storage engines:
- **Metrics Engine (Prometheus TSDB / Datadog / Mimir):** Pre-aggregates numeric counters and histogram buckets in memory, indexed by the unique combination of label key-values. Cost and memory scale linearly with the **Cartesian product of unique label values** ($\prod |L_i|$), **not** with traffic volume.
- **Distributed Tracing & Log Engine (Jaeger / Tempo / ClickHouse / BigQuery):** Stores individual event records append-only, indexed by timestamp and `trace_id` / inverted column indexes. Cost scales with **event volume and sampling rate**, making high-cardinality attributes (`user_id`, `order_id`, `idempotency_key`) nearly free to store per span.

### Mandatory Cardinality Firewall Table

| Telemetry Signal | Cardinality Budget | Permitted Attributes | Strictly Prohibited Attributes |
| --- | --- | --- | --- |
| **Metrics (`Counter`, `Histogram`, `UpDownCounter`)** | $\prod_{i} |L_i| \le 1,000$ per metric family | `http.request.method`, parameterized `http.route`, `http.response.status_class`, bounded `error.code`, `queue.name`, `db.system`, `db.operation.name` | `user_id`, `customer_id`, `tenant_id` (unbounded), `request_id`, `trace_id`, `span_id`, `correlation_id`, `order_id`, `email`, `ip_address`, raw `req.url`, `error.message` |
| **Traces (`Span` Attributes & Events)** | Unbounded ($\infty$) | All metric attributes **PLUS** `app.user_id`, `app.tenant_id`, `app.order_id`, `app.idempotency_key`, `messaging.message.id`, `db.query.summary` | Unredacted secrets (`Authorization`, `cookie`, `password`, `api_key`, raw credit cards) |
| **Logs (Structured JSON)** | Unbounded ($\infty$) | `trace_id`, `span_id`, `correlation_id`, `service.name`, `level`, `error.code`, `app.user_id`, `app.order_id` | Unredacted secrets, raw stack traces exposed to external clients, unstructured `console.log` text |

---

## 2. Defending Against the 404 Route-Scanner Cardinality Attack

Even if developers avoid putting `user_id` into metric labels, naive HTTP middleware often sets `http.route: req.path` or `req.url`. When an external vulnerability scanner probes `/wp-admin/1`, `/wp-admin/2`, ..., `/api/v1/users/9948123`, the service creates millions of distinct time-series.

**Mandatory Defense:**
1. Record metrics **after** route matching completes, reading the static route pattern (`req.route?.path ?? "__unmatched__"`).
2. Pass every route label through a deterministic sanitizer that replaces raw UUIDs, numeric IDs (`\d{3,}`), and prefixed entity IDs (`usr_...`, `ord_...`, `acc_...`) with `/:id`, and collapses unmatched routes to `"__unmatched__"`.

---

## 3. Histogram Quantile Engineering (Why Averages Lie)

Suppose an API processes 99 requests in `10ms` and 1 request hits a database lock timeout of `10,000ms`:
- The **arithmetic average** is $\frac{99 \times 10 + 10,000}{100} = 109.9\text{ms}$—looking completely healthy on a dashboard while 1 in 100 checkout users suffers a 10-second stall.
- Emitting `p99_latency_gauge.set(localP99)` from each Kubernetes pod is also broken: you **cannot** average or sum percentiles across 20 pods with uneven traffic.

**Mandatory Histogram Solution:**
1. Use a `Histogram` instrument with explicit bucket boundaries (`[5, 10, 25, 50, 100, 150, 250, 400, 750, 1500, 3000, 7500]` ms) covering both fast cache hits (`5ms`–`25ms`), SLO targets (`150ms` P95, `400ms` P99), and timeout cliffs (`3000ms`–`7500ms`).
2. Attach a **Trace Exemplar** (`{ traceId, spanId, valueMs }`) whenever a Histogram observation is recorded inside a sampled span, bridging the Low-Cardinality Metric world directly to the High-Cardinality Trace world.

---

## 4. Google SRE Multi-Window, Multi-Burn-Rate SLO Gate

For every critical service boundary, establish an Error Budget ($1 - \text{SLO}$) and enforce two Multi-Window Burn-Rate gates:
- **Fast Burn (`14.4x` over `1h` and `5m`):** Consumes 2% of the 30-day error budget in 1 hour. Triggers immediate paging and halts automated deployments.
- **Slow Burn (`6.0x` over `6h` and `30m`):** Consumes 5% of the 30-day error budget in 6 hours. Triggers an actionable remediation ticket before the budget exhausts over a weekend.
