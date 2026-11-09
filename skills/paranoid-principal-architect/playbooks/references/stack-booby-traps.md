# Stack-Specific Forensic Booby-Trap Catalog

This reference details concrete failure mechanics, root causes, blast radii, and production-hardened remedies across Kubernetes, Docker, Python, TypeScript, Bun, Rust, Golang, React, and System Architecture.

---

## 1. Kubernetes (`K8S-*`)

### `K8S-01`: Shared Liveness and Readiness Probe Death Spiral
- **Symptom:** `livenessProbe` and `readinessProbe` point to the exact same `/healthz` endpoint, which queries PostgreSQL or Redis.
- **Trigger:** Database experiences a transient 3-second latency spike under heavy concurrent load.
- **Blast Radius:** `livenessProbe` fails across all pods simultaneously. Kubelet restarts every pod at once, triggering an aggressive reconnection storm against the already degraded database and taking down the entire cluster.
- **Forensic Remedy:**
  - `livenessProbe` (`/healthz/live`): Verify local process responsiveness and event-loop liveness ONLY. Zero external network calls.
  - `readinessProbe` (`/healthz/ready`): Verify downstream dependency readiness to gate ingress traffic without killing pods.
  - `startupProbe` (`/healthz/startup`): Protect slow-starting containers from premature liveness kills.

### `K8S-02`: PreStop and SIGTERM Race Condition
- **Symptom:** Pods return `502 Bad Gateway` for 2–5 seconds during rolling deployments even though the application handles `SIGTERM`.
- **Root Cause:** Kubernetes removes the Pod IP from `EndpointSlices` (kube-proxy and Ingress controller) asynchronously in parallel with delivering `SIGTERM` to the container. If the application terminates its HTTP listener immediately upon `SIGTERM`, in-flight requests routed during endpoint propagation hit a closed socket.
- **Forensic Remedy:** Add a `lifecycle.preStop` hook (`["/bin/sh", "-c", "sleep 5"]`) or delay closing the listening socket for 5 seconds after marking `/healthz/ready` as `503 Service Unavailable`.

---

## 2. Docker (`DCK-*`)

### `DCK-01`: PID 1 Zombie and Signal Blackhole
- **Symptom:** Container takes 10–30 seconds to stop and exits with code `137` (`SIGKILL`).
- **Root Cause:** Using `CMD npm start` or `ENTRYPOINT python app.py` invokes `/bin/sh -c`, which does not forward `SIGTERM` to child processes and does not reap orphaned zombie processes.
- **Forensic Remedy:**
  ```dockerfile
  FROM node:22.14.0-bookworm-slim@sha256:7b55c3c0efdc6cfcbebbcf8eb8f1f516a2976d54203112a20b08006b527deec9
  RUN apt-get update && apt-get install -y --no-install-recommends tini \
      && rm -rf /var/lib/apt/lists/*
  USER node
  ENTRYPOINT ["/usr/bin/tini", "--"]
  CMD ["node", "dist/server.js"]
  ```

---

## 3. Python (`PY-*`)

### `PY-01`: Weak-Reference Garbage Collection of Asyncio Tasks
- **Symptom:** Background jobs spawned via `asyncio.create_task()` vanish silently under memory pressure without throwing an exception.
- **Root Cause:** The Python event loop retains only weak references to scheduled tasks. An unreferenced task object can be garbage-collected before completion.
- **Forensic Remedy:**
  ```python
  import asyncio
  from typing import Any, Coroutine

  _BACKGROUND_TASKS: set[asyncio.Task[object]] = set()

  def spawn_safe(coro: Coroutine[Any, Any, object]) -> asyncio.Task[object]:
      task = asyncio.create_task(coro)
      _BACKGROUND_TASKS.add(task)
      task.add_done_callback(_BACKGROUND_TASKS.discard)
      return task
  ```

### `PY-02`: Late-Binding Closure Trap in Loops
- **Symptom:** A list of lambdas or callbacks created inside a `for` loop all execute using the final iteration's variable value.
- **Root Cause:** Python closures bind variables by name (late binding), not by value at creation time.
- **Forensic Remedy:** Bind the loop variable as a default argument (`lambda x=item: process(x)`) or use `functools.partial`.

---

## 4. TypeScript & Bun (`TS-*` / `BUN-*`)

