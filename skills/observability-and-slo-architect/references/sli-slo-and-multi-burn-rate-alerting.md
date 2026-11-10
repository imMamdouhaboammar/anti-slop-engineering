# SLI, SLO & Multi-Window Multi-Burn-Rate Alerting

Alert fatigue is an operational failure caused by alerting on non-user-impacting symptoms (e.g. single-node CPU spikes). The Google SRE methodology solves alert fatigue by tying alerting strictly to **Service Level Indicators (SLIs)** and **Error Budget Burn Rates**.

---

## 1. Service Level Indicators (SLIs) & Objectives (SLOs)

### 1.1 Availability SLI
The ratio of successful requests to valid total requests:
$$\text{SLI}_{\text{avail}} = \frac{\sum \text{requests}_{\text{non-5xx}}}{\sum \text{requests}_{\text{valid}}}$$

### 1.2 Latency SLI
The proportion of valid requests completed faster than the target threshold $T_{\text{target}}$:
$$\text{SLI}_{\text{latency}} = \frac{\sum \text{requests}(\text{duration} \le T_{\text{target}})}{\sum \text{requests}_{\text{valid}}}$$

### 1.3 Error Budget Formulation
For a target SLO over period $P$ (e.g. 30 days):
$$\text{Error Budget } E = 1.0 - \text{SLO}$$
Example: A 99.9% availability SLO yields an Error Budget of $0.001$ ($0.1\%$).

---

## 2. Multi-Window Multi-Burn-Rate Alerting

A **Burn Rate of 1.0** indicates that the service is consuming its error budget at a rate that will exhaust the entire budget in exactly the target period (e.g. 30 days).

Alerting on high burn rates requires **two sliding windows** (a Long Window to measure sustained impact and a Short Window to ensure the issue is actively ongoing):

| Severity | Target Consumption | Burn Rate Multiplier | Long Window | Short Window | Automated Response |
| --- | --- | --- | --- | --- | --- |
| **P0 / Page** | 2% in 1 hour | **14.4x** | 1 hour | 5 minutes | Immediate on-call page; halt ongoing canary rollouts |
| **P1 / Page** | 5% in 6 hours | **6.0x** | 6 hours | 30 minutes | Page secondary on-call; escalate to component owner |
| **P2 / Ticket** | 10% in 3 days | **1.0x** | 3 days | 6 hours | Automated Jira ticket opened for next business day |

### Why Multi-Window Multi-Burn-Rate Eliminates Fatigue

1. **Immunity to Brief Blips:** A 30-second spike in error rate may consume 0.01% of the budget. Because the Long Window (1 hour) requires 2% consumption, the alert will not fire.
2. **Rapid Reaction on Total Outages:** If error rate jumps to 100% (burn rate = 1000x), the 5-minute Short Window confirms the outage within 300 seconds, triggering an immediate page.
3. **Automatic Reset:** If an issue resolves before the Long Window expires, the Short Window falls to 0, immediately muting the alert without human intervention.

---

## 3. Banned Alerting Anti-Patterns

1. **Threshold-Only Resource Alerts:** `ALERT CPU > 80% FOR 5m` is strictly prohibited. If P99 latency is within budget and error rate is 0, high CPU is healthy efficiency, not an incident.
2. **Single-Pod Metric Alerts:** Paging on a single pod's restart when the fleet has 100 healthy replicas and zero user-facing errors is prohibited.
3. **Alerts without Actionable Runbooks:** Every alert must include a direct link to a diagnosis dashboard and an automated rollback/mitigation runbook.
