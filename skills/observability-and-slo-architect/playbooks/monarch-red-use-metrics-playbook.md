# Playbook 1: Metric Cardinality Governance, RED Endpoints & USE Resources

This playbook provides actionable, step-by-step instructions for implementing metric instrumentation that strictly obeys Google Monarch low-cardinality principles, emits RED metrics for endpoints, and monitors resource capacity via USE metrics.

---

## 1. Eliminate Metric Cardinality Bombs

### Rule 1: Compile-Time Allowlist for Metric Attributes
Never pass arbitrary context objects directly into metric recorders. Construct a dedicated attributes object restricted to bounded dimensions:

```typescript
export interface BoundedHttpMetricLabels {
  readonly "http.request.method": "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  readonly "http.route": string;
  readonly "http.response.status_class": "2xx" | "3xx" | "4xx" | "5xx";
}

export function buildMetricLabels(
  method: string,
  matchedRoute: string | undefined,
  statusCode: number
): BoundedHttpMetricLabels {
  const statusClass =
    statusCode >= 500 ? "5xx" :
    statusCode >= 400 ? "4xx" :
    statusCode >= 300 ? "3xx" : "2xx";

  return {
    "http.request.method": method.toUpperCase() as any,
    "http.route": matchedRoute && matchedRoute.trim() !== "" ? matchedRoute : "__unmatched__",
    "http.response.status_class": statusClass,
  };
}
```

### Rule 2: 404 Route Collapsing
If an attacker sends 1,000,000 requests to `/users/uuid-1`, `/users/uuid-2`, etc., the routing framework must never emit the raw pathname as a label. Map unmatched requests to `"__unmatched__"`:

```typescript
app.use((req, res) => {
  recordEndpointMetrics(req.method, "__unmatched__", 404, durationMs);
  res.status(404).json({ error: "Not Found" });
});
```

---

## 2. Implement the RED Method on Endpoints

For every inbound API route:
1. **Rate:** Increment `http.server.request.count`.
2. **Errors:** When status is 4xx or 5xx, increment `http.server.error.count`.
3. **Duration:** Record latency into `http.server.duration` Histogram.

```typescript
export class RedEndpointMetrics {
  constructor(
    private readonly requestCounter: Counter,
    private readonly errorCounter: Counter,
    private readonly durationHistogram: Histogram
  ) {}

  record(method: string, route: string, statusCode: number, durationMs: number, exemplar?: { traceId: string; spanId: string }): void {
    const labels = buildMetricLabels(method, route, statusCode);
    this.requestCounter.add(1, labels);

    if (statusCode >= 400) {
      this.errorCounter.add(1, labels);
    }

    this.durationHistogram.record(durationMs, labels, exemplar);
  }
}
```

---

## 3. Implement the USE Method on Resources

For every critical resource (Database connection pool, message queue consumer pool, worker threads, memory):

### Example: Database Connection Pool USE Collector

```typescript
export class DbConnectionPoolUseCollector {
  constructor(
    private readonly pool: Pool,
    private readonly utilizationGauge: Gauge,
    private readonly saturationGauge: Gauge,
    private readonly errorCounter: Counter
  ) {}

  collect(): void {
    const active = this.pool.totalCount - this.pool.idleCount;
    const max = this.pool.options.max ?? 10;
    const pendingWaiters = this.pool.waitingCount;

    // Utilization: active / max (0.0 to 1.0)
    const utilization = max > 0 ? active / max : 0;
    this.utilizationGauge.set(utilization, { pool: "primary_pg" });

    // Saturation: count of waiting queries
    this.saturationGauge.set(pendingWaiters, { pool: "primary_pg" });
  }

  recordCheckoutTimeout(): void {
    this.errorCounter.add(1, { pool: "primary_pg", error: "checkout_timeout" });
  }
}
```

---

## 4. Verification Checklist

1. [ ] Metric labels have a Cartesian product $\le 1,000$.
2. [ ] Zero occurrences of `user_id`, `request_id`, `email`, or `ip` in metric labels.
3. [ ] All unmatched 404 paths mapped to `"__unmatched__"`.
4. [ ] Latency recorded via explicit-bucket Histogram with P50, P95, and P99 quantiles.
5. [ ] Trace Exemplars attached to sampled latency observations.
6. [ ] USE metrics instrumented on DB pools, worker queues, and memory.
