// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

/**
 * @file safe-rollout-choreographer-pipeline.ts
 * High-performance, production-grade implementation of Meta & Google SRE
 * Safe Evolution and Rollout Choreography:
 * 1. Tolerant Reader & N-1 / N+1 Wire Compatibility
 * 2. Asynchronous Shadow Reads with Fenced Side-Effects & Semantic Diffing
 * 3. Sub-Second In-Memory Kill-Switch & Feature Flag Governance
 * 4. Strangler Fig Facade Router with Deterministic Canary Shifting & Circuit Breakers
 */

import { createHash } from "node:crypto";

export interface UserContext {
  userId: string;
  tenantId: string;
  appVersion: string;
  region: string;
}

export interface CatalogItemPayload {
  id: string;
  title: string;
  priceCents: number;
  // Newly added field in N+1 - must be optional with safe default for N-1
  currency?: string;
  metadata?: Record<string, string>;
}

export interface FeatureFlagConfig {
  id: string;
  owner: string;
  createdAt: string;
  expiresAt: string;
  enabled: boolean;
  killSwitchEngaged: boolean;
  rolloutPercentage: number;
  demolitionTicket: string;
}

/**
 * 1. Wire-Compatible Parser implementing Tolerant Reader pattern.
 * Ignores unknown attributes; injects deterministic defaults for missing attributes.
 */
export function parseCatalogPayloadTolerant(raw: unknown): CatalogItemPayload {
  if (typeof raw !== "object" || raw === null) {
    throw new TypeError("Payload must be a non-null object");
  }

  const record = raw as Record<string, unknown>;

  if (typeof record.id !== "string" || !record.id.trim()) {
    throw new Error("Invalid payload: missing or empty 'id'");
  }
  if (typeof record.title !== "string" || !record.title.trim()) {
    throw new Error("Invalid payload: missing or empty 'title'");
  }
  if (typeof record.priceCents !== "number" || record.priceCents < 0) {
    throw new Error("Invalid payload: 'priceCents' must be a non-negative number");
  }

  // Backward-compatible default for missing fields from N-1 producers
  const currency = typeof record.currency === "string" ? record.currency : "USD";
  const metadata =
    typeof record.metadata === "object" && record.metadata !== null
      ? (record.metadata as Record<string, string>)
      : {};

  return {
    id: record.id,
    title: record.title,
    priceCents: record.priceCents,
    currency,
    metadata,
  };
}

/**
 * 2. Sub-Second Feature Flag Store with In-Memory Push Cache and Instant Kill-Switch.
 */
export class FeatureFlagGovernor {
  private flags = new Map<string, FeatureFlagConfig>();

  public registerFlag(config: FeatureFlagConfig): void {
    const created = new Date(config.createdAt).getTime();
    const expires = new Date(config.expiresAt).getTime();
    const ttlDays = (expires - created) / (1000 * 60 * 60 * 24);

    if (ttlDays > 90) {
      throw new Error(`Flag '${config.id}' violates maximum 90-day TTL (configured for ${ttlDays.toFixed(1)} days)`);
    }

    this.flags.set(config.id, { ...config });
  }

  public tripKillSwitch(flagId: string, reason: string): void {
    const flag = this.flags.get(flagId);
    if (!flag) throw new Error(`Flag '${flagId}' not found`);

    flag.killSwitchEngaged = true;
    flag.enabled = false;
    flag.rolloutPercentage = 0;
    // Log structured telemetry for SRE on-call
    console.error(`[KILL-SWITCH ENGAGED] Flag '${flagId}' disabled instantly. Reason: ${reason}`);
  }

  public isEnabled(flagId: string, user: UserContext): boolean {
    const flag = this.flags.get(flagId);
    if (!flag) return false;
    if (flag.killSwitchEngaged || !flag.enabled) return false;

    // Check expiration
    if (Date.now() > new Date(flag.expiresAt).getTime()) {
      console.warn(`[FLAG EXPIRED] Flag '${flagId}' exceeded TTL. Demolition required: ${flag.demolitionTicket}`);
      return false;
    }

    if (flag.rolloutPercentage >= 100) return true;
    if (flag.rolloutPercentage <= 0) return false;

    // Deterministic user hash mod 100
    const hash = createHash("sha256").update(`${flagId}:${user.userId}`).digest("hex");
    const bucket = parseInt(hash.slice(0, 8), 16) % 100;
    return bucket < flag.rolloutPercentage;
  }
}

