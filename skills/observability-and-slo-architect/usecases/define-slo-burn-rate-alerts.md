# Usecase: Define SLIs, SLOs & Multi-Window Multi-Burn-Rate Alerts

## Context
Traditional alerting strategies rely on arbitrary static thresholds (e.g. CPU > 80%, disk > 90%), leading to on-call burnout and ignored pages.

## Objective
Establish Google SRE Multi-Window Multi-Burn-Rate alerting tied to user impact and Error Budget consumption, completely eliminating non-impact alert noise.

## Execution Steps

1. **Formulate Availability and Latency SLIs:**
   Define quantitative SLIs based on client-visible status codes and latency histogram quantiles (P95 and P99).
2. **Calculate 30-Day Error Budget:**
   Determine the permissible failure budget ($1.0 - \text{SLO}$) over a rolling 30-day window.
3. **Configure Multi-Window Alerting Pairs:**
   - **Fast-Burn Alert (14.4x):** 1-hour Long Window + 5-minute Short Window $\rightarrow$ PagerDuty alert to page on-call and halt automated canary deployments.
   - **Slow-Burn Alert (6.0x):** 6-hour Long Window + 30-minute Short Window $\rightarrow$ Automatic ticket opened for next business day investigation.
4. **Decommission Non-Impact Threshold Alerts:**
   Audit and remove all single-pod CPU, memory, and raw request count alerts that do not correlate with user-facing degradation.
5. **Attach Remediation Runbooks:**
   Ensure every fired alert includes an automated rollback command or step-by-step diagnostic runbook.
