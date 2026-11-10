# Usecase: Emit Automated RED & USE Metrics Without Cardinality Explosions

## Context
Services often suffer from metric cardinality explosions when engineers pass dynamic user identifiers into Prometheus or Datadog metric labels, or fail to observe resource exhaustion until processes crash.

## Objective
Emit RED (Rate, Errors, Duration) metrics for endpoints and USE (Utilization, Saturation, Errors) metrics for resources, while strictly enforcing the Google Monarch bounded cardinality rule ($\prod |L_i| \le 1,000$).

## Execution Steps

1. **Audit Metric Label Dimensions:**
   Verify that all metric labels are drawn from a compile-time allowlist of low-cardinality values (`http.route`, `http.request.method`, `http.response.status_class`).
2. **Collapse 404 Routes:**
   Ensure unmatched routes map to `"__unmatched__"` to prevent scanner attacks from exhausting TSDB memory.
3. **Record Duration in Explicit-Bucket Histograms:**
   Define calibrated bucket thresholds (e.g. `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]` ms) and record latencies into Histograms. Ban arithmetic averages and gauge percentiles.
4. **Attach Trace Exemplars:**
   Bind active `trace_id` and `span_id` as Exemplars on Histogram bucket recordings so operators can jump directly from Grafana latency spikes to Dapper traces.
5. **Collect USE Metrics on Resources:**
   Periodically poll connection pools, thread pools, memory, and message queues to emit Utilization (fraction busy), Saturation (pending waiters), and Errors (timeouts/drops).