/**
 * 3. Asynchronous Shadow Read Runner with Semantic Diffing & Fenced Side-Effects.
 */
export interface DiffMetric {
  match: boolean;
  baselineLatencyMs: number;
  shadowLatencyMs: number;
  discrepancies: string[];
}

export class ShadowExecutionRunner {
  private mismatchCount = 0;
  private totalComparisons = 0;

  public executeWithShadowRead<TInput, TOutput>(
    input: TInput,
    user: UserContext,
    primaryExecution: (inp: TInput) => Promise<TOutput>,
    shadowExecution: (inp: TInput, fenced: boolean) => Promise<TOutput>,
    diffFn: (a: TOutput, b: TOutput) => string[]
  ): Promise<TOutput> {
    const startPrimary = performance.now();

    // 1. Execute baseline primary path (blocking for user response)
    return primaryExecution(input).then((primaryResult) => {
      const primaryDuration = performance.now() - startPrimary;

      // 2. Schedule decoupled asynchronous shadow execution (fire-and-forget)
      queueMicrotask(async () => {
        const startShadow = performance.now();
        try {
          // Strictly enforce fenced side-effects (fenced = true)
          const shadowResult = await shadowExecution(input, true);
          const shadowDuration = performance.now() - startShadow;

          const diffs = diffFn(primaryResult, shadowResult);
          this.totalComparisons++;

          if (diffs.length > 0) {
            this.mismatchCount++;
            console.warn(`[SHADOW DIFF] Discrepancies detected for user ${user.userId}:`, diffs);
          }

          // Telemetry capture without blocking user
          if (shadowDuration > primaryDuration * 1.5) {
            console.warn(`[SHADOW LATENCY SPIKE] Shadow: ${shadowDuration.toFixed(1)}ms vs Base: ${primaryDuration.toFixed(1)}ms`);
          }
        } catch (shadowErr) {
          // Fail-silent: shadow exceptions must never escape or crash the process
          console.error("[SHADOW FAILURE] Shadow execution threw unexpected error:", shadowErr);
        }
      });

      return primaryResult;
    });
  }

  public getMismatchRate(): number {
    return this.totalComparisons === 0 ? 0 : this.mismatchCount / this.totalComparisons;
  }
}

/**
 * 4. Strangler Fig Interception Facade with Automated Rollback Circuit Breakers.
 */
export class StranglerFacadeRouter {
  private consecutiveErrors = 0;
  private readonly ERROR_THRESHOLD = 5;
  private circuitOpen = false;

  constructor(
    private readonly flagGovernor: FeatureFlagGovernor,
    private readonly flagId: string
  ) {}

  public async routeRequest<TInput, TOutput>(
    input: TInput,
    user: UserContext,
    legacyService: (inp: TInput) => Promise<TOutput>,
    modernService: (inp: TInput) => Promise<TOutput>
  ): Promise<TOutput> {
    // Check if circuit breaker is tripped
    if (this.circuitOpen) {
      return legacyService(input);
    }

    const useModern = this.flagGovernor.isEnabled(this.flagId, user);

    if (!useModern) {
      return legacyService(input);
    }

    try {
      const result = await modernService(input);
      this.consecutiveErrors = 0; // Reset error streak
      return result;
    } catch (err) {
      this.consecutiveErrors++;
      console.error(`[MODERN SERVICE ERROR] Error streak: ${this.consecutiveErrors}/${this.ERROR_THRESHOLD}`);

      if (this.consecutiveErrors >= this.ERROR_THRESHOLD) {
        this.circuitOpen = true;
        this.flagGovernor.tripKillSwitch(this.flagId, "Automated rollback: modern service consecutive errors exceeded threshold");
      }

      // Safe fallback to legacy system
      return legacyService(input);
    }
  }
}
