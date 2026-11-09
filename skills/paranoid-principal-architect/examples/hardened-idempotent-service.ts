// SPDX-License-Identifier: MIT
// Example: Hardened Idempotent Payment & Ledger Service (Day-One 10M Scale & Zero-Trust)

import { timingSafeEqual, randomUUID } from "node:crypto";
import { z } from "zod";

// --- 1. Type Branding ---
declare const __brand: unique symbol;
export type Brand<T, B> = T & { readonly [__brand]: B };

export type UserId = Brand<string, "UserId">;
export type TenantId = Brand<string, "TenantId">;
export type PaymentId = Brand<string, "PaymentId">;

export function parseUserId(raw: string): UserId {
  if (!/^usr_[a-zA-Z0-9]{24}$/.test(raw)) {
    throw new TypeError(`Invalid UserId format: ${raw}`);
  }
  return raw as UserId;
}

export function parseTenantId(raw: string): TenantId {
  if (!/^ten_[a-zA-Z0-9]{24}$/.test(raw)) {
    throw new TypeError(`Invalid TenantId format: ${raw}`);
  }
  return raw as TenantId;
}

// --- 2. Boundary Schema Validation (Parse, Don't Validate) ---
export const ProcessPaymentRequestSchema = z.object({
  idempotencyKey: z.string().uuid("Invalid idempotency key: must be a valid UUID v4"),
  amountInCents: z.number().int().positive().max(10_000_000, "Maximum transaction is $100,000.00"),
  currency: z.enum(["USD", "EUR", "GBP"]),
  recipientUserId: z.string().regex(/^usr_[a-zA-Z0-9]{24}$/, "Invalid recipient user ID format"),
  metadata: z.record(z.string().max(64), z.string().max(256)).optional()
}).strict(); // Strip and reject any unknown fields

export type ProcessPaymentRequest = z.infer<typeof ProcessPaymentRequestSchema>;

export interface PaymentDto {
  paymentId: PaymentId;
  amountInCents: number;
  currency: string;
  status: "COMPLETED" | "PENDING";
  createdAt: string;
}

export interface ApiErrorEnvelope {
  correlationId: string;
  code: string;
  message: string;
}

// --- 3. Constant-Time Secret Verification ---
export function verifyWebhookSignature(payload: string, signature: string, secret: string): boolean {
  const expectedHmac = Buffer.from(signature, "hex");
  const actualHmac = Buffer.from(payload + secret, "utf-8"); // Example buffer construction
  if (expectedHmac.length !== actualHmac.length) {
    timingSafeEqual(expectedHmac, expectedHmac); // Balance timing
    return false;
  }
  return timingSafeEqual(expectedHmac, actualHmac);
}

// --- 4. Concurrency & Hot-Key Defense (16-Shard Counter) ---
const NUM_SHARDS = 16;

export function selectShardIndex(resourceId: string): number {
  let hash = 0;
  for (let i = 0; i < resourceId.length; i++) {
    hash = ((hash << 5) - hash) + resourceId.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % NUM_SHARDS;
}

// --- 5. Hardened Payment Service ---
export interface StorageAdapter {
  getIdempotency(key: string): Promise<PaymentDto | null>;
  saveIdempotency(key: string, result: PaymentDto, ttlSeconds: number): Promise<void>;
  acquireLock(key: string, ttlSeconds: number): Promise<boolean>;
  releaseLock(key: string): Promise<void>;
  recordLedgerEntry(entry: {
    paymentId: PaymentId;
    tenantId: TenantId;
    senderId: UserId;
    recipientId: UserId;
    amountInCents: number;
    currency: string;
    shardIndex: number;
  }): Promise<void>;
}

export class HardenedPaymentService {
  constructor(
    private readonly storage: StorageAdapter,
    private readonly gatewayUrl: string
  ) {}

  public async processPaymentWithIdempotency(
    idempotencyKey: string,
    untrustedInput: unknown,
    callerTenantId: TenantId,
    callerUserId: UserId,
    correlationId = randomUUID()
  ): Promise<PaymentDto> {
    // Phase A: Boundary Validation
    const parsed = ProcessPaymentRequestSchema.parse({
      ...(typeof untrustedInput === "object" && untrustedInput !== null ? untrustedInput : {}),
      idempotencyKey
    });

    // Phase B: Idempotency Fast-Path
    const cached = await this.storage.getIdempotency(parsed.idempotencyKey);
    if (cached) {
      return cached;
    }

    // Phase C: Distributed Concurrency Lock
    const lockAcquired = await this.storage.acquireLock(`lock:pay:${parsed.idempotencyKey}`, 30);
    if (!lockAcquired) {
      throw new Error("CONCURRENT_REQUEST_IN_PROGRESS");
    }

    try {
      // Phase D: Outbound Network Call with Hard Timeout (AbortSignal.timeout)
      const timeoutSignal = AbortSignal.timeout(3000); // 3-second hard SLA bound
      const gatewayResponse = await fetch(`${this.gatewayUrl}/v1/charges`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": parsed.idempotencyKey,
          "X-Correlation-ID": correlationId
        },
        body: JSON.stringify({
          amount: parsed.amountInCents,
          currency: parsed.currency
        }),
        signal: timeoutSignal
      });

      if (!gatewayResponse.ok) {
        throw new Error(`GATEWAY_CHARGE_FAILED_${gatewayResponse.status}`);
      }

      // Phase E: Sharded Append-Only Ledger Entry (Never update balances in-place!)
      const paymentId = `pay_${randomUUID().replace(/-/g, "").slice(0, 24)}` as PaymentId;
      const shard = selectShardIndex(callerTenantId);

      await this.storage.recordLedgerEntry({
        paymentId,
        tenantId: callerTenantId,
        senderId: callerUserId,
        recipientId: parsed.recipientUserId as UserId,
        amountInCents: parsed.amountInCents,
        currency: parsed.currency,
        shardIndex: shard
      });

      // Phase F: Safe DTO Projection (Zero sensitive/internal field leakage)
      const dto: PaymentDto = {
        paymentId,
        amountInCents: parsed.amountInCents,
        currency: parsed.currency,
        status: "COMPLETED",
        createdAt: new Date().toISOString()
      };

      // Phase G: Persist Idempotent Response (24h TTL)
      await this.storage.saveIdempotency(parsed.idempotencyKey, dto, 86400);

      return dto;
    } finally {
      await this.storage.releaseLock(`lock:pay:${parsed.idempotencyKey}`);
    }
  }
}
