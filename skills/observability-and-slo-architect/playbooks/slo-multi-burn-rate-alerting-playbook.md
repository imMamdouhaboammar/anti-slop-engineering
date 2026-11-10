# Playbook 3: Google SRE Multi-Window Multi-Burn-Rate Alerts

This playbook guides SREs and software architects through defining user-centric Service Level Indicators (SLIs), establishing Service Level Objectives (SLOs), calculating Error Budgets, and creating Multi-Window Multi-Burn-Rate alert rules that eliminate alert fatigue.

---

## 1. Step 1: Define User-Centric SLIs

Never define SLIs on internal server metrics (e.g. CPU utilization). SLIs must measure user happiness:

### Availability SLI
A request is successful if it returns an HTTP status code $< 500$ (or non-INTERNAL gRPC status) and does not exceed a hard timeout:

$$\text{SLI}_{\text{avail}} = \frac{\text{count}(\text{http.server.duration}\{\text{status} < 500\})}{\text{count}(\text{http.server.duration})}$$

### Latency SLI
A request is good if its duration is $\le 250\text{ms}$:

$$\text{SLI}_{\text{latency}} = \frac{\text{count}(\text{http.server.duration}\{\text{le} = 250\})}{\text{count}(\text{http.server.duration})}$$

---

## 2. Step 2: Establish the Error Budget

Define an SLO target over a 30-day rolling window:
- Availability Target: $99.9\%$
- Error Budget: $E = 1.0 - 0.999 = 0.001$ ($0.1\%$ or 1 failed request per 1,000)

---

## 3. Step 3: Implement Multi-Window Multi-Burn-Rate Rules

A single-window alert either alerts too slowly (e.g. 24-hour window) or generates massive noise on 1-minute blips. The Google SRE solution requires **both** a Long Window (to measure sustained budget consumption) and a Short Window (to ensure the issue is actively ongoing).

### The Canonical Multi-Burn-Rate Matrix

```
Burn Rate Multiplier B:
  Consumes budget at B times normal speed.
  B = (Budget Consumption Fraction) * (Period Hours) / (Window Hours)
```

| Window Pair | Target Consumption | Burn Rate Multiplier | Long Window | Short Window | Alert Route |
| --- | --- | --- | --- | --- | --- |
| **Emergency Page** | 2% in 1 hour | **14.4x** | 1 hour | 5 minutes | PagerDuty (Wake on-call) + Halt Deployments |
| **Severe Incident Page** | 5% in 6 hours | **6.0x** | 6 hours | 30 minutes | PagerDuty (Secondary / Team Lead) |
| **Ticket (Next Day)** | 10% in 3 days | **1.0x** | 3 days | 6 hours | Automated Jira Incident Ticket |

### Prometheus Alerting Rule Implementation

```yaml
groups:
  - name: slo_error_budget_burn_rate
    rules:
      # P0: 14.4x Burn Rate over 1h AND 5m (Consumes 2% budget in 1h)
      - alert: CheckoutHighErrorBudgetBurn1hAnd5m
        expr: |
          (
            sum(rate(http_server_error_count{job="checkout"}[1h]))
            /
            sum(rate(http_server_request_count{job="checkout"}[1h]))
          ) > (14.4 * 0.001)
          and
          (
            sum(rate(http_server_error_count{job="checkout"}[5m]))
            /
            sum(rate(http_server_request_count{job="checkout"}[5m]))
          ) > (14.4 * 0.001)
        for: 2m
        labels:
          severity: page
          action: halt_rollout
        annotations:
          summary: "Checkout service burning error budget at 14.4x (2% in 1 hour)"
          runbook_url: "https://wiki.corp.internal/runbooks/checkout-burn-rate"

      # P1: 6.0x Burn Rate over 6h AND 30m (Consumes 5% budget in 6h)
      - alert: CheckoutHighErrorBudgetBurn6hAnd30m
        expr: |
          (
            sum(rate(http_server_error_count{job="checkout"}[6h]))
            /
            sum(rate(http_server_request_count{job="checkout"}[6h]))
          ) > (6.0 * 0.001)
          and
          (
            sum(rate(http_server_error_count{job="checkout"}[30m]))
            /
            sum(rate(http_server_request_count{job="checkout"}[30m]))
          ) > (6.0 * 0.001)
        for: 5m
        labels:
          severity: page
        annotations:
          summary: "Checkout service burning error budget at 6.0x (5% in 6 hours)"
```

---

## 4. Elimination of Non-Impact Alert Fatigue

Enforce the following policy across the entire engineering organization:
1. **Delete all CPU > 80% alerts.** Replace with Availability SLI and Latency P99 SLI alerts.
2. **Delete all single-pod memory threshold alerts.** Replace with Out-of-Memory (OOM) kill rate metrics and connection pool saturation metrics.
3. **No alert without an automated mitigation or runbook link.**
