# Structured Logs, Golden Signal SLIs & Multi-Burn-Rate SLOs Reference

## 1. Trace-Correlated Structured JSON Logging with Deterministic Redaction

Unstructured text logs (`console.log("Order failed for user " + userId)`) cannot be joined across microservices or filtered reliably during an outage. Every log entry must be emitted as single-line JSON enriched with the active W3C trace context:

```json
{
  "timestamp": "2026-11-10T13:15:00.250Z",
  "level": "ERROR",
  "service.name": "checkout-settlement-service",
  "message": "Upstream payment capture timed out",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "a3f190bc441209e1",
  "correlation_id": "corr_01J9Z8K4M2",
  "http.route": "/v1/orders/:id/capture",
  "error.code": "UPSTREAM_PAYMENT_TIMEOUT",
  "app.user_id": "usr_994812",
  "app.order_id": "ord_772109"
}
```

### Mandatory PII & Credential Redaction Filter

Before serializing any structured log attributes or span attributes, strip sensitive keys case-insensitively:

```ts
const REDACTED_ATTRIBUTE_PATTERN =
  /(?:authorization|cookie|set-cookie|password|passwd|secret|api[-_]?key|access[-_]?token|refresh[-_]?token|private[-_]?key|client[-_]?secret|ssn|card[-_]?number|cvv)/i;

export function redactSensitiveFields(
  attributes: Record<string, unknown>
): Record<string, unknown> {
  const sanitized: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(attributes)) {
    if (REDACTED_ATTRIBUTE_PATTERN.test(key)) {
      sanitized[key] = "[REDACTED]";
    } else if (typeof value === "string" && /^Bearer\s+[A-Za-z0-9\-._~+/]+=*$/i.test(value)) {
      sanitized[key] = "[REDACTED]";
    } else {
      sanitized[key] = value;
    }
  }
  return sanitized;
}
```

---

## 2. The Four Golden Signal SLIs

| Golden Signal | Metric Instrument | Bounded Labels Allowed | Target SLI Formula |
| --- | --- | --- | --- |
| **Latency** | `Histogram` (`http.server.request.duration_ms`) | `http.request.method`, `http.route`, `http.response.status_class` | $P_{95} \le 150\text{ms}$ and $P_{99} \le 400\text{ms}$ over rolling 5m window |
| **Traffic** | `Counter` (`http.server.requests_total`) | `http.request.method`, `http.route`, `http.response.status_class` | Requests per second (`rate(http_server_requests_total[5m])`) |
| **Errors** | `Counter` (`http.server.requests_total{status_class="5xx"}`) | `http.request.method`, `http.route`, `error.code` | $\frac{\text{good (non-5xx) requests}}{\text{total valid requests}} \ge 99.9\%$ |
| **Saturation** | `Histogram` (`messaging.receive.dwell_duration_ms`) & `UpDownCounter` (`db.pool.active_connections`) | `queue.name`, `pool.name` | Queue dwell $P_{99} \le 1000\text{ms}$; DB pool utilization $< 85\%$ |

---

## 3. Google SRE Multi-Window, Multi-Burn-Rate SLO Alerting

Alerting on raw 1-minute error spikes triggers pager fatigue on harmless blips, while alerting on a 30-day rolling average detects outages way too late. Use the **Google SRE Workbook Multi-Window, Multi-Burn-Rate** model:

$$\text{Burn Rate} = \frac{\text{Observed Error Rate in Window}}{1 - \text{SLO Target}}$$

For a $99.9\%$ 30-day SLO, the total error budget is $1 - 0.999 = 0.001$ ($0.1\%$ of requests, or $43.2\text{ minutes}$ of 100% downtime).

| Alert Tier | Burn Rate Multiplier | Long Window | Short Confirmation Window | 30-Day Error Budget Consumed | Threshold at $99.9\%$ SLO | Automated Action |
| --- | --- | --- | --- | --- | --- | --- |
| **Tier 1: Fast-Burn Page** | `14.4x` | `1h` | `5m` | $2\%$ in 1 hour | Error rate $> 1.44\%$ in both `1h` AND `5m` | Page on-call engineer + freeze release pipeline / trigger rollback |
| **Tier 2: Medium-Burn Page** | `6.0x` | `6h` | `30m` | $5\%$ in 6 hours | Error rate $> 0.60\%$ in both `6h` AND `30m` | Page on-call engineer |
| **Tier 3: Slow-Burn Ticket** | `1.0x` – `3.0x` | `24h` – `72h` | `2h` – `6h` | $10\%$ in 24–72 hours | Error rate $> 0.30\%$ in both `24h` AND `2h` | Open engineering remediation ticket; prioritize reliability work |

Why the **Short Confirmation Window** (`5m` paired with `1h`) is mandatory:
- Without the `5m` window, an outage that lasted 10 minutes and resolved 45 minutes ago will keep the `1h` window above `14.4x` and continue paging engineers after recovery. Requiring **both** `1h > 14.4x` AND `5m > 14.4x` ensures the alert fires only while error budget is *actively* burning.
