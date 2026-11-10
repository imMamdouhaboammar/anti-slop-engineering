# Pit-of-Success Defaults

> The Pit of Success: In contrast to software that makes the right path hard and error-prone, well-designed systems make the right path inevitable. The default choice must be the safest, fastest, and most resilient.

## Core Architectural Invariants

| Dimension | Anti-Pattern (Trap) | Pit-of-Success Invariant |
| --- | --- | --- |
| Network Timeouts | Default to no timeout (hanging forever during outages) | Default to 10,000ms built-in timeout via `AbortSignal.timeout()` |
| Mutation Retries | Blind retry storms or no retries on transient network blips | Automatic retry on 408/429/502/503/504 with full-jitter exponential backoff |
| Mutation Idempotency | Requiring manual UUID generation or ignoring duplicates | Automatic idempotency key generation (`crypto.randomUUID()`) cached across retry attempts |
| Pagination Limits | Unbounded arrays returning 100,000 rows or defaulting to 0 | Default page size 20, hard-enforced maximum ceiling of 100 with cursor tokens |
| TLS & Encryption | Permitting unencrypted HTTP or disabled certificate checks | Enforce HTTPS/TLS 1.3 by default; require explicit opt-in only in hermetic test environments |
| Configuration Overhead | Mandatory 10-parameter constructor options bag | Zero-config or single-credential constructor (`new Client({ apiKey })`) |

---

## The 80/20 Default Calculus

APIs must distinguish the standard workflow from specialized operational tuning:

$$\text{Total Cognitive Overhead} = \text{Required Parameters} \times \text{Manual Configuration Hops}$$

Under Pit-of-Success governance, the cognitive overhead for the primary 80% use case must equal 1:

1. **Zero Required Boilerplate:** If an option can be sensibly computed, defaulted, or derived from system context (e.g. system proxy, default timeout, default retry budget, user-agent string), it must never be required from the caller.
2. **Safe Failsafe Thresholds:** Never choose a default that can corrupt data, leak secrets, or exhaust server memory. A default of `timeout: Infinity` is a critical flaw; a default of `timeout: 10_000` is resilient.
3. **Opt-Out, Not Opt-In for Security:** Telemetry redaction, certificate pinning, and input sanitization must be active by default. Callers must actively choose to bypass defenses rather than remembering to enable them.

---

## Reference TypeScript Implementation

```typescript
export interface ClientConfig {
  readonly apiKey: string;
  readonly baseUrl?: string;
  readonly timeoutMs?: number;
  readonly maxRetries?: number;
  readonly fetcher?: typeof fetch;
}

export class ResilientClient {
  readonly #apiKey: string;
  readonly #baseUrl: string;
  readonly #timeoutMs: number;
  readonly #maxRetries: number;
  readonly #fetcher: typeof fetch;

  constructor(config: ClientConfig) {
    if (!config.apiKey || config.apiKey.trim().length === 0) {
      throw new Error("Client initialization failed: apiKey is required.");
    }
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? "https://api.platform.example.com/v1";
    this.#timeoutMs = config.timeoutMs ?? 10_000;
    this.#maxRetries = config.maxRetries ?? 3;
    this.#fetcher = config.fetcher ?? globalThis.fetch;
  }
}
```
