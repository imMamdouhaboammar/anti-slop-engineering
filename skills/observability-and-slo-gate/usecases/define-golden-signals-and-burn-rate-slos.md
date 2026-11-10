# Workflow: Define Golden Signals, Structured Logs & Multi-Burn-Rate SLOs

Use this workflow when preparing a service for production traffic, replacing unstructured `console.log` calls with trace-correlated JSON logs, or establishing SLI/SLO alerting gates.

## Step-by-Step Procedure

### 1. Replace Unstructured Logs with Trace-Correlated JSON Logging
1. Remove all `console.log`, `console.error`, `print()`, and `fmt.Println` calls from production paths.
2. Route all logs through a structured JSON logger that automatically reads the active span context (`trace_id`, `span_id`, `correlation_id`) and attaches `service.name`, `timestamp`, `level`, and `error.code`.
3. Configure deterministic field redaction (`Authorization`, `cookie`, `password`, `token`, `secret`, `apiKey`, `ssn`, `cardNumber` -> `"[REDACTED]"`) before JSON serialization.

### 2. Define the Golden Signal SLIs
1. **Latency SLI:** Ratio of requests completing faster than the target threshold (e.g., `http.server.request.duration` P95 $\le 150\text{ms}$ and P99 $\le 400\text{ms}$) computed from Histogram buckets.
2. **Availability (Error Rate) SLI:** Ratio of valid requests returning non-`5xx` outcomes (excluding caller `4xx` validation errors from server error budget burn unless measuring auth gateway health).
3. **Saturation / Queue Lag SLI:** Bounded resource utilization (`db_pool_active / db_pool_max` and async queue consumer dwell time Histogram P99).

### 3. Configure Multi-Window, Multi-Burn-Rate Error Budget Alerts
1. Define the 28-day or 30-day SLO target (e.g., $99.9\% \implies 43.2\text{ minutes}$ error budget per 30 days).
2. Configure two paired Multi-Window Burn-Rate gates following the Google SRE Workbook standard:
   - **Fast-Burn Page (`14.4x` burn rate):** Both the `1h` window and `5m` window exceed $14.4 \times (1 - \text{SLO})$ (consumes 2% of the 30-day error budget in 1 hour). Action: Page on-call and halt automated rollouts.
   - **Slow-Burn Ticket (`6.0x` burn rate):** Both the `6h` window and `30m` window exceed $6.0 \times (1 - \text{SLO})$ (consumes 5% of the 30-day error budget in 6 hours). Action: Open high-priority incident ticket.

### 4. Generate & Audit the Observability & SLO Record
1. Author an `observability-slo-record.json` documenting the cardinality budget, W3C propagation hops, Histogram SLIs, and Multi-Window Burn-Rate thresholds.
2. Run `python3 scripts/observability_guard.py audit observability-slo-record.json --source <file> --json` and verify zero findings.