### `TS-01`: Truthiness Trap on Valid Zero or Empty Values
- **Symptom:** Pagination offset `0`, price `0`, or temperature `0` is rejected as "missing parameter" or falls back to an unwanted default value.
- **Root Cause:** Writing `if (!value)` or `const limit = input.limit || 20` instead of explicit nullish checks.
- **Forensic Remedy:** Use nullish coalescing (`input.limit ?? 20`) and explicit equality checks (`value === undefined || value === null`).

### `BUN-01`: Safe Command Execution via `Bun.$` vs `Bun.spawn`
- **Symptom:** File paths with spaces or user-supplied arguments break shell commands or introduce command injection vulnerabilities.
- **Forensic Remedy:**
  ```ts
  // SAFE: Bun.$ automatically escapes interpolated arguments as separate tokens
  const output = await Bun.$`git log -n 5 -- ${userFilePath}`.text();

  // SAFE: Direct argv array without shell interpretation
  const proc = Bun.spawn(["git", "log", "-n", "5", "--", userFilePath], {
    stdout: "pipe",
    stderr: "pipe",
    timeout: 5_000,
  });
  ```

---

## 5. Rust (`RS-*`)

### `RS-01`: Async Mutex Held Across `.await` Boundary
- **Symptom:** Application deadlocks under concurrent load or fails to compile with `Send` trait errors.
- **Root Cause:** Locking a `std::sync::Mutex` and holding the `MutexGuard` across an `.await` suspension point causes the worker thread to yield while holding an OS spinlock. If another task on the same thread attempts to acquire the lock, the thread deadlocks permanently.
- **Forensic Remedy:** Scope the `std::sync::MutexGuard` inside an inner block so it drops strictly before any `.await` point:
  ```rust
  {
      let mut guard = lock.lock().unwrap_or_else(|e| e.into_inner());
      guard.update(data);
  } // MutexGuard dropped here
  downstream_client.send().await?;
  ```

### `RS-02`: Silent Integer Truncation via `as`
- **Symptom:** Large payload sizes or timestamps wrap around into small or negative numbers on 32-bit targets or narrow integer fields.
- **Forensic Remedy:** Enable `#![deny(clippy::cast_possible_truncation, clippy::cast_sign_loss, clippy::unwrap_used)]` and use `u32::try_from(value)?`.

---

## 6. Golang (`GO-*`)

### `GO-01`: Context Cancellation and Goroutine Leak on Unbuffered Channels
- **Symptom:** Memory usage climbs steadily whenever downstream requests time out.
- **Root Cause:** A request handler spawns a worker goroutine that writes to an unbuffered channel `ch <- result`. If `ctx.Done()` fires first and the parent function returns early, the worker goroutine blocks on `ch <- result` indefinitely because no receiver exists.
- **Forensic Remedy:** Always use a buffered channel of size 1 (`make(chan result, 1)`) or `select` over `case <-ctx.Done():` when sending from child goroutines.

### `GO-02`: Slice Capacity Sub-Slicing Memory Leak and Append Overwrite
- **Symptom:** Two derived slices unexpectedly mutate each other's elements upon `append()`, or a 100 MB buffer stays pinned in RAM because a 12-byte header slice references it.
- **Forensic Remedy:** Use full slice expressions `sub := base[start:end:end]` to force a new allocation on `append`, or `bytes.Clone(base[start:end])` to release the backing array.

---

## 7. React (`RCT-*`)

### `RCT-01`: Stale Closure and Out-of-Order Fetch Race in `useEffect`
- **Symptom:** Rapidly switching tabs or search filters displays results from an older query over the newest selection.
- **Forensic Remedy:**
  ```tsx
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const res = await fetch(`/api/items?q=${encodeURIComponent(query)}`, {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        setItems(parseItemsSchema(data));
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    }
    void load();
    return () => controller.abort();
  }, [query]);
  ```

---

## 8. System Architecture (`ARC-*`)

### `ARC-01`: The Transactional Outbox Invariant (Defusing Dual-Writes)
- **Symptom:** Database commits an order, but the process crashes or the broker blips before publishing the `OrderCreated` event, leaving downstream inventory and billing permanently out of sync.
- **Forensic Remedy:** Write both the domain state mutation and an `outbox_events` record inside the exact same ACID database transaction. A separate relay worker polls or streams the outbox table and publishes to the broker with at-least-once delivery, while consumers enforce idempotent deduplication by `event_id`.
