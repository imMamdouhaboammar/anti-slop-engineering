# RED & USE Metrics Matrix

Observability architectures must systematically differentiate between **request-driven work** (endpoints) and **capacity-constrained infrastructure** (resources). The RED method governs endpoints; the USE method governs resources.

---

## 1. The RED Method (Request-Driven Endpoints)

Apply RED to every HTTP route, gRPC procedure, RPC client, and message queue consumer endpoint.

### RED Metric Definitions

| Metric | Dimension / Type | Metric Name Convention | Semantic Labels |
| --- | --- | --- | --- |
| **Rate** | Counter (requests/sec) | `http.server.request.count` / `rpc.server.request.count` | `http.request.method`, `http.route`, `server.address` |
| **Errors** | Counter (errors/sec) | `http.server.error.count` / `rpc.server.error.count` | `http.route`, `http.response.status_class` (4xx/5xx), `error.code` |
| **Duration** | Histogram (seconds/ms) | `http.server.duration` / `rpc.server.duration` | `http.request.method`, `http.route`, `http.response.status_code` |

### Explicit Bucket Boundaries for Latency Histograms

Never use default exponential buckets without calibration. Configure explicit bucket boundaries tailored to service SLOs:
```
[0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.000, 2.500, 5.000, 10.000] seconds
(or [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000] milliseconds)
```

Quantiles tracked across the fleet:
- **P50 (Median):** Typical user experience under nominal conditions.
- **P95 (95th Percentile):** Early indicator of degradation.
- **P99 (99th Percentile):** Tail-latency boundary governed by Service Level Agreements (SLAs).

---

## 2. The USE Method (Resources & Capacity Limits)

Apply USE to every hardware and software resource: CPU, Memory, DB Connection Pools, Worker Pools, Disk I/O, Network Interfaces, and Event Loops.

### USE Metric Definitions

| Resource | Utilization ($U \in [0.0, 1.0]$) | Saturation (Waiters / Queue Depth) | Errors (Failure Events) |
| --- | --- | --- | --- |
| **CPU** | Percent time cores are non-idle (`system.cpu.utilization`) | OS Run-queue length (`system.cpu.load_average.1m` / core count) | Hardware throttling / thermal fault events |
| **Memory** | Active resident memory / total physical limit (`process.memory.utilization`) | Major page fault rate (`system.memory.major_page_faults`) | Out-of-memory kills (`process.oom_kill.count`) |
| **Database Pool** | Active borrowed connections / max pool size (`db.client.connections.active` / `max`) | Waiting checkout threads (`db.client.connections.pending_waiters`) | Connection acquisition timeouts (`db.client.connections.timeouts`) |
| **Queue Workers** | Busy worker threads / total worker concurrency (`worker.concurrency.active` / `max`) | Unprocessed queue depth (`messaging.queue.backlog_depth`) | Message processing exceptions / Dead-letter drops (`messaging.dead_letter.count`) |
| **Node Event Loop** | Event loop busy fraction (`nodejs.eventloop.utilization`) | Event loop latency delay (`nodejs.eventloop.delay.p99`) | Unhandled rejections / uncaught fatal errors |

---

## 3. The Low-Cardinality Enforcement Wrapper

To ensure metric emissions never violate the Monarch cardinality ceiling, wrap all metric emissions in a bounded type-safe facade:

```typescript
export interface BoundedHttpLabels {
  readonly method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly route: string; // Must be normalized parameterized template
  readonly statusClass: "2xx" | "3xx" | "4xx" | "5xx";
}

export function sanitizeRoute(route: string | undefined): string {
  if (!route || route.trim() === "") return "__unmatched__";
  // Collapse arbitrary dynamic IDs
  if (/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(route)) return "__unmatched__";
  return route;
}
```
